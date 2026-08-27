from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from math import sqrt
from statistics import mean, median

from pydantic import BaseModel, ConfigDict, Field

from croviq_domain.channel import ChannelPublicMetadata, TrafficSourceMetric
from croviq_domain.channel_intelligence import (
    ChannelExperiment,
    ChannelInsight,
    EvidenceKind,
    ExperimentStatus,
    InsightEvidence,
    InsightType,
)
from croviq_domain.channel_provider import ChannelDataProvider


class DashboardChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    source_type: str
    title: str
    description: str
    avatar_url: str | None
    subscriber_count: int
    video_count: int


class DashboardKpi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    current_value: float
    previous_value: float
    change_percentage: float | None


class DashboardTrendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    views: int
    previous_views: int
    watch_time_hours: float
    previous_watch_time_hours: float
    net_subscribers: int
    previous_net_subscribers: int


class LatestVideoAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    title: str
    published_at: datetime
    views: int
    watch_time_hours: float
    subscribers_gained: int
    subscribers_lost: int
    net_subscribers: int
    view_delta_percentage: float
    subscriber_conversion_delta_percentage: float
    retention_percentage: float
    retention_delta_points: float


class VideoPerformancePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    title: str
    views: int
    ctr_percentage: float
    average_retention: float
    subscribers_gained: int
    content_pillar: str


class TopicClusterPerformance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_cluster: str
    video_count: int
    median_views: float
    median_retention: float
    median_ctr: float


class ChannelDashboard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: DashboardChannel
    period_days: int
    period_end: date
    kpis: list[DashboardKpi]
    trend: list[DashboardTrendPoint]
    latest_video: LatestVideoAnalysis
    video_performance: list[VideoPerformancePoint]
    topic_clusters: list[TopicClusterPerformance]
    traffic_sources: list[TrafficSourceMetric]
    insights: list[ChannelInsight]
    active_experiment: ChannelExperiment | None
    proposed_experiment: ChannelExperiment
    is_sample_modeled_timeseries: bool


def _percent_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return ((current / previous) - 1) * 100


def _weighted_retention(points: list) -> float:
    total_views = sum(point.views for point in points)
    if not total_views:
        return 0
    return sum(point.average_view_percentage * point.views for point in points) / total_views


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0
    x_mean = mean(xs)
    y_mean = mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    denominator = sqrt(
        sum((x - x_mean) ** 2 for x in xs) * sum((y - y_mean) ** 2 for y in ys)
    )
    return numerator / denominator if denominator else 0


async def build_channel_dashboard(
    provider: ChannelDataProvider,
    *,
    days: int,
    end_date: date | None = None,
) -> ChannelDashboard:
    if days not in {28, 90, 365}:
        raise ValueError("days must be one of 28, 90, or 365")

    channel = await provider.get_channel()
    videos = await provider.get_videos(limit=100, offset=0)
    if not videos:
        raise ValueError("channel has no videos")
    period_end = end_date or datetime.now(UTC).date()
    current_start = period_end - timedelta(days=days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    series = await provider.get_channel_timeseries(
        start_date=previous_start,
        end_date=period_end,
    )
    previous_points = [point for point in series.points if point.date <= previous_end]
    current_points = [point for point in series.points if point.date >= current_start]

    current_views = sum(point.views for point in current_points)
    previous_views = sum(point.views for point in previous_points)
    current_watch_hours = sum(point.watch_time_minutes for point in current_points) / 60
    previous_watch_hours = sum(point.watch_time_minutes for point in previous_points) / 60
    current_net_subscribers = sum(
        point.subscribers_gained - point.subscribers_lost for point in current_points
    )
    previous_net_subscribers = sum(
        point.subscribers_gained - point.subscribers_lost for point in previous_points
    )
    current_retention = _weighted_retention(current_points)
    previous_retention = _weighted_retention(previous_points)

    kpis = [
        DashboardKpi(
            metric="views",
            current_value=current_views,
            previous_value=previous_views,
            change_percentage=_percent_change(current_views, previous_views),
        ),
        DashboardKpi(
            metric="watch_time_hours",
            current_value=current_watch_hours,
            previous_value=previous_watch_hours,
            change_percentage=_percent_change(current_watch_hours, previous_watch_hours),
        ),
        DashboardKpi(
            metric="net_subscribers",
            current_value=current_net_subscribers,
            previous_value=previous_net_subscribers,
            change_percentage=_percent_change(
                current_net_subscribers, previous_net_subscribers
            ),
        ),
        DashboardKpi(
            metric="average_retention",
            current_value=current_retention,
            previous_value=previous_retention,
            change_percentage=_percent_change(current_retention, previous_retention),
        ),
    ]

    trend = [
        DashboardTrendPoint(
            date=current.date,
            views=current.views,
            previous_views=previous.views,
            watch_time_hours=current.watch_time_minutes / 60,
            previous_watch_time_hours=previous.watch_time_minutes / 60,
            net_subscribers=current.subscribers_gained - current.subscribers_lost,
            previous_net_subscribers=(
                previous.subscribers_gained - previous.subscribers_lost
            ),
        )
        for current, previous in zip(current_points, previous_points, strict=True)
    ]

    videos_by_publish_date = sorted(videos, key=lambda video: video.public.published_at)
    latest = videos_by_publish_date[-1]
    baseline_videos = videos_by_publish_date[:-1] or videos_by_publish_date
    baseline_views = median(video.analytics.views for video in baseline_videos)
    baseline_retention = median(
        video.analytics.avg_view_percentage for video in baseline_videos
    )
    conversion_rates = [
        1000
        * (video.analytics.subscribers_gained - video.analytics.subscribers_lost)
        / video.analytics.views
        for video in baseline_videos
        if video.analytics.views
    ]
    baseline_conversion = median(conversion_rates) if conversion_rates else 0
    latest_net = latest.analytics.subscribers_gained - latest.analytics.subscribers_lost
    latest_conversion = (
        1000 * latest_net / latest.analytics.views if latest.analytics.views else 0
    )
    latest_analysis = LatestVideoAnalysis(
        video_id=latest.video_id,
        title=latest.public.title,
        published_at=latest.public.published_at,
        views=latest.analytics.views,
        watch_time_hours=latest.analytics.watch_time_minutes / 60,
        subscribers_gained=latest.analytics.subscribers_gained,
        subscribers_lost=latest.analytics.subscribers_lost,
        net_subscribers=latest_net,
        view_delta_percentage=_percent_change(latest.analytics.views, baseline_views) or 0,
        subscriber_conversion_delta_percentage=(
            _percent_change(latest_conversion, baseline_conversion) or 0
        ),
        retention_percentage=latest.analytics.avg_view_percentage,
        retention_delta_points=(
            latest.analytics.avg_view_percentage - baseline_retention
        ),
    )

    video_performance = [
        VideoPerformancePoint(
            video_id=video.video_id,
            title=video.public.title,
            views=video.analytics.views,
            ctr_percentage=video.analytics.ctr_percentage,
            average_retention=video.analytics.avg_view_percentage,
            subscribers_gained=video.analytics.subscribers_gained,
            content_pillar=str(video.derived.content_pillar),
        )
        for video in videos
    ]

    grouped: dict[str, list] = defaultdict(list)
    for video in videos:
        grouped[video.derived.topic_cluster].append(video)
    topic_clusters = sorted(
        [
            TopicClusterPerformance(
                topic_cluster=name,
                video_count=len(cluster_videos),
                median_views=median(
                    video.analytics.views for video in cluster_videos
                ),
                median_retention=median(
                    video.analytics.avg_view_percentage for video in cluster_videos
                ),
                median_ctr=median(
                    video.analytics.ctr_percentage for video in cluster_videos
                ),
            )
            for name, cluster_videos in grouped.items()
        ],
        key=lambda cluster: cluster.median_views,
        reverse=True,
    )

    demo_times = [float(video.derived.first_demo_seconds) for video in videos]
    retentions = [video.analytics.avg_view_percentage for video in videos]
    correlation = _pearson(demo_times, retentions)
    direction = "lower" if correlation < 0 else "higher"
    relationship = "negative" if correlation < 0 else "positive"
    insight = ChannelInsight(
        insight_id=f"{channel.channel_id}:first-demo-retention:{period_end.isoformat()}",
        channel_id=channel.channel_id,
        type=InsightType.RETENTION,
        title="First demonstration timing tracks retention",
        statement=(
            f"Across {len(videos)} videos, first-demo timing and average retention "
            f"have a {relationship} correlation (r={correlation:.2f})."
        ),
        evidence=[
            InsightEvidence(
                kind=EvidenceKind.FACT,
                statement=(
                    f"Pearson correlation r={correlation:.2f} across {len(videos)} videos."
                ),
                metric_refs=[
                    "video:firstDemoSeconds",
                    "video:averageViewPercentage",
                ],
            ),
            InsightEvidence(
                kind=EvidenceKind.INFERENCE,
                statement=(
                    f"Earlier demonstrations are associated with {direction} retention; "
                    "this does not establish causality."
                ),
                metric_refs=["analysis:first-demo-retention-correlation"],
            ),
        ],
        confidence=min(0.99, 0.5 + abs(correlation) / 2),
        recommended_action=(
            "Test a first practical demonstration before 00:30 while holding topic and format stable."
        ),
        created_at=datetime.combine(period_end, datetime.min.time(), tzinfo=UTC),
    )
    experiment = ChannelExperiment(
        experiment_id=f"{channel.channel_id}:early-demo-retention",
        channel_id=channel.channel_id,
        hypothesis=(
            "Showing the first practical demonstration before 00:30 improves average retention."
        ),
        primary_metric="averageViewPercentage",
        baseline_value=baseline_retention,
        expected_direction="INCREASE",
        status=ExperimentStatus.PROPOSED,
        started_at=None,
        completed_at=None,
        video_ids=[],
        result=None,
        effect_size=None,
        confidence_summary=(
            f"Proposed from a historical correlation of r={correlation:.2f}; "
            "causality has not been established."
        ),
        created_by="alex",
    )

    public: ChannelPublicMetadata = channel.public
    return ChannelDashboard(
        channel=DashboardChannel(
            channel_id=channel.channel_id,
            source_type=channel.source_type,
            title=public.title,
            description=public.description,
            avatar_url=public.avatar_url,
            subscriber_count=public.subscriber_count,
            video_count=public.video_count,
        ),
        period_days=days,
        period_end=period_end,
        kpis=kpis,
        trend=trend,
        latest_video=latest_analysis,
        video_performance=video_performance,
        topic_clusters=topic_clusters,
        traffic_sources=channel.analytics.top_traffic_sources,
        insights=[insight],
        active_experiment=None,
        proposed_experiment=experiment,
        is_sample_modeled_timeseries=series.is_modeled,
    )
