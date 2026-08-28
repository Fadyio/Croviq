"""Canonical Editorial domain models for Leo (Video Editor) and Maya (Director) agents."""
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class EditorDecisionType(StrEnum):
    """Semantic action types supported by Video Editor (Leo)."""
    KEEP = "KEEP"
    REMOVE_SILENCE = "REMOVE_SILENCE"
    REMOVE_FILLER = "REMOVE_FILLER"
    REMOVE_FALSE_START = "REMOVE_FALSE_START"
    REMOVE_REPETITION = "REMOVE_REPETITION"
    TRIM_PAUSE = "TRIM_PAUSE"
    TIGHTEN_PAUSE = "TIGHTEN_PAUSE"
    TIGHTEN_EXPLANATION = "TIGHTEN_EXPLANATION"
    REMOVE_LOW_VALUE_SECTION = "REMOVE_LOW_VALUE_SECTION"
    KEEP_FOR_CLARITY = "KEEP_FOR_CLARITY"
    BROLL_COVER = "BROLL_COVER"
    BROLL_COVER_CANDIDATE = "BROLL_COVER_CANDIDATE"
    SOURCE_COVER = "SOURCE_COVER"
    CHAPTER_MARKER = "CHAPTER_MARKER"
    SHORT_CANDIDATE = "SHORT_CANDIDATE"
    NARRATION_REWRITE = "NARRATION_REWRITE"
    CAPTION_EMPHASIS = "CAPTION_EMPHASIS"

class SectionAction(StrEnum):
    """Editorial action applied to a full-timeline production section."""

    KEEP = "KEEP"
    TIGHTEN = "TIGHTEN"
    REMOVE = "REMOVE"
    COVERAGE = "COVERAGE"


class VideoSectionDecision(BaseModel):
    """Comprehensive full-timeline section decision proposed by Leo (Video Editor)."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    section_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the timeline section",
    )
    source_start_ms: int = Field(
        ...,
        ge=0,
        description="Start time in milliseconds on the source video timeline",
    )
    source_end_ms: int = Field(
        ...,
        ge=0,
        description="End time in milliseconds on the source video timeline",
    )
    transcript_start_word: int = Field(
        ...,
        ge=0,
        description="Canonical 0-indexed transcript start word index",
    )
    transcript_end_word: int = Field(
        ...,
        ge=0,
        description="Canonical 0-indexed transcript end word index",
    )
    action: SectionAction = Field(
        ...,
        description="Editorial action: KEEP, TIGHTEN, REMOVE, or COVERAGE",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Editorial justification for why this section is kept, tightened, or removed",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score for this section decision",
    )
    visual_summary: str | None = Field(
        default=None,
        max_length=500,
        description="Summary of screen content, slides, demonstration, or camera visual moments",
    )
    speech_summary: str | None = Field(
        default=None,
        max_length=500,
        description="Summary of spoken dialogue or audio in this section",
    )
    editorial_intent: str | None = Field(
        default=None,
        max_length=500,
        description="Leo's editorial rationale and narrative purpose for this section",
    )
    @model_validator(mode="after")
    def validate_bounds(self) -> "VideoSectionDecision":
        if self.source_end_ms < self.source_start_ms:
            raise ValueError(
                f"source_end_ms ({self.source_end_ms}) must be >= source_start_ms ({self.source_start_ms})"
            )
        if self.transcript_end_word < self.transcript_start_word:
            raise ValueError(
                f"transcript_end_word ({self.transcript_end_word}) must be >= transcript_start_word ({self.transcript_start_word})"
            )
        return self

class ChapterMarker(BaseModel):
    """Semantic chapter candidate generated from Leo's multimodal video understanding."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Concise descriptive chapter title",
    )
    source_start_ms: int = Field(
        ...,
        ge=0,
        description="Start time in milliseconds on the source video timeline",
    )
    source_end_ms: int = Field(
        ...,
        ge=0,
        description="End time in milliseconds on the source video timeline",
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Summary of narrative and visual content covered in this chapter",
    )
    confidence: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Confidence score for this chapter boundary",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "ChapterMarker":
        if self.source_end_ms < self.source_start_ms:
            raise ValueError(
                f"source_end_ms ({self.source_end_ms}) must be >= source_start_ms ({self.source_start_ms})"
            )
        return self


class ShortVisualRegion(BaseModel):
    """Normalized focus rectangle identifying the readable screen region for a Short scene."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    start_ms: int = Field(..., ge=0, description="Start timestamp in ms relative to Short timeline")
    end_ms: int = Field(..., ge=0, description="End timestamp in ms relative to Short timeline")
    x: float = Field(..., ge=0.0, le=1.0, description="Normalized x coordinate (0.0 to 1.0) of crop top-left in source frame")
    y: float = Field(..., ge=0.0, le=1.0, description="Normalized y coordinate (0.0 to 1.0) of crop top-left in source frame")
    width: float = Field(..., ge=0.01, le=1.0, description="Normalized width (0.0 to 1.0) of focus region")
    height: float = Field(..., ge=0.01, le=1.0, description="Normalized height (0.0 to 1.0) of focus region")
    zoom: float = Field(default=1.0, ge=1.0, le=3.0, description="Optional zoom factor")
    focus_label: str = Field(..., min_length=1, max_length=100, description="Visual description of focus area (e.g. YAML editor, status)")

    @model_validator(mode="after")
    def validate_bounds(self) -> "ShortVisualRegion":
        if self.end_ms <= self.start_ms:
            raise ValueError(f"end_ms ({self.end_ms}) must be > start_ms ({self.start_ms})")
        if self.x + self.width > 1.001:
            raise ValueError(f"x + width ({self.x + self.width}) exceeds normalized frame width 1.0")
        if self.y + self.height > 1.001:
            raise ValueError(f"y + height ({self.y + self.height}) exceeds normalized frame height 1.0")
        return self


class ShortVisualPlan(BaseModel):
    """Visual reframe plan for social Short rendering."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    regions: list[ShortVisualRegion] = Field(
        default_factory=list,
        description="List of chronological visual focus regions for the Short",
    )

class DirectorVerdict(StrEnum):
    """Review verdicts issued by Director (Maya)."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"


class EditorialRunStatus(StrEnum):
    """Operational state of an editorial analysis run."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


class ShortCandidate(BaseModel):
    """Identified 20-60s candidate segment suitable for vertical Short extraction."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    start_ms: int = Field(
        ...,
        ge=0,
        description="Start timestamp in source video milliseconds",
    )
    end_ms: int = Field(
        ...,
        ge=0,
        description="End timestamp in source video milliseconds",
    )
    transcript_start_word: int = Field(
        ...,
        ge=0,
        description="Canonical 0-indexed transcript word start boundary",
    )
    transcript_end_word: int = Field(
        ...,
        ge=0,
        description="Canonical 0-indexed transcript word end boundary",
    )
    hook_title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short hook / title proposition",
    )
    concise_reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Editorial justification for why this segment works as a standalone Short",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score for the candidate excerpt",
    )
    visual_plan: ShortVisualPlan | None = Field(
        default=None,
        description="Optional visual focus regions for 9:16 reframe",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "ShortCandidate":
        if self.end_ms <= self.start_ms:
            raise ValueError(f"end_ms ({self.end_ms}) must be greater than start_ms ({self.start_ms})")
        if self.transcript_end_word < self.transcript_start_word:
            raise ValueError(
                f"transcript_end_word ({self.transcript_end_word}) must be >= transcript_start_word ({self.transcript_start_word})"
            )
        return self


class EditorDecision(BaseModel):
    """Individual editorial decision proposed by Leo (Video Editor)."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    decision_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the decision within the proposal",
    )
    decision_type: EditorDecisionType = Field(
        ...,
        description="Semantic category of the editing decision",
    )
    transcript_start_word: int = Field(
        ...,
        ge=0,
        description="Canonical 0-indexed transcript start word index",
    )
    transcript_end_word: int = Field(
        ...,
        ge=0,
        description="Canonical 0-indexed transcript end word index",
    )
    source_start_ms: int = Field(
        ...,
        ge=0,
        description="Start time in milliseconds (derived from transcript timing)",
    )
    source_end_ms: int = Field(
        ...,
        ge=0,
        description="End time in milliseconds (derived from transcript timing)",
    )
    original_text: str = Field(
        ...,
        min_length=1,
        description="Exact spoken text corresponding to the word interval",
    )
    action: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Semantic action (e.g. remove, keep, trim, cover)",
    )
    concise_reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Short editorial rationale for the suggested action",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this decision",
    )
    visual_context: str | None = Field(
        default=None,
        max_length=500,
        description="Visual context on screen (e.g. talking head, terminal, slides)",
    )
    preserve_context: str | None = Field(
        default=None,
        max_length=500,
        description="Surrounding context that must be preserved",
    )
    risk: str | None = Field(
        default=None,
        max_length=500,
        description="Potential editorial or audio risk associated with the cut",
    )

    @model_validator(mode="after")
    def validate_indexes_and_times(self) -> "EditorDecision":
        if self.transcript_end_word < self.transcript_start_word:
            raise ValueError(
                f"transcript_end_word ({self.transcript_end_word}) must be >= "
                f"transcript_start_word ({self.transcript_start_word})"
            )
        if self.source_end_ms < self.source_start_ms:
            raise ValueError(
                f"source_end_ms ({self.source_end_ms}) must be >= "
                f"source_start_ms ({self.source_start_ms})"
            )
        return self


class EditorProposal(BaseModel):
    """Complete batch proposal emitted by Leo (Video Editor)."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    production_id: str = Field(
        ...,
        min_length=1,
        description="Associated Production entity identifier",
    )
    agent: str = Field(
        default="leo",
        description="Agent name identifier",
    )
    model: str = Field(
        ...,
        min_length=1,
        description="Model identifier used for generation (e.g. gemini-3.7-flash)",
    )
    summary: str = Field(
        ...,
        min_length=1,
        description="High-level summary of dialogue pass findings and proposed improvements",
    )
    decisions: list[EditorDecision] = Field(
        default_factory=list,
        description="List of proposed editorial decisions",
    )
    short_candidate: ShortCandidate | None = Field(
        default=None,
        description="Optional Short candidate excerpt identified during analysis",
    )
    section_plan: list[VideoSectionDecision] = Field(
        default_factory=list,
        description="Full-timeline editorial section plan covering the whole production",
    )
    chapters: list[ChapterMarker] = Field(
        default_factory=list,
        description="Multimodal semantic chapter markers across the video timeline",
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the proposal",
    )


class DirectorDecision(BaseModel):
    """Director (Maya) review verdict for an individual EditorDecision."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    editor_decision_id: str = Field(
        ...,
        min_length=1,
        description="ID of the EditorDecision being reviewed",
    )
    verdict: DirectorVerdict = Field(
        ...,
        description="Verdict: APPROVE, REJECT, or MODIFY",
    )
    concise_reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Short editorial reason for the verdict",
    )
    modified_action: str | None = Field(
        default=None,
        max_length=50,
        description="Corrected action if verdict is MODIFY",
    )
    modified_transcript_start_word: int | None = Field(
        default=None,
        ge=0,
        description="Corrected start word index if verdict is MODIFY",
    )
    modified_transcript_end_word: int | None = Field(
        default=None,
        ge=0,
        description="Corrected end word index if verdict is MODIFY",
    )
    modified_source_start_ms: int | None = Field(
        default=None,
        ge=0,
        description="Corrected start time in ms if verdict is MODIFY",
    )
    modified_source_end_ms: int | None = Field(
        default=None,
        ge=0,
        description="Corrected end time in ms if verdict is MODIFY",
    )

    @model_validator(mode="after")
    def validate_modification_fields(self) -> "DirectorDecision":
        if self.verdict == DirectorVerdict.MODIFY:
            if (
                self.modified_transcript_start_word is not None
                and self.modified_transcript_end_word is not None
                and self.modified_transcript_end_word < self.modified_transcript_start_word
            ):
                raise ValueError(
                    f"modified_transcript_end_word ({self.modified_transcript_end_word}) must be >= "
                    f"modified_transcript_start_word ({self.modified_transcript_start_word})"
                )
            if (
                self.modified_source_start_ms is not None
                and self.modified_source_end_ms is not None
                and self.modified_source_end_ms < self.modified_source_start_ms
            ):
                raise ValueError(
                    f"modified_source_end_ms ({self.modified_source_end_ms}) must be >= "
                    f"modified_source_start_ms ({self.modified_source_start_ms})"
                )
        return self


class DirectorSectionDecision(BaseModel):
    """Director review verdict for a full-timeline VideoSectionDecision."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    section_id: str = Field(..., min_length=1, max_length=64)
    verdict: DirectorVerdict = Field(..., description="Verdict: APPROVE, REJECT, or MODIFY")
    reason: str = Field(..., min_length=1, max_length=500)

class DirectorReview(BaseModel):
    """Complete review output emitted by Director (Maya)."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    production_id: str = Field(
        ...,
        min_length=1,
        description="Associated Production entity identifier",
    )
    agent: str = Field(
        default="maya",
        description="Agent identifier",
    )
    model: str = Field(
        ...,
        min_length=1,
        description="Model identifier used for review",
    )
    overall_assessment: str = Field(
        ...,
        min_length=1,
        description="Director's overall assessment of Leo's proposal",
    )
    decisions: list[DirectorDecision] = Field(
        default_factory=list,
        description="Per-decision review verdicts",
    )
    section_decisions: list[DirectorSectionDecision] = Field(
        default_factory=list,
        description="Review verdicts on Leo's full-timeline section plan",
    )
    editor_feedback: str = Field(
        ...,
        min_length=1,
        description="Direct feedback to Leo for adjustments or approval",
    )
    approved_for_edl: bool = Field(
        ...,
        description="Whether the proposal is approved to proceed to EDL assembly",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Director's confidence in the review",
    )


class AgentActivity(BaseModel):
    """Product-facing persisted activity message from Maya or Leo."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    activity_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the activity item",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        description="Associated production identifier",
    )
    run_id: str = Field(
        ...,
        min_length=1,
        description="Associated editorial run identifier",
    )
    agent: str = Field(
        ...,
        min_length=1,
        description="Agent name (e.g. Leo, Maya)",
    )
    role: str = Field(
        ...,
        description="Agent role (e.g. Video Editor, Director)",
    )
    activity_type: str = Field(
        ...,
        min_length=1,
        description="Activity category (e.g. proposal, review, note, decision)",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Clean product-facing message (no hidden chain-of-thought)",
    )
    related_decision_id: str | None = Field(
        default=None,
        description="Referenced EditorDecision ID if applicable",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the activity occurred",
    )

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class EditorialRun(BaseModel):
    """Operational record representing an editorial analysis run lifecycle."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    run_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the editorial run",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        description="Associated production entity identifier",
    )
    status: EditorialRunStatus = Field(
        default=EditorialRunStatus.PENDING,
        description="Current operational status of the run",
    )
    editor_proposal_id: str | None = Field(
        default=None,
        description="Identifier of the generated EditorProposal record",
    )
    director_review_id: str | None = Field(
        default=None,
        description="Identifier of the generated DirectorReview record",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Run start timestamp in UTC",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Run completion timestamp in UTC",
    )
    failure_code: str | None = Field(
        default=None,
        description="Sanitized failure code if run status is FAILED",
    )

    @field_validator("started_at", "completed_at", mode="after")
    @classmethod
    def validate_run_datetimes(cls, v: datetime | None) -> datetime | None:
        return validate_timezone_aware(v)
