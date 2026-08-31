"""Unit tests for Canonical EDL (EditDecisionList) and CutInstruction domain models."""

from datetime import datetime, timezone
import pytest
from croviq_domain.editorial import (
    EditorDecisionType,
    SemanticEvent,
)
from croviq_domain.edl import (
    CoverageMarker,
    CoverageType,
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
    audit_proposed_cuts,
    classify_cut_overlap,
    compute_editorial_quality_report,
    compute_interval_union,
    compute_intervals_duration,
    derive_keep_segments,
    map_source_time_to_edited,
)

def test_coverage_marker_valid():
    marker = CoverageMarker(
        marker_id="cov_001",
        decision_id="dec_002",
        source_start_ms=26160,
        source_end_ms=42340,
        coverage_type=CoverageType.SOURCE_SCREEN,
        reason="Close-up macro insert over assembly commentary",
    )
    assert marker.marker_id == "cov_001"
    assert marker.coverage_type == CoverageType.SOURCE_SCREEN
    assert marker.source_end_ms > marker.source_start_ms


def test_coverage_marker_invalid_bounds():
    with pytest.raises(ValueError, match="source_end_ms .* must be greater than source_start_ms"):
        CoverageMarker(
            marker_id="cov_001",
            decision_id="dec_002",
            source_start_ms=5000,
            source_end_ms=4000,
            coverage_type=CoverageType.SOURCE_SCREEN,
            reason="Invalid bounds",
        )


def test_cut_instruction_valid_safe():
    cut = CutInstruction(
        cut_id="cut_001",
        decision_id="dec_filler_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=3,
        transcript_end_word=4,
        requested_start_ms=1200,
        requested_end_ms=1500,
        safe_start_ms=1150,
        safe_end_ms=1550,
        removed_duration_ms=400,
        left_anchor="we",
        right_anchor="should",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Clean inter-word pause boundaries",
        confidence=0.98,
        coverage_marker_id=None,
        requires_room_tone=False,
    )
    assert cut.cut_id == "cut_001"
    assert cut.transition_ms == 20
    assert cut.removed_duration_ms == 400
    assert cut.safety_status == CutSafetyStatus.SAFE


def test_cut_instruction_needs_coverage():
    cut = CutInstruction(
        cut_id="cut_002",
        decision_id="dec_tighten_01",
        decision_type=EditorDecisionType.TIGHTEN_EXPLANATION,
        transcript_start_word=10,
        transcript_end_word=25,
        requested_start_ms=5000,
        requested_end_ms=12000,
        safe_start_ms=4950,
        safe_end_ms=12050,
        removed_duration_ms=7100,
        left_anchor="workflow",
        right_anchor="deploy",
        transition_ms=20,
        safety_status=CutSafetyStatus.NEEDS_COVERAGE,
        safety_reason="Audio clean but talking-head jump cut detected",
        confidence=0.92,
        coverage_marker_id="cov_001",
        requires_room_tone=False,
    )
    assert cut.safety_status == CutSafetyStatus.NEEDS_COVERAGE
    assert cut.coverage_marker_id == "cov_001"


def test_cut_instruction_rejected_unsafe():
    cut = CutInstruction(
        cut_id="cut_003",
        decision_id="dec_unsafe_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=5,
        transcript_end_word=5,
        requested_start_ms=2000,
        requested_end_ms=2100,
        safe_start_ms=2000,
        safe_end_ms=2100,
        removed_duration_ms=0,
        left_anchor="tight",
        right_anchor="word",
        transition_ms=20,
        safety_status=CutSafetyStatus.REJECTED_UNSAFE,
        safety_reason="Zero inter-word gap with severe co-articulation risk",
        confidence=0.45,
    )
    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE


def test_cut_instruction_invalid_bounds():
    with pytest.raises(ValueError, match="safe_end_ms .* must be >= safe_start_ms"):
        CutInstruction(
            cut_id="cut_bad",
            decision_id="dec_01",
            decision_type=EditorDecisionType.REMOVE_FILLER,
            transcript_start_word=1,
            transcript_end_word=2,
            requested_start_ms=1000,
            requested_end_ms=2000,
            safe_start_ms=2000,
            safe_end_ms=1000,
            removed_duration_ms=0,
            left_anchor="a",
            right_anchor="b",
            safety_status=CutSafetyStatus.SAFE,
            safety_reason="bad bounds",
            confidence=0.8,
        )


def test_edit_decision_list_zero_cut_valid():
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_zero_01",
        production_id="prod_f0b41bfd429e",
        source_duration_ms=97180,
        editor_proposal_id="prop_01",
        version=1,
        cuts=[],
        coverage_markers=[
            CoverageMarker(
                marker_id="cov_001",
                decision_id="dec_002",
                source_start_ms=26160,
                source_end_ms=42340,
                coverage_type=CoverageType.SOURCE_SCREEN,
                reason="Plate swap macro footage",
            )
        ],
        created_at=now,
    )
    assert edl.edl_id == "edl_zero_01"
    assert len(edl.cuts) == 0
    assert len(edl.coverage_markers) == 1
    assert edl.active_cuts_count == 0


def test_edit_decision_list_with_cuts():
    now = datetime.now(timezone.utc)
    cut1 = CutInstruction(
        cut_id="cut_01",
        decision_id="dec_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=2,
        transcript_end_word=2,
        requested_start_ms=1000,
        requested_end_ms=1400,
        safe_start_ms=980,
        safe_end_ms=1420,
        removed_duration_ms=440,
        left_anchor="start",
        right_anchor="next",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Safe filler cut",
        confidence=0.95,
    )
    cut2 = CutInstruction(
        cut_id="cut_02",
        decision_id="dec_02",
        decision_type=EditorDecisionType.REMOVE_REPETITION,
        transcript_start_word=10,
        transcript_end_word=15,
        requested_start_ms=5000,
        requested_end_ms=8000,
        safe_start_ms=4950,
        safe_end_ms=8050,
        removed_duration_ms=3100,
        left_anchor="phrase",
        right_anchor="continued",
        transition_ms=20,
        safety_status=CutSafetyStatus.NEEDS_COVERAGE,
        safety_reason="Safe audio, needs screen cover",
        confidence=0.91,
    )
    edl = EditDecisionList(
        edl_id="edl_cut_01",
        production_id="prod_test_01",
        source_duration_ms=20000,
        version=1,
        cuts=[cut1, cut2],
        created_at=now,
    )
    assert edl.active_cuts_count == 2
    assert edl.total_removed_duration_ms == 3540
    assert edl.estimated_target_duration_ms == 16460


def test_derive_keep_segments_zero_cuts():
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_zero",
        production_id="prod_01",
        source_duration_ms=50000,
        version=1,
        cuts=[],
        created_at=now,
    )
    segments = derive_keep_segments(edl)
    assert segments == [(0, 50000)]


def test_derive_keep_segments_single_cut_middle():
    now = datetime.now(timezone.utc)
    cut = CutInstruction(
        cut_id="cut_01",
        decision_id="dec_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=5,
        transcript_end_word=6,
        requested_start_ms=10000,
        requested_end_ms=15000,
        safe_start_ms=10000,
        safe_end_ms=15000,
        removed_duration_ms=5000,
        left_anchor="before",
        right_anchor="after",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="clean cut",
        confidence=0.95,
    )
    edl = EditDecisionList(
        edl_id="edl_mid",
        production_id="prod_01",
        source_duration_ms=40000,
        version=1,
        cuts=[cut],
        created_at=now,
    )
    segments = derive_keep_segments(edl)
    assert segments == [(0, 10000), (15000, 40000)]


def test_derive_keep_segments_cut_at_beginning_and_end():
    now = datetime.now(timezone.utc)
    cut_start = CutInstruction(
        cut_id="cut_01",
        decision_id="dec_01",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=0,
        transcript_end_word=0,
        requested_start_ms=0,
        requested_end_ms=2000,
        safe_start_ms=0,
        safe_end_ms=2000,
        removed_duration_ms=2000,
        left_anchor="[START]",
        right_anchor="first",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="trim intro pause",
        confidence=0.99,
    )
    cut_end = CutInstruction(
        cut_id="cut_02",
        decision_id="dec_02",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=50,
        transcript_end_word=50,
        requested_start_ms=28000,
        requested_end_ms=30000,
        safe_start_ms=28000,
        safe_end_ms=30000,
        removed_duration_ms=2000,
        left_anchor="last",
        right_anchor="[END]",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="trim outro dead air",
        confidence=0.99,
    )
    edl = EditDecisionList(
        edl_id="edl_edges",
        production_id="prod_01",
        source_duration_ms=30000,
        version=1,
        cuts=[cut_start, cut_end],
        created_at=now,
    )
    segments = derive_keep_segments(edl)
    assert segments == [(2000, 28000)]


def test_derive_keep_segments_skips_rejected_unsafe():
    now = datetime.now(timezone.utc)
    cut_safe = CutInstruction(
        cut_id="cut_safe",
        decision_id="dec_safe",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=2,
        transcript_end_word=2,
        requested_start_ms=5000,
        requested_end_ms=6000,
        safe_start_ms=5000,
        safe_end_ms=6000,
        removed_duration_ms=1000,
        left_anchor="a",
        right_anchor="b",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="safe",
        confidence=0.95,
    )
    cut_unsafe = CutInstruction(
        cut_id="cut_unsafe",
        decision_id="dec_unsafe",
        decision_type=EditorDecisionType.REMOVE_FALSE_START,
        transcript_start_word=10,
        transcript_end_word=12,
        requested_start_ms=15000,
        requested_end_ms=18000,
        safe_start_ms=15000,
        safe_end_ms=18000,
        removed_duration_ms=0,
        left_anchor="c",
        right_anchor="d",
        transition_ms=20,
        safety_status=CutSafetyStatus.REJECTED_UNSAFE,
        safety_reason="rejected unsafe",
        confidence=0.3,
    )
    edl = EditDecisionList(
        edl_id="edl_mix",
        production_id="prod_01",
        source_duration_ms=25000,
        version=1,
        cuts=[cut_safe, cut_unsafe],
        created_at=now,
    )
    segments = derive_keep_segments(edl)
    # The unsafe cut is ignored, so segment from 6000 to 25000 is kept uninterrupted
    assert segments == [(0, 5000), (6000, 25000)]
def test_map_source_time_to_edited_zero_cuts():
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_zero",
        production_id="prod_01",
        source_duration_ms=113824,
        cuts=[],
        created_at=now,
    )
    assert map_source_time_to_edited(0, edl) == 0
    assert map_source_time_to_edited(17460, edl) == 17460
    assert map_source_time_to_edited(60260, edl) == 60260
    assert map_source_time_to_edited(113824, edl) == 113824


def test_map_source_time_to_edited_two_cuts():
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_2cuts",
        production_id="prod_01",
        source_duration_ms=113824,
        cuts=[
            CutInstruction(
                cut_id="c1",
                decision_id="d1",
                decision_type=EditorDecisionType.TRIM_PAUSE,
                transcript_start_word=27,
                transcript_end_word=28,
                requested_start_ms=12540,
                requested_end_ms=15000,
                safe_start_ms=12540,
                safe_end_ms=15000,
                removed_duration_ms=2460,
                left_anchor="out.",
                right_anchor="Now",
                safety_status=CutSafetyStatus.SAFE,
                safety_reason="Clean pause",
                confidence=0.95,
            ),
            CutInstruction(
                cut_id="c2",
                decision_id="d2",
                decision_type=EditorDecisionType.REMOVE_FALSE_START,
                transcript_start_word=121,
                transcript_end_word=125,
                requested_start_ms=42340,
                requested_end_ms=44400,
                safe_start_ms=42340,
                safe_end_ms=44400,
                removed_duration_ms=2060,
                left_anchor="fingers.",
                right_anchor="And",
                safety_status=CutSafetyStatus.SAFE,
                safety_reason="Restart cleanly excised",
                confidence=0.95,
            ),
        ],
        created_at=now,
    )

    # 1. Start of video
    assert map_source_time_to_edited(0, edl) == 0

    # 2. Before cut 1
    assert map_source_time_to_edited(10000, edl) == 10000

    # 3. Inside cut 1 (snaps to cut start boundary)
    assert map_source_time_to_edited(13500, edl) == 12540

    # 4. Between cut 1 and cut 2
    # 17460ms - 2460ms cut 1 = 15000ms
    assert map_source_time_to_edited(17460, edl) == 15000

    # 5. After cut 2
    # 60260ms - 4520ms total cuts = 55740ms
    assert map_source_time_to_edited(60260, edl) == 55740

    # 75520ms - 4520ms = 71000ms
    assert map_source_time_to_edited(75520, edl) == 71000

    # 97340ms - 4520ms = 92820ms
    assert map_source_time_to_edited(97340, edl) == 92820

    # Source end: 113824ms - 4520ms = 109304ms
    assert map_source_time_to_edited(113824, edl) == 109304


def test_case_a_fully_subsumed_proposed_cut():
    """Case A: fully subsumed proposed cut => effective_removed_ms = 0."""
    existing_cuts = [(17000, 22500)]
    proposed = (18000, 21000)
    classification, newly_eff, overlap = classify_cut_overlap(proposed, existing_cuts)
    assert classification == "FULLY_SUBSUMED"
    assert newly_eff == 0
    assert overlap == 3000

    audit = audit_proposed_cuts([proposed], existing_cuts)
    assert audit["effective_removed_ms"] == 0
    assert audit["has_effective_change"] is False
    assert audit["already_removed_ms"] == 3000


def test_case_b_partially_overlapping_proposed_cut():
    """Case B: partially overlapping proposed cut => only newly uncovered interval counted."""
    existing_cuts = [(17000, 20000)]
    proposed = (19000, 22000)
    classification, newly_eff, overlap = classify_cut_overlap(proposed, existing_cuts)
    assert classification == "PARTIALLY_OVERLAPPING"
    assert newly_eff == 2000
    assert overlap == 1000

    audit = audit_proposed_cuts([proposed], existing_cuts)
    assert audit["effective_removed_ms"] == 2000
    assert audit["has_effective_change"] is True
    assert audit["already_removed_ms"] == 1000


def test_case_c_disjoint_proposed_cut():
    """Case C: disjoint proposed cut => entire duration counted."""
    existing_cuts = [(17000, 20000)]
    proposed = (25000, 28000)
    classification, newly_eff, overlap = classify_cut_overlap(proposed, existing_cuts)
    assert classification == "NEW"
    assert newly_eff == 3000
    assert overlap == 0

    audit = audit_proposed_cuts([proposed], existing_cuts)
    assert audit["effective_removed_ms"] == 3000
    assert audit["has_effective_change"] is True


def test_case_d_multiple_overlapping_proposed_cuts():
    """Case D: multiple overlapping proposed cuts => interval union counted once."""
    existing_cuts = [(10000, 15000)]
    # Proposed 1: 14000-18000 (4000 raw, overlaps existing by 1000 -> 3000 new)
    # Proposed 2: 17000-21000 (4000 raw, overlaps proposed 1 by 1000 -> 3000 new beyond p1)
    # Combined union with existing is 10000-21000 (11000 total - 5000 existing = 6000 new)
    proposed = [(14000, 18000), (17000, 21000)]
    audit = audit_proposed_cuts(proposed, existing_cuts)
    assert audit["effective_removed_ms"] == 6000
    assert audit["has_effective_change"] is True


def test_compute_editorial_quality_report_with_semantic_events():
    """Verify physical duration summing and semantic event counts in compute_editorial_quality_report."""
    now = datetime.now(timezone.utc)
    cut1 = CutInstruction(
        cut_id="cut_1",
        decision_id="dec_silence_1",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=0,
        transcript_end_word=0,
        requested_start_ms=5000,
        requested_end_ms=7000,
        safe_start_ms=5000,
        safe_end_ms=7000,
        removed_duration_ms=2000,
        left_anchor="intro",
        right_anchor="content",
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Clean silence pause",
        confidence=1.0,
        category="DEAD_AIR",
        contains_silence=True,
        contains_semantic_removal=False,
        semantic_events=[
            SemanticEvent(
                event_id="ev_1",
                decision_id="dec_silence_1",
                decision_type="TRIM_PAUSE",
                category="DEAD_AIR",
                reason="Trim silence",
                start_ms=5000,
                end_ms=7000,
                duration_ms=2000,
                is_silence=True,
            )
        ],
    )
    cut2 = CutInstruction(
        cut_id="cut_2",
        decision_id="dec_filler_1",
        decision_type=EditorDecisionType.FILLER,
        transcript_start_word=5,
        transcript_end_word=5,
        requested_start_ms=10000,
        requested_end_ms=10500,
        safe_start_ms=9800,
        safe_end_ms=13000,
        removed_duration_ms=3200,
        left_anchor="word1",
        right_anchor="word2",
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Clean filler cut merged with silence",
        confidence=1.0,
        removed_text="Okay.",
        concise_reason="Deterministic silence cleanup: 2.7s; Removed filler 'Okay.'",
        category="FILLER",
        contains_silence=True,
        contains_semantic_removal=True,
        semantic_events=[
            SemanticEvent(
                event_id="ev_2a",
                decision_id="silence_before_filler",
                decision_type="TRIM_PAUSE",
                category="DEAD_AIR",
                reason="Trim silence before filler",
                start_ms=9800,
                end_ms=10000,
                duration_ms=200,
                is_silence=True,
            ),
            SemanticEvent(
                event_id="ev_2b",
                decision_id="dec_filler_1",
                decision_type="FILLER",
                category="FILLER",
                reason="Removed filler 'Okay.'",
                removed_text="Okay.",
                start_ms=10000,
                end_ms=10500,
                duration_ms=500,
                is_silence=False,
            ),
            SemanticEvent(
                event_id="ev_2c",
                decision_id="silence_after_filler",
                decision_type="TRIM_PAUSE",
                category="DEAD_AIR",
                reason="Trim silence after filler",
                start_ms=10500,
                end_ms=13000,
                duration_ms=2500,
                is_silence=True,
            ),
        ],
    )
    cut3 = CutInstruction(
        cut_id="cut_3",
        decision_id="dec_false_start_1",
        decision_type=EditorDecisionType.FALSE_START,
        transcript_start_word=10,
        transcript_end_word=11,
        requested_start_ms=20000,
        requested_end_ms=21000,
        safe_start_ms=19500,
        safe_end_ms=21500,
        removed_duration_ms=2000,
        left_anchor="before",
        right_anchor="after",
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Cut false start",
        confidence=1.0,
        removed_text="the GitHub",
        concise_reason="Remove false start 'the GitHub'",
        category="FALSE_START",
        contains_silence=False,
        contains_semantic_removal=True,
        semantic_events=[
            SemanticEvent(
                event_id="ev_3",
                decision_id="dec_false_start_1",
                decision_type="FALSE_START",
                category="FALSE_START",
                reason="Remove false start",
                removed_text="the GitHub",
                start_ms=19500,
                end_ms=21500,
                duration_ms=2000,
                is_silence=False,
            )
        ],
    )

    edl = EditDecisionList(
        edl_id="edl_test_semantic_report",
        production_id="prod_test",
        source_duration_ms=50000,
        version=1,
        cuts=[cut1, cut2, cut3],
        created_at=now,
    )

    report = compute_editorial_quality_report(edl)
    assert report.source_duration_ms == 50000
    assert report.new_edited_duration_ms == 50000 - (2000 + 3200 + 2000)  # 42800ms
    assert report.total_removed_ms == 7200

    # Physical breakdown duration sums to exact total
    phys_sum = (
        report.dead_air.duration_ms
        + report.filler.duration_ms
        + report.false_start.duration_ms
        + report.word_repetition.duration_ms
        + report.phrase_repetition.duration_ms
        + report.redundant_explanation.duration_ms
        + report.pacing.duration_ms
        + report.other.duration_ms
    )
    assert phys_sum == report.total_removed_ms == 7200
    assert report.dead_air.count == 1
    assert report.dead_air.duration_ms == 2000
    assert report.filler.count == 1
    assert report.filler.duration_ms == 3200
    assert report.false_start.count == 1
    assert report.false_start.duration_ms == 2000
    assert report.physical_cuts_count == 3
    assert report.semantic_cuts_count == 2
    assert report.silence_only_edit is False

    # Semantic events breakdown
    assert report.semantic_events.filler == 1
    assert report.semantic_events.false_start == 1
    assert report.semantic_events.pause_trim == 3
    assert report.semantic_events.total_events == 5
    assert report.semantic_events.semantic_events_count == 2
