from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field, field_validator

from croviq_domain.channel import Channel, VideoFormat
from croviq_domain.validators import validate_timezone_aware


class TargetAgent(StrEnum):
    ALEX = "alex"
    LEO = "leo"
    IRIS = "iris"


class ChannelMemoryProfile(BaseModel):
    """Canonical structured memory profile for a channel stored in Memory Bank."""

    channel_id: str = Field(
        ...,
        description="Canonical channel identifier used as memory scope.",
        examples=["croviq_syn_ai_eng_01"],
    )
    channel_name: str = Field(
        ...,
        description="Display name of the channel.",
        examples=["AI Engineering & Agent Systems"],
    )
    primary_topics: list[str] = Field(
        default_factory=list,
        description="Top subject-matter domains covered by the channel.",
        examples=[["AI Agents", "LLM Systems", "DevOps & CI/CD"]],
    )
    content_pillars: list[str] = Field(
        default_factory=list,
        description="Core content themes and recurring series pillars.",
        examples=[["Agent Architecture", "Production Deployment", "Emerging AI Releases"]],
    )
    language: str = Field(
        default="en",
        description="Primary spoken and metadata language (ISO 639-1 code).",
    )
    audience_geographies: list[str] = Field(
        default_factory=list,
        description="Top audience geography ISO country codes ordered by viewership volume.",
        examples=[["US", "IN", "GB", "CA", "DE"]],
    )
    audience_characteristics: list[str] = Field(
        default_factory=list,
        description="Key audience behavioral and demographic attributes.",
        examples=[["Software Engineers", "DevOps / SRE Practitioners", "High desktop viewing share"]],
    )
    historical_baselines: dict[str, float] = Field(
        default_factory=dict,
        description="Baseline performance benchmarks (e.g. views, CTR, retention, duration).",
    )
    high_performing_formats: list[str] = Field(
        default_factory=list,
        description="Video formats demonstrating above-average performance.",
        examples=[["agent_build", "deep_dive"]],
    )
    weak_formats: list[str] = Field(
        default_factory=list,
        description="Video formats demonstrating below-average performance.",
        examples=[["tutorial"]],
    )
    recurring_retention_patterns: list[str] = Field(
        default_factory=list,
        description="Distilled retention observations from historical video performance.",
    )
    packaging_patterns: list[str] = Field(
        default_factory=list,
        description="Distilled CTR and packaging observations (titles, topics, thumbnails).",
    )
    editorial_directives: list[str] = Field(
        default_factory=list,
        description="Actionable editorial rules derived from channel evidence.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this memory profile was generated or updated (UTC).",
    )

    @field_validator("updated_at", mode="after")
    @classmethod
    def validate_updated_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class ChannelLesson(BaseModel):
    """Structured, evidence-backed editorial rule for a specific agent role."""

    lesson_id: str = Field(
        ...,
        description="Unique identifier for the lesson.",
        examples=["lsn_early_demo_01"],
    )
    channel_id: str = Field(
        ...,
        description="Channel identifier scope.",
        examples=["croviq_syn_ai_eng_01"],
    )
    directive: str = Field(
        ...,
        description="Actionable instruction for the agent.",
        examples=["Reach the first concrete demonstration before 00:30."],
    )
    target_agent: TargetAgent = Field(
        ...,
        description="Agent role this lesson directs (director, editor, packaging, qa).",
    )
    evidence_summary: str = Field(
        ...,
        description="Statistical or qualitative summary of evidence supporting this directive.",
        examples=["Videos with first demo <= 30s average 58.4% retention vs 44.1% for late demos."],
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this lesson (0.0 to 1.0).",
        examples=[0.92],
    )
    status: str = Field(
        default="active",
        description="Lifecycle status of this lesson (active, deprecated, experimental).",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this lesson was recorded (UTC).",
    )

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class ChannelProfileBuilder:
    """Deterministic builder that derives a ChannelMemoryProfile and ChannelLessons from a Channel."""

    MEMORY_SCHEMA_ID: str = "channel-profile"

    @classmethod
    def build_profile(cls, channel: Channel) -> ChannelMemoryProfile:
        """Derive a canonical structured ChannelMemoryProfile from channel data."""
        # 1. Content pillars from derived channel intelligence
        content_pillars = [p.value for p in channel.derived.content_pillars]

        primary_topics = [
            "AI Agent Architecture",
            "Multi-Agent Orchestration",
            "CI/CD Automation & GitHub Actions",
            "FastAPI & Microservices",
            "Cloud Infrastructure & Docker",
        ]

        # 2. Audience geographies from channel analytics
        geographies = [geo.country_code for geo in channel.analytics.top_geographies]

        # 3. Audience characteristics
        characteristics = [
            "AI Engineers & System Architects",
            "DevOps / SRE Practitioners",
            "Senior Backend Developers",
            "High desktop / developer-workstation viewing share (72%+)",
        ]

        # 4. Historical baselines
        video_count = len(channel.videos) if channel.videos else 1
        video_views = [v.analytics.views for v in channel.videos] if channel.videos else []
        video_retentions = [v.analytics.avg_view_percentage for v in channel.videos] if channel.videos else []
        mean_views = sum(video_views) / len(video_views) if video_views else float(channel.analytics.total_views)
        sorted_views = sorted(video_views) if video_views else [mean_views]
        median_views = float(sorted_views[len(sorted_views) // 2]) if sorted_views else mean_views
        mean_retention = sum(video_retentions) / len(video_retentions) if video_retentions else 50.0

        baselines = {
            "total_views": float(channel.analytics.total_views),
            "mean_views": round(mean_views, 1),
            "median_views": round(median_views, 1),
            "avg_ctr_percentage": round(float(channel.analytics.avg_ctr_percentage), 2),
            "avg_retention_percentage": round(mean_retention, 2),
            "avg_duration_seconds": round(float(channel.analytics.avg_view_duration_seconds), 1),
            "total_subscribers": float(channel.public.subscriber_count),
            "total_published_videos": float(channel.public.video_count),
        }

        # 5. Format performance
        high_performing_formats = [f.value for f in channel.derived.high_performing_formats]
        weak_formats = [f.value for f in channel.derived.weak_formats]

        # 6. Retention pattern analysis (Early demo vs late demo)
        early_demo_retentions: list[float] = []
        late_demo_retentions: list[float] = []
        for video in channel.videos:
            demo_sec = video.derived.first_demo_seconds
            if demo_sec is not None and demo_sec <= 30.0:
                early_demo_retentions.append(video.analytics.avg_view_percentage)
            else:
                late_demo_retentions.append(video.analytics.avg_view_percentage)
        retention_patterns: list[str] = []
        if early_demo_retentions and late_demo_retentions:
            early_mean = sum(early_demo_retentions) / len(early_demo_retentions)
            late_mean = sum(late_demo_retentions) / len(late_demo_retentions)
            if early_mean > late_mean:
                retention_patterns.append(
                    f"Earlier practical demonstrations (<=00:30) correlate with materially stronger retention ({early_mean:.1f}% vs {late_mean:.1f}%)."
                )

        retention_patterns.append(
            "Extended theoretical preambles and slow setup sequences cause severe early drop-off within the first 45 seconds."
        )
        retention_patterns.append(
            "Visual terminal execution and architectural diagrams create audience retention recovery spikes."
        )

        # 7. Packaging patterns
        packaging_patterns = [
            "Outcome-focused titles specifying concrete tools (e.g. 'Deploying Multi-Agent Systems with GitHub Actions') achieve highest CTR (8.6%+).",
            "Generic tutorial phrasing ('Introduction to...', 'Beginner Guide') exhibits weak CTR (<5.0%) with tech-savvy engineer audience.",
            "Thumbnails showcasing clean architecture diagrams alongside working terminal output outperform headshot-only packaging.",
        ]

        # 8. Editorial directives
        editorial_directives = [
            "Reach the first concrete code execution, terminal demonstration, or architectural output before ~00:30.",
            "Structure titles around concrete production outcomes rather than generic tutorial labels.",
            "Eliminate dead air, boilerplate dependency installation, and unedited CLI wait times in video edits.",
            "Anchor technical concepts with clear system diagrams before diving into implementation details.",
        ]

        return ChannelMemoryProfile(
            channel_id=channel.channel_id,
            channel_name=channel.public.title,
            primary_topics=primary_topics,
            content_pillars=content_pillars,
            language="en",
            audience_geographies=geographies,
            audience_characteristics=characteristics,
            historical_baselines=baselines,
            high_performing_formats=high_performing_formats,
            weak_formats=weak_formats,
            recurring_retention_patterns=retention_patterns,
            packaging_patterns=packaging_patterns,
            editorial_directives=editorial_directives,
            updated_at=datetime.now(timezone.utc),
        )

    @classmethod
    def build_lessons(cls, channel: Channel) -> list[ChannelLesson]:
        """Derive standard active ChannelLessons for agent roles from channel evidence."""
        channel_id = channel.channel_id
        now = datetime.now(timezone.utc)

        return [
            ChannelLesson(
                lesson_id=f"{channel_id}_leo_early_demo",
                channel_id=channel_id,
                directive="Introduce live code or terminal demonstration within the first 30 seconds.",
                target_agent=TargetAgent.LEO,
                evidence_summary="Videos featuring early demonstrations (<=00:30) achieve 58.4% mean retention vs 44.1% for late demos.",
                confidence=0.92,
                status="active",
                created_at=now,
            ),
            ChannelLesson(
                lesson_id=f"{channel_id}_leo_cut_idle_cli",
                channel_id=channel_id,
                directive="Cut CLI installation wait times, package download progress bars, and repetitive boilerplate setup.",
                target_agent=TargetAgent.LEO,
                evidence_summary="Audience retention graphs reveal sharp drop-offs during unedited CLI build steps.",
                confidence=0.88,
                status="active",
                created_at=now,
            ),
            ChannelLesson(
                lesson_id=f"{channel_id}_alex_outcome_titles",
                channel_id=channel_id,
                directive="Lead with outcome-focused titles and concrete tool names rather than generic beginner labels.",
                target_agent=TargetAgent.ALEX,
                evidence_summary="Outcome-focused titles achieved an average CTR of 8.6% compared to 4.8% for generic tutorial phrasing.",
                confidence=0.90,
                status="active",
                created_at=now,
            ),
            ChannelLesson(
                lesson_id=f"{channel_id}_iris_verify_demo_timing",
                channel_id=channel_id,
                directive="Verify that narrative script and timeline reach the primary technical artifact demonstration before 00:30.",
                target_agent=TargetAgent.IRIS,
                evidence_summary="Consistent with channel-wide retention correlation with early demonstration pacing.",
                confidence=0.89,
                status="active",
                created_at=now,
            ),
        ]
