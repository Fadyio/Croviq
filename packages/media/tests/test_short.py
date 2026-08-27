"""Unit tests for Short candidate validation, word rebasing, phrase grouping, and ASS subtitle generation."""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from croviq_domain.editorial import ShortCandidate
from croviq_domain.transcript import Transcript, TranscriptWord
from croviq_media.short import (
    CaptionPhrase,
    CaptionWord,
    extract_rebased_caption_words,
    format_ass_timecode,
    generate_ass_subtitles,
    group_words_into_phrases,
    validate_and_snap_short_candidate,
)


def _make_transcript(words_data: list[tuple[str, int, int]]) -> Transcript:
    words = [
        TranscriptWord(
            index=i,
            text=text,
            start_ms=start,
            end_ms=end,
        )
        for i, (text, start, end) in enumerate(words_data)
    ]
    duration_ms = words[-1].end_ms if words else 0
    return Transcript(
        transcript_id="tr_test",
        production_id="prod_test",
        language_code="en",
        duration_ms=duration_ms,
        words=words,
        created_at=datetime.now(timezone.utc),
    )


def test_validate_and_snap_short_candidate_snaps_to_word_indices():
    words_data = [
        ("Welcome", 0, 800),
        ("to", 850, 1000),
        ("the", 1050, 1200),
        ("teardown.", 1250, 2000),
        ("Today", 2500, 3000),
        ("we", 3050, 3200),
        ("repair", 3250, 3900),
        ("the", 3950, 4100),
        ("phone.", 4150, 5000),
    ]
    transcript = _make_transcript(words_data)

    candidate = ShortCandidate(
        start_ms=2400,
        end_ms=5100,
        transcript_start_word=4,  # "Today" at 2500
        transcript_end_word=8,    # "phone." at 5000
        hook_title="Repair the phone",
        concise_reason="Clear repair demonstration",
        confidence=0.95,
    )

    start_ms, end_ms = validate_and_snap_short_candidate(
        candidate=candidate,
        source_duration_ms=6000,
        transcript=transcript,
    )

    assert start_ms == 2500
    assert end_ms == 5000


def test_validate_and_snap_short_candidate_snaps_overlapping_words_when_indices_missing():
    words_data = [
        ("First", 1000, 1500),
        ("Second", 1600, 2200),
        ("Third", 2300, 3000),
    ]
    transcript = _make_transcript(words_data)

    candidate = ShortCandidate(
        start_ms=1200,  # mid-word "First"
        end_ms=2800,    # mid-word "Third"
        transcript_start_word=99,  # invalid index
        transcript_end_word=99,
        hook_title="Test hook",
        concise_reason="Test reason",
        confidence=0.9,
    )

    start_ms, end_ms = validate_and_snap_short_candidate(
        candidate=candidate,
        source_duration_ms=5000,
        transcript=transcript,
    )

    assert start_ms == 1000
    assert end_ms == 3000


def test_validate_and_snap_short_candidate_invalid_bounds():
    candidate = ShortCandidate(
        start_ms=5000,
        end_ms=8000,
        transcript_start_word=0,
        transcript_end_word=1,
        hook_title="Test",
        concise_reason="Test",
        confidence=0.9,
    )

    # Exceeds source duration
    with pytest.raises(ValueError, match="exceeds source duration"):
        validate_and_snap_short_candidate(
            candidate=candidate,
            source_duration_ms=4000,
        )


def test_extract_rebased_caption_words_rebases_timestamps():
    words_data = [
        ("Intro", 0, 500),
        ("A", 1000, 1200),
        ("Modern", 1250, 1600),
        ("Smartphone", 1650, 2200),
        ("Outro", 3000, 3500),
    ]
    transcript = _make_transcript(words_data)

    rebased = extract_rebased_caption_words(
        transcript=transcript,
        short_start_ms=1000,
        short_end_ms=2300,
    )

    assert len(rebased) == 3
    assert [w.text for w in rebased] == ["A", "Modern", "Smartphone"]
    assert rebased[0].start_ms == 0
    assert rebased[0].end_ms == 200
    assert rebased[1].start_ms == 250
    assert rebased[1].end_ms == 600
    assert rebased[2].start_ms == 650
    assert rebased[2].end_ms == 1200


def test_group_words_into_phrases_bounds_and_punctuation():
    words = [
        CaptionWord(index=0, text="Hello,", start_ms=0, end_ms=400),
        CaptionWord(index=1, text="world!", start_ms=450, end_ms=800),
        CaptionWord(index=2, text="This", start_ms=1200, end_ms=1400),  # 400ms pause from 800
        CaptionWord(index=3, text="is", start_ms=1450, end_ms=1600),
        CaptionWord(index=4, text="a", start_ms=1650, end_ms=1750),
        CaptionWord(index=5, text="deterministic", start_ms=1800, end_ms=2300),
        CaptionWord(index=6, text="Short", start_ms=2350, end_ms=2700),
        CaptionWord(index=7, text="renderer.", start_ms=2750, end_ms=3200),
    ]

    phrases = group_words_into_phrases(words, min_words=2, max_words=5, max_pause_ms=300)

    assert len(phrases) >= 2
    assert phrases[0].text == "Hello, world!"
    assert phrases[0].start_ms == 0
    assert phrases[0].end_ms == 800
    assert len(phrases[0].words) == 2


def test_format_ass_timecode():
    assert format_ass_timecode(0) == "0:00:00.00"
    assert format_ass_timecode(1500) == "0:00:01.50"
    assert format_ass_timecode(65430) == "0:01:05.43"
    assert format_ass_timecode(3661250) == "1:01:01.25"


def test_generate_ass_subtitles_includes_croviq_blue_active_word_highlight():
    phrases = [
        CaptionPhrase(
            start_ms=0,
            end_ms=1200,
            words=[
                CaptionWord(index=0, text="THIS", start_ms=0, end_ms=400),
                CaptionWord(index=1, text="is", start_ms=400, end_ms=700),
                CaptionWord(index=2, text="Croviq", start_ms=700, end_ms=1200),
            ],
        )
    ]

    ass_text = generate_ass_subtitles(
        phrases=phrases,
        font_name="Arial",
        font_size=64,
        highlight_color_bgr="&H00EB6325&",  # Croviq blue (#2563EB)
        base_color_bgr="&H00FFFFFF&",       # White
        margin_v=320,
    )

    assert "[Script Info]" in ass_text
    assert "[V4+ Styles]" in ass_text
    assert "[Events]" in ass_text
    assert "PlayResX: 1080" in ass_text
    assert "PlayResY: 1920" in ass_text

    # Verify per-word active highlight dialogue lines
    assert "{\\c&H00EB6325&}THIS{\\c&H00FFFFFF&} is Croviq" in ass_text
    assert "THIS {\\c&H00EB6325&}is{\\c&H00FFFFFF&} Croviq" in ass_text
    assert "THIS is {\\c&H00EB6325&}Croviq{\\c&H00FFFFFF&}" in ass_text
