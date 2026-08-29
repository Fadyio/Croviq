"""In-memory fake implementation of ChannelMemoryStore for automated testing and local development."""

from copy import deepcopy
from datetime import UTC, datetime
import uuid
from croviq_api.memory.store import ChannelMemoryStore
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, MemoryRecord, TargetAgent


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

    async def delete_lesson(self, lesson_id: str, channel_id: str) -> bool:
        lessons = self._lessons.get(channel_id, [])
        orig_len = len(lessons)
        self._lessons[channel_id] = [l for l in lessons if l.lesson_id != lesson_id]
        return len(self._lessons[channel_id]) < orig_len

    async def list_memories(
        self, scope: dict[str, str] | None = None, query: str | None = None
    ) -> list[MemoryRecord]:
        if not hasattr(self, "_memories"):
            self._memories: dict[str, MemoryRecord] = {}
        records = list(self._memories.values())
        if scope:
            for k, v in scope.items():
                records = [r for r in records if r.scope.get(k) == v]
        if query and query.strip():
            q = query.strip().lower()
            records = [r for r in records if q in r.fact.lower() or (r.provenance and q in r.provenance.lower())]
        return [deepcopy(r) for r in records]

    async def create_memory(
        self,
        fact: str,
        scope: dict[str, str],
        display_name: str = "",
        provenance: str | None = None,
    ) -> MemoryRecord:
        if not hasattr(self, "_memories"):
            self._memories = {}
        mid = f"mem_{uuid.uuid4().hex[:16]}"
        now = datetime.now(UTC)
        record = MemoryRecord(
            name=f"projects/croviq-test/locations/us-central1/reasoningEngines/mock/memories/{mid}",
            memory_id=mid,
            fact=fact,
            scope=scope,
            memory_type="NATURAL_LANGUAGE_COLLECTION",
            provenance=provenance,
            created_at=now,
            updated_at=now,
        )
        self._memories[mid] = record
        return deepcopy(record)

    async def delete_memory(self, memory_name_or_id: str) -> bool:
        if not hasattr(self, "_memories"):
            self._memories = {}
        target_id = memory_name_or_id.split("/")[-1]
        if target_id in self._memories:
            del self._memories[target_id]
            return True
        for mid, rec in list(self._memories.items()):
            if rec.name == memory_name_or_id or rec.memory_id == memory_name_or_id:
                del self._memories[mid]
                return True
        return False

    async def search_memories(
        self, query: str, scope: dict[str, str] | None = None, limit: int = 20
    ) -> list[MemoryRecord]:
        results = await self.list_memories(scope=scope, query=query)
        return results[:limit]


    def clear(self) -> None:
        """Clear all stored in-memory profiles and lessons."""
        self._profiles.clear()
        self._lessons.clear()
