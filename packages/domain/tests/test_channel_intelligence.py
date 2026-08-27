from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from croviq_domain.channel_intelligence import (
    ChannelExperiment,
    ChannelInsight,
    ExperimentStatus,
    FindingLifecycle,
    InsightEvidence,
    InsightType,
    ResearchCadence,
    ResearchConfig,
    ResearchFinding,
    ResearchPrompt,
    ResearchRun,
    ResearchRunStatus,
    SourceCitation,
)


NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def test_research_config_advances_from_scheduled_time() -> None:
    config = ResearchConfig(
        workspace_id="workspace-1",
        channel_id="channel-1",
        cadence=ResearchCadence.EVERY_6_HOURS,
        prompts=[ResearchPrompt(prompt_id="topics", text="Find relevant AI engineering topics")],
        next_run_at=NOW,
        updated_at=NOW,
    )

    assert config.next_scheduled_at() == NOW + timedelta(hours=6)


def test_research_prompt_rejects_internal_sources() -> None:
    for source in ("localhost", "127.0.0.1", "http://169.254.169.254/latest", "10.0.0.8"):
        with pytest.raises(ValidationError):
            ResearchPrompt(prompt_id="unsafe", text="Inspect this source", preferred_sources=[source])


def test_research_finding_requires_citation() -> None:
    with pytest.raises(ValidationError):
        ResearchFinding(
            finding_id="finding-1",
            run_id="run-1",
            channel_id="channel-1",
            category="TOPIC",
            title="New agent capability",
            summary="A capability was announced.",
            why_it_matters="The channel covers this topic.",
            relevance_score=0.8,
            freshness_score=0.9,
            opportunity_score=0.85,
            topic_fingerprint="agent-capability|example.com",
            discovered_at=NOW,
            lifecycle=FindingLifecycle.NEW,
            source_citations=[],
        )


def test_insight_and_experiment_keep_evidence_explicit() -> None:
    evidence = InsightEvidence(
        kind="FACT",
        statement="Latest-video subscriber conversion is 43% above the channel median.",
        metric_refs=["video:latest:subscriber_conversion", "channel:median:subscriber_conversion"],
    )
    insight = ChannelInsight(
        insight_id="insight-1",
        channel_id="channel-1",
        type=InsightType.PERFORMANCE,
        title="Subscriber conversion accelerated",
        statement=evidence.statement,
        evidence=[evidence],
        confidence=0.91,
        recommended_action="Publish a follow-up while the topic remains relevant.",
        created_at=NOW,
    )
    experiment = ChannelExperiment(
        experiment_id="experiment-1",
        channel_id="channel-1",
        hypothesis="Showing the first code execution before 00:30 improves average retention.",
        primary_metric="averageViewPercentage",
        baseline_value=52.4,
        expected_direction="INCREASE",
        status=ExperimentStatus.PROPOSED,
        started_at=None,
        completed_at=None,
        video_ids=[],
        result=None,
        effect_size=None,
        confidence_summary="Proposed from a historical association; causality is not established.",
        created_by="alex",
    )

    assert insight.evidence[0].kind == "FACT"
    assert experiment.status is ExperimentStatus.PROPOSED


def test_research_run_uses_deterministic_scheduled_key() -> None:
    run = ResearchRun.for_schedule(
        workspace_id="workspace-1",
        channel_id="channel-1",
        scheduled_at=NOW,
        model="gemini-3.7-flash",
    )

    assert run.run_id == "workspace-1:channel-1:2026-08-28T12:00:00+00:00"
    assert run.status is ResearchRunStatus.PENDING


def test_source_citation_requires_public_http_url() -> None:
    with pytest.raises(ValidationError):
        SourceCitation(
            url="file:///etc/passwd",
            title="Unsafe",
            domain="localhost",
        )
