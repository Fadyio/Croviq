"""Canonical domain models for Nina Packaging Agent (Issue #32)."""

from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class TitleAngle(StrEnum):
    """Packaging angles and positioning strategies for YouTube title candidates."""

    DIRECT_VALUE = "DIRECT_VALUE"
    CURIOSITY = "CURIOSITY"
    PROBLEM_SOLUTION = "PROBLEM_SOLUTION"
    CONTRARIAN = "CONTRARIAN"
    HOW_TO = "HOW_TO"
    COMPARISON = "COMPARISON"
    NEWS_RELEVANT = "NEWS_RELEVANT"


TITLE_ANGLE_FRIENDLY_NAMES: dict[TitleAngle, str] = {
    TitleAngle.DIRECT_VALUE: "Direct Value",
    TitleAngle.CURIOSITY: "Curiosity",
    TitleAngle.PROBLEM_SOLUTION: "Problem-Solution",
    TitleAngle.CONTRARIAN: "Contrarian",
    TitleAngle.HOW_TO: "How-To",
    TitleAngle.COMPARISON: "Comparison",
    TitleAngle.NEWS_RELEVANT: "News Relevant",
}


def get_title_angle_label(angle: TitleAngle | str) -> str:
    """Return product-facing friendly name for a TitleAngle enum value."""
    try:
        enum_val = TitleAngle(str(angle)) if not isinstance(angle, TitleAngle) else angle
        return TITLE_ANGLE_FRIENDLY_NAMES.get(enum_val, str(angle).replace("_", " ").title())
    except ValueError:
        return str(angle).replace("_", " ").title()


def format_ms_as_timestamp(ms: int) -> str:
    """Format millisecond offset into standard YouTube chapter timestamp (M:SS or H:MM:SS)."""
    total_seconds = max(0, int(ms / 1000))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class TitleCandidate(BaseModel):
    """Distinct title candidate representing a specific packaging strategy."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    text: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="YouTube title text",
    )
    angle: TitleAngle = Field(
        ...,
        description="Strategic packaging angle (DIRECT_VALUE, CURIOSITY, etc.)",
    )
    why_it_works: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Clear rationale for why this packaging angle fits channel audience",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this candidate (0.0 - 1.0)",
    )


class PackagingChapter(BaseModel):
    """Publish-ready chapter timestamp for YouTube description."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Polish chapter title",
    )
    start_ms: int = Field(
        ...,
        ge=0,
        description="Start time in milliseconds on the Master timeline",
    )
    end_ms: int = Field(
        ...,
        ge=0,
        description="End time in milliseconds on the Master timeline",
    )
    formatted_time: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Standard YouTube timecode string (e.g. 0:00, 1:23)",
    )
    summary: str | None = Field(
        default=None,
        max_length=500,
        description="Optional brief description of the chapter content",
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "PackagingChapter":
        if self.end_ms < self.start_ms:
            raise ValueError(
                f"end_ms ({self.end_ms}) must be >= start_ms ({self.start_ms})"
            )
        return self


class ThumbnailConcept(BaseModel):
    """Structured thumbnail concept referencing a verified visual frame in Master."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    concept_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique concept identifier",
    )
    headline: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Optional short thumbnail overlay headline / text (2-4 words)",
    )
    visual_subject: str = Field(
        ...,
        min_length=1,
        max_length=250,
        description="Description of the primary visual subject in the frame",
    )
    composition: str = Field(
        ...,
        min_length=1,
        max_length=250,
        description="Composition, framing, crop, and visual contrast direction",
    )
    emotion: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Intended viewer emotion or intrigue (e.g. Curiosity, Disbelief)",
    )
    supporting_frame_ms: int = Field(
        ...,
        ge=0,
        description="Exact millisecond timestamp in the Master video where this frame exists",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Rationale for why this visual frame attracts the target audience",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this thumbnail concept (0.0 - 1.0)",
    )
    frame_verified: bool = Field(
        default=True,
        description="Whether the supporting frame was verified against the Master video",
    )
    frame_artifact_uri: str | None = Field(
        default=None,
        description="Optional storage URI of extracted frame image",
    )


class ShortPackage(BaseModel):
    """Packaging metadata for vertical Short."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Vertical Short title",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Short description / caption",
    )
    hook: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Opening spoken / visual hook framing",
    )
    hashtags: list[str] = Field(
        default_factory=list,
        description="Useful hashtags (e.g. #shorts, #tech)",
    )


class PackagingProposal(BaseModel):
    """Canonical packaging proposal emitted by Nina (Packaging Agent)."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    proposal_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique packaging proposal identifier (e.g. pkg_...)",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Associated Production entity identifier",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Version number of packaging proposal for release locking",
    )
    agent: str = Field(
        default="nina",
        description="Agent identifier ('nina')",
    )
    model: str = Field(
        default="gemini-3.7-flash",
        min_length=1,
        description="Model identifier used for packaging generation",
    )
    primary_title: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Recommended primary title",
    )
    title_candidates: list[TitleCandidate] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of distinct title candidates across strategic angles",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Publish-ready YouTube description text with chapters",
    )
    chapters: list[PackagingChapter] = Field(
        default_factory=list,
        description="List of canonical video chapters",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Tags and keywords for search / discovery",
    )
    thumbnail_concepts: list[ThumbnailConcept] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Top thumbnail concepts with supporting frame references",
    )
    short_package: ShortPackage | None = Field(
        default=None,
        description="Vertical Short packaging if Short exists",
    )
    packaging_summary: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Concise product-facing packaging rationale",
    )
    channel_evidence: str | None = Field(
        default=None,
        max_length=1000,
        description="Product-facing channel evidence supporting primary recommendation",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence in packaging proposal",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp in UTC",
    )
    master_artifact_id: str | None = Field(
        default=None,
        description="Referenced Master RenderArtifact identifier",
    )
    prompt_version: int = Field(
        default=1,
        ge=1,
        description="Nina prompt version used for this generation",
    )

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class CreatorPackageOverrides(BaseModel):
    """Creator-defined overrides to Nina's packaging proposal."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    selected_title: str | None = Field(
        default=None,
        max_length=150,
        description="Currently selected title (from candidates or custom)",
    )
    custom_title: str | None = Field(
        default=None,
        max_length=150,
        description="Creator-edited custom title",
    )
    custom_description: str | None = Field(
        default=None,
        description="Creator-edited custom description",
    )
    custom_chapters: list[PackagingChapter] | None = Field(
        default=None,
        description="Creator-edited chapter titles",
    )
    custom_short_title: str | None = Field(
        default=None,
        max_length=100,
        description="Creator-edited Short title",
    )
    custom_short_description: str | None = Field(
        default=None,
        max_length=1000,
        description="Creator-edited Short description",
    )
    selected_thumbnail_concept_id: str | None = Field(
        default=None,
        description="ID of creator-selected thumbnail concept",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last creator edit (UTC)",
    )

    @field_validator("updated_at", mode="after")
    @classmethod
    def validate_updated_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class PublishMetadata(BaseModel):
    """Creator-owned publish metadata for video release."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Video title",
    )
    description: str = Field(
        default="",
        max_length=5000,
        description="Video description",
    )
    privacy: str = Field(
        default="private",
        description="YouTube video privacy status ('private', 'unlisted', or 'public')",
    )
    thumbnail_frame_ms: int | None = Field(
        default=None,
        description="Optional frame offset in milliseconds to extract as custom thumbnail",
    )
    made_for_kids: bool = Field(
        default=False,
        description="Whether the video is designated as made for kids",
    )
    synthetic_media: bool = Field(
        default=False,
        description="Whether altered/synthetic media disclosure is required",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last metadata update (UTC)",
    )

    @field_validator("updated_at", mode="after")
    @classmethod
    def validate_updated_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)
