"""TranscriptionService abstraction and Google Cloud Speech-to-Text v2 implementation."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import uuid

from croviq_domain.transcript import (
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)


class TranscriptionError(Exception):
    """Raised when speech transcription fails or speech service returns an error."""
    pass


def parse_duration_to_ms(offset: Any) -> int:
    """Safely convert protobuf Duration, timedelta, or numeric seconds/nanos to integer milliseconds."""
    if offset is None:
        return 0

    # If it has total_seconds() method (e.g. google.protobuf.Duration or timedelta)
    if hasattr(offset, "total_seconds") and callable(offset.total_seconds):
        try:
            return max(0, int(round(offset.total_seconds() * 1000)))
        except Exception:
            pass

    # If it has seconds and nanos attributes (google.protobuf.Duration)
    if hasattr(offset, "seconds") or hasattr(offset, "nanos"):
        seconds = getattr(offset, "seconds", 0) or 0
        nanos = getattr(offset, "nanos", 0) or 0
        return max(0, int(round(seconds * 1000 + nanos / 1_000_000)))

    # If it's a numeric value representing seconds
    if isinstance(offset, (int, float)):
        return max(0, int(round(offset * 1000)))

    return 0


def parse_google_speech_response(
    file_result: Any,
    production_id: str,
    language_code: str = "en-US",
    transcript_id: str | None = None,
) -> Transcript:
    """Parse a Google Cloud Speech-to-Text v2 recognition result into a canonical domain Transcript.

    Extracts word-level timestamps (start_ms, end_ms), confidence scores, speaker tags,
    and constructs segments while enforcing monotonicity and timing invariants.
    """
    t_id = transcript_id or f"tr_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    # In Google STT v2, file_result contains transcript with results list
    transcript_obj = getattr(file_result, "transcript", file_result)
    results_list = getattr(transcript_obj, "results", [])

    words: list[TranscriptWord] = []
    segments: list[TranscriptSegment] = []

    current_word_index = 0
    last_end_ms = 0

    for seg_idx, res in enumerate(results_list):
        alternatives = getattr(res, "alternatives", [])
        if not alternatives:
            continue
        # Take the top alternative
        top_alt = alternatives[0]
        alt_transcript = getattr(top_alt, "transcript", "").strip()
        alt_words = getattr(top_alt, "words", [])

        seg_start_idx = current_word_index
        seg_start_ms: int | None = None
        seg_end_ms: int | None = None

        for w in alt_words:
            word_text = getattr(w, "word", "").strip()
            if not word_text:
                continue

            raw_start = getattr(w, "start_offset", None)
            raw_end = getattr(w, "end_offset", None)

            start_ms = parse_duration_to_ms(raw_start)
            end_ms = parse_duration_to_ms(raw_end)

            # Ensure start_ms is monotonic with previous word
            if start_ms < last_end_ms and words:
                start_ms = last_end_ms

            # Ensure end_ms > start_ms
            if end_ms <= start_ms:
                end_ms = start_ms + 50  # minimum 50ms duration if STT produced identical offsets

            confidence_val = getattr(w, "confidence", None)
            if confidence_val is not None:
                try:
                    confidence = float(confidence_val)
                    if confidence < 0.0 or confidence > 1.0:
                        confidence = None
                except (ValueError, TypeError):
                    confidence = None
            else:
                confidence = None

            speaker_id_val = getattr(w, "speaker_label", None) or getattr(w, "speaker_tag", None)
            speaker_id = str(speaker_id_val) if speaker_id_val is not None else None

            word_obj = TranscriptWord(
                index=current_word_index,
                text=word_text,
                start_ms=start_ms,
                end_ms=end_ms,
                confidence=confidence,
                speaker_id=speaker_id,
            )
            words.append(word_obj)

            if seg_start_ms is None or start_ms < seg_start_ms:
                seg_start_ms = start_ms
            if seg_end_ms is None or end_ms > seg_end_ms:
                seg_end_ms = end_ms

            last_end_ms = end_ms
            current_word_index += 1

        if current_word_index > seg_start_idx:
            seg_end_idx = current_word_index - 1
            if seg_start_ms is not None and seg_end_ms is not None:
                # Segment text
                segment_text = alt_transcript or " ".join(
                    words[i].text for i in range(seg_start_idx, seg_end_idx + 1)
                )
                segments.append(
                    TranscriptSegment(
                        segment_id=f"seg_{seg_idx:03d}",
                        start_ms=seg_start_ms,
                        end_ms=seg_end_ms,
                        text=segment_text,
                        word_start_index=seg_start_idx,
                        word_end_index=seg_end_idx,
                    )
                )

    # Overall duration
    total_duration_ms = last_end_ms
    if not words:
        total_duration_ms = 0

    return Transcript(
        transcript_id=t_id,
        production_id=production_id,
        language_code=language_code,
        duration_ms=total_duration_ms,
        words=words,
        segments=segments,
        created_at=now,
    )


class TranscriptionService(ABC):
    """Abstract interface for word-aligned speech transcription."""

    @abstractmethod
    async def transcribe_gcs_uri(
        self,
        gcs_uri: str,
        language_code: str = "en-US",
        production_id: str = "",
    ) -> Transcript:
        """Transcribe an audio or video file located in GCS and return a canonical Transcript."""
        pass


class FakeTranscriptionService(TranscriptionService):
    """Deterministic simulated transcription service for unit testing and local development."""

    def __init__(self) -> None:
        self._preset_transcripts: dict[str, Transcript] = {}
        self._errors: dict[str, str] = {}

    def set_transcript(self, gcs_uri: str, transcript: Transcript) -> None:
        self._preset_transcripts[gcs_uri] = transcript

    def set_error(self, gcs_uri: str, error_message: str) -> None:
        self._errors[gcs_uri] = error_message

    async def transcribe_gcs_uri(
        self,
        gcs_uri: str,
        language_code: str = "en-US",
        production_id: str = "",
    ) -> Transcript:
        if gcs_uri in self._errors:
            raise TranscriptionError(self._errors[gcs_uri])

        if gcs_uri in self._preset_transcripts:
            return self._preset_transcripts[gcs_uri]

        # Generate realistic synthetic word-aligned transcript
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

            for pw in phrase_words:
                clean_pw = pw.strip()
                w_duration = max(180, len(clean_pw) * 55)
                w_start = current_time_ms
                w_end = w_start + w_duration
                words.append(
                    TranscriptWord(
                        index=word_idx,
                        text=clean_pw,
                        start_ms=w_start,
                        end_ms=w_end,
                        confidence=0.96,
                        speaker_id="speaker_0",
                    )
                )
                word_idx += 1
                current_time_ms = w_end + 120  # 120ms gap between words

            seg_end_idx = word_idx - 1
            seg_end_ms = words[-1].end_ms
            segments.append(
                TranscriptSegment(
                    segment_id=f"seg_{seg_i:03d}",
                    start_ms=seg_start_ms,
                    end_ms=seg_end_ms,
                    text=phrase,
                    word_start_index=seg_start_idx,
                    word_end_index=seg_end_idx,
                )
            )
            current_time_ms += 400  # 400ms gap between segments

        total_duration = max(current_time_ms, words[-1].end_ms if words else 0)

        return Transcript(
            transcript_id=f"tr_{uuid.uuid4().hex[:12]}",
            production_id=production_id or f"prod_{uuid.uuid4().hex[:8]}",
            language_code=language_code,
            duration_ms=total_duration,
            words=words,
            segments=segments,
            created_at=now,
        )


class GoogleSpeechTranscriptionService(TranscriptionService):
    """Production implementation of TranscriptionService using Google Cloud Speech-to-Text v2."""

    def __init__(
        self,
        project_id: str,
        location: str = "global",
        recognizer_id: str = "_",
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.recognizer_id = recognizer_id
        self._client_factory = client_factory
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            if self._client_factory:
                self._client = self._client_factory()
            else:
                from google.cloud import speech_v2
                self._client = speech_v2.SpeechClient()
        return self._client

    def _get_recognizer_path(self) -> str:
        return f"projects/{self.project_id}/locations/{self.location}/recognizers/{self.recognizer_id}"

    async def transcribe_gcs_uri(
        self,
        gcs_uri: str,
        language_code: str = "en-US",
        production_id: str = "",
    ) -> Transcript:
        """Call Google Cloud Speech-to-Text v2 BatchRecognize with word-level timestamps enabled."""
        if not gcs_uri.startswith("gs://"):
            raise TranscriptionError(f"Invalid GCS URI: '{gcs_uri}'. Must start with gs://")

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None,
                self._transcribe_gcs_sync,
                gcs_uri,
                language_code,
                production_id,
            )
        except TranscriptionError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Google Speech-to-Text v2 failed: {e}") from e

    def _transcribe_gcs_sync(
        self,
        gcs_uri: str,
        language_code: str,
        production_id: str,
    ) -> Transcript:
        from google.cloud.speech_v2.types import cloud_speech

        client = self._get_client()
        recognizer_path = self._get_recognizer_path()

        config = cloud_speech.RecognitionConfig(
            features=cloud_speech.RecognitionFeatures(
                enable_word_time_offsets=True,
                enable_word_confidence=True,
                enable_automatic_punctuation=True,
            ),
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=[language_code],
            model="long",
        )

        output_config = cloud_speech.RecognitionOutputConfig(
            inline_response_config=cloud_speech.InlineOutputConfig()
        )

        file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)

        request = cloud_speech.BatchRecognizeRequest(
            recognizer=recognizer_path,
            config=config,
            files=[file_metadata],
            recognition_output_config=output_config,
        )

        try:
            operation = client.batch_recognize(request=request)
            response = operation.result()
        except Exception as e:
            raise TranscriptionError(f"Google Speech-to-Text API operation failed: {e}") from e

        # Extract file result from response.results dictionary
        results_map = getattr(response, "results", {})
        file_result = results_map.get(gcs_uri)
        if not file_result and results_map:
            # Fallback to first available result in map
            file_result = next(iter(results_map.values()))

        if not file_result:
            raise TranscriptionError(
                f"Google Speech-to-Text returned no results for audio '{gcs_uri}'"
            )

        return parse_google_speech_response(
            file_result=file_result,
            production_id=production_id,
            language_code=language_code,
        )
