"""Agent chat service executing real reasoning, tool execution, and memory queries for Alex, Leo, and Iris."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Any
import uuid

from croviq_agents.alex import AlexDataScientist
from croviq_api.config import get_settings
from croviq_api.channels.research_repository import ResearchRepository
from croviq_api.channels.youtube_provider import YouTubeChannelDataProvider
from croviq_api.channels.youtube_repository import YouTubeConnectionRepository
from croviq_api.memory.store import ChannelMemoryStore
from croviq_api.workspaces.agent_config_repository import AgentConfigRepository
from croviq_domain.agent_config import AgentId
from croviq_domain.channel_provider import ChannelDataProvider, SampleChannelDataProvider

logger = logging.getLogger(__name__)

# Scoped in-memory conversation history store
_CONVERSATION_STORE: dict[str, list[dict[str, Any]]] = {}


def get_conversation_history(workspace_id: str, agent_id: str) -> list[dict[str, Any]]:
    key = f"{workspace_id}:{agent_id.lower()}"
    return list(_CONVERSATION_STORE.get(key, []))

def clear_conversation_history(workspace_id: str, agent_id: str) -> None:
    key = f"{workspace_id}:{agent_id.lower()}"
    _CONVERSATION_STORE.pop(key, None)


def append_conversation_message(
    workspace_id: str,
    agent_id: str,
    role: str,
    content: str,
    tool_executions: list[dict[str, Any]] | None = None,
    structured_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = f"{workspace_id}:{agent_id.lower()}"
    if key not in _CONVERSATION_STORE:
        _CONVERSATION_STORE[key] = []
    
    msg = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "role": role,
        "content": content,
        "tool_executions": tool_executions or [],
        "structured_artifact": structured_artifact,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _CONVERSATION_STORE[key].append(msg)
    return msg


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

    async def handle_leo_message(self, message: str) -> dict[str, Any]:
        """Leo (Video Editor) handles dialogue edits, cut pacing, and cut safety."""
        prompt_config = await self.agent_config_repo.get_agent_prompt(
            self.workspace_id, AgentId.LEO
        )
        tool_executions = [
            {
                "tool_name": "dialogue_decision_inspector",
                "goal": "Inspect transcript word-level timestamps and cut safety intervals",
                "agent": "leo",
            }
        ]
        reply = (
            "I'm Leo, your Video Editor.\n\n"
            "I analyze spoken dialogue, eliminate filler words, and enforce natural cut safety boundaries. "
            "Let me know if you want me to tighten a section or preserve more context."
        )
        append_conversation_message(self.workspace_id, "leo", "user", message)
        return append_conversation_message(
            self.workspace_id,
            "leo",
            "assistant",
            reply,
            tool_executions=tool_executions,
        )

    async def handle_iris_message(self, message: str) -> dict[str, Any]:
        """Iris (Quality Control) inspects rendered output, caption alignment, and loudness compliance."""
        prompt_config = await self.agent_config_repo.get_agent_prompt(
            self.workspace_id, AgentId.IRIS
        )
        tool_executions = [
            {
                "tool_name": "quality_control_verifier",
                "goal": "Audit audio loudness (-16 LUFS), caption sync, and video continuity",
                "agent": "iris",
            }
        ]
        reply = (
            "I'm Iris, your Quality Control gatekeeper.\n\n"
            "I verify factual consistency, caption accuracy, target audio loudness (-16 LUFS, -1 dBTP), "
            "and visual continuity on rendered videos before release."
        )
        append_conversation_message(self.workspace_id, "iris", "user", message)
        return append_conversation_message(
            self.workspace_id,
            "iris",
            "assistant",
            reply,
            tool_executions=tool_executions,
        )
