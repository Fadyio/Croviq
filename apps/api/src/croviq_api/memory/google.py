"""Google Agent Platform Memory Bank adapter for ChannelMemoryStore."""

from datetime import datetime, timezone
import json
import time
from typing import Any
from google.api_core.client_options import ClientOptions
from google.cloud import aiplatform_v1beta1

from croviq_api.memory.exceptions import MemoryStoreError
from croviq_api.memory.logging import log_memory_event
from croviq_api.memory.store import ChannelMemoryStore
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, TargetAgent


class GoogleMemoryBankStore(ChannelMemoryStore):
    """Production memory store connecting directly to Google Agent Platform Memory Bank."""

    SCHEMA_ID_PROFILE: str = "channel-profile"
    SCHEMA_ID_LESSON: str = "channel-lesson"

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        memory_bank_id: str = "croviq-channel-memory",
        timeout: float = 30.0,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.memory_bank_id = memory_bank_id
        self.timeout = timeout
        self._client: aiplatform_v1beta1.MemoryBankServiceClient | None = None
        self._resolved_parent: str | None = None

        if memory_bank_id.startswith("projects/"):
            self._resolved_parent = memory_bank_id
        elif memory_bank_id.isdigit():
            self._resolved_parent = (
                f"projects/{self.project_id}/locations/{self.location}/reasoningEngines/{self.memory_bank_id}"
            )

    def _get_client(self) -> aiplatform_v1beta1.MemoryBankServiceClient:
        if self._client is None:
            endpoint = f"{self.location}-aiplatform.googleapis.com"
            options = ClientOptions(api_endpoint=endpoint)
            self._client = aiplatform_v1beta1.MemoryBankServiceClient(client_options=options)
        return self._client

    def _resolve_parent(self) -> str:
        if self._resolved_parent is not None:
            return self._resolved_parent

        # Default standard reasoningEngine ID or name
        self._resolved_parent = (
            f"projects/{self.project_id}/locations/{self.location}/reasoningEngines/{self.memory_bank_id}"
        )
        return self._resolved_parent

    async def get_profile(self, channel_id: str) -> ChannelMemoryProfile | None:
        """Retrieve structured ChannelMemoryProfile from Memory Bank."""
        start_time = time.monotonic()
        parent = self._resolve_parent()
        client = self._get_client()

        try:
            memories = client.list_memories(parent=parent)
            assembled_profile: dict[str, Any] = {}

            for m in memories:
                if m.scope.get("channel_id") == channel_id:
                    try:
                        data = json.loads(m.fact)
                        if "lesson_id" not in data:
                            assembled_profile.update(data)
                    except Exception:
                        continue

            latency_ms = (time.monotonic() - start_time) * 1000.0

            if not assembled_profile or "channel_id" not in assembled_profile:
                log_memory_event(
                    event_type="memory.profile.retrieve",
                    channel_id=channel_id,
                    status=404,
                    latency_ms=latency_ms,
                    memory_schema_id=self.SCHEMA_ID_PROFILE,
                    memory_bank_resource=parent,
                    message=f"Memory profile for channel '{channel_id}' not found in Memory Bank.",
                )
                return None

            profile = ChannelMemoryProfile.model_validate(assembled_profile)
            log_memory_event(
                event_type="memory.profile.retrieve",
                channel_id=channel_id,
                status=200,
                latency_ms=latency_ms,
                memory_schema_id=self.SCHEMA_ID_PROFILE,
                memory_bank_resource=parent,
                message=f"Successfully retrieved memory profile for channel '{channel_id}'.",
            )
            return profile

        except Exception as exc:
            latency_ms = (time.monotonic() - start_time) * 1000.0
            log_memory_event(
                event_type="memory.profile.failed",
                channel_id=channel_id,
                status=500,
                latency_ms=latency_ms,
                memory_schema_id=self.SCHEMA_ID_PROFILE,
                memory_bank_resource=parent,
                message=f"Exception during Memory Bank retrieve: {type(exc).__name__}: {str(exc)}",
                error_code="memory_bank_retrieve_exception",
                exception=exc,
            )
            raise MemoryStoreError(f"Memory Bank retrieval error: {str(exc)}") from exc

    async def upsert_profile(self, profile: ChannelMemoryProfile) -> ChannelMemoryProfile:
        """Persist or update structured ChannelMemoryProfile in Memory Bank."""
        start_time = time.monotonic()
        channel_id = profile.channel_id
        parent = self._resolve_parent()
        client = self._get_client()

        log_memory_event(
            event_type="memory.profile.generate.started",
            channel_id=channel_id,
            status=200,
            memory_schema_id=self.SCHEMA_ID_PROFILE,
            memory_bank_resource=parent,
            message=f"Starting profile persist for channel '{channel_id}'.",
        )

        try:
            # 1. Identity fragment
            id_fact = json.dumps({
                "channel_id": profile.channel_id,
                "channel_name": profile.channel_name,
                "language": profile.language,
                "primary_topics": profile.primary_topics,
                "content_pillars": profile.content_pillars,
                "audience_geographies": profile.audience_geographies,
                "audience_characteristics": profile.audience_characteristics,
                "updated_at": profile.updated_at.isoformat(),
            })
            client.create_memory(
                parent=parent,
                memory=aiplatform_v1beta1.Memory(
                    display_name="channel-profile:identity",
                    description="Identity and audience profile",
                    fact=id_fact,
                    scope={"channel_id": profile.channel_id},
                ),
            )

            # 2. Performance fragment
            perf_fact = json.dumps({
                "historical_baselines": profile.historical_baselines,
                "high_performing_formats": profile.high_performing_formats,
                "weak_formats": profile.weak_formats,
            })
            client.create_memory(
                parent=parent,
                memory=aiplatform_v1beta1.Memory(
                    display_name="channel-profile:performance",
                    description="Performance baselines and formats",
                    fact=perf_fact,
                    scope={"channel_id": profile.channel_id},
                ),
            )

            # 3. Editorial fragment
            edit_fact = json.dumps({
                "recurring_retention_patterns": profile.recurring_retention_patterns,
                "packaging_patterns": profile.packaging_patterns,
                "editorial_directives": profile.editorial_directives,
            })
            client.create_memory(
                parent=parent,
                memory=aiplatform_v1beta1.Memory(
                    display_name="channel-profile:editorial",
                    description="Retention patterns and editorial directives",
                    fact=edit_fact,
                    scope={"channel_id": profile.channel_id},
                ),
            )

            latency_ms = (time.monotonic() - start_time) * 1000.0
            log_memory_event(
                event_type="memory.profile.generate.completed",
                channel_id=channel_id,
                status=200,
                latency_ms=latency_ms,
                memory_schema_id=self.SCHEMA_ID_PROFILE,
                memory_bank_resource=parent,
                message=f"Successfully persisted memory profile for channel '{channel_id}'.",
            )
            return profile

        except Exception as exc:
            latency_ms = (time.monotonic() - start_time) * 1000.0
            log_memory_event(
                event_type="memory.profile.failed",
                channel_id=channel_id,
                status=500,
                latency_ms=latency_ms,
                memory_schema_id=self.SCHEMA_ID_PROFILE,
                memory_bank_resource=parent,
                message=f"Exception during Memory Bank upsert: {type(exc).__name__}: {str(exc)}",
                error_code="memory_bank_upsert_exception",
                exception=exc,
            )
            raise MemoryStoreError(f"Memory Bank upsert error: {str(exc)}") from exc

    async def profile_exists(self, channel_id: str) -> bool:
        """Check if profile exists for channel_id."""
        profile = await self.get_profile(channel_id)
        return profile is not None

    async def get_lessons(
        self, channel_id: str, target_agent: TargetAgent | str | None = None
    ) -> list[ChannelLesson]:
        """Retrieve lessons for channel from Memory Bank."""
        parent = self._resolve_parent()
        client = self._get_client()

        try:
            memories = client.list_memories(parent=parent)
            lessons: list[ChannelLesson] = []

            for m in memories:
                if m.scope.get("channel_id") == channel_id:
                    try:
                        data = json.loads(m.fact)
                        if "lesson_id" in data:
                            lessons.append(ChannelLesson.model_validate(data))
                    except Exception:
                        continue

            if target_agent is not None:
                agent_val = target_agent.value if isinstance(target_agent, TargetAgent) else str(target_agent)
                lessons = [l for l in lessons if l.target_agent.value == agent_val]

            return lessons

        except Exception as exc:
            raise MemoryStoreError(f"Memory Bank lessons retrieval error: {str(exc)}") from exc

    async def add_lesson(self, lesson: ChannelLesson) -> ChannelLesson:
        """Persist a single ChannelLesson into Memory Bank."""
        parent = self._resolve_parent()
        client = self._get_client()

        try:
            client.create_memory(
                parent=parent,
                memory=aiplatform_v1beta1.Memory(
                    display_name=f"channel-lesson:{lesson.lesson_id}",
                    description=f"Lesson for {lesson.target_agent.value}",
                    fact=json.dumps(lesson.model_dump(mode="json")),
                    scope={"channel_id": lesson.channel_id},
                ),
            )
            return lesson

        except Exception as exc:
            raise MemoryStoreError(f"Memory Bank add_lesson error: {str(exc)}") from exc
