"""In-memory fake implementation of ChannelMemoryStore for automated testing and local development."""

from copy import deepcopy
from croviq_api.memory.store import ChannelMemoryStore
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, TargetAgent


class FakeChannelMemoryStore(ChannelMemoryStore):
    """In-memory channel-isolated memory store."""

    def __init__(self) -> None:
        self._profiles: dict[str, ChannelMemoryProfile] = {}
        self._lessons: dict[str, list[ChannelLesson]] = {}

    async def get_profile(self, channel_id: str) -> ChannelMemoryProfile | None:
        if channel_id in self._profiles:
            return deepcopy(self._profiles[channel_id])
        return None

    async def upsert_profile(self, profile: ChannelMemoryProfile) -> ChannelMemoryProfile:
        self._profiles[profile.channel_id] = deepcopy(profile)
        return deepcopy(profile)

    async def profile_exists(self, channel_id: str) -> bool:
        return channel_id in self._profiles

    async def get_lessons(
        self, channel_id: str, target_agent: TargetAgent | str | None = None
    ) -> list[ChannelLesson]:
        lessons = self._lessons.get(channel_id, [])
        if target_agent is None:
            return [deepcopy(l) for l in lessons]

        agent_val = target_agent.value if isinstance(target_agent, TargetAgent) else str(target_agent)
        return [deepcopy(l) for l in lessons if l.target_agent.value == agent_val]

    async def add_lesson(self, lesson: ChannelLesson) -> ChannelLesson:
        self._lessons.setdefault(lesson.channel_id, []).append(deepcopy(lesson))
        return deepcopy(lesson)

    def clear(self) -> None:
        """Clear all stored in-memory profiles and lessons."""
        self._profiles.clear()
        self._lessons.clear()
