"""Canonical Editorial domain models for Leo (Video Editor)."""
from datetime import datetime, timezone
from enum import StrEnum
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
