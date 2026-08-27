"""Deterministic silence cleanup planning for dead-air removal before semantic editorial passes."""

import logging
from typing import Sequence

from croviq_domain.editorial import (
    EditorDecision,
    EditorDecisionType,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.transcript import SilenceInterval, Transcript, TranscriptWord

logger = logging.getLogger(__name__)

DEFAULT_MIN_SILENCE_DURATION_MS = 1200
DEFAULT_NATURAL_PAUSE_MS = 250


def format_timecode_ms(ms: int) -> str:
    """Format milliseconds into MM:SS.s timecode."""
    total_seconds = max(0, ms) / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:04.1f}"


class SilenceCleanupPlanner:
    """Deterministic, audio-anchored dead-air silence cleanup planner.

    Identifies long pauses (default >= 1200ms) in source media transcripts,
    computes audio-safe non-destructive trim boundaries retaining natural breath pauses (~250ms),
    and formats deterministic baseline EditorDecision records for canonical EDL integration.
    """

    def __init__(
        self,
        min_silence_duration_ms: int = DEFAULT_MIN_SILENCE_DURATION_MS,
        natural_pause_ms: int = DEFAULT_NATURAL_PAUSE_MS,
    ) -> None:
        self.min_silence_duration_ms = min_silence_duration_ms
        self.natural_pause_ms = natural_pause_ms

    def plan_silence_cleanup(
        self,
        transcript: Transcript,
        media_metadata: MediaMetadata | None = None,
    ) -> list[EditorDecision]:
        """Compute deterministic baseline silence trim decisions from transcript silence intervals."""
        if not transcript.silence_intervals:
            return []

        half_pause = self.natural_pause_ms // 2
        post_pause = self.natural_pause_ms - half_pause
        total_duration = media_metadata.duration_ms if media_metadata else transcript.duration_ms

        decisions: list[EditorDecision] = []
        words = transcript.words

        for idx, silence in enumerate(transcript.silence_intervals):
            if silence.duration_ms < self.min_silence_duration_ms:
                continue

            # 1. Protect spoken content: find words overlapping or surrounding this silence
            safe_start = silence.start_ms
            safe_end = silence.end_ms

            # Clamping against any words that start or end before/across the silence boundaries
            for w in words:
                # If word overlaps or touches silence start
                if w.start_ms <= safe_start < w.end_ms or (w.start_ms < safe_end and w.end_ms > safe_start and w.end_ms <= (safe_start + safe_end) // 2):
                    safe_start = max(safe_start, w.end_ms)
                # If word overlaps or touches silence end
                if w.start_ms < safe_end <= w.end_ms or (w.start_ms < safe_end and w.end_ms > safe_start and w.start_ms >= (safe_start + safe_end) // 2):
                    safe_end = min(safe_end, w.start_ms)

            # Re-find canonical preceding and succeeding words after clamping
            prec_words = [w for w in words if w.end_ms <= safe_start]
            succ_words = [w for w in words if w.start_ms >= safe_end]

            prec_word = prec_words[-1] if prec_words else None
            succ_word = succ_words[0] if succ_words else None

            if prec_word:
                safe_start = max(safe_start, prec_word.end_ms)
            if succ_word:
                safe_end = min(safe_end, succ_word.start_ms)

            # Ensure no inner words are inside [safe_start, safe_end]
            inner_words = [w for w in words if safe_start < w.end_ms and w.start_ms < safe_end]
            if inner_words:
                continue

            # Re-check remaining silence duration after word-protection clamping
            if safe_end - safe_start < self.min_silence_duration_ms:
                continue
            # 2. Retain comfortable natural breath pause
            cut_start = safe_start + half_pause
            cut_end = safe_end - post_pause
            removed_duration = cut_end - cut_start

            if removed_duration <= 0:
                continue

            # 3. Anchor to canonical transcript word boundaries
            start_word_idx = prec_word.index if prec_word else 0
            end_word_idx = succ_word.index if succ_word else (len(words) - 1 if words else 0)

            left_anchor = prec_word.text if prec_word else "START"
            right_anchor = succ_word.text if succ_word else "END"

            decision_id = f"silence_cut_{len(decisions) + 1:03d}"
            decision = EditorDecision(
                decision_id=decision_id,
                decision_type=EditorDecisionType.TRIM_PAUSE,
                action="trim",
                transcript_start_word=start_word_idx,
                transcript_end_word=end_word_idx,
                source_start_ms=cut_start,
                source_end_ms=cut_end,
                original_text=f"[Silence: {left_anchor} ... {right_anchor}]",
                concise_reason=(
                    f"Deterministic silence cleanup: trimmed {removed_duration / 1000.0:.2f}s "
                    f"dead air (retained {self.natural_pause_ms}ms natural pause)."
                ),
                preserve_context=f"Retained {self.natural_pause_ms}ms comfortable pause padding.",
                confidence=1.0,
            )
            decisions.append(decision)

        return decisions


def format_silence_plan_for_prompt(silence_decisions: Sequence[EditorDecision]) -> str:
    """Format deterministic silence cleanup decisions into a concise agent prompt context section."""
    if not silence_decisions:
        return "Deterministic Silence Cleanup: No long dead-air pauses detected (>=1.2s)."

    lines = [
        "Deterministic Silence Cleanup Plan (Already Scheduled):",
        "The following long dead-air pauses are already scheduled for automatic cleanup.",
        "Do NOT waste editorial decisions rediscovering these obvious pauses:",
    ]
    for d in silence_decisions:
        start_tc = format_timecode_ms(d.source_start_ms)
        end_tc = format_timecode_ms(d.source_end_ms)
        dur_s = (d.source_end_ms - d.source_start_ms) / 1000.0
        lines.append(f"- {start_tc} -> {end_tc} ({dur_s:.2f}s dead air trimmed)")

    return "\n".join(lines)
