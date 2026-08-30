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


def test_canonical_kpis_end_to_end_audit_and_independent_arithmetic() -> None:
    provider = SampleChannelDataProvider()
    end_date = date(2026, 8, 30)
    dashboard = asyncio.run(
        build_channel_dashboard(
            provider,
            days=28,
            end_date=end_date,
        )
    )

    # Verify 4 KPI metrics present in exact order
    assert [k.metric for k in dashboard.kpis] == [
        "views",
        "watch_time_hours",
        "net_subscribers",
        "average_retention",
    ]

    kpi_map = {k.metric: k for k in dashboard.kpis}

    # 1. Views
    views_kpi = kpi_map["views"]
    assert views_kpi.current_value == 418_498
    assert views_kpi.previous_value == 393_494
    assert views_kpi.change_percentage == pytest.approx(6.35435, abs=0.001)

    # 2. Watch time (hours converted once from minutes)
    wt_kpi = kpi_map["watch_time_hours"]
    assert wt_kpi.current_value == pytest.approx(50_428.027, abs=0.01)
    assert wt_kpi.previous_value == pytest.approx(49_811.568, abs=0.01)
    assert wt_kpi.change_percentage == pytest.approx(1.23758, abs=0.001)

    # 3. Net subscribers (gained - lost)
    subs_kpi = kpi_map["net_subscribers"]
    assert subs_kpi.current_value == 5_473
    assert subs_kpi.previous_value == 5_020
    assert subs_kpi.change_percentage == pytest.approx(9.02390, abs=0.001)

    # 4. Average retention (view-weighted average, delta in percentage points)
    ret_kpi = kpi_map["average_retention"]
    assert ret_kpi.current_value == pytest.approx(55.75219, abs=0.001)
    assert ret_kpi.previous_value == pytest.approx(56.49649, abs=0.001)
    assert ret_kpi.change_percentage == pytest.approx(-0.74430, abs=0.001)

    # Verify trend points match current daily series
    assert len(dashboard.trend) == 28
    assert dashboard.trend[0].date == date(2026, 8, 3)
    assert dashboard.trend[-1].date == date(2026, 8, 30)
    assert sum(p.views for p in dashboard.trend) == views_kpi.current_value
    assert sum(p.watch_time_hours for p in dashboard.trend) == pytest.approx(wt_kpi.current_value, abs=0.001)
    assert sum(p.net_subscribers for p in dashboard.trend) == subs_kpi.current_value
    assert sum(p.previous_views for p in dashboard.trend) == views_kpi.previous_value
    assert sum(p.previous_watch_time_hours for p in dashboard.trend) == pytest.approx(wt_kpi.previous_value, abs=0.001)
    assert sum(p.previous_net_subscribers for p in dashboard.trend) == subs_kpi.previous_value


def test_latest_video_analysis_preserves_none_deltas_when_baseline_is_missing_or_zero() -> None:
    from datetime import datetime, UTC
    from croviq_domain.channel import ChannelVideo, VideoPublicMetadata, VideoPrivateAnalytics, DerivedVideoFeatures, ContentPillar, VideoFormat, TitleStyle
    from croviq_domain.channel_dashboard import compute_latest_video_analysis, LatestVideoAnalysis

    # Create single video with 1500 views, 0 subscribers gained, and no other baseline video (baseline_views=1500, baseline_conversion=0.0)
    # Or 2 videos where baseline has 0 views and 0 conversion
    video1 = ChannelVideo(
        video_id="vid_baseline",
        public=VideoPublicMetadata(
            video_id="vid_baseline",
            title="Old Video",
            description="",
            tags=[],
            duration_seconds=300,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            view_count=0,
            like_count=0,
            comment_count=0,
            thumbnail_url="",
            category_id="28",
        ),
        analytics=VideoPrivateAnalytics(
            views=0,
            watch_time_minutes=0.0,
            avg_view_duration_seconds=0.0,
            avg_view_percentage=0.0,
            subscribers_gained=0,
            subscribers_lost=0,
            likes=0,
            comments=0,
            shares=0,
            impressions=None,
            ctr_percentage=None,
            estimated_revenue_usd=None,
            retention_curve=[],
            traffic_sources=[],
            geography=[],
            device_types=[],
        ),
        derived=DerivedVideoFeatures(
            content_pillar=ContentPillar.EMERGING_AI,
            video_format=VideoFormat.TUTORIAL,
            title_style=TitleStyle.OUTCOME_FOCUSED,
            topic_cluster="ai",
            is_time_sensitive_topic=False,
        ),
    )
    video2 = ChannelVideo(
        video_id="vid_latest",
        public=VideoPublicMetadata(
            video_id="vid_latest",
            title="Latest Video",
            description="",
            tags=[],
            duration_seconds=300,
            published_at=datetime(2026, 2, 1, tzinfo=UTC),
            view_count=2500,
            like_count=100,
            comment_count=10,
            thumbnail_url="",
            category_id="28",
        ),
        analytics=VideoPrivateAnalytics(
            views=2500,
            watch_time_minutes=150.0,
            avg_view_duration_seconds=120.0,
            avg_view_percentage=45.0,
            subscribers_gained=15,
            subscribers_lost=0,
            likes=100,
            comments=10,
            shares=5,
            impressions=None,
            ctr_percentage=None,
            estimated_revenue_usd=None,
            retention_curve=[],
            traffic_sources=[],
            geography=[],
            device_types=[],
        ),
        derived=DerivedVideoFeatures(
            content_pillar=ContentPillar.EMERGING_AI,
            video_format=VideoFormat.TUTORIAL,
            title_style=TitleStyle.OUTCOME_FOCUSED,
            topic_cluster="ai",
            is_time_sensitive_topic=False,
        ),
    )

    analysis = compute_latest_video_analysis("UC_test_channel", [video1, video2])
    assert isinstance(analysis, LatestVideoAnalysis)
    # Baseline views is 0 -> view_delta_percentage is None
    assert analysis.view_delta_percentage is None
    # Baseline conversion is 0.0 -> subscriber_conversion_delta_percentage is None
    assert analysis.subscriber_conversion_delta_percentage is None
    # Real available metrics are preserved truthfully
    assert analysis.views == 2500
    assert analysis.retention_percentage == 45.0
    assert analysis.subscribers_gained == 15
    assert analysis.net_subscribers == 15
    assert analysis.subscriber_conversion_per_1k_views == 6.0


def test_latest_video_analysis_direct_instantiation_with_none_deltas() -> None:
    from datetime import datetime, UTC
    from croviq_domain.channel_dashboard import LatestVideoAnalysis

    analysis = LatestVideoAnalysis(
        channel_id="UC_test",
        video_id="vid_001",
        title="Live Test Video",
        published_at=datetime.now(UTC),
        views=4500,
        watch_time_hours=32.5,
        subscribers_gained=25,
        subscribers_lost=2,
        net_subscribers=23,
        view_delta_percentage=None,
        subscriber_conversion_delta_percentage=None,
        retention_percentage=52.4,
        retention_delta_points=None,
    )
    assert analysis.view_delta_percentage is None
    assert analysis.subscriber_conversion_delta_percentage is None
    assert analysis.retention_delta_points is None
    assert analysis.views == 4500
    assert analysis.net_subscribers == 23
    # Verify serialization preserves None / null
    dumped = analysis.model_dump()
    assert dumped["view_delta_percentage"] is None
    assert dumped["subscriber_conversion_delta_percentage"] is None
    assert dumped["retention_delta_points"] is None
    assert dumped["views"] == 4500
def test_bug11_grounded_video_analysis_cases_a_through_f() -> None:
    from datetime import datetime, UTC
    from croviq_domain.channel import ChannelVideo, VideoPublicMetadata, VideoPrivateAnalytics, DerivedVideoFeatures, ContentPillar, VideoFormat, TitleStyle
    from croviq_domain.channel_dashboard import (
        generate_grounded_video_analysis,
        compute_recent_video_performance,
    )

    # CASE A: poor retention + normal CTR
    interp_a, action_a = generate_grounded_video_analysis(
        views=23314,
        views_delta_pct=-21.7,
        ret=33.4,
        ret_delta_pts=-25.6,
        ctr=7.5,
        ctr_delta_pts=-0.3,
        subs_per_1k=14.3,
        subs_1k_delta_pct=-2.4,
        sample_size=100,
    )
    assert "Retention is the main weakness here" in interp_a or "Retention is the primary weakness" in interp_a
    assert "25.6 points below your channel median" in interp_a
    assert "Inspect the first 30 seconds" in action_a

    # CASE B: strong retention + weak views
    interp_b, action_b = generate_grounded_video_analysis(
        views=18000,
        views_delta_pct=-39.5,
        ret=65.2,
        ret_delta_pts=6.2,
        ctr=4.2,
        ctr_delta_pts=-3.6,
        subs_per_1k=15.0,
        subs_1k_delta_pct=2.1,
        sample_size=100,
    )
    assert "Viewer engagement is strong" in interp_b or "Content retention is strong" in interp_b
    assert "+6.2 pts" in interp_b
    assert "packaging" in interp_b or "distribution" in interp_b
    assert "thumbnail" in action_b or "packaging" in action_b

    # CASE C: missing CTR
    interp_c, action_c = generate_grounded_video_analysis(
        views=30000,
        views_delta_pct=0.8,
        ret=59.0,
        ret_delta_pts=0.0,
        ctr=None,
        ctr_delta_pts=None,
        subs_per_1k=14.7,
        subs_1k_delta_pct=0.1,
        sample_size=100,
    )
    # Must NOT diagnose or mention CTR in commentary
    assert "CTR" not in interp_c
    assert "Click-through" not in interp_c
    assert "Performance across views, retention, and subscriber conversion aligns closely" in interp_c

    # CASE D: zero/undefined comparison baseline
    interp_d, action_d = generate_grounded_video_analysis(
        views=2500,
        views_delta_pct=None,
        ret=45.0,
        ret_delta_pts=None,
        ctr=None,
        ctr_delta_pts=None,
        subs_per_1k=6.0,
        subs_1k_delta_pct=None,
        sample_size=1,
    )
    assert "Catalog baseline is insufficient" in interp_d
    assert "Publish additional uploads" in action_d

    # Helper to construct minimal test video
    def make_test_video(vid_id: str, title: str, pub_date: datetime, views: int, ret: float, ctr: float | None = None) -> ChannelVideo:
        return ChannelVideo(
            video_id=vid_id,
            public=VideoPublicMetadata(
                video_id=vid_id,
                title=title,
                description="",
                tags=[],
                duration_seconds=300,
                published_at=pub_date,
                view_count=views,
                like_count=10,
                comment_count=1,
                thumbnail_url="",
                category_id="28",
            ),
            analytics=VideoPrivateAnalytics(
                views=views,
                watch_time_minutes=views * 2.0,
                avg_view_duration_seconds=120.0,
                avg_view_percentage=ret,
                subscribers_gained=int(views * 0.01),
                subscribers_lost=0,
                likes=10,
                comments=1,
                shares=0,
                impressions=None,
                ctr_percentage=ctr,
                estimated_revenue_usd=None,
                retention_curve=[],
                traffic_sources=[],
                geography=[],
                device_types=[],
            ),
            derived=DerivedVideoFeatures(
                content_pillar=ContentPillar.EMERGING_AI,
                video_format=VideoFormat.TUTORIAL,
                title_style=TitleStyle.OUTCOME_FOCUSED,
                topic_cluster="ai",
                is_time_sensitive_topic=False,
            ),
        )

    vid1 = make_test_video("vid_oldest", "Oldest", datetime(2026, 1, 1, tzinfo=UTC), 10000, 50.0, 5.0)
    vid2 = make_test_video("vid_middle", "Middle", datetime(2026, 2, 1, tzinfo=UTC), 20000, 60.0, 8.0)
    vid3 = make_test_video("vid_newest", "Newest", datetime(2026, 3, 1, tzinfo=UTC), 5000, 20.0, 4.0)

    # CASE E: latest video ordering
    recents, baselines = compute_recent_video_performance([vid1, vid2, vid3])
    assert len(recents) == 3
    # Ordered descending: newest first
    assert recents[0].video_id == "vid_newest"
    assert recents[0].is_latest is True
    assert recents[1].video_id == "vid_middle"
    assert recents[1].is_latest is False
    assert recents[2].video_id == "vid_oldest"
    assert recents[2].is_latest is False

    # CASE F: two videos with different metrics cannot accidentally share analysis
    # vid_newest has poor retention (20% vs median 50% = -30 pts) -> diagnoses retention
    assert recents[0].alex_interpretation is not None
    assert "Retention is the main weakness" in recents[0].alex_interpretation

    # Directly analyze vid2 (strong retention 60% vs median 50%, high views)
    interp_vid2, action_vid2 = generate_grounded_video_analysis(
        views=20000,
        views_delta_pct=100.0,
        ret=60.0,
        ret_delta_pts=10.0,
        ctr=8.0,
        ctr_delta_pts=3.0,
        subs_per_1k=10.0,
        subs_1k_delta_pct=0.0,
        sample_size=3,
    )
    # vid2 recommendation must NOT be about poor retention
    assert "Retention is the main weakness" not in interp_vid2
    assert "top-of-funnel" in interp_vid2
    assert action_vid2 != recents[0].alex_next_action
