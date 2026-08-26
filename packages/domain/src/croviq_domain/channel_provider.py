from abc import ABC, abstractmethod
import json
from pathlib import Path

from croviq_domain.channel import (
    Channel,
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
