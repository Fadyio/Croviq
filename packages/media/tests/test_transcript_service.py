from datetime import datetime, timezone
from pathlib import Path

import pytest

from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_media.transcript import (
    FakeTranscriptionService,
    TranscriptionError,
    TranscriptionService,
    parse_duration_to_ms,
)


@pytest.mark.asyncio
async def test_fake_transcription_service_default(tmp_path: Path):
    service = FakeTranscriptionService()
    audio_path = tmp_path / "speech.wav"
    audio_path.write_bytes(b"RIFF fake audio")

    transcript = await service.transcribe_audio_file(
        audio_path,
        production_id="prod_101",
        source_duration_ms=5000,
    )

    assert isinstance(transcript, Transcript)
    assert isinstance(service, TranscriptionService)
    assert transcript.production_id == "prod_101"
    assert transcript.language_code == "en-US"
    assert transcript.word_count > 0
    assert transcript.duration_ms >= 5000
    for i in range(1, len(transcript.words)):
        assert transcript.words[i].start_ms >= transcript.words[i - 1].start_ms
        assert transcript.words[i].end_ms > transcript.words[i].start_ms


@pytest.mark.asyncio
async def test_fake_transcription_service_custom_transcript(tmp_path: Path):
    now = datetime.now(timezone.utc)
    audio_path = tmp_path / "custom.wav"
    audio_path.write_bytes(b"RIFF custom fake audio")
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
    service.set_transcript(str(audio_path), custom)

    result = await service.transcribe_audio_file(audio_path, production_id="prod_202")

    assert result.transcript_id == "tr_custom"
    assert result.word_count == 2


@pytest.mark.asyncio
async def test_fake_transcription_service_error(tmp_path: Path):
    audio_path = tmp_path / "error.wav"
    audio_path.write_bytes(b"RIFF error fake audio")
    service = FakeTranscriptionService()
    service.set_error(str(audio_path), "Simulated speech API failure")

    with pytest.raises(TranscriptionError, match="Simulated speech API failure"):
        await service.transcribe_audio_file(audio_path, production_id="prod_303")


def test_parse_duration_to_ms_numeric_seconds():
    assert parse_duration_to_ms(2.5) == 2500


def test_parse_duration_to_ms_protobuf_style():
    class Duration:
        seconds = 3
        nanos = 100_000_000

    assert parse_duration_to_ms(Duration()) == 3100
