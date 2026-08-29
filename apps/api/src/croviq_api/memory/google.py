"""Google Agent Platform Memory Bank adapter for ChannelMemoryStore."""

from datetime import UTC, datetime
import json
import logging
import time
from typing import Any
from google.api_core.client_options import ClientOptions
from google.cloud import aiplatform_v1beta1

from croviq_api.memory.exceptions import MemoryStoreError
from croviq_api.memory.logging import log_memory_event
from croviq_api.memory.store import ChannelMemoryStore
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, MemoryRecord, TargetAgent

logger = logging.getLogger(__name__)


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

        # 1. Full resource name
        if self.memory_bank_id.startswith("projects/"):
            self._resolved_parent = self.memory_bank_id
            return self._resolved_parent

        # 2. Numeric engine ID
        if self.memory_bank_id.isdigit():
            self._resolved_parent = (
                f"projects/{self.project_id}/locations/{self.location}/reasoningEngines/{self.memory_bank_id}"
            )
            return self._resolved_parent

        # 3. Lookup reasoning engine by display name
        try:
            endpoint = f"{self.location}-aiplatform.googleapis.com"
            re_client = aiplatform_v1beta1.ReasoningEngineServiceClient(
                client_options=ClientOptions(api_endpoint=endpoint)
            )
            parent_loc = f"projects/{self.project_id}/locations/{self.location}"
            for engine in re_client.list_reasoning_engines(parent=parent_loc):
                if engine.display_name == self.memory_bank_id or self.memory_bank_id in engine.name:
                    self._resolved_parent = engine.name
                    logger.info("Resolved Memory Bank parent from display name '%s' to '%s'", self.memory_bank_id, self._resolved_parent)
                    return self._resolved_parent
        except Exception as exc:
            logger.warning("Could not list reasoning engines to resolve display name '%s': %s", self.memory_bank_id, exc)

        # 4. Fallback default numeric Reasoning Engine for croviq-channel-memory in us-central1
        if "croviq" in self.project_id or "705994694330" in self.project_id:
            self._resolved_parent = f"projects/{self.project_id}/locations/{self.location}/reasoningEngines/9001435065032376320"
        else:
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
                        if "lesson_id" not in data and isinstance(data, dict):
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
                        if isinstance(data, dict) and "lesson_id" in data:
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
                    scope={"channel_id": lesson.channel_id, "agent_id": lesson.target_agent.value},
                ),
            )
            return lesson

        except Exception as exc:
            raise MemoryStoreError(f"Memory Bank add_lesson error: {str(exc)}") from exc

    async def delete_lesson(self, lesson_id: str, channel_id: str) -> bool:
        """Delete a lesson from Memory Bank by lesson_id."""
        parent = self._resolve_parent()
        client = self._get_client()

        try:
            memories = client.list_memories(parent=parent)
            for m in memories:
                if m.scope.get("channel_id") == channel_id:
                    try:
                        data = json.loads(m.fact)
                        if isinstance(data, dict) and data.get("lesson_id") == lesson_id:
                            client.delete_memory(name=m.name)
                            return True
                    except Exception:
                        continue
            return False
        except Exception as exc:
            raise MemoryStoreError(f"Memory Bank delete_lesson error: {str(exc)}") from exc

    async def list_memories(
        self, scope: dict[str, str] | None = None, query: str | None = None
    ) -> list[MemoryRecord]:
        """List and format MemoryRecords from Memory Bank."""
        parent = self._resolve_parent()
        client = self._get_client()

        try:
            memories = client.list_memories(parent=parent)
            records: list[MemoryRecord] = []

            for m in memories:
                # Filter by scope if provided
                if scope:
                    matches_scope = True
                    for k, v in scope.items():
                        if m.scope.get(k) != v:
                            matches_scope = False
                            break
                    if not matches_scope:
                        continue

                # Parse fact text and provenance
                fact_text = m.fact
                provenance = None
                try:
                    parsed = json.loads(m.fact)
                    if isinstance(parsed, dict):
                        if "directive" in parsed:
                            fact_text = parsed["directive"]
                            if parsed.get("evidence_summary"):
                                fact_text = f"{parsed['directive']}\n{parsed['evidence_summary']}"
                            provenance = parsed.get("learned_from") or parsed.get("source") or "Channel analytics"
                        elif "channel_name" in parsed:
                            fact_text = f"Channel Profile: {parsed.get('channel_name')}. Pillars: {', '.join(parsed.get('content_pillars', []))}"
                            provenance = "Channel Profile"
                        elif "recurring_retention_patterns" in parsed:
                            fact_text = "Retention Patterns: " + "; ".join(parsed["recurring_retention_patterns"])
                            provenance = "Retention Analysis"
                        elif "historical_baselines" in parsed:
                            fact_text = "Historical Baselines: " + ", ".join(f"{k}={v}" for k, v in parsed["historical_baselines"].items())
                            provenance = "Performance Baselines"
                except Exception:
                    pass

                # Filter by query if provided
                if query and query.strip():
                    q = query.strip().lower()
                    if q not in fact_text.lower() and (not provenance or q not in provenance.lower()):
                        continue

                mem_id = m.name.split("/")[-1]
                rec = MemoryRecord(
                    name=m.name,
                    memory_id=mem_id,
                    fact=fact_text,
                    scope=dict(m.scope),
                    memory_type=getattr(m, "memory_type", "NATURAL_LANGUAGE_COLLECTION") or "NATURAL_LANGUAGE_COLLECTION",
                    provenance=provenance,
                    created_at=m.create_time if getattr(m, "create_time", None) else datetime.now(UTC),
                    updated_at=m.update_time if getattr(m, "update_time", None) else datetime.now(UTC),
                )
                records.append(rec)

            return records

        except Exception as exc:
            raise MemoryStoreError(f"Memory Bank list_memories error: {str(exc)}") from exc

    async def create_memory(
        self,
        fact: str,
        scope: dict[str, str],
        display_name: str = "",
        provenance: str | None = None,
    ) -> MemoryRecord:
        """Create a new memory in Google Memory Bank."""
        parent = self._resolve_parent()
        client = self._get_client()

        try:
            # If provenance is provided, we can store it cleanly in fact JSON or text
            stored_fact = fact
            if provenance:
                fact_obj = {"directive": fact, "evidence_summary": "", "source": provenance}
                stored_fact = json.dumps(fact_obj)

            resp = client.create_memory(
                parent=parent,
                memory=aiplatform_v1beta1.Memory(
                    display_name=display_name or "creator-memory",
                    fact=stored_fact,
                    scope=scope,
                ),
            )
            # In Google Cloud client SDK, create_memory returns an Operation (LRO)
            if hasattr(resp, "result") and callable(resp.result):
                memory_obj = resp.result()
                name = getattr(memory_obj, "name", "") or getattr(resp, "name", "")
            elif hasattr(resp, "name"):
                name = resp.name
            elif hasattr(resp, "response") and hasattr(resp.response, "name"):
                name = resp.response.name
            else:
                name = f"{parent}/memories/created"
            mem_id = name.split("/")[-1]
            now = datetime.now(UTC)
            return MemoryRecord(
                name=name,
                memory_id=mem_id,
                fact=fact,
                scope=scope,
                memory_type="NATURAL_LANGUAGE_COLLECTION",
                provenance=provenance or "Creator Added",
                created_at=now,
                updated_at=now,
            )

        except Exception as exc:
            raise MemoryStoreError(f"Memory Bank create_memory error: {str(exc)}") from exc

    async def delete_memory(self, memory_name_or_id: str) -> bool:
        """Delete a memory resource from Google Memory Bank."""
        parent = self._resolve_parent()
        client = self._get_client()

        if memory_name_or_id.startswith("projects/"):
            full_name = memory_name_or_id
        else:
            full_name = f"{parent}/memories/{memory_name_or_id}"

        try:
            client.delete_memory(name=full_name)
            return True
        except TypeError:
            # Google Cloud GAPIC client SDK unpacking quirk when DeleteMemory returns Memory in LRO payload
            return True
        except Exception as exc:
            if "Could not convert" in str(exc) or "Empty" in str(exc):
                return True
            raise MemoryStoreError(f"Memory Bank delete_memory error: {str(exc)}") from exc

    async def search_memories(
        self, query: str, scope: dict[str, str] | None = None, limit: int = 20
    ) -> list[MemoryRecord]:
        """Search memory records in Google Memory Bank."""
        # Query list_memories with filter
        records = await self.list_memories(scope=scope, query=query)
        return records[:limit]
