from datetime import date, datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator

from croviq_domain.validators import validate_timezone_aware


class VideoFormat(StrEnum):
    TUTORIAL = "tutorial"
    ARCHITECTURE_DEEP_DIVE = "architecture_deep_dive"
    TOOL_COMPARISON = "tool_comparison"
    RELEASE_ANALYSIS = "release_analysis"
    PRODUCTION_EXPERIMENT = "production_experiment"
    DEVOPS_PIPELINE = "devops_pipeline"
    AGENT_BUILD = "agent_build"


class TitleStyle(StrEnum):
    OUTCOME_FOCUSED = "outcome_focused"
    BENCHMARK_COMPARISON = "benchmark_comparison"
    GENERIC_TUTORIAL = "generic_tutorial"
    NEWS_ANNOUNCEMENT = "news_announcement"
    PROBLEM_SOLUTION = "problem_solution"


class ContentPillar(StrEnum):
    AI_AGENTS = "AI Agents"
    GEMINI_VERTEX = "Gemini & Vertex AI"
    AI_ENGINEERING = "AI Engineering"
    GITHUB_ACTIONS_DEVOPS = "GitHub Actions & DevOps"
    CLOUD_RUN_GCP = "Cloud Run & GCP"
    RAG_MEMORY = "RAG & Memory Systems"
    MULTIMODAL_AI = "Multimodal AI"
    AI_CODING_TOOLS = "AI Coding Tools"
    PRODUCTION_LLM = "Production LLM Systems"
    EMERGING_AI = "Emerging AI Releases"


class RetentionPoint(BaseModel):
    """A single sample point along a video's audience retention curve."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    percent_offset: int = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage offset from video start (0 to 100)",
    )
    retention_percentage: float = Field(
        ...,
        ge=0.0,
        le=200.0,
        description="Audience retention percentage at this time offset",
    )
    relative_retention: float | None = Field(
        default=None,
        ge=0.0,
        description="Retention relative to channel / platform average at this point",
    )


class TrafficSourceMetric(BaseModel):
    """Breakdown of views by traffic source."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    source: str = Field(
        ...,
        min_length=1,
        description="Traffic source name (e.g. youtube_search, suggested_videos, browse_features)",
    )
    views: int = Field(..., ge=0, description="Views originating from this source")
    percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage share of total views"
    )


class GeographyMetric(BaseModel):
    """Breakdown of views by country geography."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    country_code: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"
    )
    views: int = Field(..., ge=0, description="Views from this country")
    percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage share of total views"
    )


class DeviceMetric(BaseModel):
    """Breakdown of views by device category."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    device_type: str = Field(
        ...,
        min_length=1,
        description="Device type (desktop, mobile_phone, tablet, tv)",
    )
    views: int = Field(..., ge=0, description="Views from this device type")
    percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage share of total views"
    )


class DerivedVideoFeatures(BaseModel):
    """Croviq-derived analytical features extracted from video content and structure."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    content_pillar: ContentPillar = Field(
        ..., description="Primary content pillar classification"
    )
    video_format: VideoFormat = Field(
        ..., description="Structural format of the video"
    )
    title_style: TitleStyle = Field(
        ..., description="Stylistic framing of the video title"
    )
    first_demo_seconds: int = Field(
        ...,
        ge=0,
        description="Elapsed seconds until the first practical demonstration / code",
    )
    hook_length_seconds: int = Field(
        ..., ge=0, description="Length of opening premise / hook in seconds"
    )
    setup_time_seconds: int = Field(
        ..., ge=0, description="Elapsed seconds spent on theoretical intro / setup"
    )
    topic_cluster: str = Field(
        ..., min_length=1, description="Topical grouping for clustering analysis"
    )
    is_time_sensitive_topic: bool = Field(
        ..., description="Whether the topic is time-sensitive (e.g. new model release)"
    )


class VideoPublicMetadata(BaseModel):
    """Public YouTube-style video metadata."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, validate_assignment=True
    )

    video_id: str = Field(..., min_length=1, description="Unique video identifier")
    title: str = Field(..., min_length=1, description="Video title")
    description: str = Field(..., description="Video description text")
    tags: list[str] = Field(default_factory=list, description="Video keyword tags")
    duration_seconds: int = Field(
        ..., ge=1, description="Total video runtime in seconds"
    )
    published_at: datetime = Field(
        ..., description="UTC timestamp when video was published"
    )
    view_count: int = Field(..., ge=0, description="Public view count")
    like_count: int = Field(..., ge=0, description="Public like count")
    comment_count: int = Field(..., ge=0, description="Public comment count")
    thumbnail_url: str = Field(..., description="Thumbnail asset URL")
    category_id: str = Field(
        default="28", description="YouTube category ID (default 28: Science & Tech)"
    )

    @field_validator("published_at")
    @classmethod
    def check_timezone_aware(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class VideoPrivateAnalytics(BaseModel):
    """Private analytics-shaped performance metrics for a single video."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    views: int = Field(..., ge=0, description="Total authenticated views")
    watch_time_minutes: float = Field(
        ..., ge=0.0, description="Total watch time in minutes"
    )
    avg_view_duration_seconds: float = Field(
        ..., ge=0.0, description="Average view duration in seconds"
    )
    avg_view_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Average view percentage (duration / total_duration)",
    )
    subscribers_gained: int = Field(
        ..., ge=0, description="Subscribers gained from this video"
    )
    subscribers_lost: int = Field(
        ..., ge=0, description="Subscribers lost during this video"
    )
    likes: int = Field(..., ge=0, description="Total likes")
    comments: int = Field(..., ge=0, description="Total comments")
    shares: int = Field(..., ge=0, description="Total shares")
    impressions: int = Field(
        ..., ge=0, description="Thumbnail impressions served by YouTube"
    )
    ctr_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Thumbnail click-through rate percentage"
    )
    estimated_revenue_usd: float | None = Field(
        default=None, ge=0.0, description="Estimated monetization revenue in USD"
    )
    retention_curve: list[RetentionPoint] = Field(
        ..., description="Audience retention curve sample points (0 to 100%)"
    )
    traffic_sources: list[TrafficSourceMetric] = Field(
        ..., description="Traffic source distribution"
    )
    geography: list[GeographyMetric] = Field(
        ..., description="Top audience geographies"
    )
    device_types: list[DeviceMetric] = Field(
        ..., description="Device category distribution"
    )


class ChannelVideo(BaseModel):
    """Unified representation of a channel video with public, private, and derived data."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    video_id: str = Field(..., min_length=1, description="Unique video identifier")
    public: VideoPublicMetadata = Field(
        ..., description="Public-style YouTube metadata"
    )
    analytics: VideoPrivateAnalytics = Field(
        ..., description="Private analytics-shaped performance data"
    )
    derived: DerivedVideoFeatures = Field(
        ..., description="Croviq-derived analytical features"
    )


class ChannelPublicMetadata(BaseModel):
    """Public YouTube-style channel metadata."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, validate_assignment=True
    )

    channel_id: str = Field(..., min_length=1, description="Unique channel identifier")
    title: str = Field(..., min_length=1, description="Channel title")
    description: str = Field(..., description="Channel description")
    custom_url: str = Field(..., description="Channel handle / custom URL")
    subscriber_count: int = Field(
        ..., ge=0, description="Current public subscriber count"
    )
    video_count: int = Field(..., ge=0, description="Total public video count")
    total_views: int = Field(..., ge=0, description="Total lifetime public views")
    joined_at: datetime = Field(
        ..., description="UTC timestamp when channel was created"
    )
    country: str = Field(default="US", description="Channel origin country code")
    avatar_url: str | None = Field(default=None, description="Channel avatar image URL")
    banner_url: str | None = Field(default=None, description="Channel banner image URL")

    @field_validator("joined_at")
    @classmethod
    def check_timezone_aware(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class ChannelAnalyticsPoint(BaseModel):
    """Canonical daily channel analytics returned by every Channel Data Provider."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    date: date
    views: int = Field(..., ge=0)
    watch_time_minutes: float = Field(..., ge=0)
    subscribers_gained: int = Field(..., ge=0)
    subscribers_lost: int = Field(..., ge=0)
    average_view_percentage: float = Field(..., ge=0, le=100)


class ChannelAnalyticsTimeSeries(BaseModel):
    """Chronological daily channel metrics for a bounded inclusive period."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    start_date: date
    end_date: date
    points: list[ChannelAnalyticsPoint]
    is_modeled: bool = Field(
        default=False,
        description="True only for deterministically modeled sample-channel daily distribution.",
    )


class ChannelPrivateAnalytics(BaseModel):
    """Aggregated private channel analytics metrics."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_views: int = Field(..., ge=0, description="Total channel views")
    total_watch_time_hours: float = Field(
        ..., ge=0.0, description="Total channel watch time in hours"
    )
    current_subscribers: int = Field(
        ..., ge=0, description="Current net subscriber count"
    )
    total_subscribers_gained: int = Field(
        ..., ge=0, description="Lifetime subscribers gained"
    )
    total_subscribers_lost: int = Field(
        ..., ge=0, description="Lifetime subscribers lost"
    )
    avg_view_duration_seconds: float = Field(
        ..., ge=0.0, description="Channel-wide average view duration in seconds"
    )
    avg_ctr_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Channel-wide average CTR percentage"
    )
    total_impressions: int = Field(
        ..., ge=0, description="Lifetime thumbnail impressions"
    )
    top_traffic_sources: list[TrafficSourceMetric] = Field(
        ..., description="Aggregate channel traffic sources"
    )
    top_geographies: list[GeographyMetric] = Field(
        ..., description="Aggregate audience geography breakdown"
    )
    device_distribution: list[DeviceMetric] = Field(
        ..., description="Aggregate device type distribution"
    )


class DerivedChannelFeatures(BaseModel):
    """Croviq-derived intelligence and baselines for the channel."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    primary_niche: str = Field(
        ..., min_length=1, description="Inferred primary channel niche"
    )
    content_pillars: list[ContentPillar] = Field(
        ..., description="Active content pillars for the channel"
    )
    high_performing_formats: list[VideoFormat] = Field(
        ..., description="Formats that consistently outperform channel baselines"
    )
    weak_formats: list[VideoFormat] = Field(
        ..., description="Formats with below-baseline retention or CTR"
    )
    average_publish_interval_days: float = Field(
        ..., ge=0.0, description="Average days between video releases"
    )
    inferred_audience_level: str = Field(
        ..., description="Inferred technical depth of the target audience"
    )


class Channel(BaseModel):
    """Canonical Channel model for Croviq, unifying public metadata, private analytics, and derived intelligence."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    channel_id: str = Field(..., min_length=1, description="Unique channel identifier")
    source_type: str = Field(
        ..., description="Source origin: 'synthetic' or 'youtube'"
    )
    public: ChannelPublicMetadata = Field(
        ..., description="Public YouTube-style metadata"
    )
    analytics: ChannelPrivateAnalytics = Field(
        ..., description="Aggregated private performance analytics"
    )
    derived: DerivedChannelFeatures = Field(
        ..., description="Croviq-derived channel intelligence"
    )
    videos: list[ChannelVideo] = Field(
        ..., description="Historical video list with per-video analytics and features"
    )


class SampleChannelFixture(BaseModel):
    """Root model for the static committed sample channel dataset fixture."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    fixture_version: str = Field(
        ..., min_length=1, description="Version string of the fixture (e.g. 1.0.0)"
    )
    schema_version: str = Field(
        ..., min_length=1, description="Schema version string (e.g. 1.0.0)"
    )
    source_type: str = Field(
        default="synthetic", description="Source type identifier: strictly synthetic"
    )
    generated_by: str = Field(
        ..., description="Script or tool that generated this fixture"
    )
    seed: int = Field(..., description="Deterministic random seed used for generation")
    generated_at: datetime = Field(
        ..., description="UTC timestamp when fixture was generated"
    )
    video_count: int = Field(
        ..., ge=1, description="Exact number of videos contained in fixture"
    )
    channel: Channel = Field(..., description="Canonical Channel object")

    @field_validator("generated_at")
    @classmethod
    def check_timezone_aware(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)
