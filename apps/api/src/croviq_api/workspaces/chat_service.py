"""Agent chat service executing real reasoning, tool execution, and memory queries for Alex.

Bounded ephemeral conversation storage:
- Max 50 messages per conversation (oldest FIFO evicted).
- Max 10,000 characters per message.
- 24-hour TTL with automatic eviction.
- Workspace, user, and agent scope isolation (`{workspace_id}:{user_id}:{agent_id}`).
- Ephemeral in-memory storage; durable knowledge lives in Google Agent Platform Memory Bank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
import logging
import os
from typing import Any, Sequence
import uuid

from croviq_agents.alex import AlexDataScientist
from croviq_agents.editor import LeoVideoEditor
from croviq_agents.tools import build_editor_chat_tool_registry
from croviq_api.config import get_settings
from croviq_api.channels.research_repository import ResearchRepository
from croviq_api.channels.youtube_provider import YouTubeChannelDataProvider
from croviq_api.channels.youtube_repository import YouTubeConnectionRepository
from croviq_api.memory.store import ChannelMemoryStore
from croviq_api.workspaces.agent_config_repository import AgentConfigRepository
from croviq_domain.agent_config import AgentId
from croviq_domain.channel_provider import ChannelDataProvider, SampleChannelDataProvider

logger = logging.getLogger(__name__)

MAX_MESSAGES_PER_CONVERSATION = 50
MAX_CHARS_PER_MESSAGE = 10_000
CONVERSATION_TTL_HOURS = 24


@dataclass
class ConversationEntry:
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class BoundedConversationStore:
    """Bounded, TTL-aware in-memory conversation store with workspace/user/agent isolation."""

    def __init__(
        self,
        *,
        max_messages: int = MAX_MESSAGES_PER_CONVERSATION,
        max_chars: int = MAX_CHARS_PER_MESSAGE,
        ttl_hours: int = CONVERSATION_TTL_HOURS,
    ) -> None:
        self._store: dict[str, ConversationEntry] = {}
        self._max_messages = max_messages
        self._max_chars = max_chars
        self._ttl = timedelta(hours=ttl_hours)

    def _build_key(self, workspace_id: str, agent_id: str, user_id: str | None = None) -> str:
        uid = (user_id or "default").strip()
        return f"{workspace_id.strip()}:{uid}:{agent_id.lower().strip()}"

    def _evict_expired(self) -> None:
        now = datetime.now(UTC)
        expired = [
            k
            for k, entry in self._store.items()
            if (now - entry.last_accessed_at) > self._ttl
        ]
        for k in expired:
            self._store.pop(k, None)

    def get_history(
        self, workspace_id: str, agent_id: str, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        self._evict_expired()
        key = self._build_key(workspace_id, agent_id, user_id)
        entry = self._store.get(key)
        if entry is None:
            return []
        entry.last_accessed_at = datetime.now(UTC)
        return list(entry.messages)

    def append_message(
        self,
        workspace_id: str,
        agent_id: str,
        role: str,
        content: str,
        tool_executions: list[dict[str, Any]] | None = None,
        structured_artifact: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        self._evict_expired()
        key = self._build_key(workspace_id, agent_id, user_id)
        if key not in self._store:
            self._store[key] = ConversationEntry()

        entry = self._store[key]
        entry.last_accessed_at = datetime.now(UTC)

        bounded_content = (
            content[: self._max_chars] if len(content) > self._max_chars else content
        )

        msg = {
            "message_id": f"msg_{uuid.uuid4().hex[:12]}",
            "role": role,
            "content": bounded_content,
            "tool_executions": tool_executions or [],
            "structured_artifact": structured_artifact,
            "created_at": datetime.now(UTC).isoformat(),
        }

        entry.messages.append(msg)
        if len(entry.messages) > self._max_messages:
            entry.messages = entry.messages[-self._max_messages :]
        return msg

    def clear(
        self, workspace_id: str, agent_id: str, user_id: str | None = None
    ) -> None:
        key = self._build_key(workspace_id, agent_id, user_id)
        self._store.pop(key, None)


_GLOBAL_CONVERSATION_STORE = BoundedConversationStore()


def get_conversation_history(
    workspace_id: str, agent_id: str, user_id: str | None = None
) -> list[dict[str, Any]]:
    return _GLOBAL_CONVERSATION_STORE.get_history(workspace_id, agent_id, user_id)


def clear_conversation_history(
    workspace_id: str, agent_id: str, user_id: str | None = None
) -> None:
    _GLOBAL_CONVERSATION_STORE.clear(workspace_id, agent_id, user_id)


def append_conversation_message(
    workspace_id: str,
    agent_id: str,
    role: str,
    content: str,
    tool_executions: list[dict[str, Any]] | None = None,
    structured_artifact: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    return _GLOBAL_CONVERSATION_STORE.append_message(
        workspace_id=workspace_id,
        agent_id=agent_id,
        role=role,
        content=content,
        tool_executions=tool_executions,
        structured_artifact=structured_artifact,
        user_id=user_id,
    )

async def get_production_chat_history(
    production_id: str,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load Leo production chat from Firestore, with bounded local storage outside cloud."""
    settings = get_settings()
    if not settings.is_production and not os.getenv("FIRESTORE_EMULATOR_HOST"):
        return get_conversation_history(f"production:{production_id}", "leo", user_id)
    from google.cloud.firestore import AsyncClient

    client = AsyncClient(project=settings.gcp_project_id or None)
    query = (
        client.collection("productions")
        .document(production_id)
        .collection("leo_chat")
        .order_by("created_at")
        .limit(MAX_MESSAGES_PER_CONVERSATION)
    )
    docs = [doc async for doc in query.stream()]
    messages: list[dict[str, Any]] = []
    for doc in docs:
        data = doc.to_dict()
        created_at = data.get("created_at")
        if isinstance(created_at, datetime):
            data["created_at"] = created_at.isoformat()
        data["message_id"] = doc.id
        messages.append(data)
    return messages


async def clear_production_chat_history(production_id: str, user_id: str | None = None) -> None:
    """Delete every persisted Leo chat message for one production."""
    settings = get_settings()
    if not settings.is_production and not os.getenv("FIRESTORE_EMULATOR_HOST"):
        clear_conversation_history(f"production:{production_id}", "leo", user_id)
        return
    from google.cloud.firestore import AsyncClient

    client = AsyncClient(project=settings.gcp_project_id or None)
    collection = (
        client.collection("productions")
        .document(production_id)
        .collection("leo_chat")
    )
    async for doc in collection.stream():
        await doc.reference.delete()


async def _append_production_chat_message(
    production_id: str,
    role: str,
    content: str,
    *,
    tool_executions: list[dict[str, Any]] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)
    payload = {
        "message_id": message_id,
        "role": role,
        "content": content[:MAX_CHARS_PER_MESSAGE],
        "tool_executions": tool_executions or [],
        "created_at": now.isoformat(),
    }
    if not settings.is_production and not os.getenv("FIRESTORE_EMULATOR_HOST"):
        local_message = append_conversation_message(
            f"production:{production_id}",
            "leo",
            role,
            content,
            tool_executions=tool_executions,
            user_id=user_id,
        )
        local_message.pop("structured_artifact", None)
        return local_message
    from google.cloud.firestore import AsyncClient

    client = AsyncClient(project=settings.gcp_project_id or None)
    reference = (
        client.collection("productions")
        .document(production_id)
        .collection("leo_chat")
        .document(message_id)
    )
    firestore_payload = dict(payload)
    firestore_payload["created_at"] = now
    firestore_payload["user_id"] = user_id
    await reference.set(firestore_payload)
    return payload


class AgentChatService:
    """Executes authentic agent conversations with domain tools, code execution, and persistent memory."""

    def __init__(
        self,
        *,
        workspace_id: str,
        agent_config_repo: AgentConfigRepository,
        memory_store: ChannelMemoryStore,
        youtube_repo: YouTubeConnectionRepository | None = None,
        research_repo: ResearchRepository | None = None,
    ) -> None:
        self.workspace_id = workspace_id
        self.agent_config_repo = agent_config_repo
        self.memory_store = memory_store
        self.youtube_repo = youtube_repo
        self.research_repo = research_repo

    async def handle_alex_message(
        self,
        message: str,
        *,
        channel_id: str = "croviq_syn_ai_eng_01",
    ) -> dict[str, Any]:
        """Alex (Data Scientist) investigates channel analytics, runs calculations, and returns evidence."""
        prompt_config = await self.agent_config_repo.get_agent_prompt(
            self.workspace_id, AgentId.ALEX
        )
        custom_prompt = prompt_config.prompt_text if prompt_config.is_custom else None

        # 1. Resolve active channel data provider
        provider: ChannelDataProvider = SampleChannelDataProvider()
        if self.youtube_repo:
            conn = await self.youtube_repo.get_connection(self.workspace_id)
            if conn and conn.connected and conn.access_token:
                try:
                    provider = YouTubeChannelDataProvider(access_token=conn.access_token)
                except Exception:
                    logger.warning("Falling back to sample provider for disconnected session")

        # 2. Extract channel history, videos, and memory safely
        channel = await provider.get_channel()
        raw_videos = await provider.get_videos(limit=100)
        # Order videos chronologically newest-first based on canonical published_at
        videos = sorted(
            raw_videos,
            key=lambda v: (
                getattr(getattr(v, "public", None), "published_at", None)
                or getattr(v, "published_at", None)
                or datetime.min.replace(tzinfo=UTC)
            ),
            reverse=True,
        )
        try:
            profile = await self.memory_store.get_profile(channel.channel_id)
        except Exception as exc:
            logger.warning("Memory profile retrieval non-fatal error: %s", exc)
            profile = None

        try:
            lessons = await self.memory_store.get_lessons(channel.channel_id)
        except Exception as exc:
            logger.warning("Memory lessons retrieval non-fatal error: %s", exc)
            lessons = []

        try:
            memory_records = await self.memory_store.list_memories(scope={"channel_id": channel.channel_id})
        except Exception as exc:
            logger.warning("Memory records list non-fatal error: %s", exc)
            memory_records = []

        # 3. Retrieve findings
        findings = []
        if self.research_repo:
            try:
                findings = await self.research_repo.list_findings(self.workspace_id, channel.channel_id, limit=5)
            except Exception:
                pass

        # 4. Get conversation history
        history = get_conversation_history(self.workspace_id, "alex")

        # 5. Execute Alex chat
        settings = get_settings()
        alex = AlexDataScientist(project_id=settings.gcp_project_id)
        chat_result = await alex.chat(
            message=message,
            conversation_history=history,
            channel_profile=profile,
            channel_lessons=lessons,
            memory_records=memory_records,
            channel=channel,
            videos=videos,
            findings=findings,
            custom_prompt=custom_prompt,
            workspace_id=self.workspace_id,
            channel_id=channel.channel_id,
        )

        reply = chat_result["reply"]
        tool_executions = chat_result.get("tool_executions", [])
        structured_artifact = chat_result.get("structured_artifact")

        append_conversation_message(self.workspace_id, "alex", "user", message)
        return append_conversation_message(
            self.workspace_id,
            "alex",
            "assistant",
            reply,
            tool_executions=tool_executions,
            structured_artifact=structured_artifact,
        )

    async def handle_leo_message(
        self,
        message: str,
        user_id: str | None = None,
        *,
        production: Any | None = None,
        media_metadata: Any | None = None,
        transcript: Any | None = None,
        proposal: Any | None = None,
        edl: Any | None = None,
        artifacts: Sequence[Any] | None = None,
        current_playhead_ms: int | None = None,
        selected_range: Sequence[int] | None = None,
        selected_element: dict[str, Any] | None = None,
        channel_profile: Any | None = None,
        lessons: list[Any] | None = None,
        editor: LeoVideoEditor | None = None,
        editorial_repo: Any | None = None,
        edl_repo: Any | None = None,
        proposal_id: str | None = None,
        callbacks: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Delegate production chat to Leo and durably persist every canonical state change."""
        if production is None or transcript is None or proposal is None or edl is None:
            reply = "Open a production in the Editor workspace to chat with Leo about its timeline."
            append_conversation_message(self.workspace_id, "leo", "user", message, user_id=user_id)
            return append_conversation_message(
                self.workspace_id,
                "leo",
                "assistant",
                reply,
                user_id=user_id,
            )

        production_id = production.production_id
        history = await get_production_chat_history(production_id, user_id)
        prompt_config = await self.agent_config_repo.get_agent_prompt(
            self.workspace_id, AgentId.LEO
        )
        custom_prompt = prompt_config.prompt_text if prompt_config.is_custom else None
        registry = build_editor_chat_tool_registry(
            production_id=production_id,
            transcript=transcript,
            proposal=proposal,
            edl=edl,
            artifacts=artifacts,
            media_metadata=media_metadata,
            callbacks=callbacks,
        )
        if editor is None:
            raise RuntimeError("Leo production chat requires the configured GenAI client")
        leo = editor
        leo._tool_registry = registry
        chat_result = await leo.chat(
            message=message,
            conversation_history=history,
            production=production,
            media_metadata=media_metadata,
            transcript=transcript,
            proposal=proposal,
            edl=edl,
            artifacts=artifacts,
            current_playhead_ms=current_playhead_ms,
            selected_range=selected_range,
            selected_element=selected_element,
            channel_profile=channel_profile,
            lessons=lessons,
            custom_prompt=custom_prompt,
        )

        updated_proposal = chat_result["proposal"]
        updated_edl = chat_result["edl"]
        if chat_result["timeline_updated"]:
            if editorial_repo is None or edl_repo is None or proposal_id is None:
                raise RuntimeError("Leo edit changed canonical state without persistence repositories")
            await editorial_repo.save_editor_proposal(updated_proposal, proposal_id=proposal_id)
            await edl_repo.save_edl(updated_edl)

        await _append_production_chat_message(
            production_id,
            "user",
            message,
            user_id=user_id,
        )
        assistant = await _append_production_chat_message(
            production_id,
            "assistant",
            chat_result["reply"],
            tool_executions=chat_result["tool_executions"],
            user_id=user_id,
        )
        assistant.update({
            "edl": updated_edl,
            "timeline_updated": chat_result["timeline_updated"],
            "voiceover_updated": chat_result["voiceover_updated"],
            "preview_updated": chat_result["preview_updated"],
            "seek_range": chat_result.get("seek_range"),
        })
        return assistant

    async def handle_iris_message(self, message: str, user_id: str | None = None) -> dict[str, Any]:
        """Iris (Quality Control) conversational chat activates in Release QA phase."""
        reply = (
            "Iris is active at the Release QA gate where she inspects rendered videos for loudness (-16 LUFS), "
            "caption sync, and factual integrity. Direct conversational chat with Iris will activate in the QA development phase."
        )
        append_conversation_message(self.workspace_id, "iris", "user", message, user_id=user_id)
        return append_conversation_message(
            self.workspace_id,
            "iris",
            "assistant",
            reply,
            user_id=user_id,
        )
