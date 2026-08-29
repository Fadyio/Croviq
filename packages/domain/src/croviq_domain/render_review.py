"""Canonical domain models for post-render quality review and bounded correction."""

from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class RenderReviewVerdict(StrEnum):
    """Post-render quality review verdicts."""

    APPROVE = "APPROVE"
    CORRECT = "CORRECT"


class RenderReviewIssueType(StrEnum):
    """Categorized editorial issues identified in rendered preview video."""

    UNNATURAL_AUDIO_JOIN = "UNNATURAL_AUDIO_JOIN"
    VISUAL_JUMP = "VISUAL_JUMP"
    OVER_AGGRESSIVE_CUT = "OVER_AGGRESSIVE_CUT"
    MISSED_EDIT = "MISSED_EDIT"
    CONTEXT_LOSS = "CONTEXT_LOSS"
    PACING = "PACING"
    COVERAGE_NEEDED = "COVERAGE_NEEDED"


class RenderReviewSeverity(StrEnum):
    """Severity classification of identified post-render review issues."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RenderReviewIssue(BaseModel):
    """Specific editorial or media issue observed during rendered preview inspection."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    issue_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the review issue",
    )
    issue_type: RenderReviewIssueType = Field(
        ...,
        description="Categorized issue type",
    )
    source_start_ms: int = Field(
        ...,
        ge=0,
        description="Start time of the affected region in source media milliseconds",
    )
    source_end_ms: int = Field(
        ...,
        ge=0,
        description="End time of the affected region in source media milliseconds",
    )
    related_decision_id: str | None = Field(
        default=None,
        description="Referenced EditorDecision ID if directly tied to an existing decision",
    )
    severity: RenderReviewSeverity = Field(
        ...,
        description="Severity level of the issue (LOW, MEDIUM, HIGH)",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Concise product-facing explanation of the issue (no raw chain-of-thought)",
    )
    suggested_action: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Suggested editorial correction to resolve the issue",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "RenderReviewIssue":
        if self.source_end_ms < self.source_start_ms:
            raise ValueError(
                f"source_end_ms ({self.source_end_ms}) must be >= source_start_ms ({self.source_start_ms})"
            )
        return self


class RenderReview(BaseModel):
    """Complete post-render quality review after preview inspection."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    review_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the post-render review record",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        description="Associated Production entity identifier",
    )
    edl_id: str = Field(
        ...,
        min_length=1,
        description="Associated EDL identifier that produced the preview",
    )
    preview_artifact_id: str = Field(
        ...,
        min_length=1,
        description="Associated RenderArtifact identifier of the rendered preview",
    )
    agent: str = Field(
        default="iris",
        description="Agent identifier (Iris)",
    )
    model: str = Field(
        ...,
        min_length=1,
        description="Model identifier used for the post-render evaluation",
    )
    verdict: RenderReviewVerdict = Field(
        ...,
        description="Post-render verdict: APPROVE or CORRECT",
    )
    summary: str = Field(
        ...,
        min_length=1,
        description="Concise product-facing summary of the post-render review",
    )
    issues: list[RenderReviewIssue] = Field(
        default_factory=list,
        description="List of specific issues identified in the rendered preview",
    )
    approved_for_master: bool = Field(
        ...,
        description="Whether the preview is approved to proceed to deterministic Master render",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Iris confidence in the review",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp in UTC",
    )

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class EditorSelfReviewVerdict(StrEnum):
    """Verdicts emitted by Leo (Video Editor) during multimodal self-review of rendered preview video."""

    APPROVE_UNCHANGED = "APPROVE_UNCHANGED"
    NEEDS_REVISION = "NEEDS_REVISION"


class EditorSelfReview(BaseModel):
    """Complete multimodal self-review output emitted by Leo (Video Editor) after watching preview MP4."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    review_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the self-review record",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Associated Production entity identifier",
    )
    edl_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Originating Edit Decision List identifier",
    )
    preview_artifact_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Associated RenderArtifact identifier of the rendered preview video",
    )
    agent: str = Field(
        default="leo",
        description="Agent identifier (Leo)",
    )
    model: str = Field(
        ...,
        min_length=1,
        description="Model identifier used for the multimodal video self-review",
    )
    verdict: EditorSelfReviewVerdict = Field(
        ...,
        description="Self-review verdict: APPROVE_UNCHANGED or NEEDS_REVISION",
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Concise editorial summary of the rendered preview inspection findings",
    )
    narrative_pacing_assessment: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Assessment of narrative pacing and energy across the edit",
    )
    removals_assessment: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Evaluation of whether each removal improved the overall edit",
    )
    visual_continuity_assessment: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Evaluation of visual continuity, jump cuts, and screen flow",
    )
    audio_joins_assessment: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Evaluation of audio joins, room tone, and speech tails",
    )
    coverage_needed: bool = Field(
        default=False,
        description="Whether additional B-roll visual coverage is recommended",
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Concise findings without chain-of-thought",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Leo's confidence in the self-review assessment",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp in UTC",
    )

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)
