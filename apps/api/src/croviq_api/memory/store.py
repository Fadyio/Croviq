"""Abstract interface for Channel Memory persistence."""

from abc import ABC, abstractmethod
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, MemoryRecord, TargetAgent


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

    @abstractmethod
    async def delete_lesson(self, lesson_id: str, channel_id: str) -> bool:
        """Remove a ChannelLesson from the memory store."""
        pass

    @abstractmethod
    async def list_memories(
        self, scope: dict[str, str] | None = None, query: str | None = None
    ) -> list[MemoryRecord]:
        """List MemoryRecords from the canonical Memory Bank matching optional scope and query."""
        pass

    @abstractmethod
    async def create_memory(
        self,
        fact: str,
        scope: dict[str, str],
        display_name: str = "",
        provenance: str | None = None,
    ) -> MemoryRecord:
        """Create a new MemoryRecord in the canonical Memory Bank."""
        pass

    @abstractmethod
    async def delete_memory(self, memory_name_or_id: str) -> bool:
        """Delete a MemoryRecord from the canonical Memory Bank by resource name or ID."""
        pass

    @abstractmethod
    async def search_memories(
        self, query: str, scope: dict[str, str] | None = None, limit: int = 20
    ) -> list[MemoryRecord]:
        """Search memory records using similarity retrieval or keyword matching."""
        pass
