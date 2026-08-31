"""Canonical Edit Decision List (EDL) domain models for deterministic media rendering."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Sequence
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from croviq_domain.editorial import (
    EditorialCategoryBreakdown,
    EditorialQualityReport,
    EditorDecisionType,
    EditorVoiceMode,
    SemanticEvent,
    SemanticEventBreakdown,
)
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.validators import validate_timezone_aware


class CutSafetyStatus(StrEnum):
    """Deterministic safety classification for proposed cuts."""

    SAFE = "SAFE"
    NEEDS_COVERAGE = "NEEDS_COVERAGE"
    REJECTED_UNSAFE = "REJECTED_UNSAFE"


class CoverageType(StrEnum):
    """Visual coverage types supported for jump-cut mitigation."""

    SOURCE_SCREEN = "SOURCE_SCREEN"

class CoverageMarker(BaseModel):
    """Visual coverage metadata identifying footage insertion candidates."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    marker_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the coverage marker",
    )
    decision_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="ID of the related editorial decision",
    )
    source_start_ms: int = Field(
        ...,
        ge=0,
        description="Start timestamp in source video milliseconds",
    )
    source_end_ms: int = Field(
        ...,
        ge=0,
        description="End timestamp in source video milliseconds",
    )
    coverage_type: CoverageType | str = Field(
        default=CoverageType.SOURCE_SCREEN,
        description="Coverage category (e.g. SOURCE_SCREEN)",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Editorial justification for the visual coverage",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "CoverageMarker":
        if self.source_end_ms <= self.source_start_ms:
            raise ValueError(
                f"source_end_ms ({self.source_end_ms}) must be greater than source_start_ms ({self.source_start_ms})"
            )
        return self


class VoiceoverSegment(BaseModel):
    """Persisted narration replacement placed on the source timeline."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    segment_id: str = Field(..., min_length=1, max_length=64)
    source_start_ms: int = Field(..., ge=0)
    source_end_ms: int = Field(..., ge=0)
    text: str = Field(..., min_length=1, max_length=10_000)
    original_text: str | None = Field(default=None, max_length=10_000)
    voice_mode: EditorVoiceMode = Field(default=EditorVoiceMode.PREBUILT_STUDIO_VOICE)
    voice_id: str | None = Field(default=None, max_length=64)
    generated_duration_ms: int | None = Field(default=None, ge=0)
    preview_artifact_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_bounds(self) -> "VoiceoverSegment":
        if self.source_end_ms <= self.source_start_ms:
            raise ValueError("Voiceover source_end_ms must be greater than source_start_ms")
        return self


class BackgroundMusicMix(BaseModel):
    """Canonical background music selection and speech-ducking parameters."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    style: str = Field(..., min_length=1, max_length=120)
    model_id: str = Field(default="lyria-3-pro-preview", max_length=64)
    prompt: str | None = Field(default=None, max_length=1000)
    duration_ms: int | None = Field(default=None, ge=0)
    volume_db: float = Field(default=-24.0, le=0)
    ducking_db: float = Field(default=-14.0, le=0)
    target_lufs: float = Field(default=-32.0, ge=-45.0, le=-8.0)
    music_gcs_object: str = Field(..., min_length=1)
    preview_artifact_id: str | None = Field(default=None, max_length=64)
    is_muted: bool = Field(default=False)

class CutInstruction(BaseModel):
    """Deterministic, audio-safe cut instruction ready for FFmpeg render execution."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    cut_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the cut instruction",
    )
    decision_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Originating Editor decision identifier",
    )
    decision_type: EditorDecisionType = Field(
        ...,
        description="Semantic decision type (e.g. REMOVE_FILLER, REMOVE_FALSE_START, etc.)",
    )
    transcript_start_word: int = Field(
        ...,
        ge=0,
        description="0-indexed start word boundary in canonical transcript",
    )
    transcript_end_word: int = Field(
        ...,
        ge=0,
        description="0-indexed end word boundary in canonical transcript",
    )
    requested_start_ms: int = Field(
        ...,
        ge=0,
        description="Raw requested start timestamp from word anchor in ms",
    )
    requested_end_ms: int = Field(
        ...,
        ge=0,
        description="Raw requested end timestamp from word anchor in ms",
    )
    safe_start_ms: int = Field(
        ...,
        ge=0,
        description="Deterministic cut start timestamp snapped to inter-word silence in ms",
    )
    safe_end_ms: int = Field(
        ...,
        ge=0,
        description="Deterministic cut end timestamp snapped to inter-word silence in ms",
    )
    removed_duration_ms: int = Field(
        default=0,
        ge=0,
        description="Total duration removed by this cut in milliseconds",
    )
    left_anchor: str = Field(
        ...,
        description="Spoken word or marker immediately preceding the cut boundary",
    )
    right_anchor: str = Field(
        ...,
        description="Spoken word or marker immediately following the cut boundary",
    )
    transition_ms: int = Field(
        default=20,
        ge=0,
        le=200,
        description="Micro-crossfade transition duration in milliseconds (canonical 20ms)",
    )
    safety_status: CutSafetyStatus = Field(
        ...,
        description="Cut safety classification: SAFE, NEEDS_COVERAGE, or REJECTED_UNSAFE",
    )
    safety_reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Deterministic explanation for safety status determination",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this cut instruction",
    )
    coverage_marker_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional associated coverage marker ID when visual cut needs covering",
    )
    requires_room_tone: bool = Field(
        default=False,
        description="Whether a room-tone bridge is recommended across the join",
    )
    removed_text: str | None = Field(
        default=None,
        description="Exact spoken transcript text removed by this cut",
    )
    context_before: str | None = Field(
        default=None,
        description="Retained spoken context immediately preceding the cut",
    )
    context_after: str | None = Field(
        default=None,
        description="Retained spoken context immediately following the cut",
    )
    concise_reason: str | None = Field(
        default=None,
        description="Editorial rationale explaining why this cut was made",
    )
    category: str | None = Field(
        default=None,
        description="Canonical category name (e.g. FALSE_START, WORD_REPETITION)",
    )
    semantic_events: list[SemanticEvent] = Field(
        default_factory=list,
        description="All individual semantic decisions / events represented inside this physical cut",
    )
    contains_silence: bool = Field(
        default=False,
        description="Whether this physical cut removes dead air / silence",
    )
    contains_semantic_removal: bool = Field(
        default=False,
        description="Whether this physical cut removes semantic speech",
    )
    @model_validator(mode="after")
    def validate_cut_bounds(self) -> "CutInstruction":
        if self.transcript_end_word < self.transcript_start_word:
            raise ValueError(
                f"transcript_end_word ({self.transcript_end_word}) must be >= transcript_start_word ({self.transcript_start_word})"
            )
        if self.requested_end_ms < self.requested_start_ms:
            raise ValueError(
                f"requested_end_ms ({self.requested_end_ms}) must be >= requested_start_ms ({self.requested_start_ms})"
            )
        if self.safe_end_ms < self.safe_start_ms:
            raise ValueError(
                f"safe_end_ms ({self.safe_end_ms}) must be >= safe_start_ms ({self.safe_start_ms})"
            )
        if self.removed_duration_ms == 0:
            self.removed_duration_ms = self.safe_end_ms - self.safe_start_ms
        return self


class EditDecisionList(BaseModel):
    """Canonical, vendor-neutral Edit Decision List (EDL) schema."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    edl_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the Edit Decision List",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Associated Production entity identifier",
    )
    source_duration_ms: int = Field(
        ...,
        gt=0,
        description="Total duration of the source media in milliseconds",
    )
    editor_proposal_id: str | None = Field(
        default=None,
        max_length=64,
        description="Reference to the originating EditorProposal",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Monotonically increasing version number for this production's EDL",
    )
    cuts: list[CutInstruction] = Field(
        default_factory=list,
        description="Ordered list of deterministic cut instructions",
    )
    coverage_markers: list[CoverageMarker] = Field(
        default_factory=list,
        description="Visual coverage markers for screen recordings",
    )
    voiceover_segments: list[VoiceoverSegment] = Field(
        default_factory=list,
        description="Persisted generated narration segments mixed into the preview",
    )
    background_music: BackgroundMusicMix | None = Field(
        default=None,
        description="Active persisted background music mix, if any",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the EDL was generated (UTC)",
    )

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)

    @property
    def active_cuts(self) -> list[CutInstruction]:
        """Return cuts that are executable (SAFE or NEEDS_COVERAGE)."""
        return [
            c for c in self.cuts
            if c.safety_status in (CutSafetyStatus.SAFE, CutSafetyStatus.NEEDS_COVERAGE)
        ]

    @property
    def active_cuts_count(self) -> int:
        """Count of executable cuts."""
        return len(self.active_cuts)

    @property
    def total_removed_duration_ms(self) -> int:
        """Total duration in milliseconds removed by active cuts (merging overlaps)."""
        return max(0, self.source_duration_ms - self.estimated_target_duration_ms)

    @property
    def estimated_target_duration_ms(self) -> int:
        """Estimated final video duration after active cuts derived from merged keep segments."""
        keep_segments = derive_keep_segments(self)
        return sum(end - start for start, end in keep_segments)


class EdlRevisionHistoryEntry(BaseModel):
    """Persisted snapshot and provenance entry for an EDL mutation enabling durable undo."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    history_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the revision history entry",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Associated Production entity identifier",
    )
    previous_edl_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="EDL ID before mutation",
    )
    previous_version: int = Field(
        ...,
        ge=1,
        description="EDL version before mutation",
    )
    new_edl_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="EDL ID after mutation",
    )
    new_version: int = Field(
        ...,
        ge=1,
        description="EDL version after mutation",
    )
    tool_name: str = Field(
        ...,
        description="Name of tool that triggered mutation: remove_selection, tighten_selection, etc.",
    )
    user_request: str | None = Field(
        default=None,
        description="User request or prompt that triggered this mutation",
    )
    requested_range_ms: list[int] | None = Field(
        default=None,
        description="Requested start and end offsets in milliseconds",
    )
    applied_range_ms: list[int] | None = Field(
        default=None,
        description="Actual applied start and end offsets in milliseconds",
    )
    previous_edl: EditDecisionList = Field(
        ...,
        description="Complete snapshot of the previous EDL state for deterministic undo",
    )
    previous_proposal: dict[str, Any] | None = Field(
        default=None,
        description="Snapshot of previous proposal decisions for deterministic undo",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when mutation was recorded in UTC",
    )

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class EdlMutationResult(BaseModel):
    """Canonical representation of an EDL mutation attempt with overlap and duration truth."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    tool_name: str = Field(
        ...,
        description="Name of tool that triggered mutation: tighten_selection, remove_selection, etc.",
    )
    requested_range_ms: list[int] = Field(
        default_factory=list,
        description="Source range requested by user [start_ms, end_ms]",
    )
    proposed_cuts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Candidate cut intervals proposed during mutation inspection",
    )
    applied_cuts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Cuts successfully applied to the EDL",
    )
    skipped_existing_cuts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Proposed cuts skipped due to existing overlap or subsumption",
    )
    effective_removed_ms: int = Field(
        default=0,
        ge=0,
        description="Net effective video duration removed by this mutation in ms",
    )
    before_duration_ms: int = Field(
        default=0,
        ge=0,
        description="Target edited duration before mutation in ms",
    )
    after_duration_ms: int = Field(
        default=0,
        ge=0,
        description="Target edited duration after mutation in ms",
    )
    changed: bool = Field(
        default=False,
        description="Whether the EDL actually changed in effective duration or canonical structure",
    )
    message: str = Field(
        default="",
        description="Truthful user-facing explanation of the mutation result",
    )
    reason: str | None = Field(
        default=None,
        description="Concise reason for no-change or applied edits",
    )


def compute_interval_union(intervals: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Compute the deterministic sorted union of non-empty intervals (merging overlaps and adjacent spans)."""
    valid = [
        (int(start), int(end))
        for start, end in intervals
        if end > start and start >= 0
    ]
    if not valid:
        return []
    valid.sort(key=lambda item: (item[0], item[1]))
    merged: list[tuple[int, int]] = [valid[0]]
    for start, end in valid[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def compute_intervals_duration(intervals: Sequence[tuple[int, int]]) -> int:
    """Compute the total effective non-overlapping duration represented by a set of intervals."""
    merged = compute_interval_union(intervals)
    return sum(end - start for start, end in merged)


def classify_cut_overlap(
    proposed: tuple[int, int],
    existing_intervals: Sequence[tuple[int, int]],
) -> tuple[str, int, int]:
    """Classify a proposed cut interval against existing cut intervals using interval-union math.

    Returns (classification, newly_effective_ms, overlapping_ms) where classification is one of:
    - 'NEW': completely disjoint from existing cuts (newly_effective_ms == proposed_duration)
    - 'PARTIALLY_OVERLAPPING': partially covered by existing cuts (0 < newly_effective_ms < proposed_duration)
    - 'FULLY_SUBSUMED': completely contained within existing cuts (newly_effective_ms == 0)
    - 'DUPLICATE': exactly matches an existing cut interval (newly_effective_ms == 0)
    """
    p_start, p_end = int(proposed[0]), int(proposed[1])
    if p_end <= p_start:
        return ("FULLY_SUBSUMED", 0, 0)

    proposed_dur = p_end - p_start
    existing_union = compute_interval_union(existing_intervals)

    overlapping_ms = 0
    for ex_start, ex_end in existing_union:
        overlap_s = max(p_start, ex_start)
        overlap_e = min(p_end, ex_end)
        if overlap_e > overlap_s:
            overlapping_ms += (overlap_e - overlap_s)

    newly_effective_ms = max(0, proposed_dur - overlapping_ms)

    if newly_effective_ms == 0:
        is_exact = any(
            ex_s == p_start and ex_e == p_end
            for ex_s, ex_e in existing_union
        ) or any(
            int(ex_s) == p_start and int(ex_e) == p_end
            for ex_s, ex_e in existing_intervals
        )
        classification = "DUPLICATE" if is_exact else "FULLY_SUBSUMED"
    elif overlapping_ms == 0:
        classification = "NEW"
    else:
        classification = "PARTIALLY_OVERLAPPING"

    return (classification, newly_effective_ms, overlapping_ms)


def audit_proposed_cuts(
    proposed_cuts: Sequence[tuple[int, int]],
    existing_cuts: Sequence[CutInstruction | tuple[int, int]],
) -> dict[str, Any]:
    """Audit a set of proposed cuts against existing active cuts using interval-union math."""
    existing_intervals: list[tuple[int, int]] = []
    for c in existing_cuts:
        if isinstance(c, tuple):
            existing_intervals.append(c)
        elif hasattr(c, "safe_start_ms") and hasattr(c, "safe_end_ms"):
            existing_intervals.append((c.safe_start_ms, c.safe_end_ms))
        elif hasattr(c, "requested_start_ms") and hasattr(c, "requested_end_ms"):
            existing_intervals.append((c.requested_start_ms, c.requested_end_ms))

    existing_union = compute_interval_union(existing_intervals)
    combined_union = compute_interval_union([*existing_intervals, *proposed_cuts])

    before_removed_ms = compute_intervals_duration(existing_union)
    after_removed_ms = compute_intervals_duration(combined_union)
    effective_removed_ms = max(0, after_removed_ms - before_removed_ms)

    proposed_raw_ms = sum(max(0, int(e) - int(s)) for s, e in proposed_cuts if int(e) > int(s))

    cut_audits: list[dict[str, Any]] = []
    for p in proposed_cuts:
        p_tuple = (int(p[0]), int(p[1]))
        classification, newly_eff, overlap = classify_cut_overlap(p_tuple, existing_union)
        cut_audits.append({
            "cut_range": [p_tuple[0], p_tuple[1]],
            "raw_duration_ms": max(0, p_tuple[1] - p_tuple[0]),
            "classification": classification,
            "newly_effective_ms": newly_eff,
            "overlapping_ms": overlap,
        })

    return {
        "proposed_total_raw_ms": proposed_raw_ms,
        "effective_removed_ms": effective_removed_ms,
        "already_removed_ms": max(0, proposed_raw_ms - effective_removed_ms),
        "cut_audits": cut_audits,
        "has_effective_change": effective_removed_ms > 0,
    }

def derive_keep_segments(edl: EditDecisionList) -> list[tuple[int, int]]:
    """Deterministically derive the contiguous source media segments to KEEP for master rendering.

    Consumes the source_duration_ms minus all active cuts (SAFE or NEEDS_COVERAGE),
    producing an ordered list of non-empty (start_ms, end_ms) intervals.
    """
    active_cuts = sorted(edl.active_cuts, key=lambda c: c.safe_start_ms)
    if not active_cuts:
        return [(0, edl.source_duration_ms)]

    segments: list[tuple[int, int]] = []
    current_pos = 0

    for cut in active_cuts:
        cut_start = max(0, min(cut.safe_start_ms, edl.source_duration_ms))
        cut_end = max(0, min(cut.safe_end_ms, edl.source_duration_ms))

        if cut_start > current_pos:
            segments.append((current_pos, cut_start))

        current_pos = max(current_pos, cut_end)

    if current_pos < edl.source_duration_ms:
        segments.append((current_pos, edl.source_duration_ms))
    return segments if segments else [(0, edl.source_duration_ms)]


def map_source_time_to_edited(
    source_ms: int,
    edl_or_keep_segments: EditDecisionList | list[tuple[int, int]],
) -> int:
    """Map a timestamp on the source video timeline into the edited master video timeline.

    Subtracts cut durations preceding source_ms, pinning time inside cuts to the start
    of the cut / adjacent keep boundary.
    """
    if source_ms <= 0:
        return 0

    if isinstance(edl_or_keep_segments, EditDecisionList):
        keep_segments = derive_keep_segments(edl_or_keep_segments)
    else:
        keep_segments = edl_or_keep_segments

    accumulated_ms = 0
    for seg_start, seg_end in keep_segments:
        if source_ms < seg_start:
            return accumulated_ms
        if seg_start <= source_ms <= seg_end:
            return accumulated_ms + (source_ms - seg_start)
        accumulated_ms += (seg_end - seg_start)

    return accumulated_ms


def derive_edited_transcript(
    transcript: Transcript,
    edl: EditDecisionList,
) -> Transcript:
    """Derive an edited transcript aligned strictly to the rendered video timeline."""
    active_cuts = sorted(edl.active_cuts, key=lambda c: c.safe_start_ms)
    keep_segments = derive_keep_segments(edl)
    target_duration_ms = sum(end - start for start, end in keep_segments)

    def is_in_cut(start_ms: int, end_ms: int) -> bool:
        mid_ms = (start_ms + end_ms) // 2
        for cut in active_cuts:
            if cut.safe_start_ms <= mid_ms <= cut.safe_end_ms:
                return True
        return False

    edited_words: list[TranscriptWord] = []
    idx = 0
    for w in transcript.words:
        if is_in_cut(w.start_ms, w.end_ms):
            continue
        new_start = map_source_time_to_edited(w.start_ms, keep_segments)
        new_end = map_source_time_to_edited(w.end_ms, keep_segments)
        if new_end <= new_start:
            new_end = new_start + max(1, w.end_ms - w.start_ms)
        edited_words.append(
            TranscriptWord(
                index=idx,
                text=w.text,
                start_ms=new_start,
                end_ms=new_end,
                confidence=w.confidence,
                speaker_id=w.speaker_id,
            )
        )
        idx += 1

    edited_segments: list[TranscriptSegment] = []
    if edited_words:
        cur_seg_words = [edited_words[0]]
        for w in edited_words[1:]:
            prev = cur_seg_words[-1]
            if w.start_ms - prev.end_ms > 1500 or len(cur_seg_words) >= 20:
                seg_text = " ".join(sw.text for sw in cur_seg_words)
                edited_segments.append(
                    TranscriptSegment(
                        segment_id=f"seg_{len(edited_segments) + 1:03d}",
                        text=seg_text,
                        start_ms=cur_seg_words[0].start_ms,
                        end_ms=cur_seg_words[-1].end_ms,
                        word_start_index=cur_seg_words[0].index,
                        word_end_index=cur_seg_words[-1].index,
                    )
                )
                cur_seg_words = [w]
            else:
                cur_seg_words.append(w)
        if cur_seg_words:
            seg_text = " ".join(sw.text for sw in cur_seg_words)
            edited_segments.append(
                TranscriptSegment(
                    segment_id=f"seg_{len(edited_segments) + 1:03d}",
                    text=seg_text,
                    start_ms=cur_seg_words[0].start_ms,
                    end_ms=cur_seg_words[-1].end_ms,
                    word_start_index=cur_seg_words[0].index,
                    word_end_index=cur_seg_words[-1].index,
                )
            )
    return Transcript(
        transcript_id=f"tr_ed_{uuid.uuid4().hex[:8]}",
        production_id=transcript.production_id,
        language_code=transcript.language_code,
        duration_ms=target_duration_ms,
        words=edited_words,
        segments=edited_segments,
        silence_intervals=[],
        created_at=datetime.now(timezone.utc),
    )


def compute_editorial_quality_report(
    edl: EditDecisionList,
    current_edited_duration_ms: int | None = None,
) -> EditorialQualityReport:
    """Compute the canonical editorial quality report, physical cut duration breakdown, and semantic event breakdown from an EDL."""
    source_dur = edl.source_duration_ms
    new_dur = edl.estimated_target_duration_ms
    cur_dur = current_edited_duration_ms if current_edited_duration_ms is not None else source_dur
    total_removed = edl.total_removed_duration_ms

    dead_air_ms = 0
    dead_air_count = 0
    false_start_ms = 0
    false_start_count = 0
    word_rep_ms = 0
    word_rep_count = 0
    phrase_rep_ms = 0
    phrase_rep_count = 0
    redundant_ms = 0
    redundant_count = 0
    filler_ms = 0
    filler_count = 0
    pacing_ms = 0
    pacing_count = 0
    other_ms = 0
    other_count = 0

    false_start_events = 0
    word_rep_events = 0
    phrase_rep_events = 0
    redundant_events = 0
    filler_events = 0
    rambling_events = 0
    pause_trim_events = 0
    pacing_events = 0
    other_events = 0

    physical_cuts_count = 0
    semantic_cuts_count = 0

    for cut in edl.cuts:
        if cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE:
            continue
        physical_cuts_count += 1
        dur = cut.removed_duration_ms
        t = str(cut.decision_type).upper()
        cat = (cut.category or "").upper()

        if t in ("DEAD_AIR", "PAUSE_TRIM", "REMOVE_SILENCE", "TRIM_PAUSE", "TIGHTEN_PAUSE") and cat in ("DEAD_AIR", "PAUSE_TRIM", "SILENCE", "") and not cut.contains_semantic_removal:
            dead_air_ms += dur
            dead_air_count += 1
        elif t in ("FALSE_START", "REMOVE_FALSE_START") or cat == "FALSE_START":
            false_start_ms += dur
            false_start_count += 1
            semantic_cuts_count += 1
        elif t in ("WORD_REPETITION", "REMOVE_REPETITION") or cat == "WORD_REPETITION":
            word_rep_ms += dur
            word_rep_count += 1
            semantic_cuts_count += 1
        elif t == "PHRASE_REPETITION" or cat == "PHRASE_REPETITION":
            phrase_rep_ms += dur
            phrase_rep_count += 1
            semantic_cuts_count += 1
        elif t in ("REDUNDANT_EXPLANATION", "TIGHTEN_EXPLANATION", "REMOVE_LOW_VALUE_SECTION") or cat == "REDUNDANT_EXPLANATION":
            redundant_ms += dur
            redundant_count += 1
            semantic_cuts_count += 1
        elif t in ("FILLER", "REMOVE_FILLER") or cat == "FILLER":
            filler_ms += dur
            filler_count += 1
            semantic_cuts_count += 1
        elif t in ("PACING",) or cat == "PACING":
            pacing_ms += dur
            pacing_count += 1
            semantic_cuts_count += 1
        else:
            if cut.contains_semantic_removal or (cut.removed_text and cut.removed_text != "None"):
                other_ms += dur
                other_count += 1
                semantic_cuts_count += 1
            else:
                dead_air_ms += dur
                dead_air_count += 1

        if cut.semantic_events:
            for ev in cut.semantic_events:
                ev_t = str(ev.decision_type).upper()
                ev_cat = str(ev.category).upper()
                if ev.is_silence or ev_t in ("DEAD_AIR", "PAUSE_TRIM", "REMOVE_SILENCE", "TRIM_PAUSE", "TIGHTEN_PAUSE") or ev_cat in ("DEAD_AIR", "PAUSE_TRIM", "SILENCE"):
                    pause_trim_events += 1
                elif ev_t in ("FALSE_START", "REMOVE_FALSE_START") or ev_cat == "FALSE_START":
                    false_start_events += 1
                elif ev_t in ("WORD_REPETITION", "REMOVE_REPETITION") or ev_cat == "WORD_REPETITION":
                    word_rep_events += 1
                elif ev_t == "PHRASE_REPETITION" or ev_cat == "PHRASE_REPETITION":
                    phrase_rep_events += 1
                elif ev_t in ("REDUNDANT_EXPLANATION", "TIGHTEN_EXPLANATION") or ev_cat == "REDUNDANT_EXPLANATION":
                    redundant_events += 1
                elif ev_t in ("FILLER", "REMOVE_FILLER") or ev_cat == "FILLER":
                    filler_events += 1
                elif ev_t in ("RAMBLING",) or ev_cat == "RAMBLING":
                    rambling_events += 1
                elif ev_t in ("PACING",) or ev_cat == "PACING":
                    pacing_events += 1
                else:
                    other_events += 1
        else:
            if t in ("DEAD_AIR", "PAUSE_TRIM", "REMOVE_SILENCE", "TRIM_PAUSE", "TIGHTEN_PAUSE") or cat in ("DEAD_AIR", "PAUSE_TRIM", "SILENCE"):
                pause_trim_events += 1
            elif t in ("FALSE_START", "REMOVE_FALSE_START") or cat == "FALSE_START":
                false_start_events += 1
            elif t in ("WORD_REPETITION", "REMOVE_REPETITION") or cat == "WORD_REPETITION":
                word_rep_events += 1
            elif t == "PHRASE_REPETITION" or cat == "PHRASE_REPETITION":
                phrase_rep_events += 1
            elif t in ("REDUNDANT_EXPLANATION", "TIGHTEN_EXPLANATION") or cat == "REDUNDANT_EXPLANATION":
                redundant_events += 1
            elif t in ("FILLER", "REMOVE_FILLER") or cat == "FILLER":
                filler_events += 1
            elif t in ("RAMBLING",) or cat == "RAMBLING":
                rambling_events += 1
            elif t in ("PACING",) or cat == "PACING":
                pacing_events += 1
            else:
                other_events += 1

    total_events = (
        false_start_events + word_rep_events + phrase_rep_events +
        redundant_events + filler_events + rambling_events +
        pause_trim_events + pacing_events + other_events
    )
    semantic_events_count = (
        false_start_events + word_rep_events + phrase_rep_events +
        redundant_events + filler_events + rambling_events +
        pacing_events + other_events
    )

    silence_only = semantic_cuts_count == 0 and semantic_events_count == 0

    return EditorialQualityReport(
        source_duration_ms=source_dur,
        current_edited_duration_ms=cur_dur,
        new_edited_duration_ms=new_dur,
        total_removed_ms=total_removed,
        dead_air=EditorialCategoryBreakdown(count=dead_air_count, duration_ms=dead_air_ms),
        false_start=EditorialCategoryBreakdown(count=false_start_count, duration_ms=false_start_ms),
        word_repetition=EditorialCategoryBreakdown(count=word_rep_count, duration_ms=word_rep_ms),
        phrase_repetition=EditorialCategoryBreakdown(count=phrase_rep_count, duration_ms=phrase_rep_ms),
        redundant_explanation=EditorialCategoryBreakdown(count=redundant_count, duration_ms=redundant_ms),
        filler=EditorialCategoryBreakdown(count=filler_count, duration_ms=filler_ms),
        pacing=EditorialCategoryBreakdown(count=pacing_count, duration_ms=pacing_ms),
        other=EditorialCategoryBreakdown(count=other_count, duration_ms=other_ms),
        physical_cuts_count=physical_cuts_count,
        semantic_cuts_count=semantic_cuts_count,
        silence_only_edit=silence_only,
        semantic_events=SemanticEventBreakdown(
            false_start=false_start_events,
            word_repetition=word_rep_events,
            phrase_repetition=phrase_rep_events,
            redundant_explanation=redundant_events,
            filler=filler_events,
            rambling=rambling_events,
            pause_trim=pause_trim_events,
            pacing=pacing_events,
            other=other_events,
            total_events=total_events,
            semantic_events_count=semantic_events_count,
        ),
    )
