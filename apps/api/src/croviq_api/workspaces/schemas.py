"""Pydantic schemas for Workspace and Agent Settings API endpoints."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from croviq_domain.agent_config import (
    AgentPromptConfig,
    NarrationMode,
    VoiceCatalogItem,
    VoiceReplicationConfig,
    VoiceSampleRequest,
    VoiceSampleResponse,
    VoiceSettingsConfig,
)


class UpdatePromptRequest(BaseModel):
    """Request payload for updating an agent's working prompt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prompt_text: str = Field(..., min_length=1, description="Updated editorial working prompt")


class UpdateVoiceSettingsRequest(BaseModel):
    """Request payload for updating narration and Studio Voice settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    narration_mode: NarrationMode = Field(..., description="Selected narration mode")
    selected_voice: str = Field(default="Puck", min_length=1)
    language: str = Field(default="en-US", min_length=2)
    my_voice: VoiceReplicationConfig | None = Field(default=None, description="Optional My Voice replication configuration")

class MemoryItemResponse(BaseModel):
    """Single read-only memory entry displayed in creator Agent Settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    learned_from: str | None = Field(default=None)


class AgentMemorySummaryResponse(BaseModel):
    """Read-only summary of current channel memory."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    channel_title: str
    style_guide: str
    creator_preferences: list[str] = Field(default_factory=list)
    lessons: list[MemoryItemResponse] = Field(default_factory=list)


class AgentSettingsResponse(BaseModel):
    """Complete Agent Settings state returned to client."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    leo_prompt: AgentPromptConfig
    alex_prompt: AgentPromptConfig
    iris_prompt: AgentPromptConfig
    voice_settings: VoiceSettingsConfig
    voices: list[VoiceCatalogItem]


class ToolExecutionRecord(BaseModel):
    """Single internal tool execution trace for an agent message."""

    model_config = ConfigDict(extra="allow")
    tool_name: str = Field(..., description="Canonical tool name")
    goal: str | None = Field(default=None, description="Operational goal of tool execution")


class AgentChatMessageRequest(BaseModel):
    """Incoming user chat message to a specific agent."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(..., min_length=1, description="Message text sent by creator")
    context: dict[str, str] | None = Field(default=None, description="Optional production or channel context")


class AgentChatMessageResponse(BaseModel):
    """Single agent chat message with internal tool telemetry and optional structured artifacts."""

    model_config = ConfigDict(extra="allow")
    message_id: str
    role: str = Field(default="assistant")
    content: str
    tool_executions: list[dict[str, object]] = Field(default_factory=list)
    structured_artifact: dict[str, object] | None = None
    created_at: str


class AgentConversationHistoryResponse(BaseModel):
    """Conversation history for an agent workspace."""

    model_config = ConfigDict(extra="allow")
    agent_id: str
    messages: list[AgentChatMessageResponse] = Field(default_factory=list)
