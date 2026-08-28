from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
import ipaddress
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class ResearchCadence(StrEnum):
    EVERY_HOUR = "EVERY_HOUR"
    EVERY_6_HOURS = "EVERY_6_HOURS"
    EVERY_12_HOURS = "EVERY_12_HOURS"
    EVERY_DAY = "EVERY_DAY"
    EVERY_3_DAYS = "EVERY_3_DAYS"
    EVERY_WEEK = "EVERY_WEEK"

    @property
    def interval(self) -> timedelta:
        return {
            ResearchCadence.EVERY_HOUR: timedelta(hours=1),
            ResearchCadence.EVERY_6_HOURS: timedelta(hours=6),
            ResearchCadence.EVERY_12_HOURS: timedelta(hours=12),
            ResearchCadence.EVERY_DAY: timedelta(days=1),
            ResearchCadence.EVERY_3_DAYS: timedelta(days=3),
            ResearchCadence.EVERY_WEEK: timedelta(weeks=1),
        }[self]

    def next_run_after(self, scheduled_at: datetime) -> datetime:
        return scheduled_at + self.interval


class ResearchRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FindingLifecycle(StrEnum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    SEEN = "SEEN"
    EXPIRED = "EXPIRED"


class InsightType(StrEnum):
    PERFORMANCE = "PERFORMANCE"
    RETENTION = "RETENTION"
    AUDIENCE = "AUDIENCE"
    TRAFFIC = "TRAFFIC"
    TOPIC = "TOPIC"
    EXPERIMENT = "EXPERIMENT"


class EvidenceKind(StrEnum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    RESEARCH = "RESEARCH"
    RECOMMENDATION = "RECOMMENDATION"


class ExperimentStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    INCONCLUSIVE = "INCONCLUSIVE"


def _validate_public_source(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("source cannot be empty")
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source must be an HTTP(S) URL or domain")
    hostname = parsed.hostname.rstrip(".").lower()
    if parsed.username or parsed.password:
        raise ValueError("source credentials are not allowed")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("private or internal sources are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return candidate
    if not address.is_global:
        raise ValueError("private or reserved IP sources are not allowed")
    return candidate


class ResearchPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prompt_id: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=4000)
    enabled: bool = True
    use_broad_web_search: bool = True
    preferred_sources: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("preferred_sources")
    @classmethod
    def validate_sources(cls, values: list[str]) -> list[str]:
        return [_validate_public_source(value) for value in values]


class ResearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    workspace_id: str = Field(..., min_length=1)
    channel_id: str = Field(..., min_length=1)
    enabled: bool = True
    cadence: ResearchCadence
    prompts: list[ResearchPrompt] = Field(default_factory=list, max_length=20)
    last_run_at: datetime | None = None
    next_run_at: datetime
    updated_at: datetime

    @field_validator("last_run_at", "next_run_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return validate_timezone_aware(value) if value is not None else None

    def next_scheduled_at(self, scheduled_at: datetime | None = None) -> datetime:
        return (scheduled_at or self.next_run_at) + self.cadence.interval


class ResearchRun(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    run_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    channel_id: str = Field(..., min_length=1)
    scheduled_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: ResearchRunStatus
    model: str = Field(..., min_length=1)
    findings_count: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    search_queries: list[str] = Field(default_factory=list)
    error_code: str | None = None

    @field_validator("scheduled_at", "started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return validate_timezone_aware(value) if value is not None else None

    @classmethod
    def for_schedule(
        cls,
        *,
        workspace_id: str,
        channel_id: str,
        scheduled_at: datetime,
        model: str,
    ) -> ResearchRun:
        scheduled_at = validate_timezone_aware(scheduled_at)
        run_id = f"{workspace_id}:{channel_id}:{scheduled_at.isoformat()}"
        return cls(
            run_id=run_id,
            workspace_id=workspace_id,
            channel_id=channel_id,
            scheduled_at=scheduled_at,
            status=ResearchRunStatus.PENDING,
            model=model,
        )


class SourceCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str
    title: str = Field(..., min_length=1, max_length=500)
    domain: str = Field(..., min_length=1, max_length=253)
    published_at: datetime | None = None
    grounding_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        validated = _validate_public_source(value)
        if "://" not in validated:
            raise ValueError("citation must contain a full HTTP(S) URL")
        return validated

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime | None) -> datetime | None:
        return validate_timezone_aware(value) if value is not None else None


class ResearchFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    finding_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    channel_id: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1, max_length=4000)
    why_it_matters: str = Field(..., min_length=1, max_length=4000)
    relevance_score: float = Field(..., ge=0, le=1)
    freshness_score: float = Field(..., ge=0, le=1)
    opportunity_score: float = Field(..., ge=0, le=1)
    source_citations: list[SourceCitation] = Field(..., min_length=1)
    topic_fingerprint: str = Field(..., min_length=1)
    topic_cluster: str | None = None
    primary_entity: str | None = None
    novelty_score: float | None = Field(default=None, ge=0, le=1)
    discovered_at: datetime
    updated_at: datetime | None = None
    expires_at: datetime | None = None
    lifecycle: FindingLifecycle = FindingLifecycle.NEW

    @field_validator("discovered_at", "updated_at", "expires_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return validate_timezone_aware(value) if value is not None else None


class InsightEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: EvidenceKind
    statement: str = Field(..., min_length=1, max_length=2000)
    metric_refs: list[str] = Field(default_factory=list)
    citation_urls: list[str] = Field(default_factory=list)


class ChannelInsight(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    insight_id: str = Field(..., min_length=1)
    channel_id: str = Field(..., min_length=1)
    type: InsightType
    title: str = Field(..., min_length=1, max_length=500)
    statement: str = Field(..., min_length=1, max_length=2000)
    evidence: list[InsightEvidence] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    recommended_action: str = Field(..., min_length=1, max_length=2000)
    created_at: datetime
    expires_at: datetime | None = None

    @field_validator("created_at", "expires_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return validate_timezone_aware(value) if value is not None else None


class ChannelExperiment(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    experiment_id: str = Field(..., min_length=1)
    channel_id: str = Field(..., min_length=1)
    hypothesis: str = Field(..., min_length=1, max_length=2000)
    primary_metric: str = Field(..., min_length=1)
    baseline_value: float
    expected_direction: str = Field(..., pattern="^(INCREASE|DECREASE)$")
    status: ExperimentStatus
    started_at: datetime | None
    completed_at: datetime | None
    video_ids: list[str]
    result: str | None
    effect_size: float | None
    confidence_summary: str = Field(..., min_length=1, max_length=2000)
    created_by: str = Field(..., min_length=1)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return validate_timezone_aware(value) if value is not None else None

    @model_validator(mode="after")
    def validate_completion(self) -> ChannelExperiment:
        if self.status in {ExperimentStatus.COMPLETED, ExperimentStatus.INCONCLUSIVE}:
            if self.completed_at is None or self.result is None:
                raise ValueError("completed experiments require completed_at and result")
        return self
