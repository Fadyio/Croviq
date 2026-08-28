import asyncio
from datetime import date

import pytest

from croviq_domain.channel_dashboard import build_channel_dashboard
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.channel_intelligence import EvidenceKind, ExperimentStatus


def test_sample_dashboard_is_computed_from_canonical_fixture() -> None:
    dashboard = asyncio.run(
        build_channel_dashboard(
            SampleChannelDataProvider(),
            days=28,
            end_date=date(2026, 8, 26),
        )
    )

    assert dashboard.channel.channel_id == "croviq_syn_ai_eng_01"
    assert dashboard.channel.source_type == "synthetic"
    assert [metric.metric for metric in dashboard.kpis] == [
        "views",
        "watch_time_hours",
        "net_subscribers",
        "average_retention",
    ]
    assert all(metric.current_value >= 0 for metric in dashboard.kpis)
    assert len(dashboard.trend) == 28
    assert dashboard.trend[0].date == date(2026, 7, 30)
    assert dashboard.trend[-1].date == date(2026, 8, 26)
    assert dashboard.is_sample_modeled_timeseries is True


def test_latest_video_analysis_uses_channel_baselines() -> None:
    dashboard = asyncio.run(
        build_channel_dashboard(
            SampleChannelDataProvider(), days=90, end_date=date(2026, 8, 26)
        )
    )

    latest = dashboard.latest_video
    assert latest.video_id == "vid_syn_100"
    assert latest.views == 23_314
    assert latest.subscribers_gained == 334
    assert latest.subscribers_lost == 31
    assert latest.net_subscribers == 303
    assert latest.subscriber_conversion_delta_percentage == pytest.approx(-2.84, abs=0.01)
    assert latest.retention_delta_points == pytest.approx(-25.61, abs=0.01)


def test_dashboard_contains_evidence_backed_insight_and_experiment() -> None:
    dashboard = asyncio.run(
        build_channel_dashboard(
            SampleChannelDataProvider(), days=365, end_date=date(2026, 8, 26)
        )
    )

    assert dashboard.insights
    assert all(insight.evidence for insight in dashboard.insights)
    assert all(
        evidence.kind in {EvidenceKind.FACT, EvidenceKind.INFERENCE}
        for insight in dashboard.insights
        for evidence in insight.evidence
    )
    assert dashboard.proposed_experiment.status is ExperimentStatus.PROPOSED
    assert dashboard.proposed_experiment.primary_metric == "averageViewPercentage"
    assert dashboard.proposed_experiment.baseline_value == pytest.approx(59.01, abs=0.01)
    assert dashboard.topic_clusters[0].median_views > 0
    assert len(dashboard.video_performance) == 100


def test_sample_timeseries_does_not_drop_to_zero_at_later_end_date() -> None:
    dashboard = asyncio.run(
        build_channel_dashboard(
            SampleChannelDataProvider(),
            days=28,
            end_date=date(2026, 8, 28),
        )
    )

    assert len(dashboard.trend) == 28
    assert dashboard.trend[-1].date == date(2026, 8, 28)
    # Trailing dates beyond fixture generated_at must not drop to 0
    for point in dashboard.trend:
        assert point.views > 500, f"Expected non-zero views on {point.date}, got {point.views}"
        assert point.watch_time_hours > 50.0
        assert point.net_subscribers != 0
