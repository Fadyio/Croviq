"""Unit tests for CutSafetyAnalyzer and deterministic natural-cut boundary calculations."""

from datetime import datetime, timezone
import pytest

from croviq_domain.editorial import (
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
)
from croviq_domain.edl import (
    BackgroundMusicMix,
    CoverageType,
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
    compute_editorial_quality_report,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_media.cut_safety import CutSafetyAnalyzer, assemble_edl_from_proposal


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
        transcript=transcript,
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
        transcript=transcript,
    )

    assert cut.safety_status == CutSafetyStatus.SAFE
    assert cut.left_anchor == "[START]"
    assert cut.right_anchor == "I'll"
    assert cut.safe_start_ms == 0
    assert cut.safe_end_ms == 550  # 450 + 100ms
    assert cut.removed_duration_ms == 550


def test_tighten_explanation_cut():
    # Words 0..6, cutting words 2..4
    # "First (100-300) we (320-450) do (600-800) unnecessary (820-1200) steps (1220-1500) then (1700-1900) deploy (1920-2200)"
    words = [
        (0, "First", 100, 300),
        (1, "we", 320, 450),
        (2, "do", 600, 800),
        (3, "unnecessary", 820, 1200),
        (4, "steps", 1220, 1500),
        (5, "then", 1700, 1900),
        (6, "deploy", 1920, 2200),
    ]
    transcript = _create_sample_transcript(words)
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_tighten_01",
        decision_type=EditorDecisionType.TIGHTEN_EXPLANATION,
        transcript_start_word=2,
        transcript_end_word=4,
        source_start_ms=600,
        source_end_ms=1500,
        original_text="do unnecessary steps",
        action="remove",
        concise_reason="Tighten explanation by removing tangential filler sentence",
        confidence=0.92,
        visual_context="talking head",
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        transcript=transcript,
    )

    assert cut.safety_status == CutSafetyStatus.NEEDS_COVERAGE
    assert cut.left_anchor == "we"
    assert cut.right_anchor == "then"
    assert cut.safe_start_ms == 500
    assert cut.safe_end_ms == 1600
    assert cut.removed_duration_ms == 1100


def test_cut_rejected_too_short():
    # Attempting to cut a 50ms interval with no silence
    words = [
        (0, "word1", 100, 200),
        (1, "a", 210, 260),
        (2, "word2", 270, 400),
    ]
    transcript = _create_sample_transcript(words)
    analyzer = CutSafetyAnalyzer(min_cut_duration_ms=120)

    decision = EditorDecision(
        decision_id="dec_tiny_01",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=1,
        transcript_end_word=1,
        source_start_ms=210,
        source_end_ms=260,
        original_text="a",
        action="remove",
        concise_reason="Tiny word",
        confidence=0.75,
        visual_context="screencast",
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        transcript=transcript,
    )

    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE
    assert "below the deterministic minimum" in cut.safety_reason


def test_cut_rejected_zero_silence():
    # Words with 0ms gap
    words = [
        (0, "start", 100, 300),
        (1, "middle", 300, 500),
        (2, "end", 500, 700),
    ]
    transcript = _create_sample_transcript(words)
    analyzer = CutSafetyAnalyzer()

    decision = EditorDecision(
        decision_id="dec_zerosilence",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=1,
        transcript_end_word=1,
        source_start_ms=300,
        source_end_ms=500,
        original_text="middle",
        action="remove",
        concise_reason="Connected word with 0 gap",
        confidence=0.8,
        visual_context="screencast",
    )

    cut = analyzer.analyze_cut(
        decision=decision,
        transcript=transcript,
    )

    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE
    assert "zero inter-word silence" in cut.safety_reason


def test_cut_safety_protects_kept_decisions():
    words = [
        (0, "Hello", 0, 500),
        (1, "world", 700, 1200),
        (2, "welcome", 1400, 1800),
    ]
    transcript = _create_sample_transcript(words)
    analyzer = CutSafetyAnalyzer()

    kept = EditorDecision(
        decision_id="dec_keep",
        decision_type=EditorDecisionType.KEEP,
        transcript_start_word=0,
        transcript_end_word=1,
        source_start_ms=0,
        source_end_ms=1200,
        original_text="Hello world",
        action="keep",
        concise_reason="Keep greeting",
        confidence=0.99,
    )

    cut_decision = EditorDecision(
        decision_id="dec_cut",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=0,
        transcript_end_word=0,
        source_start_ms=0,
        source_end_ms=500,
        original_text="Hello",
        action="remove",
        concise_reason="Remove intro",
        confidence=0.9,
    )

    cut = analyzer.analyze_cut(
        decision=cut_decision,
        transcript=transcript,
        protected_decisions=[kept],
    )

    assert cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE
    assert "protected KEEP decision" in cut.safety_reason


def test_assemble_edl_from_proposal_zero_cuts():
    words = [
        (0, "The", 0, 200),
        (1, "phone", 220, 500),
        (2, "is", 520, 700),
        (3, "modular", 720, 1400),
    ]
    transcript = _create_sample_transcript(words)

    proposal = EditorProposal(
        production_id="prod_01",
        model="gemini-3.7-flash",
        summary="Zero cuts proposal",
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
        ],
        overall_confidence=0.97,
    )

    edl = assemble_edl_from_proposal(
        proposal=proposal,
        transcript=transcript,
    )

    assert edl.production_id == "prod_01"
    assert edl.cuts == []
    assert len(edl.coverage_markers) == 0
    assert edl.active_cuts_count == 0
    assert edl.total_removed_duration_ms == 0


def test_assemble_edl_from_proposal_with_multiple_cuts():
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

    edl = assemble_edl_from_proposal(
        proposal=proposal,
        transcript=transcript,
    )

    assert len(edl.cuts) == 2
    assert edl.active_cuts_count == 2
    assert edl.cuts[0].decision_id == "dec_filler"
    assert edl.cuts[1].decision_id == "dec_rep"
    assert edl.cuts[0].safe_start_ms < edl.cuts[1].safe_start_ms
    assert edl.total_removed_duration_ms > 0


def test_merged_silence_and_semantic_cuts_preserves_category_and_events():
    """Verify that merging adjacent silence and filler/false-start cuts retains the semantic category and events."""
    words = [
        (0, "Intro", 100, 400),
        (1, "content", 450, 800),
        # silence: 800-4000 (3.2s)
        (2, "Okay.", 4050, 4300),
        # silence: 4300-6000 (1.7s)
        (3, "And", 6050, 6300),
        (4, "next", 6350, 6700),
    ]
    transcript = _create_sample_transcript(words)

    proposal = EditorProposal(
        production_id="prod_merge_test",
        model="gemini-3.7-flash",
        summary="Silence and filler merging test",
        decisions=[
            EditorDecision(
                decision_id="silence_cut_001",
                decision_type=EditorDecisionType.TRIM_PAUSE,
                transcript_start_word=1,
                transcript_end_word=2,
                source_start_ms=1050,
                source_end_ms=3950,
                original_text="[Silence: content ... Okay.]",
                action="trim",
                concise_reason="Deterministic silence cleanup: 2.9s",
                confidence=1.0,
            ),
            EditorDecision(
                decision_id="dec_filler_01",
                decision_type=EditorDecisionType.FILLER,
                transcript_start_word=2,
                transcript_end_word=2,
                source_start_ms=4050,
                source_end_ms=4300,
                original_text="Okay.",
                action="remove",
                concise_reason="Removed filler word 'Okay.'",
                confidence=0.95,
            ),
            EditorDecision(
                decision_id="silence_cut_002",
                decision_type=EditorDecisionType.TRIM_PAUSE,
                transcript_start_word=2,
                transcript_end_word=3,
                source_start_ms=4400,
                source_end_ms=5800,
                original_text="[Silence: Okay. ... And]",
                action="trim",
                concise_reason="Deterministic silence cleanup: 1.4s",
                confidence=1.0,
            ),
        ],
        overall_confidence=0.96,
    )

    bgm = BackgroundMusicMix(
        style="tech ambient",
        prompt="Ambient synth score",
        model_id="lyria-3-pro-preview",
        music_gcs_object="music/test.wav",
        preview_artifact_id="art_mus_test",
    )

    edl = assemble_edl_from_proposal(
        proposal=proposal,
        transcript=transcript,
        background_music=bgm,
    )

    # All three decisions should merge into 1 contiguous physical cut
    assert len(edl.cuts) == 1
    merged_cut = edl.cuts[0]
    assert merged_cut.decision_type == EditorDecisionType.FILLER
    assert merged_cut.category == "FILLER"
    assert merged_cut.contains_silence is True
    assert merged_cut.contains_semantic_removal is True
    assert "Okay." in (merged_cut.removed_text or "")
    assert "Removed filler word 'Okay.'" in (merged_cut.concise_reason or "")
    assert len(merged_cut.semantic_events) == 3
    assert edl.background_music == bgm

    # Compute report
    report = compute_editorial_quality_report(edl)
    assert report.filler.count == 1
    assert report.filler.duration_ms == merged_cut.removed_duration_ms
    assert report.dead_air.count == 0
    assert report.dead_air.duration_ms == 0
    assert report.semantic_cuts_count == 1
    assert report.silence_only_edit is False
    assert report.semantic_events.filler == 1
    assert report.semantic_events.pause_trim == 2
    assert report.semantic_events.total_events == 3
    assert report.semantic_events.semantic_events_count == 1
