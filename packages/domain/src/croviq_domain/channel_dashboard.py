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
    model_config = ConfigDict(extra="allow")

    channel_id: str = "croviq_syn_ai_eng_01"
    video_id: str
    title: str
    published_at: datetime
    views: int
    watch_time_hours: float
    subscribers_gained: int
    subscribers_lost: int = 0
    net_subscribers: int
    view_delta_percentage: float
    subscriber_conversion_delta_percentage: float
    retention_percentage: float
    retention_delta_points: float
    views_percentile: float = 50.0
    retention_percentile: float = 50.0
    ctr_percentile: float | None = None
    subscriber_conversion_per_1k_views: float = 0.0
    comparison_window: str = "lifetime catalog baseline"
    baseline_sample_size: int = 0
    median_views: float = 0.0
    median_retention: float = 0.0
    median_ctr: float | None = None
    ctr: float | None = None
    retention: float | None = None
    subscriber_gain: int | None = None


class ChannelBaselines(BaseModel):
    model_config = ConfigDict(extra="forbid")

    median_views: float
    median_retention: float
    median_ctr: float | None = None
    median_subs_per_1k: float | None = None
    median_net_subscribers: float | None = None
    sample_size: int = 0


class RecentVideoPerformance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    title: str
    published_at: datetime
    views: int
    views_delta_percentage: float | None = None
    average_retention: float
    retention_delta_points: float | None = None
    ctr_percentage: float | None = None
    ctr_delta_points: float | None = None
    subscribers_gained: int
    subscribers_lost: int = 0
    net_subscribers: int
    subs_per_1k: float | None = None
    subs_per_1k_delta_percentage: float | None = None
    is_latest: bool = False
    alex_interpretation: str | None = None
    alex_next_action: str | None = None


class VideoPerformancePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    title: str
    views: int
    ctr_percentage: float | None
    discovery_metric: str
    discovery_value: float
    average_retention: float
    subscribers_gained: int
    content_pillar: str


class TopicClusterPerformance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_cluster: str
    video_count: int
    median_views: float
    median_retention: float
    median_ctr: float | None


class ChannelDashboard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: DashboardChannel
    period_days: int
    period_end: date
    kpis: list[DashboardKpi]
    trend: list[DashboardTrendPoint]
    latest_video: LatestVideoAnalysis
    video_performance: list[VideoPerformancePoint]
    recent_videos: list[RecentVideoPerformance] = Field(default_factory=list)
    channel_baselines: ChannelBaselines | None = None
    topic_clusters: list[TopicClusterPerformance]
    traffic_sources: list[TrafficSourceMetric]
    insights: list[ChannelInsight]
    active_experiment: ChannelExperiment | None
    proposed_experiment: ChannelExperiment | None = None
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

def compute_latest_video_analysis(
    channel_id: str,
    videos: list[Any],
) -> LatestVideoAnalysis:
    """Compute deterministic provenance object for the latest published video against catalog baselines."""
    if not videos:
        now = datetime.now(UTC)
        return LatestVideoAnalysis(
            channel_id=channel_id,
            video_id="none",
            title="No Published Videos",
            published_at=now,
            views=0,
            watch_time_hours=0.0,
            subscribers_gained=0,
            subscribers_lost=0,
            net_subscribers=0,
            view_delta_percentage=0.0,
            subscriber_conversion_delta_percentage=0.0,
            retention_percentage=0.0,
            retention_delta_points=0.0,
            views_percentile=50.0,
            retention_percentile=50.0,
            ctr_percentile=None,
            subscriber_conversion_per_1k_views=0.0,
            comparison_window="lifetime catalog baseline",
            baseline_sample_size=0,
            median_views=0.0,
            median_retention=0.0,
            median_ctr=None,
            ctr=None,
            retention=0.0,
            subscriber_gain=0,
        )

    def _get_pub_date(v: Any) -> datetime:
        pub = getattr(getattr(v, "public", None), "published_at", None) or getattr(v, "published_at", None)
        if isinstance(pub, str):
            return datetime.fromisoformat(pub.replace("Z", "+00:00"))
        if isinstance(pub, datetime):
            return pub
        return datetime.min.replace(tzinfo=UTC)

    videos_by_publish_date = sorted(videos, key=_get_pub_date)
    latest = videos_by_publish_date[-1]
    latest_v_id = getattr(latest, "video_id", "vid_latest")
    baseline_videos = [v for v in videos_by_publish_date if getattr(v, "video_id", None) != latest_v_id] or [latest]

    latest_views = int(getattr(getattr(latest, "analytics", None), "views", 0))
    latest_retention = float(getattr(getattr(latest, "analytics", None), "avg_view_percentage", 0.0))
    latest_ctr = getattr(getattr(latest, "analytics", None), "ctr_percentage", None)
    latest_ctr_float = float(latest_ctr) if latest_ctr is not None else None
    latest_subs_gained = int(getattr(getattr(latest, "analytics", None), "subscribers_gained", 0))
    latest_subs_lost = int(getattr(getattr(latest, "analytics", None), "subscribers_lost", 0))
    latest_net = latest_subs_gained - latest_subs_lost
    latest_watch_time_mins = float(getattr(getattr(latest, "analytics", None), "watch_time_minutes", 0.0))
    latest_title = getattr(getattr(latest, "public", None), "title", "Latest Video")
    latest_pub = _get_pub_date(latest)

    baseline_views_list = [int(getattr(getattr(v, "analytics", None), "views", 0)) for v in baseline_videos]
    baseline_ret_list = [float(getattr(getattr(v, "analytics", None), "avg_view_percentage", 0.0)) for v in baseline_videos]
    baseline_ctr_videos = [v for v in baseline_videos if getattr(getattr(v, "analytics", None), "ctr_percentage", None) is not None]
    baseline_ctr_list = [float(getattr(getattr(v, "analytics", None), "ctr_percentage", 0.0)) for v in baseline_ctr_videos]

    baseline_views = float(median(baseline_views_list)) if baseline_views_list else float(latest_views)
    baseline_retention = float(median(baseline_ret_list)) if baseline_ret_list else latest_retention
    baseline_ctr = float(median(baseline_ctr_list)) if baseline_ctr_list else latest_ctr_float

    conversion_rates = [
        1000.0 * (int(getattr(getattr(v, "analytics", None), "subscribers_gained", 0)) - int(getattr(getattr(v, "analytics", None), "subscribers_lost", 0)))
        / int(getattr(getattr(v, "analytics", None), "views", 1))
        for v in baseline_videos
        if int(getattr(getattr(v, "analytics", None), "views", 0)) > 0
    ]
    baseline_conversion = float(median(conversion_rates)) if conversion_rates else 0.0
    latest_conversion = (1000.0 * latest_net / latest_views) if latest_views > 0 else 0.0

    total_baseline_count = len(baseline_videos)
    views_percentile = (
        (sum(1 for v in baseline_videos if int(getattr(getattr(v, "analytics", None), "views", 0)) <= latest_views) / total_baseline_count) * 100.0
        if total_baseline_count > 0
        else 50.0
    )
    retention_percentile = (
        (sum(1 for v in baseline_videos if float(getattr(getattr(v, "analytics", None), "avg_view_percentage", 0.0)) <= latest_retention) / total_baseline_count) * 100.0
        if total_baseline_count > 0
        else 50.0
    )
    ctr_percentile = (
        (sum(1 for v in baseline_ctr_videos if float(getattr(getattr(v, "analytics", None), "ctr_percentage", 0.0)) <= (latest_ctr_float or 0.0)) / len(baseline_ctr_videos)) * 100.0
        if (latest_ctr_float is not None and baseline_ctr_videos)
        else None
    )
    sub_conv_per_1k = (1000.0 * latest_subs_gained / latest_views) if latest_views > 0 else 0.0

    return LatestVideoAnalysis(
        channel_id=channel_id,
        video_id=latest_v_id,
        title=latest_title,
        published_at=latest_pub,
        views=latest_views,
        watch_time_hours=latest_watch_time_mins / 60.0,
        subscribers_gained=latest_subs_gained,
        subscribers_lost=latest_subs_lost,
        net_subscribers=latest_net,
        view_delta_percentage=_percent_change(latest_views, baseline_views),
        subscriber_conversion_delta_percentage=_percent_change(
            latest_conversion, baseline_conversion
        ),
        retention_percentage=latest_retention,
        retention_delta_points=latest_retention - baseline_retention,
        views_percentile=views_percentile,
        retention_percentile=retention_percentile,
        ctr_percentile=ctr_percentile,
        subscriber_conversion_per_1k_views=sub_conv_per_1k,
        comparison_window="lifetime catalog baseline",
        baseline_sample_size=total_baseline_count,
        median_views=baseline_views,
        median_retention=baseline_retention,
        median_ctr=baseline_ctr,
        ctr=latest_ctr_float,
        retention=latest_retention,
        subscriber_gain=latest_subs_gained,
    )

def compute_recent_video_performance(
    videos: list[Any],
    limit: int = 5,
) -> tuple[list[RecentVideoPerformance], ChannelBaselines]:
    """Compute recent video performance rows with median comparisons and Alex actionable signal."""
    if not videos:
        return [], ChannelBaselines(
            median_views=0.0,
            median_retention=0.0,
            median_ctr=None,
            median_subs_per_1k=None,
            median_net_subscribers=None,
            sample_size=0,
        )

    def _get_pub_date(v: Any) -> datetime:
        pub = getattr(getattr(v, "public", None), "published_at", None) or getattr(v, "published_at", None)
        if isinstance(pub, str):
            return datetime.fromisoformat(pub.replace("Z", "+00:00"))
        if isinstance(pub, datetime):
            return pub
        return datetime.min.replace(tzinfo=UTC)

    sorted_videos = sorted(videos, key=_get_pub_date, reverse=True)

    all_views = [int(getattr(getattr(v, "analytics", None), "views", 0)) for v in videos]
    all_ret = [float(getattr(getattr(v, "analytics", None), "avg_view_percentage", 0.0)) for v in videos]
    all_ctr = [
        float(getattr(getattr(v, "analytics", None), "ctr_percentage", 0.0))
        for v in videos
        if getattr(getattr(v, "analytics", None), "ctr_percentage", None) is not None
    ]
    all_subs_g = [int(getattr(getattr(v, "analytics", None), "subscribers_gained", 0)) for v in videos]
    all_subs_l = [int(getattr(getattr(v, "analytics", None), "subscribers_lost", 0)) for v in videos]
    all_net = [g - l for g, l in zip(all_subs_g, all_subs_l, strict=True)]
    all_subs_per_1k = [
        (1000.0 * g / v)
        for g, v in zip(all_subs_g, all_views, strict=True)
        if v > 0
    ]

    median_views = float(median(all_views)) if all_views else 0.0
    median_ret = float(median(all_ret)) if all_ret else 0.0
    median_ctr = float(median(all_ctr)) if all_ctr else None
    median_subs_1k = float(median(all_subs_per_1k)) if all_subs_per_1k else None
    median_net = float(median(all_net)) if all_net else None

    baselines = ChannelBaselines(
        median_views=median_views,
        median_retention=median_ret,
        median_ctr=median_ctr,
        median_subs_per_1k=median_subs_1k,
        median_net_subscribers=median_net,
        sample_size=len(videos),
    )

    recent_list: list[RecentVideoPerformance] = []
    for idx, v in enumerate(sorted_videos[:limit]):
        v_id = getattr(v, "video_id", f"vid_{idx}")
        title = getattr(getattr(v, "public", None), "title", "Untitled Video")
        pub = _get_pub_date(v)
        views = int(getattr(getattr(v, "analytics", None), "views", 0))
        ret = float(getattr(getattr(v, "analytics", None), "avg_view_percentage", 0.0))
        ctr_raw = getattr(getattr(v, "analytics", None), "ctr_percentage", None)
        ctr = float(ctr_raw) if ctr_raw is not None else None
        subs_g = int(getattr(getattr(v, "analytics", None), "subscribers_gained", 0))
        subs_l = int(getattr(getattr(v, "analytics", None), "subscribers_lost", 0))
        net = subs_g - subs_l
        subs_per_1k = (1000.0 * subs_g / views) if views > 0 else None

        views_delta_pct = _percent_change(views, median_views) if median_views > 0 else None
        ret_delta_pts = (ret - median_ret) if median_ret > 0 else None
        ctr_delta_pts = (ctr - median_ctr) if (ctr is not None and median_ctr is not None) else None
        subs_1k_delta_pct = _percent_change(subs_per_1k, median_subs_1k) if (subs_per_1k is not None and median_subs_1k is not None and median_subs_1k > 0) else None

        is_latest = (idx == 0)
        alex_interp: str | None = None
        alex_action: str | None = None
        if is_latest:
            if ret_delta_pts is not None and ret_delta_pts <= -10.0:
                alex_interp = (
                    f"Retention is the main weakness here. The video is "
                    f"{abs(ret_delta_pts):.1f} points below your channel median despite normal subscriber conversion."
                )
                alex_action = "Inspect the first 30 seconds for delayed demonstration or setup."
            elif ctr_delta_pts is not None and ctr_delta_pts <= -2.0:
                alex_interp = (
                    f"Click-through rate is the main bottleneck. Thumbnail CTR is "
                    f"{abs(ctr_delta_pts):.1f} points below your channel median."
                )
                alex_action = "Test alternative thumbnail compositions and high-contrast typography."
            elif views_delta_pct is not None and views_delta_pct >= 20.0:
                alex_interp = (
                    f"Strong top-of-funnel momentum. Views are "
                    f"{views_delta_pct:+.1f}% vs channel median."
                )
                alex_action = "Evaluate audience retention curve to optimize long-tail engagement."
            else:
                alex_interp = "Performance across views, retention, and conversion aligns closely with your channel median."
                alex_action = "Maintain format consistency for upcoming uploads."

        recent_list.append(
            RecentVideoPerformance(
                video_id=v_id,
                title=title,
                published_at=pub,
                views=views,
                views_delta_percentage=views_delta_pct,
                average_retention=ret,
                retention_delta_points=ret_delta_pts,
                ctr_percentage=ctr,
                ctr_delta_points=ctr_delta_pts,
                subscribers_gained=subs_g,
                subscribers_lost=subs_l,
                net_subscribers=net,
                subs_per_1k=subs_per_1k,
                subs_per_1k_delta_percentage=subs_1k_delta_pct,
                is_latest=is_latest,
                alex_interpretation=alex_interp,
                alex_next_action=alex_action,
            )
        )

    return recent_list, baselines


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

    trend: list[DashboardTrendPoint] = []
    for idx, current in enumerate(current_points):
        previous = previous_points[idx] if idx < len(previous_points) else None
        prev_views = previous.views if previous else 0
        prev_watch = (previous.watch_time_minutes / 60) if previous else 0.0
        prev_net = (
            (previous.subscribers_gained - previous.subscribers_lost)
            if previous
            else 0
        )
        trend.append(
            DashboardTrendPoint(
                date=current.date,
                views=current.views,
                previous_views=prev_views,
                watch_time_hours=current.watch_time_minutes / 60,
                previous_watch_time_hours=prev_watch,
                net_subscribers=current.subscribers_gained - current.subscribers_lost,
                previous_net_subscribers=prev_net,
            )
        )

    latest_analysis = compute_latest_video_analysis(channel.channel_id, videos)
    recent_videos, channel_baselines = compute_recent_video_performance(videos, limit=5)

    video_performance = [
        VideoPerformancePoint(
            video_id=video.video_id,
            title=video.public.title,
            views=video.analytics.views,
            ctr_percentage=video.analytics.ctr_percentage,
            discovery_metric=(
                "thumbnail_ctr"
                if video.analytics.ctr_percentage is not None
                else "subscriber_conversion_per_1k_views"
            ),
            discovery_value=(
                video.analytics.ctr_percentage
                if video.analytics.ctr_percentage is not None
                else (
                    1000 * video.analytics.subscribers_gained / video.analytics.views
                    if video.analytics.views
                    else 0
                )
            ),
            average_retention=video.analytics.avg_view_percentage,
            subscribers_gained=video.analytics.subscribers_gained,
            content_pillar=str(video.derived.content_pillar),
        )
        for video in videos
    ]

    grouped: dict[str, list] = defaultdict(list)
    for video in videos:
        grouped[video.derived.topic_cluster].append(video)
    topic_clusters_unsorted: list[TopicClusterPerformance] = []
    for name, cluster_videos in grouped.items():
        ctr_values = [
            video.analytics.ctr_percentage
            for video in cluster_videos
            if video.analytics.ctr_percentage is not None
        ]
        topic_clusters_unsorted.append(
            TopicClusterPerformance(
                topic_cluster=name,
                video_count=len(cluster_videos),
                median_views=median(
                    video.analytics.views for video in cluster_videos
                ),
                median_retention=median(
                    video.analytics.avg_view_percentage for video in cluster_videos
                ),
                median_ctr=median(ctr_values) if ctr_values else None,
            )
        )
    topic_clusters = sorted(
        topic_clusters_unsorted,
        key=lambda cluster: cluster.median_views,
        reverse=True,
    )

    analysis_videos = [
        video for video in videos if video.derived.first_demo_seconds is not None
    ]
    demo_times = [
        float(video.derived.first_demo_seconds) for video in analysis_videos
    ]
    retentions = [
        video.analytics.avg_view_percentage for video in analysis_videos
    ]
    correlation = _pearson(demo_times, retentions)
    early_videos = [
        v for v in analysis_videos if float(v.derived.first_demo_seconds) <= 30.0
    ]
    late_videos = [
        v for v in analysis_videos if float(v.derived.first_demo_seconds) > 30.0
    ]
    early_avg = (
        sum(v.analytics.avg_view_percentage for v in early_videos) / len(early_videos)
        if early_videos
        else 0.0
    )
    late_avg = (
        sum(v.analytics.avg_view_percentage for v in late_videos) / len(late_videos)
        if late_videos
        else 0.0
    )
    diff = early_avg - late_avg
    insight = ChannelInsight(
        insight_id=f"{channel.channel_id}:first-demo-retention:{period_end.isoformat()}",
        channel_id=channel.channel_id,
        type=InsightType.RETENTION,
        title="First demonstration timing tracks retention",
        statement=(
            f"Videos reaching the first demonstration within 00:30 average {early_avg:.1f}% retention "
            f"vs {late_avg:.1f}% for later demonstrations (n={len(analysis_videos)} videos, r={correlation:.2f})."
        ),
        evidence=[
            InsightEvidence(
                kind=EvidenceKind.FACT,
                statement=(
                    f"MEASUREMENT: Videos with early demonstrations (<=00:30) average {early_avg:.1f}% retention "
                    f"vs {late_avg:.1f}% for later demonstrations across n={len(analysis_videos)} videos (delta {diff:+.1f}%)."
                ),
                metric_refs=[
                    "video:firstDemoSeconds",
                    "video:averageViewPercentage",
                ],
            ),
            InsightEvidence(
                kind=EvidenceKind.INFERENCE,
                statement=(
                    "INTERPRETATION: The association between early demonstration and viewer retention "
                    f"is strong (r={correlation:.2f}), but observational rather than established causal certainty."
                ),
                metric_refs=["analysis:first-demo-retention-correlation"],
            ),
        ],
        confidence=min(0.99, 0.5 + abs(correlation) / 2),
        recommended_action=(
            "ACTION: For the next upload, reach the first usable demonstration by 00:25 while holding topic and format stable."
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
        baseline_value=latest_analysis.median_retention,
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
        recent_videos=recent_videos,
        channel_baselines=channel_baselines,
        topic_clusters=topic_clusters,
        traffic_sources=channel.analytics.top_traffic_sources,
        insights=[insight],
        active_experiment=None,
        proposed_experiment=experiment,
        is_sample_modeled_timeseries=series.is_modeled,
    )
