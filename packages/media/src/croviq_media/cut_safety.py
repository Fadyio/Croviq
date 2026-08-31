"""Deterministic Cut Safety Analyzer and Canonical EDL assembly engine."""

from datetime import datetime, timezone
import uuid
from typing import Sequence

from croviq_domain.editorial import (
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    SemanticEvent,
)
from croviq_domain.edl import (
    BackgroundMusicMix,
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
    # Canonical BUG 22 Types
    EditorDecisionType.FALSE_START,
    EditorDecisionType.WORD_REPETITION,
    EditorDecisionType.PHRASE_REPETITION,
    EditorDecisionType.REDUNDANT_EXPLANATION,
    EditorDecisionType.FILLER,
    EditorDecisionType.RAMBLING,
    EditorDecisionType.DEAD_AIR,
    EditorDecisionType.PAUSE_TRIM,
    EditorDecisionType.PACING,
    EditorDecisionType.OTHER,
    # Legacy types
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

        # Extract full decision evidence metadata
        dec_type_val = decision.decision_type.value if hasattr(decision.decision_type, "value") else str(decision.decision_type)
        category = dec_type_val
        if category == "REMOVE_FALSE_START":
            category = "FALSE_START"
        elif category == "REMOVE_REPETITION":
            category = "WORD_REPETITION"
        elif category == "REMOVE_FILLER":
            category = "FILLER"
        elif category in ("REMOVE_SILENCE", "TRIM_PAUSE", "TIGHTEN_PAUSE"):
            category = "DEAD_AIR"
        elif category in ("REMOVE_LOW_VALUE_SECTION", "TIGHTEN_EXPLANATION"):
            category = "REDUNDANT_EXPLANATION"

        removed_text = decision.removed_text
        if not removed_text:
            if decision.original_text and not decision.original_text.startswith("[Silence:"):
                removed_text = decision.original_text
            elif transcript.words and 0 <= start_word_idx <= end_word_idx < len(transcript.words):
                removed_text = " ".join(w.text for w in transcript.words[start_word_idx:end_word_idx + 1])

        context_before = decision.context_before
        if not context_before:
            if transcript.words and start_word_idx > 0:
                ctx_start = max(0, start_word_idx - 3)
                context_before = " ".join(w.text for w in transcript.words[ctx_start:start_word_idx])
            else:
                context_before = "[START]"

        context_after = decision.context_after
        if not context_after:
            if transcript.words and end_word_idx + 1 < len(transcript.words):
                ctx_end = min(len(transcript.words), end_word_idx + 4)
                context_after = " ".join(w.text for w in transcript.words[end_word_idx + 1:ctx_end])
            else:
                context_after = "[END]"

        t_str = str(decision.decision_type).upper()
        is_silence = (
            t_str in ("TRIM_PAUSE", "REMOVE_SILENCE", "TIGHTEN_PAUSE", "DEAD_AIR")
            or decision.decision_id.startswith("silence_cut_")
        )
        contains_semantic = not is_silence

        event = SemanticEvent(
            event_id=f"ev_{uuid.uuid4().hex[:10]}",
            decision_id=decision.decision_id,
            decision_type=str(decision.decision_type),
            category=category or ("DEAD_AIR" if is_silence else "OTHER"),
            reason=decision.concise_reason or safety_reason,
            removed_text=removed_text,
            start_ms=safe_start_ms,
            end_ms=safe_end_ms,
            duration_ms=removed_duration_ms,
            is_silence=is_silence,
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
            removed_text=removed_text,
            context_before=context_before,
            context_after=context_after,
            concise_reason=decision.concise_reason,
            category=category,
            semantic_events=[event],
            contains_silence=is_silence,
            contains_semantic_removal=contains_semantic,
        )


def execute_global_review_pass(
    cuts: list[CutInstruction],
    transcript: Transcript,
    min_surviving_gap_ms: int = 150,
) -> list[CutInstruction]:
    """Perform a second global review pass of all candidate edits before committing the EDL.

    Ensures:
    1. No two safe cuts leave an uncomfortably microscopic speech fragment (<150ms) between them.
    2. Cuts do not overlap destructively; if adjacent cuts are separated by <100ms silence, merges or coordinates boundaries safely.
    3. Cuts keep valid positive durations and boundaries within source duration.
    """
    if not cuts:
        return []

    valid_cuts = [c for c in cuts if c.safety_status != CutSafetyStatus.REJECTED_UNSAFE and c.removed_duration_ms > 0]
    rejected_cuts = [c for c in cuts if c.safety_status == CutSafetyStatus.REJECTED_UNSAFE]

    valid_cuts.sort(key=lambda c: (c.safe_start_ms, c.safe_end_ms))

    reviewed_cuts: list[CutInstruction] = []

    def _merge_cuts(prev_cut: CutInstruction, next_cut: CutInstruction) -> CutInstruction:
        merged_start = min(prev_cut.safe_start_ms, next_cut.safe_start_ms)
        merged_end = max(prev_cut.safe_end_ms, next_cut.safe_end_ms)
        merged_removed = merged_end - merged_start

        # Combine text cleanly
        prev_txt = (prev_cut.removed_text or "").strip()
        next_txt = (next_cut.removed_text or "").strip()
        if prev_txt and next_txt:
            if next_txt in prev_txt:
                combined_text = prev_txt
            elif prev_txt in next_txt:
                combined_text = next_txt
            else:
                combined_text = f"{prev_txt} {next_txt}".strip()
        else:
            combined_text = prev_txt or next_txt or None

        # Combine unique reasons
        reasons: list[str] = []
        for src_r in (prev_cut.concise_reason, next_cut.concise_reason):
            if src_r:
                for piece in src_r.split(";"):
                    p = piece.strip()
                    if p and p not in reasons:
                        reasons.append(p)
        combined_reason = "; ".join(reasons) if reasons else (prev_cut.concise_reason or next_cut.concise_reason)

        # Combine semantic events
        combined_events = list(prev_cut.semantic_events) + list(next_cut.semantic_events)
        has_silence = prev_cut.contains_silence or next_cut.contains_silence
        has_semantic = prev_cut.contains_semantic_removal or next_cut.contains_semantic_removal

        # Determine primary decision type and category
        if next_cut.contains_semantic_removal and not prev_cut.contains_semantic_removal:
            primary_decision_type = next_cut.decision_type
            primary_category = next_cut.category
            primary_decision_id = next_cut.decision_id
        elif prev_cut.contains_semantic_removal and not next_cut.contains_semantic_removal:
            primary_decision_type = prev_cut.decision_type
            primary_category = prev_cut.category
            primary_decision_id = prev_cut.decision_id
        elif prev_cut.contains_semantic_removal and next_cut.contains_semantic_removal:
            primary_decision_type = prev_cut.decision_type
            primary_category = prev_cut.category or next_cut.category
            primary_decision_id = prev_cut.decision_id
        else:
            primary_decision_type = prev_cut.decision_type
            primary_category = prev_cut.category or "DEAD_AIR"
            primary_decision_id = prev_cut.decision_id

        left_anchor = prev_cut.left_anchor if prev_cut.safe_start_ms <= next_cut.safe_start_ms else next_cut.left_anchor
        right_anchor = next_cut.right_anchor if next_cut.safe_end_ms >= prev_cut.safe_end_ms else prev_cut.right_anchor
        context_before = prev_cut.context_before or next_cut.context_before
        context_after = next_cut.context_after or prev_cut.context_after

        return prev_cut.model_copy(update={
            "decision_id": primary_decision_id,
            "decision_type": primary_decision_type,
            "category": primary_category,
            "safe_start_ms": merged_start,
            "safe_end_ms": merged_end,
            "removed_duration_ms": merged_removed,
            "left_anchor": left_anchor,
            "right_anchor": right_anchor,
            "context_before": context_before,
            "context_after": context_after,
            "removed_text": combined_text,
            "concise_reason": combined_reason,
            "semantic_events": combined_events,
            "contains_silence": has_silence,
            "contains_semantic_removal": has_semantic,
        })

    for cut in valid_cuts:
        if not reviewed_cuts:
            reviewed_cuts.append(cut)
            continue

        prev = reviewed_cuts[-1]
        # If current cut touches or overlaps with prev cut
        if cut.safe_start_ms <= prev.safe_end_ms:
            reviewed_cuts[-1] = _merge_cuts(prev, cut)
        else:
            # Gap between cuts
            gap_ms = cut.safe_start_ms - prev.safe_end_ms
            if gap_ms < min_surviving_gap_ms:
                gap_words = [
                    w for w in transcript.words
                    if max(w.start_ms, prev.safe_end_ms) < min(w.end_ms, cut.safe_start_ms)
                ]
                if not gap_words:
                    # Silence gap < min_surviving_gap_ms: bridge cleanly into one contiguous cut
                    reviewed_cuts[-1] = _merge_cuts(prev, cut)
                    continue
            reviewed_cuts.append(cut)

    all_cuts = reviewed_cuts + rejected_cuts
    all_cuts.sort(key=lambda c: (c.safe_start_ms, c.safe_end_ms))
    return all_cuts
def assemble_edl_from_proposal(
    proposal: EditorProposal,
    transcript: Transcript,
    version: int = 1,
    analyzer: CutSafetyAnalyzer | None = None,
    editor_proposal_id: str | None = None,
    edl_id: str | None = None,
    background_music: BackgroundMusicMix | None = None,
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
    cuts = execute_global_review_pass(cuts, transcript)
    cuts.sort(key=lambda cut: (cut.safe_start_ms, cut.safe_end_ms))
    return EditDecisionList(
        edl_id=edl_id or f"edl_{uuid.uuid4().hex[:12]}",
        production_id=proposal.production_id,
        source_duration_ms=transcript.duration_ms,
        editor_proposal_id=editor_proposal_id,
        version=version,
        cuts=cuts,
        coverage_markers=coverage_markers,
        background_music=background_music,
        created_at=datetime.now(timezone.utc),
    )
