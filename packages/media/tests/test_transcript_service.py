from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_media.transcript import (
    FakeTranscriptionService,
    GoogleSpeechTranscriptionService,
    TranscriptionError,
    TranscriptionService,
    parse_google_speech_response,
)


@pytest.mark.asyncio
async def test_fake_transcription_service_default():
    service = FakeTranscriptionService()
    transcript = await service.transcribe_gcs_uri(
        "gs://croviq-media-raw/test.mp4",
        production_id="prod_101",
    )

    assert isinstance(transcript, Transcript)
    assert transcript.production_id == "prod_101"
    assert transcript.language_code == "en-US"
    assert transcript.word_count > 0
    assert transcript.duration_ms > 0
    # Invariant: monotonic start times
    for i in range(1, len(transcript.words)):
        assert transcript.words[i].start_ms >= transcript.words[i - 1].start_ms
        assert transcript.words[i].end_ms > transcript.words[i].start_ms


@pytest.mark.asyncio
async def test_fake_transcription_service_custom_transcript():
    now = datetime.now(timezone.utc)
    custom = Transcript(
        transcript_id="tr_custom",
        production_id="prod_202",
        language_code="en-US",
        duration_ms=5000,
        words=[
            TranscriptWord(index=0, text="Custom", start_ms=0, end_ms=500),
            TranscriptWord(index=1, text="Word", start_ms=600, end_ms=1200),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_0",
                start_ms=0,
                end_ms=1200,
                text="Custom Word",
                word_start_index=0,
                word_end_index=1,
            )
        ],
        created_at=now,
    )
    service = FakeTranscriptionService()
    service.set_transcript("gs://my-bucket/custom.mp4", custom)

    result = await service.transcribe_gcs_uri("gs://my-bucket/custom.mp4", production_id="prod_202")
    assert result.transcript_id == "tr_custom"
    assert result.word_count == 2


@pytest.mark.asyncio
async def test_fake_transcription_service_error():
    service = FakeTranscriptionService()
    service.set_error("gs://fail-bucket/error.mp4", "Simulated speech API failure")

    with pytest.raises(TranscriptionError, match="Simulated speech API failure"):
        await service.transcribe_gcs_uri("gs://fail-bucket/error.mp4", production_id="prod_303")


def test_parse_google_speech_response_mapping():
    """Verify parsing of Google Speech v2 response structures into canonical domain Transcript."""
    # Mock a Google Speech v2 BatchRecognizeResponse or file result
    mock_word_1 = MagicMock()
    mock_word_1.word = "Welcome"
    mock_word_1.start_offset.total_seconds.return_value = 0.12  # 120ms
    mock_word_1.end_offset.total_seconds.return_value = 0.54    # 540ms
    mock_word_1.confidence = 0.95
    mock_word_1.speaker_label = "1"

    mock_word_2 = MagicMock()
    mock_word_2.word = "to"
    mock_word_2.start_offset.total_seconds.return_value = 0.60  # 600ms
    mock_word_2.end_offset.total_seconds.return_value = 0.85    # 850ms
    mock_word_2.confidence = 0.99
    mock_word_2.speaker_label = "1"

    mock_word_3 = MagicMock()
    mock_word_3.word = "Croviq"
    mock_word_3.start_offset.total_seconds.return_value = 0.90  # 900ms
    mock_word_3.end_offset.total_seconds.return_value = 1.45    # 1450ms
    mock_word_3.confidence = 0.92
    mock_word_3.speaker_label = "1"

    mock_alternative = MagicMock()
    mock_alternative.transcript = "Welcome to Croviq"
    mock_alternative.words = [mock_word_1, mock_word_2, mock_word_3]

    mock_result_item = MagicMock()
    mock_result_item.alternatives = [mock_alternative]

    mock_file_result = MagicMock()
    mock_file_result.transcript.results = [mock_result_item]

    transcript = parse_google_speech_response(
        file_result=mock_file_result,
        production_id="prod_test",
        language_code="en-US",
    )

    assert transcript.production_id == "prod_test"
    assert transcript.language_code == "en-US"
    assert transcript.word_count == 3
    assert transcript.words[0].text == "Welcome"
    assert transcript.words[0].start_ms == 120
    assert transcript.words[0].end_ms == 540
    assert transcript.words[0].confidence == 0.95
    assert transcript.words[0].speaker_id == "1"

    assert transcript.words[1].text == "to"
    assert transcript.words[1].start_ms == 600
    assert transcript.words[1].end_ms == 850

    assert transcript.words[2].text == "Croviq"
    assert transcript.words[2].start_ms == 900
    assert transcript.words[2].end_ms == 1450

    assert transcript.segment_count == 1
    assert transcript.segments[0].text == "Welcome to Croviq"
    assert transcript.segments[0].word_start_index == 0
    assert transcript.segments[0].word_end_index == 2
    assert transcript.segments[0].start_ms == 120
    assert transcript.segments[0].end_ms == 1450
    assert transcript.duration_ms >= 1450


def test_parse_google_speech_response_protobuf_nanos():
    """Verify parsing when start_offset and end_offset have seconds and nanos attributes."""
    mock_word = MagicMock()
    mock_word.word = "Hello"
    # Create object with seconds and nanos (google.protobuf.Duration style)
    mock_word.start_offset = MagicMock(spec=["seconds", "nanos"])
    mock_word.start_offset.seconds = 2
    mock_word.start_offset.nanos = 500_000_000  # 2500ms
    mock_word.end_offset = MagicMock(spec=["seconds", "nanos"])
    mock_word.end_offset.seconds = 3
    mock_word.end_offset.nanos = 100_000_000  # 3100ms
    mock_word.confidence = 0.98
    mock_word.speaker_label = None

    mock_alt = MagicMock()
    mock_alt.transcript = "Hello"
    mock_alt.words = [mock_word]

    mock_res = MagicMock()
    mock_res.alternatives = [mock_alt]

    mock_file_res = MagicMock()
    mock_file_res.transcript.results = [mock_res]

    transcript = parse_google_speech_response(
        file_result=mock_file_res,
        production_id="prod_duration_test",
        language_code="en-US",
    )

    assert transcript.words[0].start_ms == 2500
    assert transcript.words[0].end_ms == 3100
    assert transcript.duration_ms >= 3100


@pytest.mark.asyncio
async def test_google_speech_transcription_service_mock_api():
    """Test GoogleSpeechTranscriptionService with mocked SpeechClient."""
    mock_client = MagicMock()
    mock_operation = MagicMock()
    
    mock_word = MagicMock()
    mock_word.word = "Test"
    mock_word.start_offset.total_seconds.return_value = 0.1
    mock_word.end_offset.total_seconds.return_value = 0.5
    mock_word.confidence = 0.9
    mock_word.speaker_label = None

    mock_alt = MagicMock()
    mock_alt.transcript = "Test"
    mock_alt.words = [mock_word]

    mock_res = MagicMock()
    mock_res.alternatives = [mock_alt]

    mock_batch_response = MagicMock()
    mock_file_result = MagicMock()
    mock_file_result.transcript.results = [mock_res]
    mock_batch_response.results = {"gs://bucket/test.mp4": mock_file_result}

    mock_operation.result.return_value = mock_batch_response
    mock_client.batch_recognize.return_value = mock_operation

    service = GoogleSpeechTranscriptionService(
        project_id="croviq-506602",
        location="global",
        client_factory=lambda: mock_client,
    )

    transcript = await service.transcribe_gcs_uri(
        "gs://bucket/test.mp4",
        production_id="prod_gcs_mock",
    )

    assert transcript.production_id == "prod_gcs_mock"
    assert transcript.word_count == 1
    assert transcript.words[0].text == "Test"
    mock_client.batch_recognize.assert_called_once()
