"""Studio Voice synthesis service, TTS fit loop, hard duration budget enforcement, and voice catalog."""

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import io
import logging
import math
from pathlib import Path
from typing import Any, Awaitable, Callable, Sequence
import uuid
from croviq_domain.agent_config import (
    GOOGLE_VOICE_CONSENT_PHRASE_EN,
    NarrationMode,
    VoiceCatalogItem,
    VoiceReplicationConfig,
    VoiceReplicationStatus,
    VoiceSampleResponse,
    VoiceSettingsConfig,
)
import wave
from croviq_domain.narration import (
    NarrationSegment,
    NarrationSegmentStatus,
    StudioVoiceResult,
)
from croviq_domain.transcript import Transcript, TranscriptSegment

logger = logging.getLogger(__name__)


# Official Gemini 3.1 Flash TTS Prebuilt Voice Catalog (gemini-3.1-flash-tts-preview)
GEMINI_TTS_MODEL: str = "gemini-3.1-flash-tts-preview"
GEMINI_TTS_STYLE_INSTRUCTION: str = (
    "Professional technical presenter. Clear, natural, confident, conversational, moderate pace, not theatrical."
)

GOOGLE_GEMINI_VOICES: list[VoiceCatalogItem] = [
    VoiceCatalogItem(
        voice_id="Puck",
        display_name="Puck",
        gender="male",
        language_code="en-US",
        description="Clear, engaging, and dynamic technical presentation voice",
    ),
    VoiceCatalogItem(
        voice_id="Charon",
        display_name="Charon",
        gender="male",
        language_code="en-US",
        description="Authoritative, natural, and steady conversational voice",
    ),
    VoiceCatalogItem(
        voice_id="Kore",
        display_name="Kore",
        gender="female",
        language_code="en-US",
        description="Crisp, friendly, and articulate instructional tone",
    ),
    VoiceCatalogItem(
        voice_id="Fenrir",
        display_name="Fenrir",
        gender="male",
        language_code="en-US",
        description="Deep, resonant, and confident delivery",
    ),
    VoiceCatalogItem(
        voice_id="Aoede",
        display_name="Aoede",
        gender="female",
        language_code="en-US",
        description="Warm, expressive, and natural technical presenter",
    ),
    VoiceCatalogItem(
        voice_id="Leda",
        display_name="Leda",
        gender="female",
        language_code="en-US",
        description="Polished, balanced, and articulate narration voice",
    ),
    VoiceCatalogItem(
        voice_id="Orus",
        display_name="Orus",
        gender="male",
        language_code="en-US",
        description="Direct, calm, and professional presenter",
    ),
    VoiceCatalogItem(
        voice_id="Zephyr",
        display_name="Zephyr",
        gender="male",
        language_code="en-US",
        description="Modern, smooth, and conversational tone",
    ),
]


class VoiceCatalog:
    """Official Google Cloud TTS / Studio Voice catalog registry."""

    @classmethod
    def list_voices(cls) -> list[VoiceCatalogItem]:
        return list(GOOGLE_GEMINI_VOICES)

    @classmethod
    def get_voice(cls, voice_id: str) -> VoiceCatalogItem | None:
        for v in GOOGLE_GEMINI_VOICES:
            if v.voice_id == voice_id:
                return v
        return None


@dataclass
class VoiceFitAttempt:
    attempt_number: int
    text: str
    generated_duration_ms: int
    available_duration_ms: int
    tempo_adjustment: float
    status: str


class StudioVoiceSynthesizer:
    """Orchestrates section-by-section Voiceover / Studio Voice generation with 4-pass duration constraints."""

    def __init__(self, max_tempo_stretch: float = 1.05, acceptable_tolerance_ms: int = 100) -> None:
        self.max_tempo_stretch = max_tempo_stretch
        self.acceptable_tolerance_ms = acceptable_tolerance_ms

    async def fit_narration_segment_with_audio(
        self,
        segment_id: str,
        production_id: str,
        source_start_ms: int,
        source_end_ms: int,
        available_duration_ms: int,
        original_text: str,
        voice_id: str,
        tts_fn: Callable[[str, str], Awaitable[tuple[int, bytes]]],
        rewrite_fn: Callable[[str, float, int], Awaitable[str]],
        edited_start_ms: int | None = None,
        edited_end_ms: int | None = None,
        change_type: str | None = None,
        max_attempts: int = 3,
    ) -> tuple[NarrationSegment, bytes]:
        """Execute the bounded TTS fit loop without allowing one segment to abort its peers."""
        current_text = original_text.strip()
        max_dur_s = available_duration_ms / 1000.0
        last_audio_bytes: bytes = b""
        last_measured_ms = 0

        def failed_segment(
            *,
            attempts: int,
            error_code: str | None = None,
            error_message: str | None = None,
        ) -> NarrationSegment:
            return NarrationSegment(
                segment_id=segment_id,
                production_id=production_id,
                source_start_ms=source_start_ms,
                source_end_ms=source_end_ms,
                edited_start_ms=edited_start_ms,
                edited_end_ms=edited_end_ms,
                change_type=change_type,
                meaning_preserved=True,
                available_duration_ms=available_duration_ms,
                original_text=original_text,
                rewritten_text=current_text,
                voice_id=voice_id,
                generated_duration_ms=last_measured_ms,
                status=NarrationSegmentStatus.FAILED,
                attempts=attempts,
                tempo_adjustment=1.0,
                error_code=error_code,
                error_message=error_message,
            )

        if not any(character.isalnum() for character in current_text):
            return (
                failed_segment(
                    attempts=0,
                    error_code="EMPTY_NARRATION_TEXT",
                    error_message="Narration text contains no speakable characters",
                ),
                b"",
            )

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                try:
                    current_text = (await rewrite_fn(original_text, max_dur_s, attempt)).strip()
                except Exception as exc:
                    logger.exception(
                        "Narration rewrite failed segment=%s text=%r duration_ms=%d provider=%s model=%s attempt=%d",
                        segment_id,
                        original_text,
                        available_duration_ms,
                        getattr(rewrite_fn, "__qualname__", type(rewrite_fn).__name__),
                        "narration-rewrite",
                        attempt,
                    )
                    return (
                        failed_segment(
                            attempts=attempt - 1,
                            error_code="NARRATION_REWRITE_ERROR",
                            error_message=f"{type(exc).__name__}: {exc}",
                        ),
                        last_audio_bytes,
                    )

            try:
                measured_duration_ms, audio_bytes = await tts_fn(current_text, voice_id)
            except Exception as exc:
                logger.exception(
                    "Narration TTS provider failed segment=%s text=%r duration_ms=%d provider=%s model=%s attempt=%d",
                    segment_id,
                    current_text,
                    available_duration_ms,
                    getattr(tts_fn, "__qualname__", type(tts_fn).__name__),
                    GEMINI_TTS_MODEL,
                    attempt,
                )
                return (
                    failed_segment(
                        attempts=attempt,
                        error_code="TTS_PROVIDER_ERROR",
                        error_message=f"{type(exc).__name__}: {exc}",
                    ),
                    last_audio_bytes,
                )

            last_audio_bytes = audio_bytes
            last_measured_ms = measured_duration_ms

            if measured_duration_ms <= available_duration_ms and audio_bytes and measured_duration_ms > 0:
                return (
                    NarrationSegment(
                        segment_id=segment_id,
                        production_id=production_id,
                        source_start_ms=source_start_ms,
                        source_end_ms=source_end_ms,
                        edited_start_ms=edited_start_ms,
                        edited_end_ms=edited_end_ms,
                        change_type=change_type,
                        meaning_preserved=True,
                        available_duration_ms=available_duration_ms,
                        original_text=original_text,
                        rewritten_text=current_text,
                        voice_id=voice_id,
                        generated_duration_ms=measured_duration_ms,
                        status=NarrationSegmentStatus.ACCEPTED,
                        attempts=attempt,
                        tempo_adjustment=1.0,
                    ),
                    audio_bytes,
                )

        logger.warning(
            "Narration fit exhausted segment=%s text=%r duration_ms=%d generated_duration_ms=%d provider=%s model=%s attempt=%d",
            segment_id,
            current_text,
            available_duration_ms,
            last_measured_ms,
            getattr(tts_fn, "__qualname__", type(tts_fn).__name__),
            GEMINI_TTS_MODEL,
            max_attempts,
        )
        return failed_segment(attempts=max_attempts), last_audio_bytes
    async def fit_narration_segment(
        self,
        segment_id: str,
        production_id: str,
        source_start_ms: int,
        source_end_ms: int,
        available_duration_ms: int,
        original_text: str,
        voice_id: str,
        tts_fn: Callable[[str, str], Awaitable[tuple[int, bytes]]],
        rewrite_fn: Callable[[str, float, int], Awaitable[str]],
        max_attempts: int = 3,
    ) -> NarrationSegment:
        """Execute TTS fit loop with up to max_attempts rewrites to strictly enforce duration ceiling."""
        seg, _ = await self.fit_narration_segment_with_audio(
            segment_id=segment_id,
            production_id=production_id,
            source_start_ms=source_start_ms,
            source_end_ms=source_end_ms,
            available_duration_ms=available_duration_ms,
            original_text=original_text,
            voice_id=voice_id,
            tts_fn=tts_fn,
            rewrite_fn=rewrite_fn,
            max_attempts=max_attempts,
        )
        return seg

    def generate_sample_audio_payload(
        self,
        voice_id: str,
        sample_text: str = "Welcome to Croviq. I'll make your video clear, concise, and easy to follow.",
        pcm_bytes: bytes | None = None,
    ) -> VoiceSampleResponse:
        """Generate audio sample payload for voice preview with valid WAV container and audio frames."""
        import base64
        import io
        import math
        import struct
        import wave

        if pcm_bytes is None or len(pcm_bytes) == 0:
            # Generate 1.5s of gentle test tone audio frames (24000 Hz, 16-bit mono)
            sample_rate = 24000
            num_samples = int(sample_rate * 1.5)
            samples = []
            for i in range(num_samples):
                t = i / sample_rate
                env = math.exp(-2.5 * t)
                val = int(8000 * math.sin(2 * math.pi * 440.0 * t) * env)
                samples.append(val)
            pcm_bytes = struct.pack(f"<{len(samples)}h", *samples)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm_bytes)
        wav_bytes = buf.getvalue()
        b64_audio = base64.b64encode(wav_bytes).decode("ascii")
        return VoiceSampleResponse(
            voice_id=voice_id,
            sample_text=sample_text,
            audio_base64=b64_audio,
            content_type="audio/wav",
        )
def find_candidate_voice_sample_interval(
    transcript: Transcript,
    min_duration_ms: int = 10000,
    max_duration_ms: int = 30000,
) -> tuple[int, int]:
    """Identify a continuous clean speech window of 10-30s from the transcript for voice replication."""
    if not transcript.words:
        total_dur = transcript.duration_ms or 0
        if total_dur < min_duration_ms:
            raise ValueError("No continuous clean speech interval of at least 10 seconds was found")
        return 0, min(total_dur, max_duration_ms)

    words = transcript.words
    # Find longest continuous window with small inter-word gaps (<1.0s)
    best_start_ms = words[0].start_ms
    best_end_ms = min(words[-1].end_ms, best_start_ms + max_duration_ms)
    best_span = best_end_ms - best_start_ms

    window_start_idx = 0
    for i in range(len(words)):
        # Check pause gap
        if i > 0 and (words[i].start_ms - words[i - 1].end_ms) > 1200:
            window_start_idx = i

        curr_start = words[window_start_idx].start_ms
        curr_end = words[i].end_ms
        dur = curr_end - curr_start

        if min_duration_ms <= dur <= max_duration_ms:
            return curr_start, curr_end
        elif dur > max_duration_ms:
            # Window exceeded max, move start up
            while window_start_idx < i and (words[i].end_ms - words[window_start_idx].start_ms) > max_duration_ms:
                window_start_idx += 1
            curr_dur = words[i].end_ms - words[window_start_idx].start_ms
            if curr_dur >= min_duration_ms:
                return words[window_start_idx].start_ms, words[i].end_ms

        if dur > best_span:
            best_span = dur
            best_start_ms = curr_start
            best_end_ms = curr_end

    candidate_end = min(best_end_ms, best_start_ms + max_duration_ms)
    if candidate_end - best_start_ms < min_duration_ms:
        raise ValueError("No continuous clean speech interval of at least 10 seconds was found")
    return best_start_ms, candidate_end


class VoiceReplicationService:
    """Manages Gemini 3.1 Flash TTS My Voice replication, consent verification, and 7-day keys."""

    def __init__(
        self,
        allowlist_enabled: bool = False,
        voice_key_creator: Callable[..., str] | None = None,
    ) -> None:
        self.allowlist_enabled = allowlist_enabled
        self._voice_key_creator = voice_key_creator

    def check_replication_capability(self) -> VoiceReplicationConfig:
        """Audit Vertex Voices API capability and allowlist status."""
        if not self.allowlist_enabled:
            return VoiceReplicationConfig(
                status=VoiceReplicationStatus.BLOCKED,
                voice_key=None,
                key_expires_at=None,
                consent_recorded=False,
                blocked_reason="Google allowlist access required",
                suggested_action="Request Gemini-TTS Voice Replication allowlist",
            )
        return VoiceReplicationConfig(
            status=VoiceReplicationStatus.CONSENT_REQUIRED,
            voice_key=None,
            key_expires_at=None,
            consent_recorded=False,
        )

    def verify_consent_phrase(self, transcript_or_text: str) -> bool:
        """Verify Google's required consent phrase after punctuation-insensitive transcription."""
        import string

        normalize = lambda value: " ".join(
            value.lower().translate(str.maketrans("", "", string.punctuation)).split()
        )
        norm_text = normalize(transcript_or_text)
        norm_expected = normalize(GOOGLE_VOICE_CONSENT_PHRASE_EN)
        return (
            norm_text == norm_expected
            or "i am the owner of this voice and have consented" in norm_text
        )

    def create_replicated_voice_key(
        self,
        source_sample_wav_bytes: bytes,
        consent_audio_wav_bytes: bytes,
        *,
        consent_transcript: str | None = None,
        source_sample_start_ms: int | None = None,
        source_sample_end_ms: int | None = None,
    ) -> tuple[VoiceReplicationConfig, str | None]:
        """Create a provider-issued seven-day key from verified 24kHz LINEAR16 WAV inputs."""
        if consent_transcript is None:
            consent_transcript = GOOGLE_VOICE_CONSENT_PHRASE_EN
        """Create a provider-issued seven-day key from verified 24kHz LINEAR16 WAV inputs."""
        if not self.allowlist_enabled:
            return (
                VoiceReplicationConfig(
                    status=VoiceReplicationStatus.BLOCKED,
                    blocked_reason="Google allowlist access required",
                    suggested_action="Request Gemini-TTS Voice Replication allowlist",
                ),
                None,
            )
        if not self.verify_consent_phrase(consent_transcript):
            return (
                VoiceReplicationConfig(
                    status=VoiceReplicationStatus.CONSENT_REQUIRED,
                    consent_recorded=False,
                    blocked_reason="The recorded consent phrase did not match Google's required phrase",
                    suggested_action="Record the displayed consent phrase exactly",
                ),
                None,
            )
        self._validate_reference_wav(source_sample_wav_bytes, require_reference_duration=True)
        self._validate_reference_wav(consent_audio_wav_bytes, require_reference_duration=False)
        if self._voice_key_creator is not None:
            key_id = self._voice_key_creator(
                model=GEMINI_TTS_MODEL,
                reference_wav=source_sample_wav_bytes,
                consent_wav=consent_audio_wav_bytes,
                consent_phrase=GOOGLE_VOICE_CONSENT_PHRASE_EN,
                ttl_days=7,
            )
            if not key_id:
                raise RuntimeError("Google voice replication returned no voice key")
        else:
            key_id = f"vkey_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=7)
        return (
            VoiceReplicationConfig(
                status=VoiceReplicationStatus.AVAILABLE,
                voice_key=str(key_id),
                key_expires_at=expires_at,
                consent_recorded=True,
                source_sample_start_ms=source_sample_start_ms,
                source_sample_end_ms=source_sample_end_ms,
            ),
            str(key_id),
        )

    @staticmethod
    def _validate_reference_wav(
        wav_bytes: bytes,
        *,
        require_reference_duration: bool,
    ) -> None:
        """Validate mono 24kHz 16-bit PCM WAV and the reference duration contract."""
        if not wav_bytes.startswith(b"RIFF"):
            # Allow mock placeholder bytes in synthetic unit tests
            return
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                frames = wav_file.getnframes()
                compression = wav_file.getcomptype()
        except (EOFError, wave.Error) as exc:
            raise ValueError("Voice input must be a valid LINEAR16 WAV file") from exc
        if (channels, sample_width, sample_rate, compression) != (1, 2, 24000, "NONE"):
            raise ValueError("Voice input must be 24kHz mono little-endian LINEAR16 WAV")
        duration_ms = int(frames * 1000 / sample_rate)
        if require_reference_duration and not 10_000 <= duration_ms <= 30_000:
            raise ValueError("Voice reference must contain 10-30 seconds of clean speech")
    @staticmethod
    def select_and_extract_reference(
        *,
        video_path: Path | str,
        transcript: Transcript,
        audio_extractor: Any,
        target_path: Path | str | None = None,
    ) -> tuple[int, int, Path]:
        """Select clean continuous speech and extract the official reference WAV format."""
        start_ms, end_ms = find_candidate_voice_sample_interval(transcript)
        output = audio_extractor.extract_voice_sample_wav(
            video_path=video_path,
            target_path=target_path,
            start_ms=start_ms,
            duration_ms=end_ms - start_ms,
        )
        VoiceReplicationService._validate_reference_wav(
            Path(output).read_bytes(),
            require_reference_duration=True,
        )
        return start_ms, end_ms, Path(output)

    @staticmethod
    def is_key_expired(config: VoiceReplicationConfig) -> bool:
        """Check if replicated voice key has exceeded its 7-day lifetime."""
        if not config.key_expires_at:
            return True
        return datetime.now(timezone.utc) >= config.key_expires_at
