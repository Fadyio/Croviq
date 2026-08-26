from pathlib import Path

import pytest

from croviq_media.transcript import (
    GroqTranscriptionService,
    TranscriptionError,
    parse_groq_transcription_response,
)


class MockGroqResponse:
    def __init__(self, status_code: int, payload: dict, request_id: str = "req_test_123") -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {"x-request-id": request_id}
        self.text = "raw provider body must not leak"

    def json(self) -> dict:
        return self._payload


GROQ_VERBOSE_JSON = {
    "text": "Welcome to Croviq. GitHub Actions runs the workflow.",
    "duration": 3.2,
    "words": [
        {"word": "Welcome", "start": 0.1, "end": 0.48},
        {"word": "to", "start": 0.5, "end": 0.62},
        {"word": "Croviq.", "start": 0.65, "end": 1.0},
        {"word": "GitHub", "start": 1.4, "end": 1.72},
        {"word": "Actions", "start": 1.75, "end": 2.12},
        {"word": "runs", "start": 2.2, "end": 2.45},
        {"word": "the", "start": 2.5, "end": 2.62},
        {"word": "workflow.", "start": 2.66, "end": 3.05},
    ],
    "segments": [
        {"id": 0, "start": 0.1, "end": 1.0, "text": "Welcome to Croviq."},
        {"id": 1, "start": 1.4, "end": 3.05, "text": "GitHub Actions runs the workflow."},
    ],
}


def test_parse_groq_verbose_json_maps_words_and_segments_to_canonical_transcript() -> None:
    transcript = parse_groq_transcription_response(
        GROQ_VERBOSE_JSON,
        production_id="prod_groq_contract",
        language_code="en",
        source_duration_ms=3_250,
    )

    assert transcript.production_id == "prod_groq_contract"
    assert transcript.language_code == "en"
    assert transcript.duration_ms == 3200
    assert [word.text for word in transcript.words[:3]] == ["Welcome", "to", "Croviq."]
    assert [word.start_ms for word in transcript.words[:3]] == [100, 500, 650]
    assert [word.end_ms for word in transcript.words[:3]] == [480, 620, 1000]
    assert all(word.confidence is None for word in transcript.words)
    assert transcript.segments[0].segment_id == "seg_000"
    assert transcript.segments[0].word_start_index == 0
    assert transcript.segments[0].word_end_index == 2
    assert transcript.segments[1].word_start_index == 3
    assert transcript.segments[1].word_end_index == 7


def test_parse_groq_verbose_json_rejects_non_monotonic_word_timestamps() -> None:
    payload = {
        **GROQ_VERBOSE_JSON,
        "words": [
            {"word": "second", "start": 1.0, "end": 1.2},
            {"word": "first", "start": 0.5, "end": 0.8},
        ],
    }

    with pytest.raises(TranscriptionError, match="monotonic"):
        parse_groq_transcription_response(payload, production_id="prod_bad")


def test_parse_groq_verbose_json_rejects_source_duration_mismatch() -> None:
    with pytest.raises(TranscriptionError, match="source duration"):
        parse_groq_transcription_response(
            GROQ_VERBOSE_JSON,
            production_id="prod_duration_mismatch",
            source_duration_ms=1_000,
        )


@pytest.mark.asyncio
async def test_groq_transcription_service_posts_audio_and_returns_transcript(tmp_path: Path) -> None:
    audio_path = tmp_path / "speech.wav"
    audio_path.write_bytes(b"RIFF fake wav bytes")
    calls: list[dict] = []

    def post_audio(**kwargs):
        calls.append(kwargs)
        return MockGroqResponse(200, GROQ_VERBOSE_JSON, request_id="req_contract")

    service = GroqTranscriptionService(
        api_key="test-secret-key",
        http_post=post_audio,
        prompt="Croviq, GitHub Actions, YAML, workflow",
        timeout_seconds=12.5,
    )

    transcript = await service.transcribe_audio_file(
        audio_path,
        production_id="prod_http_contract",
        language_code="en-US",
        source_duration_ms=3_250,
    )

    assert transcript.production_id == "prod_http_contract"
    assert transcript.word_count == 8
    assert transcript.segment_count == 2
    assert calls[0]["url"] == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert calls[0]["headers"] == {"Authorization": "Bearer test-secret-key"}
    assert calls[0]["data"]["model"] == "whisper-large-v3"
    assert calls[0]["data"]["response_format"] == "verbose_json"
    assert calls[0]["data"]["timestamp_granularities[]"] == ["word", "segment"]
    assert calls[0]["data"]["prompt"] == "Croviq, GitHub Actions, YAML, workflow"
    assert calls[0]["timeout"] == 12.5


@pytest.mark.asyncio
async def test_groq_transcription_service_maps_provider_failure_without_raw_body(tmp_path: Path) -> None:
    audio_path = tmp_path / "speech.wav"
    audio_path.write_bytes(b"RIFF fake wav bytes")

    def post_audio(**kwargs):
        return MockGroqResponse(
            429,
            {"error": {"code": "rate_limit_exceeded", "message": "too many requests"}},
            request_id="req_rate_limit",
        )

    service = GroqTranscriptionService(api_key="test-secret-key", http_post=post_audio)

    with pytest.raises(TranscriptionError) as exc_info:
        await service.transcribe_audio_file(audio_path, production_id="prod_provider_error")

    message = str(exc_info.value)
    assert "Groq transcription failed" in message
    assert "429" in message
    assert "rate_limit_exceeded" in message
    assert "raw provider body" not in message
    assert "test-secret-key" not in message
