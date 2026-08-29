"""TranscriptionService abstraction and Gemini 3.5 Transcribe implementation."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import re
import time
from typing import Any, Callable
import uuid

from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_observability import log_ai_event
from croviq_observability.events import EventType

GEMINI_TRANSCRIBE_MODEL = "gemini-3.5-transcribe-preview"
DEFAULT_GEMINI_LOCATION = "global"
DEFAULT_CUSTOM_VOCABULARY = [
    "Croviq",
    "GitHub Actions",
    "GitHub",
    "CI/CD",
    "YAML",
    "Terraform",
    "Cloud Run",
    "Google Cloud",
    "Vertex AI",
    "Gemini",
    "Docker",
    "Kubernetes",
    "OIDC",
    "Workload Identity Federation",
    "Firestore",
    "Twick",
    "FFmpeg",
]
SOURCE_DURATION_TOLERANCE_MS = 2_000


class TranscriptionError(Exception):
    """Raised when speech transcription fails or speech service returns an error."""

    pass


def parse_duration_to_ms(offset: Any) -> int:
    """Convert seconds-like offsets to integer milliseconds."""
    if offset is None:
        return 0
    if hasattr(offset, "total_seconds") and callable(offset.total_seconds):
        try:
            return max(0, int(round(offset.total_seconds() * 1000)))
        except Exception:
            pass
    if hasattr(offset, "seconds") or hasattr(offset, "nanos"):
        seconds = getattr(offset, "seconds", 0) or 0
        nanos = getattr(offset, "nanos", 0) or 0
        return max(0, int(round(seconds * 1000 + nanos / 1_000_000)))
    if isinstance(offset, (int, float)):
        return max(0, int(round(offset * 1000)))
    if isinstance(offset, str):
        cleaned = offset.strip()
        if not cleaned:
            return 0
        if cleaned.endswith("ms"):
            try:
                return max(0, int(round(float(cleaned[:-2]))))
            except Exception:
                pass
        if cleaned.endswith("s"):
            cleaned = cleaned[:-1]
        try:
            return max(0, int(round(float(cleaned) * 1000)))
        except Exception:
            pass
    raise TranscriptionError(f"Unsupported timestamp value: {offset!r}")

def _get_text(value: Any, *names: str) -> str:
    for name in names:
        if isinstance(value, dict) and name in value:
            candidate = value[name]
        else:
            candidate = getattr(value, name, None)
        if candidate is not None:
            return str(candidate).strip()
    return ""


def _get_value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _require_reasonable_source_duration(last_timestamp_ms: int, source_duration_ms: int | None) -> None:
    if source_duration_ms is None:
        return
    if source_duration_ms < 0:
        raise TranscriptionError("source duration must be non-negative")
    if last_timestamp_ms > source_duration_ms + SOURCE_DURATION_TOLERANCE_MS:
        raise TranscriptionError(
            f"last transcript timestamp {last_timestamp_ms}ms is inconsistent with source duration {source_duration_ms}ms"
        )


def parse_gemini_transcription_response(
    response: Any,
    production_id: str,
    language_code: str = "en-US",
    source_duration_ms: int | None = None,
) -> Transcript:
    """Map Gemini 3.5 Transcribe response into the canonical Croviq Transcript."""
    candidates = _get_value(response, "candidates", []) or []
    if not candidates:
        raise TranscriptionError("Gemini transcription response contained no candidates")

    audio_transcription: Any = None
    full_text = ""
    candidate = candidates[0]
    content = _get_value(candidate, "content")
    parts = _get_value(content, "parts", []) if content else []
    for part in parts:
        at = _get_value(part, "audio_transcription")
        if at is not None:
            audio_transcription = at
        pt = _get_value(part, "text")
        if pt and not full_text:
            full_text = str(pt).strip()

    if audio_transcription is None:
        audio_transcription = _get_value(response, "audio_transcription")

    words_payload: list[Any] = []
    if audio_transcription is not None:
        words_payload = _get_value(audio_transcription, "words", []) or []
        transcription_text = _get_value(audio_transcription, "text")
        if transcription_text:
            full_text = str(transcription_text).strip()
        detected_lang = _get_value(audio_transcription, "language_code")
        if detected_lang:
            language_code = str(detected_lang).strip()

    words: list[TranscriptWord] = []
    previous_start_ms = -1
    for index, raw_word in enumerate(words_payload):
        text = _get_text(raw_word, "word", "text")
        if not text:
            raise TranscriptionError(f"word {index} is missing text")
        raw_start_ms = parse_duration_to_ms(_get_value(raw_word, "start_offset", _get_value(raw_word, "start")))
        raw_end_ms = parse_duration_to_ms(_get_value(raw_word, "end_offset", _get_value(raw_word, "end")))

        if previous_start_ms >= 0 and raw_start_ms < previous_start_ms:
            raise TranscriptionError(f"Word timestamps must be monotonic (got {raw_start_ms}ms after {previous_start_ms}ms)")
        start_ms = raw_start_ms
        end_ms = max(raw_end_ms, start_ms + 10)

        words.append(
            TranscriptWord(
                index=index,
                text=text,
                start_ms=start_ms,
                end_ms=end_ms,
                confidence=None,
            )
        )
        previous_start_ms = start_ms

    if not words:
        raise TranscriptionError("Gemini transcription response did not include word timestamps")

    segments: list[TranscriptSegment] = []
    if full_text:
        sentence_texts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", full_text.strip()) if s.strip()]
    else:
        sentence_texts = []

    if sentence_texts:
        word_idx = 0
        for seg_i, sent_text in enumerate(sentence_texts):
            sent_clean_words = [w for w in re.findall(r"\S+", sent_text)]
            if not sent_clean_words or word_idx >= len(words):
                continue
            start_word_idx = word_idx
            end_word_idx = min(len(words) - 1, start_word_idx + len(sent_clean_words) - 1)
            if seg_i == len(sentence_texts) - 1:
                end_word_idx = len(words) - 1

            start_ms = words[start_word_idx].start_ms
            end_ms = words[end_word_idx].end_ms
            segments.append(
                TranscriptSegment(
                    segment_id=f"seg_{seg_i:03d}",
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=sent_text,
                    word_start_index=start_word_idx,
                    word_end_index=end_word_idx,
                )
            )
            word_idx = end_word_idx + 1

    if not segments:
        segments.append(
            TranscriptSegment(
                segment_id="seg_000",
                start_ms=words[0].start_ms,
                end_ms=words[-1].end_ms,
                text=full_text or " ".join(w.text for w in words),
                word_start_index=0,
                word_end_index=len(words) - 1,
            )
        )

    last_timestamp_ms = max(words[-1].end_ms, max(segment.end_ms for segment in segments))
    duration_ms = max(last_timestamp_ms, source_duration_ms or 0)
    _require_reasonable_source_duration(last_timestamp_ms, source_duration_ms)

    return Transcript(
        transcript_id=f"tr_{uuid.uuid4().hex[:12]}",
        production_id=production_id or f"prod_{uuid.uuid4().hex[:8]}",
        language_code=language_code,
        duration_ms=duration_ms,
        words=words,
        segments=segments,
        created_at=datetime.now(timezone.utc),
    )


class TranscriptionService(ABC):
    """Abstract interface for word-aligned speech transcription from extracted audio."""

    @abstractmethod
    async def transcribe_audio_file(
        self,
        audio_path: Path | str,
        language_code: str = "en-US",
        production_id: str = "",
        source_duration_ms: int | None = None,
    ) -> Transcript:
        """Transcribe a local speech-optimized audio file into a canonical Transcript."""
        pass


class FakeTranscriptionService(TranscriptionService):
    """Deterministic simulated transcription service for unit testing and local development."""

    def __init__(self) -> None:
        self._preset_transcripts: dict[str, Transcript] = {}
        self._errors: dict[str, str] = {}

    def set_transcript(self, key: str, transcript: Transcript) -> None:
        self._preset_transcripts[key] = transcript

    def set_error(self, key: str, error_message: str) -> None:
        self._errors[key] = error_message

    async def transcribe_audio_file(
        self,
        audio_path: Path | str,
        language_code: str = "en-US",
        production_id: str = "",
        source_duration_ms: int | None = None,
    ) -> Transcript:
        key = str(audio_path)
        if key in self._errors:
            raise TranscriptionError(self._errors[key])
        if key in self._preset_transcripts:
            return self._preset_transcripts[key]

        now = datetime.now(timezone.utc)
        sample_phrases = [
            "Welcome back to the channel.",
            "Today we are automating our deployments with GitHub Actions.",
            "Let's dive right into the workflow file.",
        ]

        words: list[TranscriptWord] = []
        segments: list[TranscriptSegment] = []
        current_time_ms = 500
        word_idx = 0

        for seg_i, phrase in enumerate(sample_phrases):
            phrase_words = phrase.split()
            seg_start_idx = word_idx
            seg_start_ms = current_time_ms

            for phrase_word in phrase_words:
                clean_word = phrase_word.strip()
                duration_ms = max(180, len(clean_word) * 55)
                start_ms = current_time_ms
                end_ms = start_ms + duration_ms
                words.append(
                    TranscriptWord(
                        index=word_idx,
                        text=clean_word,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        confidence=0.96,
                        speaker_id="speaker_0",
                    )
                )
                word_idx += 1
                current_time_ms = end_ms + 120

            segments.append(
                TranscriptSegment(
                    segment_id=f"seg_{seg_i:03d}",
                    start_ms=seg_start_ms,
                    end_ms=words[-1].end_ms,
                    text=phrase,
                    word_start_index=seg_start_idx,
                    word_end_index=word_idx - 1,
                )
            )
            current_time_ms += 400

        total_duration = max(source_duration_ms or 0, current_time_ms, words[-1].end_ms if words else 0)
        return Transcript(
            transcript_id=f"tr_{uuid.uuid4().hex[:12]}",
            production_id=production_id or f"prod_{uuid.uuid4().hex[:8]}",
            language_code=language_code,
            duration_ms=total_duration,
            words=words,
            segments=segments,
            created_at=now,
        )


class GeminiTranscriptionService(TranscriptionService):
    """Google GenAI SDK adapter for Gemini 3.5 Transcribe audio transcription."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str = DEFAULT_GEMINI_LOCATION,
        model: str = GEMINI_TRANSCRIBE_MODEL,
        custom_vocabulary: list[str] | None = None,
        timeout_seconds: float = 120.0,
        generate_content_func: Callable[..., Any] | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.model = model
        self.custom_vocabulary = custom_vocabulary
        self.timeout_seconds = timeout_seconds
        self._generate_content_func = generate_content_func
        self._client: Any = None
        self.last_request_id: str | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            )
        return self._client

    async def transcribe_audio_file(
        self,
        audio_path: Path | str,
        language_code: str = "en-US",
        production_id: str = "",
        source_duration_ms: int | None = None,
    ) -> Transcript:
        path = Path(audio_path)
        if not path.exists() or path.stat().st_size <= 0:
            raise TranscriptionError("transcription_invalid_media")

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None,
                self._transcribe_audio_file_sync,
                path,
                language_code,
                production_id,
                source_duration_ms,
            )
        except TranscriptionError:
            raise
        except Exception as exc:
            err_type = type(exc).__name__
            err_msg = str(exc).split("secret=")[0].split("Bearer ")[0].strip()
            raise TranscriptionError(f"Gemini transcription failed: {err_type} {err_msg}".strip()) from exc

    def _transcribe_audio_file_sync(
        self,
        path: Path,
        language_code: str,
        production_id: str,
        source_duration_ms: int | None,
    ) -> Transcript:
        from google.genai import types

        with path.open("rb") as f:
            audio_bytes = f.read()

        part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
        transcription_config = types.AudioTranscriptionConfig(
            mode=types.AudioTranscriptionConfigMode.VERBATIM,
            word_timestamp=True,
        )
        # Note: word_timestamp=True is required for word-level timing anchors.
        # On Gemini 3.5 Transcribe Preview, custom_vocabulary is incompatible with word_timestamp=True.
        config = types.GenerateContentConfig(
            audio_transcription_config=transcription_config,
        )

        start_time = time.perf_counter()
        req_id = f"req_transcribe_{uuid.uuid4().hex[:8]}"
        log_ai_event(
            event_type=EventType.AI_REQUEST_STARTED,
            agent="transcription",
            model=self.model,
            provider="google",
            backend="vertex_ai",
            location=self.location,
            operation="transcribe",
            production_id=production_id,
            request_id=req_id,
            audio_duration_ms=source_duration_ms,
            status="started",
        )

        try:
            if self._generate_content_func is not None:
                response = self._generate_content_func(
                    model=self.model,
                    contents=[part],
                    config=config,
                )
            else:
                client = self._get_client()
                response = client.models.generate_content(
                    model=self.model,
                    contents=[part],
                    config=config,
                )

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self.last_request_id = getattr(response, "response_id", None) or req_id

            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            log_ai_event(
                event_type=EventType.AI_REQUEST_COMPLETED,
                agent="transcription",
                model=self.model,
                provider="google",
                backend="vertex_ai",
                location=self.location,
                operation="transcribe",
                production_id=production_id,
                request_id=self.last_request_id,
                latency_ms=latency_ms,
                audio_duration_ms=source_duration_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                status="completed",
            )

            return parse_gemini_transcription_response(
                response=response,
                production_id=production_id,
                language_code=language_code,
                source_duration_ms=source_duration_ms,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            log_ai_event(
                event_type=EventType.AI_REQUEST_FAILED,
                agent="transcription",
                model=self.model,
                provider="google",
                backend="vertex_ai",
                location=self.location,
                operation="transcribe",
                production_id=production_id,
                request_id=req_id,
                latency_ms=latency_ms,
                audio_duration_ms=source_duration_ms,
                status="failed",
                error_code="TRANSCRIPTION_FAILED",
                message=str(exc),
            )
            raise
