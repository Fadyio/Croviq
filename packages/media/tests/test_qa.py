"""Unit tests for deterministic Media QA checks (Issue #33)."""

from datetime import datetime, timezone
import pytest

from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.packaging import PackagingChapter
from croviq_domain.release_review import ReleaseIssueSeverity, ReleaseIssueType
from croviq_domain.transcript import Transcript, TranscriptWord
from croviq_media.qa import (
    AudioQAResult,
    CaptionQAResult,
    ChapterQAResult,
    DeterministicMediaQAService,
    MediaQAResult,
)


def test_validate_chapters_valid():
    chapters = [
        PackagingChapter(start_ms=0, end_ms=30000, formatted_time="0:00", title="Intro"),
        PackagingChapter(start_ms=30000, end_ms=60000, formatted_time="0:30", title="Unboxing"),
        PackagingChapter(start_ms=60000, end_ms=90000, formatted_time="1:00", title="Review"),
    ]
    service = DeterministicMediaQAService()
    result = service.validate_chapters(chapters=chapters, master_duration_ms=90000)

    assert result.is_valid is True
    assert len(result.issues) == 0


def test_validate_chapters_invalid_unordered_and_out_of_bounds():
    chapters = [
        PackagingChapter(start_ms=30000, end_ms=40000, formatted_time="0:30", title="Unboxing"),
        PackagingChapter(start_ms=10000, end_ms=20000, formatted_time="0:10", title="Intro"),
        PackagingChapter(start_ms=120000, end_ms=130000, formatted_time="2:00", title="End (Beyond Master)"),
    ]
    service = DeterministicMediaQAService()
    result = service.validate_chapters(chapters=chapters, master_duration_ms=90000)

    assert result.is_valid is False
    assert len(result.issues) >= 2
    types = [i.issue_type for i in result.issues]
    assert ReleaseIssueType.CHAPTER_TIMING in types


def test_validate_captions_against_transcript_and_timeline():
    now = datetime.now(timezone.utc)
    transcript = Transcript(
        transcript_id="tr_01",
        production_id="prod_01",
        language_code="en",
        created_at=now,
        duration_ms=60000,
        words=[
            TranscriptWord(index=0, text="Hello", start_ms=1000, end_ms=1500, confidence=0.99),
            TranscriptWord(index=1, text="world", start_ms=1600, end_ms=2000, confidence=0.99),
        ],
    )
    service = DeterministicMediaQAService()
    result = service.validate_captions(transcript=transcript, master_duration_ms=60000)

    assert result.is_valid is True
    assert len(result.issues) == 0

def test_validate_captions_out_of_bounds():
    now = datetime.now(timezone.utc)
    transcript = Transcript(
        transcript_id="tr_01",
        production_id="prod_01",
        language_code="en",
        created_at=now,
        duration_ms=80000,
        words=[
            TranscriptWord(index=0, text="Out", start_ms=70000, end_ms=75000, confidence=0.99),
        ],
    )
    service = DeterministicMediaQAService()
    result = service.validate_captions(transcript=transcript, master_duration_ms=60000)

    assert result.is_valid is False
    assert any(i.issue_type == ReleaseIssueType.CAPTION_TIMING for i in result.issues)


def test_validate_short_media_metadata_valid():
    short_meta = MediaMetadata(
        duration_ms=45000,
        width=1080,
        height=1920,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        size_bytes=5_000_000,
    )
    service = DeterministicMediaQAService()
    result = service.validate_short_metadata(short_meta)

    assert result.is_valid is True
    assert len(result.issues) == 0


def test_validate_short_media_metadata_invalid_aspect_and_duration():
    short_meta = MediaMetadata(
        duration_ms=95000,  # Too long (>60s)
        width=1920,         # Landscape, not 9:16
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        size_bytes=10_000_000,
    )
    service = DeterministicMediaQAService()
    result = service.validate_short_metadata(short_meta)

    assert result.is_valid is False
    assert any(i.issue_type == ReleaseIssueType.SHORT_CROP for i in result.issues)
    assert any(i.issue_type == ReleaseIssueType.SHORT_QUALITY for i in result.issues)


def test_validate_audio_levels():
    service = DeterministicMediaQAService()
    # Good audio (~ -16 LUFS, -1 dBTP)
    res_good = service.validate_audio_loudness(integrated_lufs=-15.8, true_peak_dbtp=-1.1)
    assert res_good.is_valid is True

    # Bad audio (clipping + too loud)
    res_bad = service.validate_audio_loudness(integrated_lufs=-8.0, true_peak_dbtp=1.5)
    assert res_bad.is_valid is False
    assert any(i.issue_type == ReleaseIssueType.AUDIO_LEVEL for i in res_bad.issues)
