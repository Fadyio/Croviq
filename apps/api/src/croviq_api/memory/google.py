"""Google Agent Platform Memory Bank adapter for ChannelMemoryStore."""

import asyncio
from datetime import datetime, timezone
import json
import time
from typing import Any
import httpx

import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest

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
        self._credentials = None
        self._auth_request = GoogleAuthRequest()

        # Google Agent Platform / Vertex AI Regional Endpoint
        self.base_url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1beta1/"
            f"projects/{self.project_id}/locations/{self.location}/memoryBanks/{self.memory_bank_id}"
        )
        self.resource_name = (
            f"projects/{self.project_id}/locations/{self.location}/memoryBanks/{self.memory_bank_id}"
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Obtain fresh Google Cloud authorization headers via Application Default Credentials."""
        if self._credentials is None:
            self._credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        if not self._credentials.valid:
            self._credentials.refresh(self._auth_request)
        return {
            "Authorization": f"Bearer {self._credentials.token}",
            "Content-Type": "application/json",
        }

    async def get_profile(self, channel_id: str) -> ChannelMemoryProfile | None:
        """Retrieve structured ChannelMemoryProfile from Memory Bank."""
        start_time = time.monotonic()
        url = f"{self.base_url}/memories:retrieveProfiles"
        payload = {
            "scope": {"channel_id": channel_id},
            "schemaId": self.SCHEMA_ID_PROFILE,
        }

        try:
            headers = self._get_auth_headers()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

            latency_ms = (time.monotonic() - start_time) * 1000.0

            if response.status_code == 404:
                log_memory_event(
                    event_type="memory.profile.retrieve",
                    channel_id=channel_id,
                    status=404,
                    latency_ms=latency_ms,
                    memory_schema_id=self.SCHEMA_ID_PROFILE,
                    memory_bank_resource=self.resource_name,
                    message=f"Memory profile for channel '{channel_id}' not found in Memory Bank.",
                )
                return None

            if response.status_code != 200:
                error_msg = f"Memory Bank retrieveProfiles failed ({response.status_code}): {response.text}"
                log_memory_event(
                    event_type="memory.profile.failed",
                    channel_id=channel_id,
                    status=response.status_code,
                    latency_ms=latency_ms,
                    memory_schema_id=self.SCHEMA_ID_PROFILE,
                    memory_bank_resource=self.resource_name,
                    message=error_msg,
                    error_code="memory_bank_retrieve_failed",
                )
                raise MemoryStoreError(error_msg, status_code=response.status_code)

            data = response.json()
            profiles_data = data.get("profiles", [])
            if not profiles_data:
                # Also check top-level fields or memories
                if "fields" in data:
                    raw_profile = data["fields"]
                elif "structuredMemory" in data:
                    raw_profile = data["structuredMemory"].get("fields", {})
                else:
                    log_memory_event(
                        event_type="memory.profile.retrieve",
                        channel_id=channel_id,
                        status=200,
                        latency_ms=latency_ms,
                        memory_schema_id=self.SCHEMA_ID_PROFILE,
                        memory_bank_resource=self.resource_name,
                        message="No profiles found in Memory Bank response.",
                    )
                    return None
            else:
                profile_entry = profiles_data[0]
                raw_profile = profile_entry.get("fields", profile_entry)

            # Ensure channel_id is present
            if "channel_id" not in raw_profile:
                raw_profile["channel_id"] = channel_id

            profile = ChannelMemoryProfile.model_validate(raw_profile)

            log_memory_event(
                event_type="memory.profile.retrieve",
                channel_id=channel_id,
                status=200,
                latency_ms=latency_ms,
                memory_schema_id=self.SCHEMA_ID_PROFILE,
                memory_bank_resource=self.resource_name,
                message=f"Successfully retrieved memory profile for channel '{channel_id}'.",
            )
            return profile

        except MemoryStoreError:
            raise
        except Exception as exc:
            latency_ms = (time.monotonic() - start_time) * 1000.0
            log_memory_event(
                event_type="memory.profile.failed",
                channel_id=channel_id,
                status=500,
                latency_ms=latency_ms,
                memory_schema_id=self.SCHEMA_ID_PROFILE,
                memory_bank_resource=self.resource_name,
                message=f"Exception during Memory Bank retrieve: {type(exc).__name__}: {str(exc)}",
                error_code="memory_bank_retrieve_exception",
                exception=exc,
            )
            raise MemoryStoreError(f"Memory Bank retrieval error: {str(exc)}") from exc

    async def upsert_profile(self, profile: ChannelMemoryProfile) -> ChannelMemoryProfile:
        """Persist or update structured ChannelMemoryProfile in Memory Bank."""
        start_time = time.monotonic()
        channel_id = profile.channel_id

        log_memory_event(
            event_type="memory.profile.generate.started",
            channel_id=channel_id,
            status=200,
            memory_schema_id=self.SCHEMA_ID_PROFILE,
            memory_bank_resource=self.resource_name,
            message=f"Starting profile persist for channel '{channel_id}'.",
        )

        url = f"{self.base_url}/memories"
        profile_dict = profile.model_dump(mode="json")
        payload = {
            "scope": {"channel_id": channel_id},
            "structuredMemory": {
                "schemaId": self.SCHEMA_ID_PROFILE,
                "fields": profile_dict,
            },
        }

        try:
            headers = self._get_auth_headers()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

            latency_ms = (time.monotonic() - start_time) * 1000.0

            if response.status_code not in (200, 201):
                error_msg = f"Memory Bank memory creation failed ({response.status_code}): {response.text}"
                log_memory_event(
                    event_type="memory.profile.failed",
                    channel_id=channel_id,
                    status=response.status_code,
                    latency_ms=latency_ms,
                    memory_schema_id=self.SCHEMA_ID_PROFILE,
                    memory_bank_resource=self.resource_name,
                    message=error_msg,
                    error_code="memory_bank_upsert_failed",
                )
                raise MemoryStoreError(error_msg, status_code=response.status_code)

            log_memory_event(
                event_type="memory.profile.generate.completed",
                channel_id=channel_id,
                status=response.status_code,
                latency_ms=latency_ms,
                memory_schema_id=self.SCHEMA_ID_PROFILE,
                memory_bank_resource=self.resource_name,
                message=f"Successfully persisted memory profile for channel '{channel_id}'.",
            )
            return profile

        except MemoryStoreError:
            raise
        except Exception as exc:
            latency_ms = (time.monotonic() - start_time) * 1000.0
            log_memory_event(
                event_type="memory.profile.failed",
                channel_id=channel_id,
                status=500,
                latency_ms=latency_ms,
                memory_schema_id=self.SCHEMA_ID_PROFILE,
                memory_bank_resource=self.resource_name,
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
        start_time = time.monotonic()
        url = f"{self.base_url}/memories:retrieve"
        payload = {
            "scope": {"channel_id": channel_id},
        }

        try:
            headers = self._get_auth_headers()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 404:
                return []

            if response.status_code != 200:
                raise MemoryStoreError(
                    f"Memory Bank retrieve lessons failed ({response.status_code}): {response.text}",
                    status_code=response.status_code,
                )

            data = response.json()
            memories = data.get("memories", [])
            lessons: list[ChannelLesson] = []

            for mem in memories:
                struct_mem = mem.get("structuredMemory", {})
                if struct_mem.get("schemaId") == self.SCHEMA_ID_LESSON:
                    fields = struct_mem.get("fields", {})
                    try:
                        lesson = ChannelLesson.model_validate(fields)
                        lessons.append(lesson)
                    except Exception:
                        continue

            if target_agent is not None:
                agent_val = target_agent.value if isinstance(target_agent, TargetAgent) else str(target_agent)
                lessons = [l for l in lessons if l.target_agent.value == agent_val]

            return lessons

        except MemoryStoreError:
            raise
        except Exception as exc:
            raise MemoryStoreError(f"Memory Bank lessons retrieval error: {str(exc)}") from exc

    async def add_lesson(self, lesson: ChannelLesson) -> ChannelLesson:
        """Persist a single ChannelLesson into Memory Bank."""
        url = f"{self.base_url}/memories"
        payload = {
            "scope": {"channel_id": lesson.channel_id},
            "structuredMemory": {
                "schemaId": self.SCHEMA_ID_LESSON,
                "fields": lesson.model_dump(mode="json"),
            },
        }

        try:
            headers = self._get_auth_headers()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

            if response.status_code not in (200, 201):
                raise MemoryStoreError(
                    f"Memory Bank lesson create failed ({response.status_code}): {response.text}",
                    status_code=response.status_code,
                )

            return lesson

        except MemoryStoreError:
            raise
        except Exception as exc:
            raise MemoryStoreError(f"Memory Bank add_lesson error: {str(exc)}") from exc
