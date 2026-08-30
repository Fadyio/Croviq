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


def test_recent_video_performance_ordering_and_comparisons() -> None:
    dashboard = asyncio.run(
        build_channel_dashboard(
            SampleChannelDataProvider(), days=28, end_date=date(2026, 8, 26)
        )
    )

    assert len(dashboard.recent_videos) == 5
    assert dashboard.channel_baselines is not None
    assert dashboard.channel_baselines.sample_size == 100
    assert dashboard.channel_baselines.median_views == pytest.approx(29769.5, abs=0.5)
    assert dashboard.channel_baselines.median_retention == pytest.approx(58.98, abs=0.1)
    assert dashboard.channel_baselines.median_ctr == pytest.approx(7.78, abs=0.1)

    # Verify ordered descending by published_at
    for i in range(len(dashboard.recent_videos) - 1):
        assert dashboard.recent_videos[i].published_at >= dashboard.recent_videos[i + 1].published_at

    # Latest video
    v1 = dashboard.recent_videos[0]
    assert v1.video_id == "vid_syn_100"
    assert v1.is_latest is True
    assert v1.views == 23_314
    assert v1.average_retention == pytest.approx(33.4, abs=0.01)
    assert v1.ctr_percentage == pytest.approx(4.29, abs=0.01)
    assert v1.subscribers_gained == 334
    assert v1.subscribers_lost == 31
    assert v1.net_subscribers == 303
    assert v1.subs_per_1k == pytest.approx(14.33, abs=0.01)
    assert v1.retention_delta_points == pytest.approx(-25.58, abs=0.1)
    assert v1.alex_interpretation is not None
    assert "Retention is the main weakness here" in v1.alex_interpretation
    assert "25.6 points below your channel median" in v1.alex_interpretation
    assert v1.alex_next_action == "Inspect the first 30 seconds for delayed demonstration or setup."

    # Non-latest videos
    v2 = dashboard.recent_videos[1]
    assert v2.video_id == "vid_syn_099"
    assert v2.is_latest is False
    assert v2.alex_interpretation is None

def test_dashboard_contains_evidence_backed_insight_and_experiment() -> None:
    dashboard = asyncio.run(
        build_channel_dashboard(
            SampleChannelDataProvider(), days=365, end_date=date(2026, 8, 26)
        )
    )

    assert len(dashboard.insights) == 1
    insight = dashboard.insights[0]
    assert insight.title == "First demonstration timing tracks retention"
    assert "60.6%" in insight.statement
    assert "37.6%" in insight.statement
    assert insight.confidence is None
    assert not insight.recommended_action.startswith("ACTION:")
    assert insight.evidence_stats is not None
    assert insight.evidence_stats.eligible_video_count == 100
    assert insight.evidence_stats.early_count == 65
    assert insight.evidence_stats.late_count == 35
    assert insight.evidence_stats.early_mean_retention == pytest.approx(60.56, abs=0.01)
    assert insight.evidence_stats.late_mean_retention == pytest.approx(37.60, abs=0.01)
    assert insight.evidence_stats.delta_percentage_points == pytest.approx(22.96, abs=0.01)
    assert insight.evidence_stats.correlation == pytest.approx(-0.9638, abs=0.01)
    assert insight.evidence_stats.threshold_seconds == 30.0
    assert all(
        evidence.kind in {EvidenceKind.FACT, EvidenceKind.INFERENCE}
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


def test_build_channel_dashboard_handles_sparse_historical_timeseries() -> None:
    from croviq_domain.channel import ChannelAnalyticsPoint, ChannelAnalyticsTimeSeries

    class SparseTimeseriesProvider(SampleChannelDataProvider):
        async def get_channel_timeseries(
            self, *, start_date: date, end_date: date
        ) -> ChannelAnalyticsTimeSeries:
            full_series = await super().get_channel_timeseries(start_date=start_date, end_date=end_date)
            # Truncate points to only the current period (simulating sparse/missing historical days)
            cutoff = end_date - timedelta(days=28)
            sparse_points = [p for p in full_series.points if p.date > cutoff]
            return ChannelAnalyticsTimeSeries(
                start_date=start_date,
                end_date=end_date,
                points=sparse_points,
                is_modeled=False,
            )

    from datetime import timedelta
    dashboard = asyncio.run(
        build_channel_dashboard(
            SparseTimeseriesProvider(),
            days=28,
            end_date=date(2026, 8, 28),
        )
    )
    assert len(dashboard.trend) == 28
    assert dashboard.trend[0].views > 0
