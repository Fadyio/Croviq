"""Targeted regression tests for Leo editorial quality and cut safety."""

from datetime import datetime, timezone
import pytest

from croviq_domain.editorial import (
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    SectionAction,
    VideoSectionDecision,
)
from croviq_domain.edl import (
    CutSafetyStatus,
    derive_edited_transcript,
    derive_keep_segments,
)
from croviq_domain.transcript import (
    SilenceInterval,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from croviq_media.cut_safety import CutSafetyAnalyzer, assemble_edl_from_proposal


def _sample_transcript() -> Transcript:
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=100, end_ms=500),
        TranscriptWord(index=1, text="to", start_ms=550, end_ms=700),
        TranscriptWord(index=2, text="the", start_ms=750, end_ms=900),
        TranscriptWord(index=3, text="demo", start_ms=950, end_ms=1400),
        TranscriptWord(index=4, text="um", start_ms=1700, end_ms=1900),
        TranscriptWord(index=5, text="false", start_ms=2100, end_ms=2400),
        TranscriptWord(index=6, text="start", start_ms=2450, end_ms=2800),
        TranscriptWord(index=7, text="here", start_ms=3200, end_ms=3600),
        TranscriptWord(index=8, text="is", start_ms=3650, end_ms=3800),
        TranscriptWord(index=9, text="code", start_ms=3850, end_ms=4300),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_001",
            text="Welcome to the demo um false start here is code",
            start_ms=100,
            end_ms=4300,
            word_start_index=0,
            word_end_index=9,
        )
    ]
    return Transcript(
        transcript_id="tr_reg_01",
        production_id="prod_reg_01",
        language_code="en",
        duration_ms=5000,
        words=words,
        segments=segments,
        silence_intervals=[
            SilenceInterval(start_ms=1400, end_ms=1700, duration_ms=300),
            SilenceInterval(start_ms=2800, end_ms=3200, duration_ms=400),
            SilenceInterval(start_ms=4300, end_ms=5000, duration_ms=700),
        ],
        created_at=now,
    )


def test_destructive_decision_types_include_silence_and_pauses():
    """Verify REMOVE_SILENCE, TIGHTEN_PAUSE, and REMOVE_LOW_VALUE_SECTION are treated as destructive cuts."""
    tr = _sample_transcript()
    analyzer = CutSafetyAnalyzer()

    # False start decision
    fs_dec = EditorDecision(
        decision_id="dec_fs_01",
        decision_type=EditorDecisionType.REMOVE_FALSE_START,
        transcript_start_word=5,
        transcript_end_word=6,
        source_start_ms=2100,
        source_end_ms=2800,
        original_text="false start",
        action="remove",
        concise_reason="Remove stumbling false start",
        confidence=0.95,
    )
    cut = analyzer.analyze_cut(fs_dec, tr)
    assert cut.safety_status == CutSafetyStatus.SAFE
    assert cut.removed_duration_ms > 0

    # Pause tighten decision
    pt_dec = EditorDecision(
        decision_id="dec_pt_01",
        decision_type=EditorDecisionType.TIGHTEN_PAUSE,
        transcript_start_word=3,
        transcript_end_word=4,
        source_start_ms=1400,
        source_end_ms=1700,
        original_text="[Silence: demo ... um]",
        action="trim",
        concise_reason="Tighten dead air pause",
        confidence=0.9,
    )
    cut_pt = analyzer.analyze_cut(pt_dec, tr)
    assert cut_pt.safety_status == CutSafetyStatus.SAFE


def test_derive_edited_transcript_remaps_timing():
    """Verify derive_edited_transcript removes cut words and shifts kept words accurately."""
    tr = _sample_transcript()
    proposal = EditorProposal(
        production_id="prod_reg_01",
        agent="leo",
        model="gemini-3.7-flash",
        summary="Test edit",
        decisions=[
            EditorDecision(
                decision_id="dec_fs_01",
                decision_type=EditorDecisionType.REMOVE_FALSE_START,
                transcript_start_word=4,
                transcript_end_word=6,
                source_start_ms=1700,
                source_end_ms=2800,
                original_text="um false start",
                action="remove",
                concise_reason="Cut verbal stumbling",
                confidence=0.95,
            )
        ],
        section_plan=[
            VideoSectionDecision(
                section_id="sec_01",
                source_start_ms=0,
                source_end_ms=5000,
                transcript_start_word=0,
                transcript_end_word=9,
                action=SectionAction.KEEP,
                reason="Clean intro",
                confidence=0.95,
            )
        ],
        chapters=[],
        overall_confidence=0.95,
    )

    edl = assemble_edl_from_proposal(proposal, tr)
    assert edl.active_cuts_count == 1

    edited_tr = derive_edited_transcript(tr, edl)
    assert edited_tr.duration_ms < tr.duration_ms
    assert len(edited_tr.words) == 7  # 10 original - 3 removed ('um', 'false', 'start')
    assert "um" not in [w.text for w in edited_tr.words]
    assert "false" not in [w.text for w in edited_tr.words]
    assert "start" not in [w.text for w in edited_tr.words]
    assert edited_tr.words[0].text == "Welcome"
    assert edited_tr.words[-1].text == "code"


