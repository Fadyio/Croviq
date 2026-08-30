"""Unit tests for Video-Grounded Transcript Correction domain models and methods."""

from datetime import datetime, timezone
import pytest
from croviq_domain.transcript import (
    CorrectedTranscript,
    CorrectedTranscriptSegment,
    EntailmentVerdict,
    ScriptCorrectionChangeType,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)


def test_corrected_transcript_segment_validation():
    seg = CorrectedTranscriptSegment(
        source_start_ms=16200,
        source_end_ms=20300,
        original_text="So uh what we're gonna... what we're gonna do now is deploy it.",
        corrected_text="So what we're going to do now is deploy it.",
        change_type=ScriptCorrectionChangeType.FALSE_START,
        reason="Removed filler and repeated phrase.",
        visual_evidence="IDE shows active deploy command.",
        meaning_changed=False,
        target_duration_ms=4100,
        confidence=0.97,
        entailment_verdict=EntailmentVerdict.SUPPORTED,
    )
    assert seg.source_start_ms == 16200
    assert seg.source_end_ms == 20300
    assert seg.target_duration_ms == 4100
    assert seg.meaning_changed is False
    assert seg.change_type == ScriptCorrectionChangeType.FALSE_START
    assert seg.entailment_verdict == EntailmentVerdict.SUPPORTED


def test_corrected_transcript_segment_invalid_bounds():
    with pytest.raises(ValueError, match="source_end_ms"):
        CorrectedTranscriptSegment(
            source_start_ms=5000,
            source_end_ms=4000,
            original_text="Hello",
            corrected_text="Hello",
            target_duration_ms=1000,
        )


def test_corrected_transcript_metrics():
    now = datetime.now(timezone.utc)
    segments = [
        CorrectedTranscriptSegment(
            source_start_ms=0,
            source_end_ms=4000,
            original_text="Welcome to this video.",
            corrected_text="Welcome to this video.",
            change_type=ScriptCorrectionChangeType.KEEP,
            target_duration_ms=4000,
        ),
        CorrectedTranscriptSegment(
            source_start_ms=4000,
            source_end_ms=8000,
            original_text="We is going to configure get hub actions.",
            corrected_text="We are going to configure GitHub Actions.",
            change_type=ScriptCorrectionChangeType.TRANSCRIPTION_ERROR,
            reason="Corrected terminology and grammar",
            target_duration_ms=4000,
            meaning_changed=False,
            entailment_verdict=EntailmentVerdict.SUPPORTED,
        ),
        CorrectedTranscriptSegment(
            source_start_ms=8000,
            source_end_ms=12000,
            original_text="Um basically like this workflow triggers.",
            corrected_text="This workflow triggers.",
            change_type=ScriptCorrectionChangeType.FILLER,
            reason="Removed conversational filler",
            target_duration_ms=4000,
            meaning_changed=False,
            entailment_verdict=EntailmentVerdict.SUPPORTED,
        ),
    ]
    ct = CorrectedTranscript(
        transcript_id="corr_test_01",
        production_id="prod_test_01",
        segments=segments,
        created_at=now,
    )
    assert ct.corrections_count == 2
    assert ct.transcription_corrections_count == 1
    assert ct.filler_corrections_count == 1
    assert ct.meaning_preserved is True
    assert ct.supported_corrections_count == 2
