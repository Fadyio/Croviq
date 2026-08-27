from abc import ABC, abstractmethod
from datetime import date, timedelta
import json
from math import exp
from pathlib import Path

from croviq_domain.channel import (
    Channel,
    ChannelAnalyticsPoint,
    ChannelAnalyticsTimeSeries,
    ChannelPrivateAnalytics,
    ChannelVideo,
    SampleChannelFixture,
    VideoPrivateAnalytics,
)


class ChannelDataProvider(ABC):
    """Abstract base class for channel data providers (sample synthetic or real YouTube)."""

    @abstractmethod
    async def get_channel(self) -> Channel:
        """Retrieve the canonical channel model."""
        pass

    @abstractmethod
    async def get_videos(
        self, limit: int = 100, offset: int = 0
    ) -> list[ChannelVideo]:
        """Retrieve a paginated list of channel videos."""
        pass

    @abstractmethod
    async def get_video(self, video_id: str) -> ChannelVideo | None:
        """Retrieve a single video by its identifier."""
        pass

    @abstractmethod
    async def get_channel_analytics(self) -> ChannelPrivateAnalytics:
        """Retrieve aggregated private channel analytics."""
        pass

    @abstractmethod
    async def get_video_analytics(self, video_id: str) -> VideoPrivateAnalytics | None:
        """Retrieve private analytics for a specific video."""
        pass

    @abstractmethod
    async def get_channel_timeseries(
        self, *, start_date: date, end_date: date
    ) -> ChannelAnalyticsTimeSeries:
        """Retrieve canonical daily analytics for an inclusive date range."""
        pass


class SampleChannelDataProvider(ChannelDataProvider):
    """Deterministic sample channel provider that reads a committed static JSON fixture."""

    def __init__(self, fixture_path: Path | str | None = None) -> None:
        if fixture_path is None:
            base_dir = Path(__file__).resolve().parent
            fixture_path = (
                base_dir / "fixtures" / "sample_channel_ai_engineering_v1.json"
            )
        self._fixture_path = Path(fixture_path)
        self._fixture: SampleChannelFixture | None = None
        self._load_and_validate_fixture()

    def _load_and_validate_fixture(self) -> None:
        if not self._fixture_path.exists():
            raise FileNotFoundError(
                f"Sample channel fixture not found at {self._fixture_path}"
            )
        try:
            with open(self._fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._fixture = SampleChannelFixture.model_validate(data)
        except Exception as e:
            raise ValueError(
                f"Failed to validate sample channel fixture at {self._fixture_path}: {e}"
            ) from e

    @property
    def fixture(self) -> SampleChannelFixture:
        if self._fixture is None:
            self._load_and_validate_fixture()
        assert self._fixture is not None
        return self._fixture

    async def get_channel(self) -> Channel:
        return self.fixture.channel

    async def get_videos(
        self, limit: int = 100, offset: int = 0
    ) -> list[ChannelVideo]:
        videos = self.fixture.channel.videos
        return videos[offset : offset + limit]

    async def get_video(self, video_id: str) -> ChannelVideo | None:
        for video in self.fixture.channel.videos:
            if video.video_id == video_id:
                return video
        return None

    async def get_channel_analytics(self) -> ChannelPrivateAnalytics:
        return self.fixture.channel.analytics

    async def get_video_analytics(self, video_id: str) -> VideoPrivateAnalytics | None:
        video = await self.get_video(video_id)
        if video is None:
            return None
        return video.analytics

    async def get_channel_timeseries(
        self, *, start_date: date, end_date: date
    ) -> ChannelAnalyticsTimeSeries:
        if end_date < start_date:
            raise ValueError("end_date must not precede start_date")

        reference_date = self.fixture.generated_at.date()
        aggregates: dict[date, dict[str, float]] = {}
        for video in self.fixture.channel.videos:
            published_date = video.public.published_at.date()
            available_days = (reference_date - published_date).days + 1
            if available_days <= 0:
                continue
            weights = [exp(-day / 45) for day in range(available_days)]
            weight_total = sum(weights)
            for day_offset, weight in enumerate(weights):
                point_date = published_date + timedelta(days=day_offset)
                share = weight / weight_total
                daily_views = round(video.analytics.views * share)
                bucket = aggregates.setdefault(
                    point_date,
                    {
                        "views": 0,
                        "watch_time_minutes": 0.0,
                        "subscribers_gained": 0,
                        "subscribers_lost": 0,
                        "retention_weighted_views": 0.0,
                    },
                )
                bucket["views"] += daily_views
                bucket["watch_time_minutes"] += (
                    video.analytics.watch_time_minutes * share
                )
                bucket["subscribers_gained"] += round(
                    video.analytics.subscribers_gained * share
                )
                bucket["subscribers_lost"] += round(
                    video.analytics.subscribers_lost * share
                )
                bucket["retention_weighted_views"] += (
                    video.analytics.avg_view_percentage * daily_views
                )

        points: list[ChannelAnalyticsPoint] = []
        cursor = start_date
        while cursor <= end_date:
            bucket = aggregates.get(cursor)
            views = int(bucket["views"]) if bucket else 0
            weighted_retention = bucket["retention_weighted_views"] if bucket else 0
            points.append(
                ChannelAnalyticsPoint(
                    date=cursor,
                    views=views,
                    watch_time_minutes=(
                        float(bucket["watch_time_minutes"]) if bucket else 0
                    ),
                    subscribers_gained=(
                        int(bucket["subscribers_gained"]) if bucket else 0
                    ),
                    subscribers_lost=(
                        int(bucket["subscribers_lost"]) if bucket else 0
                    ),
                    average_view_percentage=(
                        weighted_retention / views if views else 0
                    ),
                )
            )
            cursor += timedelta(days=1)

        return ChannelAnalyticsTimeSeries(
            start_date=start_date,
            end_date=end_date,
            points=points,
            is_modeled=True,
        )
