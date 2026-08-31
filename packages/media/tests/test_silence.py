"""Unit tests for SilenceCleanupPlanner and deterministic silence cleanup before Leo."""

from datetime import datetime, timezone
import pytest

from croviq_domain.editorial import EditorDecisionType
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.transcript import (
    SilenceInterval,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from croviq_media.silence import SilenceCleanupPlanner


def _create_transcript_with_silence(
    words_data: list[tuple[int, str, int, int]],
    silences_data: list[tuple[int, int]],
    total_duration_ms: int = 60000,
) -> Transcript:
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=idx, text=text, start_ms=s_ms, end_ms=e_ms, confidence=0.98)
        for idx, text, s_ms, e_ms in words_data
    ]
    silence_intervals = [
        SilenceInterval(start_ms=s_ms, end_ms=e_ms, duration_ms=e_ms - s_ms)
        for s_ms, e_ms in silences_data
    ]
    return Transcript(
        transcript_id="tr_silence_test",
        production_id="prod_silence_test",
        language_code="en",
        duration_ms=total_duration_ms,
        words=words,
        silence_intervals=silence_intervals,
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                text=" ".join(w.text for w in words),
                start_ms=words[0].start_ms if words else 0,
                end_ms=words[-1].end_ms if words else total_duration_ms,
                word_start_index=0,
                word_end_index=len(words) - 1 if words else 0,
            )
        ],
        created_at=now,
    )


def test_silence_greater_than_threshold_becomes_cut():
    """Silence intervals >= 1200ms must produce deterministic TRIM_PAUSE baseline cuts."""
    words = [
        (0, "First", 1000, 2000),
        (1, "Second", 9700, 11000),  # 7.7s gap between 2000 and 9700
    ]
    silences = [(2000, 9700)]
    transcript = _create_transcript_with_silence(words, silences, total_duration_ms=15000)

    planner = SilenceCleanupPlanner(min_silence_duration_ms=1200, natural_pause_ms=250)
    decisions = planner.plan_silence_cleanup(transcript)

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.decision_type == EditorDecisionType.TRIM_PAUSE
    assert decision.action == "trim"
    assert decision.confidence == 1.0
    # Retaining 250ms natural pause (125ms after word 0, 125ms before word 1)
    assert decision.source_start_ms == 2125
    assert decision.source_end_ms == 9575
    # Total removed duration = 7450ms (7.45s) out of 7.7s dead air
    assert (decision.source_end_ms - decision.source_start_ms) == 7450
    assert decision.transcript_start_word == 0
    assert decision.transcript_end_word == 1


def test_short_natural_pauses_remain_preserved():
    """Silence intervals < 1200ms (e.g. 500ms, 800ms) are preserved as natural pacing."""
    words = [
        (0, "Hello", 1000, 1500),
        (1, "world", 2000, 2500),  # 500ms pause
        (2, "again", 3400, 4000),  # 900ms pause
    ]
    silences = [(1500, 2000), (2500, 3400)]
    transcript = _create_transcript_with_silence(words, silences, total_duration_ms=5000)

    planner = SilenceCleanupPlanner(min_silence_duration_ms=1200, natural_pause_ms=250)
    decisions = planner.plan_silence_cleanup(transcript)

    assert len(decisions) == 0


def test_silence_cut_never_intersects_words():
    """Silence cut boundaries must strictly respect preceding and succeeding word boundaries."""
    # Even if silence interval metadata claims to overlap slightly with a word
    words = [
        (0, "Code", 1000, 2100),
        (1, "tutorial", 5900, 7000),
    ]
    # Faulty silence interval starting at 1900 (inside word 0) and ending at 6100 (inside word 1)
    silences = [(1900, 6100)]
    transcript = _create_transcript_with_silence(words, silences, total_duration_ms=10000)

    planner = SilenceCleanupPlanner(min_silence_duration_ms=1200, natural_pause_ms=250)
    decisions = planner.plan_silence_cleanup(transcript)

    assert len(decisions) == 1
    decision = decisions[0]
    # Safe boundary clamped to word 0 end (2100) + 125ms = 2225ms
    assert decision.source_start_ms >= 2100 + 125
    # Safe boundary clamped to word 1 start (5900) - 125ms = 5775ms
    assert decision.source_end_ms <= 5900 - 125

    # Check zero intersection with words
    for w in transcript.words:
        # Cut must not contain any word start or end
        assert not (decision.source_start_ms < w.start_ms < decision.source_end_ms)
        assert not (decision.source_start_ms < w.end_ms < decision.source_end_ms)

