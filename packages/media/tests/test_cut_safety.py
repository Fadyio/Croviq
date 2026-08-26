"""Unit tests for CutSafetyAnalyzer and deterministic natural-cut boundary calculations."""

from datetime import datetime, timezone
import pytest

from croviq_domain.editorial import (
    DirectorDecision,
    DirectorReview,
    DirectorVerdict,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
)
from croviq_domain.edl import (
    CoverageType,
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_media.cut_safety import CutSafetyAnalyzer, assemble_edl_from_review


def _create_sample_transcript(words_data: list[tuple[int, str, int, int]]) -> Transcript:
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=idx, text=text, start_ms=s_ms, end_ms=e_ms, confidence=0.98)
        for idx, text, s_ms, e_ms in words_data
    ]
    return Transcript(
        transcript_id="tr_fixture_01",
        production_id="prod_fixture_01",
        language_code="en",
        duration_ms=words[-1].end_ms + 1000 if words else 10000,
        words=words,
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                text=" ".join(w.text for w in words),
                start_ms=words[0].start_ms if words else 0,
                end_ms=words[-1].end_ms if words else 10000,
                word_start_index=0,
                word_end_index=len(words) - 1 if words else 0,
            )
        ],
        created_at=now,
    )


def _sample_media_metadata(duration_ms: int = 60000) -> MediaMetadata:
    return MediaMetadata(
        duration_ms=duration_ms,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        size_bytes=10_000_000,
    )


def test_safe_filler_cut():
    # "we (100-300) should (320-500) um (700-900) deploy (1100-1400) this (1420-1600)"
    # Gap before "um": 500 -> 700 (200ms)
    # Gap after "um": 900 -> 1100 (200ms)
    words = [
        (0, "we", 100, 300),
        (1, "should", 320, 500),
        (2, "um", 700, 900),
        (3, "deploy", 1100, 1400),
        (4, "this", 1420, 1600),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_filler_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=2,
        transcript_end_word=2,
        source_start_ms=700,
        source_end_ms=900,
        original_text="um",
        action="remove",
        concise_reason="Remove filler word um",
        confidence=0.98,
        visual_context="terminal screen demo",
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.SAFE
    assert cut.decision_id == "dec_filler_01"
    assert cut.requested_start_ms == 700
    assert cut.requested_end_ms == 900
    # Safe boundaries snap into adjacent silence up to 100ms
    assert cut.safe_start_ms == 600  # 700 - 100
    assert cut.safe_end_ms == 1000  # 900 + 100
    assert cut.removed_duration_ms == 400
    assert cut.left_anchor == "should"
    assert cut.right_anchor == "deploy"
    assert cut.transition_ms == 20


def test_false_start_cut():
    # "I'll (0-200) show (220-450) [gap 450-800] I'll (800-1000) show (1020-1200) you (1220-1400)"
    words = [
        (0, "I'll", 0, 200),
        (1, "show", 220, 450),
        (2, "I'll", 800, 1000),
        (3, "show", 1020, 1200),
        (4, "you", 1220, 1400),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_fs_01",
        decision_type=EditorDecisionType.REMOVE_FALSE_START,
        transcript_start_word=0,
        transcript_end_word=1,
        source_start_ms=0,
        source_end_ms=450,
        original_text="I'll show",
        action="remove",
        concise_reason="Abandoned false start before second clean take",
        confidence=0.95,
        visual_context="terminal screen demo",
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.SAFE
    assert cut.left_anchor == "[START]"
    assert cut.right_anchor == "I'll"
    assert cut.safe_start_ms == 0
    assert cut.safe_end_ms == 550  # 450 + 100ms into the 350ms gap
    assert cut.removed_duration_ms == 550


def test_repetition_cut():
    # "This (100-300) workflow (320-600) deploys (620-900) the (920-1050) API (1070-1300) [gap 1300-1800] This (1800-2000) workflow (2020-2300)..."
    words = [
        (0, "This", 100, 300),
        (1, "workflow", 320, 600),
        (2, "deploys", 620, 900),
        (3, "the", 920, 1050),
        (4, "API", 1070, 1300),
        (5, "This", 1800, 2000),
        (6, "workflow", 2020, 2300),
        (7, "deploys", 2320, 2600),
        (8, "the", 2620, 2750),
        (9, "API", 2770, 3000),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_rep_01",
        decision_type=EditorDecisionType.REMOVE_REPETITION,
        transcript_start_word=0,
        transcript_end_word=4,
        source_start_ms=100,
        source_end_ms=1300,
        original_text="This workflow deploys the API",
        action="remove",
        concise_reason="Remove duplicated initial sentence",
        confidence=0.96,
        visual_context="screen recording",
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.SAFE
    assert cut.safe_start_ms == 0  # Starts at 0
    assert cut.safe_end_ms == 1400  # 1300 + 100ms
    assert cut.left_anchor == "[START]"
    assert cut.right_anchor == "This"


def test_pause_trim_cut():
    # "Before (0-400) [silence 400-3000: 2600ms dead air] After (3000-3400)"
    words = [
        (0, "Before", 0, 400),
        (1, "After", 3000, 3400),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_pause_01",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=0,
        transcript_end_word=0,
        source_start_ms=400,
        source_end_ms=3000,
        original_text="Before",
        action="trim",
        concise_reason="Trim 2.6s dead air pause",
        confidence=0.97,
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.SAFE
    # Natural pause trimming leaves natural breathing room (e.g. 200ms after 'Before' and 200ms before 'After')
    assert cut.safe_start_ms == 600  # 400 + 200ms natural breath preserved
    assert cut.safe_end_ms == 2800  # 3000 - 200ms natural lead-in preserved
    assert cut.removed_duration_ms == 2200


def test_unsafe_tight_join_rejected():
    # "tightly (100-400) joined (400-700) words (700-1000)" - 0ms gap between all words
    words = [
        (0, "tightly", 100, 400),
        (1, "joined", 400, 700),
        (2, "words", 700, 1000),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_tight_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=1,
        transcript_end_word=1,
        source_start_ms=400,
        source_end_ms=700,
        original_text="joined",
        action="remove",
        concise_reason="Attempt to cut mid-phrase word with zero acoustic silence",
        confidence=0.60,
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE
    assert "tightly joined" in cut.safety_reason.lower() or "zero gap" in cut.safety_reason.lower() or "co-articulation" in cut.safety_reason.lower()


def test_protected_keep_region_overlap_rejected():
    words = [
        (0, "We", 100, 300),
        (1, "must", 320, 500),
        (2, "never", 520, 700),
        (3, "compromise", 720, 1100),
        (4, "on", 1120, 1250),
        (5, "security", 1270, 1600),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    # Protected KEEP_FOR_CLARITY decision covering words 2-5 ("never compromise on security")
    protected_decision = EditorDecision(
        decision_id="dec_keep_sec",
        decision_type=EditorDecisionType.KEEP_FOR_CLARITY,
        transcript_start_word=2,
        transcript_end_word=5,
        source_start_ms=520,
        source_end_ms=1600,
        original_text="never compromise on security",
        action="keep",
        concise_reason="Critical security clarification",
        confidence=0.99,
    )

    # Conflicting removal decision proposing to cut words 4-5 ("on security")
    cut_decision = EditorDecision(
        decision_id="dec_cut_overlap",
        decision_type=EditorDecisionType.TIGHTEN_EXPLANATION,
        transcript_start_word=4,
        transcript_end_word=5,
        source_start_ms=1120,
        source_end_ms=1600,
        original_text="on security",
        action="remove",
        concise_reason="Tighten phrasing",
        confidence=0.85,
    )

    cut = analyzer.analyze_cut(
        decision=cut_decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
        protected_decisions=[protected_decision],
    )

    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE
    assert "protected" in cut.safety_reason.lower()


def test_director_reject_verdict():
    words = [
        (0, "Hello", 100, 400),
        (1, "world", 500, 900),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=0,
        transcript_end_word=0,
        source_start_ms=100,
        source_end_ms=400,
        original_text="Hello",
        action="remove",
        concise_reason="Remove intro greeting",
        confidence=0.8,
    )
    director_dec = DirectorDecision(
        editor_decision_id="dec_01",
        verdict=DirectorVerdict.REJECT,
        concise_reason="Maya rejected: Keep intro greeting for personality.",
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.REJECT,
        director_decision=director_dec,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE
    assert "director rejected" in cut.safety_reason.lower()


def test_director_modify_verdict():
    # "So (100-300) [gap 300-500] basically (500-800) [gap 800-1000] you (1000-1200) run (1220-1500)"
    words = [
        (0, "So", 100, 300),
        (1, "basically", 500, 800),
        (2, "you", 1000, 1200),
        (3, "run", 1220, 1500),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    # Leo proposed cutting 0 to 1 ("So basically")
    decision = EditorDecision(
        decision_id="dec_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=0,
        transcript_end_word=1,
        source_start_ms=100,
        source_end_ms=800,
        original_text="So basically",
        action="remove",
        concise_reason="Remove filler phrase",
        confidence=0.9,
    )

    # Maya modifies to only cut word 1 ("basically")
    director_dec = DirectorDecision(
        editor_decision_id="dec_01",
        verdict=DirectorVerdict.MODIFY,
        concise_reason="Keep 'So' for transition, remove only 'basically'",
        modified_action="remove",
        modified_transcript_start_word=1,
        modified_transcript_end_word=1,
        modified_source_start_ms=500,
        modified_source_end_ms=800,
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.MODIFY,
        director_decision=director_dec,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.SAFE
    assert cut.transcript_start_word == 1
    assert cut.transcript_end_word == 1
    assert cut.requested_start_ms == 500
    assert cut.requested_end_ms == 800
    assert cut.left_anchor == "So"
    assert cut.right_anchor == "you"


def test_needs_coverage_visual_jump_cut():
    words = [
        (0, "First", 100, 400),
        (1, "point", 420, 800),
        (2, "and", 1000, 1200),
        (3, "then", 1220, 1400),
        (4, "second", 1600, 1900),
        (5, "point", 1920, 2200),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    # Removal on a talking head presenter causing visual discontinuity
    decision = EditorDecision(
        decision_id="dec_th_01",
        decision_type=EditorDecisionType.TIGHTEN_EXPLANATION,
        transcript_start_word=2,
        transcript_end_word=3,
        source_start_ms=1000,
        source_end_ms=1400,
        original_text="and then",
        action="remove",
        concise_reason="Remove filler connector",
        confidence=0.92,
        visual_context="Presenter on camera talking head",
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.NEEDS_COVERAGE
    assert "jump cut" in cut.safety_reason.lower() or "visual" in cut.safety_reason.lower()


def test_broll_cover_candidate_creates_coverage_marker_not_destructive_cut():
    words = [
        (0, "Look", 100, 400),
        (1, "at", 420, 600),
        (2, "this", 620, 900),
        (3, "part", 920, 1200),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_broll_01",
        decision_type=EditorDecisionType.BROLL_COVER_CANDIDATE,
        transcript_start_word=0,
        transcript_end_word=3,
        source_start_ms=100,
        source_end_ms=1200,
        original_text="Look at this part",
        action="cover",
        concise_reason="Overlay close-up hardware insert",
        confidence=0.95,
        visual_context="Hardware closeup",
    )

    marker = analyzer.extract_coverage_marker(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
    )

    assert marker is not None
    assert marker.decision_id == "dec_broll_01"
    assert marker.coverage_type == CoverageType.BROLL_CANDIDATE
    assert marker.source_start_ms == 100
    assert marker.source_end_ms == 1200


def test_invalid_transcript_word_index_rejected():
    words = [
        (0, "Single", 100, 400),
        (1, "word", 420, 800),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata()
    analyzer = CutSafetyAnalyzer()

    # Index 99 is out of bounds
    decision = EditorDecision(
        decision_id="dec_bad_idx",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=99,
        transcript_end_word=99,
        source_start_ms=100,
        source_end_ms=400,
        original_text="nonexistent",
        action="remove",
        concise_reason="Bad index",
        confidence=0.5,
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE
    assert "index" in cut.safety_reason.lower()


def test_cut_exceeding_source_duration_rejected():
    words = [
        (0, "Beyond", 65000, 68000),
    ]
    transcript = _create_sample_transcript(words)
    # Media duration is only 60000ms
    metadata = _sample_media_metadata(duration_ms=60000)
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_beyond",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=0,
        transcript_end_word=0,
        source_start_ms=65000,
        source_end_ms=68000,
        original_text="Beyond",
        action="remove",
        concise_reason="Timestamp beyond video end",
        confidence=0.5,
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        verdict=DirectorVerdict.APPROVE,
        director_decision=None,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE
    assert "duration" in cut.safety_reason.lower()

def test_assemble_edl_from_review_zero_cuts():
    words = [
        (0, "The", 0, 300),
        (1, "phone", 320, 600),
        (2, "is", 620, 800),
        (3, "modular", 820, 1400),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata(duration_ms=5000)

    proposal = EditorProposal(
        production_id="prod_01",
        model="gemini-3.7-flash",
        summary="Keep all dialogue, insert plate macro footage",
        decisions=[
            EditorDecision(
                decision_id="dec_k1",
                decision_type=EditorDecisionType.KEEP,
                transcript_start_word=0,
                transcript_end_word=3,
                source_start_ms=0,
                source_end_ms=1400,
                original_text="The phone is modular",
                action="keep",
                concise_reason="Strong hook",
                confidence=0.98,
            ),
            EditorDecision(
                decision_id="dec_b1",
                decision_type=EditorDecisionType.BROLL_COVER_CANDIDATE,
                transcript_start_word=0,
                transcript_end_word=3,
                source_start_ms=0,
                source_end_ms=1400,
                original_text="The phone is modular",
                action="cover",
                concise_reason="Close-up macro insert",
                confidence=0.95,
            ),
        ],
        overall_confidence=0.97,
    )

    review = DirectorReview(
        production_id="prod_01",
        model="director-maya-v2",
        overall_assessment="Approved without cuts",
        decisions=[
            DirectorDecision(
                editor_decision_id="dec_k1",
                verdict=DirectorVerdict.APPROVE,
                concise_reason="Approved hook",
            ),
            DirectorDecision(
                editor_decision_id="dec_b1",
                verdict=DirectorVerdict.APPROVE,
                concise_reason="Approved B-roll marker",
            ),
        ],
        editor_feedback="Proceed to EDL",
        approved_for_edl=True,
        confidence=0.96,
    )

    edl = assemble_edl_from_review(
        production_id="prod_01",
        proposal=proposal,
        review=review,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert edl.production_id == "prod_01"
    assert edl.source_duration_ms == 5000
    assert edl.cuts == []
    assert len(edl.coverage_markers) == 1
    assert edl.coverage_markers[0].coverage_type == CoverageType.BROLL_CANDIDATE
    assert edl.active_cuts_count == 0
    assert edl.total_removed_duration_ms == 0
    assert edl.estimated_target_duration_ms == 5000


def test_assemble_edl_from_review_with_multiple_cuts():
    words = [
        (0, "we", 100, 300),
        (1, "should", 320, 500),
        (2, "um", 700, 900),
        (3, "deploy", 1100, 1400),
        (4, "this", 1420, 1600),
        (5, "This", 2000, 2200),
        (6, "workflow", 2220, 2500),
        (7, "This", 2800, 3000),
        (8, "workflow", 3020, 3300),
    ]
    transcript = _create_sample_transcript(words)
    metadata = _sample_media_metadata(duration_ms=10000)

    proposal = EditorProposal(
        production_id="prod_02",
        model="gemini-3.7-flash",
        summary="Cut filler and repetition",
        decisions=[
            EditorDecision(
                decision_id="dec_filler",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=2,
                transcript_end_word=2,
                source_start_ms=700,
                source_end_ms=900,
                original_text="um",
                action="remove",
                concise_reason="Remove filler um",
                confidence=0.95,
            ),
            EditorDecision(
                decision_id="dec_rep",
                decision_type=EditorDecisionType.REMOVE_REPETITION,
                transcript_start_word=5,
                transcript_end_word=6,
                source_start_ms=2000,
                source_end_ms=2500,
                original_text="This workflow",
                action="remove",
                concise_reason="Remove duplicate phrase",
                confidence=0.92,
            ),
        ],
        overall_confidence=0.94,
    )

    review = DirectorReview(
        production_id="prod_02",
        model="director-maya-v2",
        overall_assessment="Approved removals",
        decisions=[
            DirectorDecision(
                editor_decision_id="dec_filler",
                verdict=DirectorVerdict.APPROVE,
                concise_reason="Approved filler removal",
            ),
            DirectorDecision(
                editor_decision_id="dec_rep",
                verdict=DirectorVerdict.APPROVE,
                concise_reason="Approved repetition removal",
            ),
        ],
        editor_feedback="Assemble EDL",
        approved_for_edl=True,
        confidence=0.95,
    )

    edl = assemble_edl_from_review(
        production_id="prod_02",
        proposal=proposal,
        review=review,
        transcript=transcript,
        media_metadata=metadata,
    )

    assert len(edl.cuts) == 2
    assert edl.active_cuts_count == 2
    assert edl.cuts[0].decision_id == "dec_filler"
    assert edl.cuts[1].decision_id == "dec_rep"
    assert edl.cuts[0].safe_start_ms < edl.cuts[1].safe_start_ms
    assert edl.total_removed_duration_ms > 0
