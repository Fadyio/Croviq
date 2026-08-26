"""Abstract interface for Channel Memory persistence."""

from abc import ABC, abstractmethod
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, TargetAgent


class ChannelMemoryStore(ABC):
    """Provider-neutral abstract repository for channel memory profile and lessons."""

    @abstractmethod
    async def get_profile(self, channel_id: str) -> ChannelMemoryProfile | None:
        """Retrieve the canonical structured ChannelMemoryProfile for a channel scope."""
        pass

    @abstractmethod
    async def upsert_profile(self, profile: ChannelMemoryProfile) -> ChannelMemoryProfile:
        """Create or update a structured ChannelMemoryProfile in the memory store."""
        pass

    @abstractmethod
    async def profile_exists(self, channel_id: str) -> bool:
        """Check if a memory profile exists for the specified channel."""
        pass

    @abstractmethod
    async def get_lessons(
        self, channel_id: str, target_agent: TargetAgent | str | None = None
    ) -> list[ChannelLesson]:
        """Retrieve active ChannelLessons scoped to a channel, optionally filtered by target agent."""
        pass

    @abstractmethod
    async def add_lesson(self, lesson: ChannelLesson) -> ChannelLesson:
        """Persist a new ChannelLesson record for a channel."""
        pass
