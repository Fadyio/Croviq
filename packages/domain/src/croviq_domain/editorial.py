"""Canonical Editorial domain models for Leo (Video Editor)."""
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class EditorDecisionType(StrEnum):
    """Semantic action types supported by Video Editor (Leo)."""
    # Canonical BUG 22 Editorial Decision Types
    FALSE_START = "FALSE_START"
    WORD_REPETITION = "WORD_REPETITION"
    PHRASE_REPETITION = "PHRASE_REPETITION"
    REDUNDANT_EXPLANATION = "REDUNDANT_EXPLANATION"
    FILLER = "FILLER"
    RAMBLING = "RAMBLING"
    DEAD_AIR = "DEAD_AIR"
    PAUSE_TRIM = "PAUSE_TRIM"
    PACING = "PACING"
    OTHER = "OTHER"

    # Legacy & operational types for backward compatibility
    KEEP = "KEEP"
    KEEP_FOR_CLARITY = "KEEP_FOR_CLARITY"
    REMOVE_SILENCE = "REMOVE_SILENCE"
    REMOVE_FILLER = "REMOVE_FILLER"
    REMOVE_FALSE_START = "REMOVE_FALSE_START"
    REMOVE_REPETITION = "REMOVE_REPETITION"
    TRIM_PAUSE = "TRIM_PAUSE"
    TIGHTEN_PAUSE = "TIGHTEN_PAUSE"
    TIGHTEN_EXPLANATION = "TIGHTEN_EXPLANATION"
    REMOVE_LOW_VALUE_SECTION = "REMOVE_LOW_VALUE_SECTION"
    SOURCE_COVER = "SOURCE_COVER"
    CHAPTER_MARKER = "CHAPTER_MARKER"
    NARRATION_REWRITE = "NARRATION_REWRITE"
    CAPTION_EMPHASIS = "CAPTION_EMPHASIS"
class EditorSelectionType(StrEnum):
    """Canonical timeline selection type in Croviq Editor."""
    POINT = "POINT"
    RANGE = "RANGE"
    TRANSCRIPT_WORD = "TRANSCRIPT_WORD"
    TRANSCRIPT_SEGMENT = "TRANSCRIPT_SEGMENT"
    CUT = "CUT"
    CHAPTER = "CHAPTER"


class CoordinateSpace(StrEnum):
    """Coordinate space of the selected timestamp/range."""
    SOURCE = "SOURCE"
    EDITED = "EDITED"


class ActivePreviewMode(StrEnum):
    """Preview mode active in the video player during selection."""
    ORIGINAL = "ORIGINAL"
    EDITED = "EDITED"
    VOICEOVER = "VOICEOVER"
    FINAL_MIX = "FINAL_MIX"


class EditorSelectionContext(BaseModel):
    """Single canonical editor selection context for agent reasoning."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    production_id: str = Field(..., min_length=1)
    selection_type: EditorSelectionType
    coordinate_space: CoordinateSpace
    source_start_ms: int = Field(..., ge=0)
    source_end_ms: int = Field(..., ge=0)
    edited_start_ms: int | None = Field(default=None, ge=0)
    edited_end_ms: int | None = Field(default=None, ge=0)
    transcript_text: str | None = None
    transcript_word_ids: list[int] | None = None
    cut_id: str | None = None
    chapter_id: str | None = None
    active_edl_id: str | None = None
    active_preview_mode: ActivePreviewMode = ActivePreviewMode.FINAL_MIX
    label: str | None = None
    cut_reason: str | None = None
    removed_duration_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_ranges(self) -> "EditorSelectionContext":
        if self.source_end_ms < self.source_start_ms:
            self.source_end_ms = self.source_start_ms
        if self.edited_start_ms is not None and self.edited_end_ms is not None:
            if self.edited_end_ms < self.edited_start_ms:
                self.edited_end_ms = self.edited_start_ms
        return self


class EditorVoiceMode(StrEnum):
    """Truthful audio provenance modes surfaced by Leo's editor tools."""

    ORIGINAL_VOICE = "ORIGINAL_VOICE"
    ORIGINAL_AUDIO = "ORIGINAL_AUDIO"
    REPLICATED_MY_VOICE = "REPLICATED_MY_VOICE"
    PREBUILT_STUDIO_VOICE = "PREBUILT_STUDIO_VOICE"
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
    chapter_id: str = Field(
        default_factory=lambda: f"chap_{uuid.uuid4().hex[:12]}",
        min_length=1,
        max_length=64,
        description="Stable chapter identifier for typed editor operations",
    )
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




class EditorialRunStatus(StrEnum):
    """Operational state of an editorial analysis run."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"




class EditorDecision(BaseModel):
    """Individual editorial decision proposed by Leo (Video Editor)."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    decision_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the decision within the proposal",
    )
    decision_type: EditorDecisionType | str = Field(
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
        description="Concise editorial rationale for the suggested action",
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
    removed_text: str | None = Field(
        default=None,
        description="Exact spoken transcript text removed by this decision",
    )
    context_before: str | None = Field(
        default=None,
        description="Retained spoken context immediately preceding the cut",
    )
    context_after: str | None = Field(
        default=None,
        description="Retained spoken context immediately following the cut",
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
        extra="ignore",
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


class AgentActivity(BaseModel):
    """Product-facing persisted activity message from an active agent."""

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
        description="Agent name (e.g. Leo, Alex, Iris)",
    )
    role: str = Field(
        ...,
        description="Agent role (e.g. Video Editor, Data Scientist, Quality Assurance)",
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
        extra="ignore",
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
    self_review_id: str | None = Field(
        default=None,
        description="Identifier of the generated EditorSelfReview record",
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


class EditorialCategoryBreakdown(BaseModel):
    """Exact count and duration breakdown for a canonical editorial removal category."""

    model_config = ConfigDict(extra="ignore")

    count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)

    @property
    def duration_s(self) -> float:
        return self.duration_ms / 1000.0

class SemanticEvent(BaseModel):
    """An individual editorial decision / semantic event contained within a physical cut."""

    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(..., description="Unique event identifier")
    decision_id: str = Field(..., description="Originating Editor decision identifier")
    decision_type: str = Field(..., description="Decision type (e.g. FALSE_START, FILLER, TRIM_PAUSE)")
    category: str = Field(..., description="Canonical category (e.g. FALSE_START, FILLER, DEAD_AIR)")
    reason: str = Field(..., description="Editorial rationale for the event")
    removed_text: str | None = Field(default=None, description="Removed text for this event if applicable")
    start_ms: int = Field(default=0, ge=0, description="Start time in milliseconds")
    end_ms: int = Field(default=0, ge=0, description="End time in milliseconds")
    duration_ms: int = Field(default=0, ge=0, description="Event duration in milliseconds")
    is_silence: bool = Field(default=False, description="Whether this event is a silence/pause trim")


class SemanticEventBreakdown(BaseModel):
    """Event counts for canonical semantic editorial categories."""

    model_config = ConfigDict(extra="ignore")

    false_start: int = Field(default=0, ge=0)
    word_repetition: int = Field(default=0, ge=0)
    phrase_repetition: int = Field(default=0, ge=0)
    redundant_explanation: int = Field(default=0, ge=0)
    filler: int = Field(default=0, ge=0)
    rambling: int = Field(default=0, ge=0)
    pause_trim: int = Field(default=0, ge=0)
    pacing: int = Field(default=0, ge=0)
    other: int = Field(default=0, ge=0)
    total_events: int = Field(default=0, ge=0)
    semantic_events_count: int = Field(default=0, ge=0)


class EditorialQualityReport(BaseModel):
    """Comprehensive editorial quality report summarizing source duration and categorized removals."""

    model_config = ConfigDict(extra="ignore")

    source_duration_ms: int = Field(default=0, ge=0)
    current_edited_duration_ms: int = Field(default=0, ge=0)
    new_edited_duration_ms: int = Field(default=0, ge=0)
    total_removed_ms: int = Field(default=0, ge=0)

    dead_air: EditorialCategoryBreakdown = Field(default_factory=EditorialCategoryBreakdown)
    false_start: EditorialCategoryBreakdown = Field(default_factory=EditorialCategoryBreakdown)
    word_repetition: EditorialCategoryBreakdown = Field(default_factory=EditorialCategoryBreakdown)
    phrase_repetition: EditorialCategoryBreakdown = Field(default_factory=EditorialCategoryBreakdown)
    redundant_explanation: EditorialCategoryBreakdown = Field(default_factory=EditorialCategoryBreakdown)
    filler: EditorialCategoryBreakdown = Field(default_factory=EditorialCategoryBreakdown)
    pacing: EditorialCategoryBreakdown = Field(default_factory=EditorialCategoryBreakdown)
    other: EditorialCategoryBreakdown = Field(default_factory=EditorialCategoryBreakdown)

    physical_cuts_count: int = Field(default=0, ge=0)
    semantic_cuts_count: int = Field(default=0, ge=0)
    silence_only_edit: bool = Field(default=False)

    semantic_events: SemanticEventBreakdown = Field(default_factory=SemanticEventBreakdown)

    @property
    def total_removed_s(self) -> float:
        return self.total_removed_ms / 1000.0
