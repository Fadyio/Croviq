"""Deterministic Cut Safety Analyzer and Canonical EDL assembly engine."""

from datetime import datetime, timezone
import uuid
from typing import Sequence

from croviq_domain.editorial import (
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
)
from croviq_domain.edl import (
    CoverageMarker,
    CoverageType,
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
)
from croviq_domain.transcript import Transcript


# Canonical safety parameters
MAX_BOUNDARY_ADJUSTMENT_MS = 100
DEFAULT_TRANSITION_MS = 20
MIN_CUT_DURATION_MS = 120
DEFAULT_NATURAL_PAUSE_BREATH_MS = 200

DESTRUCTIVE_DECISION_TYPES = frozenset({
    EditorDecisionType.REMOVE_SILENCE,
    EditorDecisionType.REMOVE_FILLER,
    EditorDecisionType.REMOVE_FALSE_START,
    EditorDecisionType.REMOVE_REPETITION,
    EditorDecisionType.TRIM_PAUSE,
    EditorDecisionType.TIGHTEN_PAUSE,
    EditorDecisionType.TIGHTEN_EXPLANATION,
    EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
})


class CutSafetyAnalyzer:
    """Deterministic, audio-safe cut boundary analyzer.

    Evaluates proposed editorial decisions against canonical transcript word anchors,
    inter-word silence intervals, and visual context without calling external AI models.
    """

    def __init__(
        self,
        max_boundary_adjustment_ms: int = MAX_BOUNDARY_ADJUSTMENT_MS,
        default_transition_ms: int = DEFAULT_TRANSITION_MS,
        natural_pause_breath_ms: int = DEFAULT_NATURAL_PAUSE_BREATH_MS,
        min_cut_duration_ms: int = MIN_CUT_DURATION_MS,
    ) -> None:
        self.max_boundary_adjustment_ms = max_boundary_adjustment_ms
        self.default_transition_ms = default_transition_ms
        self.natural_pause_breath_ms = natural_pause_breath_ms
        self.min_cut_duration_ms = min_cut_duration_ms

    def analyze_cut(
        self,
        decision: EditorDecision,
        transcript: Transcript,
        protected_decisions: Sequence[EditorDecision] | None = None,
    ) -> CutInstruction:
        """Evaluate one proposal decision against transcript word boundaries and speech padding."""
        cut_id = f"cut_{uuid.uuid4().hex[:12]}"


        # 2. Check destructive action applicability
        if decision.decision_type not in DESTRUCTIVE_DECISION_TYPES:
            return CutInstruction(
                cut_id=cut_id,
                decision_id=decision.decision_id,
                decision_type=decision.decision_type,
                transcript_start_word=decision.transcript_start_word,
                transcript_end_word=decision.transcript_end_word,
                requested_start_ms=decision.source_start_ms,
                requested_end_ms=decision.source_end_ms,
                safe_start_ms=decision.source_start_ms,
                safe_end_ms=decision.source_end_ms,
                removed_duration_ms=0,
                left_anchor="[NON_DESTRUCTIVE]",
                right_anchor="[NON_DESTRUCTIVE]",
                transition_ms=self.default_transition_ms,
                safety_status=CutSafetyStatus.REJECTED_UNSAFE,
                safety_reason=f"Decision type {decision.decision_type} does not represent an executable media removal.",
                confidence=decision.confidence,
            )

        start_word_idx = decision.transcript_start_word
        end_word_idx = decision.transcript_end_word

        # 4. Validate word indexes
        if not transcript.words:
            return CutInstruction(
                cut_id=cut_id,
                decision_id=decision.decision_id,
                decision_type=decision.decision_type,
                transcript_start_word=start_word_idx,
                transcript_end_word=end_word_idx,
                requested_start_ms=decision.source_start_ms,
                requested_end_ms=decision.source_end_ms,
                safe_start_ms=decision.source_start_ms,
                safe_end_ms=decision.source_end_ms,
                removed_duration_ms=0,
                left_anchor="[EMPTY]",
                right_anchor="[EMPTY]",
                transition_ms=self.default_transition_ms,
                safety_status=CutSafetyStatus.REJECTED_UNSAFE,
                safety_reason="Transcript contains no word alignment data.",
                confidence=0.0,
            )

        if start_word_idx < 0 or end_word_idx < start_word_idx or end_word_idx >= len(transcript.words):
            return CutInstruction(
                cut_id=cut_id,
                decision_id=decision.decision_id,
                decision_type=decision.decision_type,
                transcript_start_word=max(0, min(start_word_idx, len(transcript.words) - 1)),
                transcript_end_word=max(0, min(end_word_idx, len(transcript.words) - 1)),
                requested_start_ms=decision.source_start_ms,
                requested_end_ms=decision.source_end_ms,
                safe_start_ms=decision.source_start_ms,
                safe_end_ms=decision.source_end_ms,
                removed_duration_ms=0,
                left_anchor="[INVALID_INDEX]",
                right_anchor="[INVALID_INDEX]",
                transition_ms=self.default_transition_ms,
                safety_status=CutSafetyStatus.REJECTED_UNSAFE,
                safety_reason=f"Invalid transcript word index range [{start_word_idx}, {end_word_idx}] for transcript with {len(transcript.words)} words.",
                confidence=decision.confidence,
            )

        # 5. Extract canonical word timing anchors
        start_word = transcript.words[start_word_idx]
        end_word = transcript.words[end_word_idx]

        req_start_ms = start_word.start_ms
        req_end_ms = end_word.end_ms

        if decision.decision_type in (EditorDecisionType.TRIM_PAUSE, EditorDecisionType.REMOVE_SILENCE, EditorDecisionType.TIGHTEN_PAUSE) and decision.original_text.startswith("[Silence:"):
            left_anchor = start_word.text
            right_anchor = end_word.text
        else:
            left_anchor = transcript.words[start_word_idx - 1].text if start_word_idx > 0 else "[START]"
            right_anchor = transcript.words[end_word_idx + 1].text if end_word_idx + 1 < len(transcript.words) else "[END]"

        # Validate bounds against canonical transcript duration.
        if req_start_ms >= transcript.duration_ms or req_end_ms > transcript.duration_ms:
            return CutInstruction(
                cut_id=cut_id,
                decision_id=decision.decision_id,
                decision_type=decision.decision_type,
                transcript_start_word=start_word_idx,
                transcript_end_word=end_word_idx,
                requested_start_ms=req_start_ms,
                requested_end_ms=req_end_ms,
                safe_start_ms=req_start_ms,
                safe_end_ms=req_end_ms,
                removed_duration_ms=0,
                left_anchor=left_anchor,
                right_anchor=right_anchor,
                transition_ms=self.default_transition_ms,
                safety_status=CutSafetyStatus.REJECTED_UNSAFE,
                safety_reason=f"Cut timestamps [{req_start_ms}, {req_end_ms}] exceed transcript duration {transcript.duration_ms} ms.",
                confidence=decision.confidence,
            )

        # 7. Check Protected Decisions overlap (e.g. KEEP_FOR_CLARITY)
        if protected_decisions:
            for prot in protected_decisions:
                if prot.decision_type in (EditorDecisionType.KEEP_FOR_CLARITY, EditorDecisionType.KEEP):
                    prot_start = prot.transcript_start_word
                    prot_end = prot.transcript_end_word
                    if not (end_word_idx < prot_start or start_word_idx > prot_end):
                        return CutInstruction(
                            cut_id=cut_id,
                            decision_id=decision.decision_id,
                            decision_type=decision.decision_type,
                            transcript_start_word=start_word_idx,
                            transcript_end_word=end_word_idx,
                            requested_start_ms=req_start_ms,
                            requested_end_ms=req_end_ms,
                            safe_start_ms=req_start_ms,
                            safe_end_ms=req_end_ms,
                            removed_duration_ms=0,
                            left_anchor=left_anchor,
                            right_anchor=right_anchor,
                            transition_ms=self.default_transition_ms,
                            safety_status=CutSafetyStatus.REJECTED_UNSAFE,
                            safety_reason=f"Cut overlaps protected {prot.decision_type} decision '{prot.decision_id}'.",
                            confidence=decision.confidence,
                        )

        # 8. Boundary Snapping & Safety Assessment
        if decision.decision_type in (EditorDecisionType.TRIM_PAUSE, EditorDecisionType.REMOVE_SILENCE, EditorDecisionType.TIGHTEN_PAUSE) and (decision.decision_id.startswith("silence_cut_") or decision.original_text.startswith("[Silence:")):
            # Special case for pause trimming: deterministic silence cleanup already retains natural pause padding
            safe_start_ms = decision.source_start_ms
            safe_end_ms = decision.source_end_ms
            safety_status = CutSafetyStatus.SAFE
            safety_reason = "Natural pause trimming leaving comfortable breath padding."
        elif decision.decision_type in (EditorDecisionType.TRIM_PAUSE, EditorDecisionType.REMOVE_SILENCE, EditorDecisionType.TIGHTEN_PAUSE) and decision.transcript_start_word == decision.transcript_end_word and (decision.source_end_ms - decision.source_start_ms > self.natural_pause_breath_ms * 2):
            raw_start = decision.source_start_ms
            raw_end = decision.source_end_ms
            pause_duration = raw_end - raw_start
            safe_start_ms = raw_start + self.natural_pause_breath_ms
            safe_end_ms = raw_end - self.natural_pause_breath_ms
            safety_status = CutSafetyStatus.SAFE
            safety_reason = "Natural pause trimming leaving comfortable breath padding."
        else:
            # Left boundary calculation
            left_gap = 0
            if start_word_idx == 0:
                safe_start_ms = 0
                left_gap = req_start_ms
            else:
                prev_word = transcript.words[start_word_idx - 1]
                left_gap = start_word.start_ms - prev_word.end_ms
                if left_gap > 0:
                    adjustment = min(self.max_boundary_adjustment_ms, left_gap)
                    safe_start_ms = max(0, start_word.start_ms - adjustment)
                else:
                    safe_start_ms = start_word.start_ms

            # Right boundary calculation
            right_gap = 0
            if end_word_idx + 1 >= len(transcript.words):
                right_gap = max(0, transcript.duration_ms - end_word.end_ms)
                adjustment = min(self.max_boundary_adjustment_ms, right_gap)
                safe_end_ms = min(transcript.duration_ms, end_word.end_ms + adjustment)
            else:
                next_word = transcript.words[end_word_idx + 1]
                right_gap = next_word.start_ms - end_word.end_ms
                if right_gap > 0:
                    adjustment = min(self.max_boundary_adjustment_ms, right_gap)
                    safe_end_ms = min(next_word.start_ms, end_word.end_ms + adjustment)
                else:
                    safe_end_ms = end_word.end_ms

            # Co-articulation check: zero gap on both sides
            if start_word_idx > 0 and (end_word_idx + 1 < len(transcript.words)):
                if left_gap <= 0 and right_gap <= 0:
                    return CutInstruction(
                        cut_id=cut_id,
                        decision_id=decision.decision_id,
                        decision_type=decision.decision_type,
                        transcript_start_word=start_word_idx,
                        transcript_end_word=end_word_idx,
                        requested_start_ms=req_start_ms,
                        requested_end_ms=req_end_ms,
                        safe_start_ms=req_start_ms,
                        safe_end_ms=req_end_ms,
                        removed_duration_ms=0,
                        left_anchor=left_anchor,
                        right_anchor=right_anchor,
                        transition_ms=self.default_transition_ms,
                        safety_status=CutSafetyStatus.REJECTED_UNSAFE,
                        safety_reason="Tightly joined words with zero inter-word silence gap and severe co-articulation risk.",
                        confidence=decision.confidence,
                    )

            # Visual discontinuity / Jump cut analysis
            vis_ctx = (decision.visual_context or "").lower()
            if (
                ("talking head" in vis_ctx or "presenter" in vis_ctx or "on camera" in vis_ctx)
                and "screen" not in vis_ctx
                and "demo" not in vis_ctx
                and "terminal" not in vis_ctx
                and "b-roll" not in vis_ctx
            ):
                safety_status = CutSafetyStatus.NEEDS_COVERAGE
                safety_reason = "Audio join is safe, but visual context indicates talking-head jump cut requiring coverage."
            else:
                safety_status = CutSafetyStatus.SAFE
                safety_reason = "Clean inter-word silence boundaries verified."

        safe_start_ms = max(0, min(safe_start_ms, transcript.duration_ms))
        safe_end_ms = max(safe_start_ms, min(safe_end_ms, transcript.duration_ms))
        removed_duration_ms = safe_end_ms - safe_start_ms
        if removed_duration_ms < self.min_cut_duration_ms:
            safety_status = CutSafetyStatus.REJECTED_UNSAFE
            safety_reason = (
                f"Cut duration {removed_duration_ms} ms is below the deterministic "
                f"minimum of {self.min_cut_duration_ms} ms."
            )

        return CutInstruction(
            cut_id=cut_id,
            decision_id=decision.decision_id,
            decision_type=decision.decision_type,
            transcript_start_word=start_word_idx,
            transcript_end_word=end_word_idx,
            requested_start_ms=req_start_ms,
            requested_end_ms=req_end_ms,
            safe_start_ms=safe_start_ms,
            safe_end_ms=safe_end_ms,
            removed_duration_ms=removed_duration_ms,
            left_anchor=left_anchor,
            right_anchor=right_anchor,
            transition_ms=self.default_transition_ms,
            safety_status=safety_status,
            safety_reason=safety_reason,
            confidence=decision.confidence,
        )

    def extract_coverage_marker(
        self,
        decision: EditorDecision,
    ) -> CoverageMarker | None:
        """Extract a visual coverage marker for B-roll insert footage."""
        if decision.decision_type in (
            EditorDecisionType.BROLL_COVER_CANDIDATE,
            EditorDecisionType.BROLL_COVER,
        ):
            return CoverageMarker(
                marker_id=f"cov_{uuid.uuid4().hex[:12]}",
                decision_id=decision.decision_id,
                source_start_ms=decision.source_start_ms,
                source_end_ms=decision.source_end_ms,
                coverage_type=CoverageType.BROLL_CANDIDATE,
                reason=decision.concise_reason,
            )

        return None


def assemble_edl_from_proposal(
    proposal: EditorProposal,
    transcript: Transcript,
    version: int = 1,
    analyzer: CutSafetyAnalyzer | None = None,
    editor_proposal_id: str | None = None,
    edl_id: str | None = None,
) -> EditDecisionList:
    """Assemble a canonical EDL directly from Leo's proposal using deterministic safety rules."""
    if analyzer is None:
        analyzer = CutSafetyAnalyzer()

    protected_decisions = [
        decision
        for decision in proposal.decisions
        if decision.decision_type in (EditorDecisionType.KEEP, EditorDecisionType.KEEP_FOR_CLARITY)
    ]

    cuts: list[CutInstruction] = []
    coverage_markers: list[CoverageMarker] = []

    for decision in proposal.decisions:
        marker = analyzer.extract_coverage_marker(decision)
        if marker is not None:
            coverage_markers.append(marker)

        if decision.decision_type in DESTRUCTIVE_DECISION_TYPES:
            cut = analyzer.analyze_cut(
                decision=decision,
                transcript=transcript,
                protected_decisions=protected_decisions,
            )
            if cut.safety_status == CutSafetyStatus.NEEDS_COVERAGE:
                coverage_marker = CoverageMarker(
                    marker_id=f"cov_{uuid.uuid4().hex[:12]}",
                    decision_id=decision.decision_id,
                    source_start_ms=cut.safe_start_ms,
                    source_end_ms=cut.safe_end_ms,
                    coverage_type=CoverageType.SOURCE_SCREEN,
                    reason=f"Cover jump cut: {cut.safety_reason}",
                )
                coverage_markers.append(coverage_marker)
                cut.coverage_marker_id = coverage_marker.marker_id

            cuts.append(cut)

    cuts.sort(key=lambda cut: (cut.safe_start_ms, cut.safe_end_ms))

    return EditDecisionList(
        edl_id=edl_id or f"edl_{uuid.uuid4().hex[:12]}",
        production_id=proposal.production_id,
        source_duration_ms=transcript.duration_ms,
        editor_proposal_id=editor_proposal_id,
        version=version,
        cuts=cuts,
        coverage_markers=coverage_markers,
        created_at=datetime.now(timezone.utc),
    )
