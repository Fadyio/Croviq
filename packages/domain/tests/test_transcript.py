from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.transcript import (
    SilenceInterval,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)


def test_transcript_word_valid():
    word = TranscriptWord(
        index=0,
        text="Hello",
        start_ms=100,
        end_ms=450,
        confidence=0.98,
        speaker_id="speaker_1",
    )
    assert word.index == 0
    assert word.text == "Hello"
    assert word.start_ms == 100
    assert word.end_ms == 450
    assert word.duration_ms == 350
    assert word.confidence == 0.98
    assert word.speaker_id == "speaker_1"


def test_transcript_word_validation_errors():
    # Negative index
    with pytest.raises(ValidationError):
        TranscriptWord(index=-1, text="test", start_ms=0, end_ms=100)

    # Empty text
    with pytest.raises(ValidationError):
        TranscriptWord(index=0, text="", start_ms=0, end_ms=100)

    # Negative start_ms
    with pytest.raises(ValidationError):
        TranscriptWord(index=0, text="test", start_ms=-10, end_ms=100)

    # end_ms <= start_ms
    with pytest.raises(ValidationError):
        TranscriptWord(index=0, text="test", start_ms=100, end_ms=100)
    with pytest.raises(ValidationError):
        TranscriptWord(index=0, text="test", start_ms=150, end_ms=100)

    # Invalid confidence range
    with pytest.raises(ValidationError):
        TranscriptWord(index=0, text="test", start_ms=0, end_ms=100, confidence=1.5)
    with pytest.raises(ValidationError):
        TranscriptWord(index=0, text="test", start_ms=0, end_ms=100, confidence=-0.1)


def test_transcript_segment_valid():
    segment = TranscriptSegment(
        segment_id="seg_01",
        start_ms=100,
        end_ms=1200,
        text="Hello world welcome",
        word_start_index=0,
        word_end_index=2,
    )
    assert segment.segment_id == "seg_01"
    assert segment.start_ms == 100
    assert segment.end_ms == 1200
    assert segment.word_count == 3


def test_transcript_segment_validation_errors():
    with pytest.raises(ValidationError):
        TranscriptSegment(
            segment_id="",
            start_ms=0,
            end_ms=100,
            text="valid",
            word_start_index=0,
            word_end_index=0,
        )

    with pytest.raises(ValidationError):
        TranscriptSegment(
            segment_id="seg_1",
            start_ms=100,
            end_ms=50,
            text="invalid timing",
            word_start_index=0,
            word_end_index=0,
        )

    with pytest.raises(ValidationError):
        TranscriptSegment(
            segment_id="seg_1",
            start_ms=0,
            end_ms=100,
            text="invalid indices",
            word_start_index=2,
            word_end_index=1,
        )


def test_transcript_valid():
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=100, end_ms=400, confidence=0.95),
        TranscriptWord(index=1, text="to", start_ms=450, end_ms=600, confidence=0.99),
        TranscriptWord(index=2, text="Croviq", start_ms=750, end_ms=1200, confidence=0.92),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_01",
            start_ms=100,
            end_ms=1200,
            text="Welcome to Croviq",
            word_start_index=0,
            word_end_index=2,
        )
    ]
    transcript = Transcript(
        transcript_id="tr_12345",
        production_id="prod_67890",
        language_code="en-US",
        duration_ms=1500,
        words=words,
        segments=segments,
        created_at=now,
    )

    assert transcript.transcript_id == "tr_12345"
    assert transcript.production_id == "prod_67890"
    assert transcript.word_count == 3
    assert transcript.segment_count == 1
    assert transcript.duration_ms == 1500


def test_transcript_silence_intervals():
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="First", start_ms=100, end_ms=400),
        # silence: 400 -> 800 (400ms)
        TranscriptWord(index=1, text="Second", start_ms=800, end_ms=1200),
        # silence: 1200 -> 1250 (50ms)
        TranscriptWord(index=2, text="Third", start_ms=1250, end_ms=1500),
    ]
    transcript = Transcript(
        transcript_id="tr_1",
        production_id="prod_1",
        language_code="en",
        duration_ms=2000,
        words=words,
        segments=[],
        created_at=now,
    )

    # Silence intervals with default threshold
    silences = transcript.get_silence_intervals(min_silence_ms=100)
    assert len(silences) == 1
    assert silences[0] == SilenceInterval(start_ms=400, end_ms=800, duration_ms=400)

    # Silence intervals with min_silence_ms=0 includes 50ms gap
    all_silences = transcript.get_silence_intervals(min_silence_ms=0)
    assert len(all_silences) == 2
    assert all_silences[0] == SilenceInterval(start_ms=400, end_ms=800, duration_ms=400)
    assert all_silences[1] == SilenceInterval(start_ms=1200, end_ms=1250, duration_ms=50)


def test_transcript_monotonicity_validation():
    now = datetime.now(timezone.utc)
    # Non-monotonic start times
    words = [
        TranscriptWord(index=0, text="First", start_ms=500, end_ms=800),
        TranscriptWord(index=1, text="Second", start_ms=400, end_ms=700),
    ]
    with pytest.raises(ValidationError, match="monotonic"):
        Transcript(
            transcript_id="tr_1",
            production_id="prod_1",
            language_code="en",
            duration_ms=1000,
            words=words,
            segments=[],
            created_at=now,
        )


def test_transcript_index_continuity_validation():
    now = datetime.now(timezone.utc)
    # Discontinuous index
    words = [
        TranscriptWord(index=0, text="First", start_ms=100, end_ms=300),
        TranscriptWord(index=2, text="Second", start_ms=400, end_ms=600),
    ]
    with pytest.raises(ValidationError, match="contiguous"):
        Transcript(
            transcript_id="tr_1",
            production_id="prod_1",
            language_code="en",
            duration_ms=1000,
            words=words,
            segments=[],
            created_at=now,
        )


def test_transcript_duration_validation():
    now = datetime.now(timezone.utc)
    # Last word ends at 1200ms, but declared duration is 1000ms
    words = [
        TranscriptWord(index=0, text="First", start_ms=100, end_ms=1200),
    ]
    with pytest.raises(ValidationError, match="duration_ms"):
        Transcript(
            transcript_id="tr_1",
            production_id="prod_1",
            language_code="en",
            duration_ms=1000,
            words=words,
            segments=[],
            created_at=now,
        )


def test_transcript_words_in_range():
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="Word0", start_ms=0, end_ms=300),
        TranscriptWord(index=1, text="Word1", start_ms=400, end_ms=700),
        TranscriptWord(index=2, text="Word2", start_ms=800, end_ms=1100),
        TranscriptWord(index=3, text="Word3", start_ms=1200, end_ms=1500),
    ]
    transcript = Transcript(
        transcript_id="tr_1",
        production_id="prod_1",
        language_code="en",
        duration_ms=2000,
        words=words,
        segments=[],
        created_at=now,
    )

    in_range = transcript.get_words_in_range(start_ms=350, end_ms=1150)
    assert [w.text for w in in_range] == ["Word1", "Word2"]


def test_transcript_serialization_roundtrip():
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="Hello", start_ms=100, end_ms=500, confidence=0.95),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_01",
            start_ms=100,
            end_ms=500,
            text="Hello",
            word_start_index=0,
            word_end_index=0,
        )
    ]
    transcript = Transcript(
        transcript_id="tr_100",
        production_id="prod_200",
        language_code="en-US",
        duration_ms=1000,
        words=words,
        segments=segments,
        created_at=now,
    )

    dump = transcript.model_dump(mode="json")
    assert dump["transcript_id"] == "tr_100"
    assert dump["words"][0]["text"] == "Hello"

    loaded = Transcript.model_validate(dump)
    assert loaded == transcript
