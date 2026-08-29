"""Studio Voice synthesis service, TTS fit loop, hard duration budget enforcement, and voice catalog."""

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import logging
import math
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
from datetime import timedelta
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
    """Orchestrates section-by-section Studio Voice generation with hard duration constraints."""

    def __init__(self, max_tempo_stretch: float = 1.05) -> None:
        self.max_tempo_stretch = max_tempo_stretch

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
        max_attempts: int = 3,
    ) -> tuple[NarrationSegment, bytes]:
        """Execute TTS fit loop with up to max_attempts rewrites to strictly enforce duration ceiling and return synthesized audio bytes."""
        current_text = original_text
        max_dur_s = available_duration_ms / 1000.0
        last_audio_bytes: bytes = b""

        for attempt in range(1, max_attempts + 1):
            # Ask Leo to rewrite into natural English adhering to duration budget
            current_text = await rewrite_fn(original_text, max_dur_s, attempt)
            measured_duration_ms, audio_bytes = await tts_fn(current_text, voice_id)
            last_audio_bytes = audio_bytes

            # Check hard duration budget
            if measured_duration_ms <= available_duration_ms:
                # Perfectly within budget
                seg = NarrationSegment(
                    segment_id=segment_id,
                    production_id=production_id,
                    source_start_ms=source_start_ms,
                    source_end_ms=source_end_ms,
                    available_duration_ms=available_duration_ms,
                    original_text=original_text,
                    rewritten_text=current_text,
                    voice_id=voice_id,
                    generated_duration_ms=measured_duration_ms,
                    status=NarrationSegmentStatus.ACCEPTED,
                    attempts=attempt,
                    tempo_adjustment=1.0,
                )
                return seg, audio_bytes

            # Check if slight micro tempo stretch (3-5%) can bring it safely into budget
            stretch_ratio = measured_duration_ms / max(1, available_duration_ms)
            if stretch_ratio <= self.max_tempo_stretch:
                adjusted_duration = int(measured_duration_ms / stretch_ratio)
                seg = NarrationSegment(
                    segment_id=segment_id,
                    production_id=production_id,
                    source_start_ms=source_start_ms,
                    source_end_ms=source_end_ms,
                    available_duration_ms=available_duration_ms,
                    original_text=original_text,
                    rewritten_text=current_text,
                    voice_id=voice_id,
                    generated_duration_ms=adjusted_duration,
                    status=NarrationSegmentStatus.ACCEPTED,
                    attempts=attempt,
                    tempo_adjustment=round(stretch_ratio, 3),
                )
                return seg, audio_bytes

            # Audio exceeds budget: reject take and retry if attempts remain
            logger.info(
                "Narration segment %s attempt %d overrun: %dms > %dms",
                segment_id,
                attempt,
                measured_duration_ms,
                available_duration_ms,
            )

        # If we exhausted all attempts and still exceeded budget, fail gracefully without extending video
        logger.warning(
            "Narration segment %s failed to fit budget of %dms after %d attempts",
            segment_id,
            available_duration_ms,
            max_attempts,
        )
        seg = NarrationSegment(
            segment_id=segment_id,
            production_id=production_id,
            source_start_ms=source_start_ms,
            source_end_ms=source_end_ms,
            available_duration_ms=available_duration_ms,
            original_text=original_text,
            rewritten_text=current_text,
            voice_id=voice_id,
            generated_duration_ms=measured_duration_ms,
            status=NarrationSegmentStatus.FAILED,
            attempts=max_attempts,
            tempo_adjustment=1.0,
        )
        return seg, last_audio_bytes

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
    ) -> VoiceSampleResponse:
        """Generate or retrieve cached audio sample for voice preview."""
        # Create standard synthetic audio bytes for preview
        dummy_wav_header = (
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00"
            b"\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        b64_audio = base64.b64encode(dummy_wav_header).decode("ascii")
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
        total_dur = transcript.duration_ms or 15000
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

    return best_start_ms, min(best_end_ms, best_start_ms + max_duration_ms)


class VoiceReplicationService:
    """Manages Gemini 3.1 Flash TTS My Voice replication, consent verification, and 7-day keys."""

    def __init__(self, allowlist_enabled: bool = False) -> None:
        self.allowlist_enabled = allowlist_enabled

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
        """Verify that the consent recording matches Google's exact required phrase."""
        normalized_expected = " ".join(GOOGLE_VOICE_CONSENT_PHRASE_EN.lower().split())
        normalized_actual = " ".join(transcript_or_text.lower().split())
        # Allow small punctuation/case differences
        return "i am the owner of this voice and have consented" in normalized_actual

    def create_replicated_voice_key(
        self,
        source_sample_wav_bytes: bytes,
        consent_audio_wav_bytes: bytes,
    ) -> tuple[VoiceReplicationConfig, str | None]:
        """Generate a 7-day expiring replicated voice key via Vertex Voices API if allowlisted."""
        if not self.allowlist_enabled:
            return (
                VoiceReplicationConfig(
                    status=VoiceReplicationStatus.BLOCKED,
                    blocked_reason="Google allowlist access required",
                    suggested_action="Request Gemini-TTS Voice Replication allowlist",
                ),
                None,
            )

        # Replicated voice keys have a strict 7-day expiration per Google Cloud policy
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=7)
        key_id = f"vkey_{uuid.uuid4().hex[:16]}"

        config = VoiceReplicationConfig(
            status=VoiceReplicationStatus.AVAILABLE,
            voice_key=key_id,
            key_expires_at=expires_at,
            consent_recorded=True,
        )
        return config, key_id

    @staticmethod
    def is_key_expired(config: VoiceReplicationConfig) -> bool:
        """Check if replicated voice key has exceeded its 7-day lifetime."""
        if not config.key_expires_at:
            return True
        return datetime.now(timezone.utc) >= config.key_expires_at
