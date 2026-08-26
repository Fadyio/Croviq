from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_media.transcript import (
    GEMINI_TRANSCRIBE_MODEL,
    GeminiTranscriptionService,
    TranscriptionError,
    parse_duration_to_ms,
    parse_gemini_transcription_response,
)


@dataclass
class MockWordInfo:
    word: str
    start_offset: str | float
    end_offset: str | float


@dataclass
class MockAudioTranscription:
    text: str
    words: list[MockWordInfo]
    language_code: str = "en-US"
    speaker_label: str | None = None
    finished: bool = True


@dataclass
class MockPart:
    text: str = ""
    audio_transcription: MockAudioTranscription | None = None


@dataclass
class MockContent:
    parts: list[MockPart]


@dataclass
class MockCandidate:
    content: MockContent


@dataclass
class MockGenerateContentResponse:
    candidates: list[MockCandidate]


def _sample_gemini_response() -> MockGenerateContentResponse:
    words = [
        MockWordInfo(word="The", start_offset="0.200s", end_offset="0.300s"),
        MockWordInfo(word="Fairphone", start_offset="0.300s", end_offset="1.000s"),
        MockWordInfo(word="6", start_offset="1.000s", end_offset="1.400s"),
        MockWordInfo(word="Plus", start_offset="1.400s", end_offset="2.000s"),
        MockWordInfo(word="is", start_offset="2.000s", end_offset="2.200s"),
        MockWordInfo(word="great.", start_offset="2.200s", end_offset="2.800s"),
        MockWordInfo(word="Something", start_offset="3.000s", end_offset="3.500s"),
        MockWordInfo(word="extra.", start_offset="3.500s", end_offset="4.200s"),
    ]
    text = "The Fairphone 6 Plus is great. Something extra."
    return MockGenerateContentResponse(
        candidates=[
            MockCandidate(
                content=MockContent(
                    parts=[
                        MockPart(
                            text=text,
                            audio_transcription=MockAudioTranscription(
                                text=text,
                                words=words,
                                language_code="en-US",
                            ),
                        )
                    ]
                )
            )
        ]
    )


def test_parse_duration_to_ms_supports_seconds_strings() -> None:
    assert parse_duration_to_ms("0.200s") == 200
    assert parse_duration_to_ms("1.4s") == 1400
    assert parse_duration_to_ms("12s") == 12000
    assert parse_duration_to_ms("3.5") == 3500
    assert parse_duration_to_ms(4.2) == 4200
    assert parse_duration_to_ms(None) == 0


def test_parse_gemini_response_maps_words_and_reconstructs_segments() -> None:
    resp = _sample_gemini_response()
    transcript = parse_gemini_transcription_response(
        resp,
        production_id="prod_gemini_01",
        language_code="en-US",
        source_duration_ms=5000,
    )

    assert isinstance(transcript, Transcript)
    assert transcript.production_id == "prod_gemini_01"
    assert transcript.language_code == "en-US"
    assert len(transcript.words) == 8
    assert transcript.words[0].text == "The"
    assert transcript.words[0].start_ms == 200
    assert transcript.words[0].end_ms == 300
    assert transcript.words[3].text == "Plus"
    assert transcript.words[3].start_ms == 1400
    assert transcript.words[3].end_ms == 2000

    # 2 sentences -> 2 segments
    assert len(transcript.segments) == 2
    assert transcript.segments[0].segment_id == "seg_000"
    assert transcript.segments[0].start_ms == 200
    assert transcript.segments[0].end_ms == 2800
    assert transcript.segments[0].word_start_index == 0
    assert transcript.segments[0].word_end_index == 5

    assert transcript.segments[1].segment_id == "seg_001"
    assert transcript.segments[1].start_ms == 3000
    assert transcript.segments[1].end_ms == 4200
    assert transcript.segments[1].word_start_index == 6
    assert transcript.segments[1].word_end_index == 7


def test_parse_gemini_response_rejects_missing_words() -> None:
    resp = MockGenerateContentResponse(
        candidates=[
            MockCandidate(
                content=MockContent(
                    parts=[
                        MockPart(
                            text="Empty audio",
                            audio_transcription=MockAudioTranscription(
                                text="Empty audio",
                                words=[],
                            ),
                        )
                    ]
                )
            )
        ]
    )
    with pytest.raises(TranscriptionError, match="word timestamps"):
        parse_gemini_transcription_response(resp, production_id="prod_bad")


def test_parse_gemini_response_rejects_non_monotonic_words() -> None:
    words = [
        MockWordInfo(word="First", start_offset="2.0s", end_offset="2.5s"),
        MockWordInfo(word="Second", start_offset="1.0s", end_offset="1.5s"),
    ]
    resp = MockGenerateContentResponse(
        candidates=[
            MockCandidate(
                content=MockContent(
                    parts=[
                        MockPart(
                            text="First Second",
                            audio_transcription=MockAudioTranscription(
                                text="First Second",
                                words=words,
                            ),
                        )
                    ]
                )
            )
        ]
    )
    with pytest.raises(TranscriptionError, match="monotonic"):
        parse_gemini_transcription_response(resp, production_id="prod_bad")


def test_parse_gemini_response_rejects_source_duration_mismatch() -> None:
    resp = _sample_gemini_response()
    with pytest.raises(TranscriptionError, match="source duration"):
        parse_gemini_transcription_response(
            resp,
            production_id="prod_bad",
            source_duration_ms=1000,  # last word is at 4200ms
        )


@pytest.mark.asyncio
async def test_gemini_transcription_service_success(tmp_path: Path) -> None:
    audio_path = tmp_path / "speech.wav"
    audio_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00data\x00\x00\x00\x00")

    recorded_calls: list[dict[str, Any]] = []

    def mock_generate_content(model: str, contents: list[Any], config: Any) -> Any:
        recorded_calls.append({"model": model, "contents": contents, "config": config})
        return _sample_gemini_response()

    service = GeminiTranscriptionService(
        project_id="test-project",
        location="global",
        model=GEMINI_TRANSCRIBE_MODEL,
        generate_content_func=mock_generate_content,
    )

    transcript = await service.transcribe_audio_file(
        audio_path,
        language_code="en-US",
        production_id="prod_test_01",
        source_duration_ms=5000,
    )

    assert transcript.production_id == "prod_test_01"
    assert len(transcript.words) == 8
    assert len(recorded_calls) == 1
    assert recorded_calls[0]["model"] == "gemini-3.5-transcribe-preview"

    cfg = recorded_calls[0]["config"]
    assert cfg.audio_transcription_config is not None
    # Check mode is verbatim
    mode_val = cfg.audio_transcription_config.mode
    assert str(mode_val).upper().endswith("VERBATIM")
    assert cfg.audio_transcription_config.word_timestamp is True


@pytest.mark.asyncio
async def test_gemini_transcription_service_handles_missing_file() -> None:
    service = GeminiTranscriptionService(project_id="test-project")
    with pytest.raises(TranscriptionError, match="transcription_invalid_media"):
        await service.transcribe_audio_file(
            Path("/nonexistent/audio.wav"),
            production_id="prod_missing",
        )


@pytest.mark.asyncio
async def test_gemini_transcription_service_maps_provider_failure(tmp_path: Path) -> None:
    audio_path = tmp_path / "speech.wav"
    audio_path.write_bytes(b"RIFF dummy audio")

    def failing_generate_content(model: str, contents: list[Any], config: Any) -> Any:
        raise RuntimeError("Service unavailable with secret key secret=MY_SECRET_KEY")

    service = GeminiTranscriptionService(
        project_id="test-project",
        generate_content_func=failing_generate_content,
    )

    with pytest.raises(TranscriptionError) as exc_info:
        await service.transcribe_audio_file(audio_path, production_id="prod_fail")

    message = str(exc_info.value)
    assert "Gemini transcription failed" in message
    assert "MY_SECRET_KEY" not in message
