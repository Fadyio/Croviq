"""Canonical Edit Decision List (EDL) domain models for deterministic media rendering."""

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.editorial import EditorDecisionType
from croviq_domain.validators import validate_timezone_aware


class CutSafetyStatus(StrEnum):
    """Deterministic safety classification for proposed cuts."""

    SAFE = "SAFE"
    NEEDS_COVERAGE = "NEEDS_COVERAGE"
    REJECTED_UNSAFE = "REJECTED_UNSAFE"


class CoverageType(StrEnum):
    """Visual coverage types supported for jump-cut mitigation and B-roll insertion."""

    SOURCE_SCREEN = "SOURCE_SCREEN"
    BROLL_CANDIDATE = "BROLL_CANDIDATE"


class CoverageMarker(BaseModel):
    """Visual coverage metadata identifying footage insertion candidates."""

    model_config = ConfigDict(
        extra="forbid",
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
    coverage_type: CoverageType = Field(
        ...,
        description="Coverage category (e.g. SOURCE_SCREEN, BROLL_CANDIDATE)",
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
        description="Originating Editor/Director decision identifier",
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
        extra="forbid",
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
    director_review_id: str | None = Field(
        default=None,
        max_length=64,
        description="Reference to the originating DirectorReview",
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
        description="Visual coverage markers for B-roll and screen recordings",
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
        """Total duration in milliseconds removed by active cuts."""
        return sum(c.removed_duration_ms for c in self.active_cuts)

    @property
    def estimated_target_duration_ms(self) -> int:
        """Estimated final video duration after active cuts."""
        return max(0, self.source_duration_ms - self.total_removed_duration_ms)


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

    return segments
