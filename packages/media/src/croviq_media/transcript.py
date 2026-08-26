"""TranscriptionService abstraction and Groq Whisper implementation."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import uuid

from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord

GROQ_TRANSCRIPTION_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_WHISPER_MODEL = "whisper-large-v3"
DEFAULT_GROQ_PROMPT = (
    "Croviq, GitHub Actions, GitHub, YAML, workflow, runner, CI/CD, "
    "Cloud Run, Terraform, Docker, Google Cloud, repository, commit, deployment"
)
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


def _map_segment_word_indexes(
    words: list[TranscriptWord],
    start_ms: int,
    end_ms: int,
) -> tuple[int, int]:
    matching = [
        word.index
        for word in words
        if word.start_ms >= start_ms and word.end_ms <= end_ms
    ]
    if matching:
        return matching[0], matching[-1]

    overlapping = [
        word.index
        for word in words
        if word.end_ms > start_ms and word.start_ms < end_ms
    ]
    if overlapping:
        return overlapping[0], overlapping[-1]

    closest = min(
        words,
        key=lambda w: min(abs(w.start_ms - start_ms), abs(w.end_ms - end_ms)),
    )
    return closest.index, closest.index

def parse_groq_transcription_response(
    payload: Any,
    production_id: str,
    language_code: str = "en-US",
    source_duration_ms: int | None = None,
) -> Transcript:
    """Map Groq Whisper verbose JSON into the canonical Croviq Transcript."""
    words_payload = _get_value(payload, "words", []) or []
    segments_payload = _get_value(payload, "segments", []) or []

    words: list[TranscriptWord] = []
    previous_start_ms = -1
    for index, raw_word in enumerate(words_payload):
        text = _get_text(raw_word, "word", "text")
        if not text:
            raise TranscriptionError(f"word {index} is missing text")
        raw_start_ms = parse_duration_to_ms(_get_value(raw_word, "start"))
        raw_end_ms = parse_duration_to_ms(_get_value(raw_word, "end"))

        start_ms = max(raw_start_ms, previous_start_ms if previous_start_ms >= 0 else 0)
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
        raise TranscriptionError("Groq transcription response did not include word timestamps")

    segments: list[TranscriptSegment] = []
    for segment_index, raw_segment in enumerate(segments_payload):
        start_ms = parse_duration_to_ms(_get_value(raw_segment, "start"))
        end_ms = parse_duration_to_ms(_get_value(raw_segment, "end"))
        text = _get_text(raw_segment, "text")
        if not text:
            raise TranscriptionError(f"segment {segment_index} is missing text")
        word_start_index, word_end_index = _map_segment_word_indexes(words, start_ms, end_ms)
        segments.append(
            TranscriptSegment(
                segment_id=f"seg_{segment_index:03d}",
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                word_start_index=word_start_index,
                word_end_index=word_end_index,
            )
        )

    if not segments:
        word_start_index, word_end_index = 0, len(words) - 1
        segments.append(
            TranscriptSegment(
                segment_id="seg_000",
                start_ms=words[0].start_ms,
                end_ms=words[-1].end_ms,
                text=_get_text(payload, "text") or " ".join(word.text for word in words),
                word_start_index=word_start_index,
                word_end_index=word_end_index,
            )
        )

    last_timestamp_ms = max(words[-1].end_ms, max(segment.end_ms for segment in segments))
    response_duration_ms = parse_duration_to_ms(_get_value(payload, "duration")) if _get_value(payload, "duration") is not None else 0
    duration_ms = max(response_duration_ms, last_timestamp_ms)
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


def _default_http_post(**kwargs: Any) -> Any:
    import httpx

    with httpx.Client() as client:
        return client.post(**kwargs)

class GroqTranscriptionService(TranscriptionService):
    """Thin HTTP adapter for Groq Whisper audio transcription."""

    def __init__(
        self,
        api_key: str,
        endpoint_url: str = GROQ_TRANSCRIPTION_ENDPOINT,
        model: str = GROQ_WHISPER_MODEL,
        prompt: str | None = DEFAULT_GROQ_PROMPT,
        timeout_seconds: float = 120.0,
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        cleaned_key = api_key.strip()
        if not cleaned_key:
            raise TranscriptionError("GROQ_API_KEY is required for Groq transcription")
        self.api_key = cleaned_key
        self.endpoint_url = endpoint_url
        self.model = model
        self.prompt = prompt.strip() if prompt else None
        self.timeout_seconds = timeout_seconds
        self._http_post = http_post or _default_http_post
        self.last_request_id: str | None = None

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
            raise TranscriptionError(f"Groq transcription failed: {type(exc).__name__}") from exc

    def _transcribe_audio_file_sync(
        self,
        path: Path,
        language_code: str,
        production_id: str,
        source_duration_ms: int | None,
    ) -> Transcript:
        data: dict[str, Any] = {
            "model": self.model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": ["word", "segment"],
            "temperature": "0",
        }
        if language_code:
            data["language"] = language_code.split("-")[0].lower()
        if self.prompt:
            data["prompt"] = self.prompt

        with path.open("rb") as audio_file:
            response = self._http_post(
                url=self.endpoint_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "croviq-api/0.1.0",
                },
                data=data,
                files={"file": (path.name, audio_file, "audio/wav")},
                timeout=self.timeout_seconds,
            )

        self.last_request_id = getattr(response, "headers", {}).get("x-request-id") or getattr(response, "headers", {}).get("x-groq-id")
        status_code = getattr(response, "status_code", 0)
        if status_code < 200 or status_code >= 300:
            error_code = "unknown"
            try:
                body = response.json()
                error_obj = body.get("error", {}) if isinstance(body, dict) else {}
                error_code = str(error_obj.get("code") or error_obj.get("type") or "unknown")
            except Exception:
                pass
            raise TranscriptionError(
                f"Groq transcription failed status={status_code} code={error_code} request_id={self.last_request_id or 'unknown'}"
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise TranscriptionError("Groq transcription failed: invalid JSON response") from exc

        return parse_groq_transcription_response(
            payload,
            production_id=production_id,
            language_code=language_code,
            source_duration_ms=source_duration_ms,
        )
