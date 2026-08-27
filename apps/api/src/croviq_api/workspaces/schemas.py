"""Pydantic schemas for Workspace and Agent Settings API endpoints."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from croviq_domain.agent_config import (
    AgentPromptConfig,
    NarrationMode,
    VoiceCatalogItem,
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
    selected_voice: str = Field(default="en-US-Journey-F", min_length=1)
    language: str = Field(default="en-US", min_length=2)


class MemoryItemResponse(BaseModel):
    """Single read-only memory entry displayed in creator Agent Settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    learned_from: str | None = Field(default=None)


class AgentMemorySummaryResponse(BaseModel):
    """Read-only summary of what Leo and Maya currently know."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    channel_title: str
    style_guide: str
    creator_preferences: list[str] = Field(default_factory=list)
    lessons: list[MemoryItemResponse] = Field(default_factory=list)


class AgentSettingsResponse(BaseModel):
    """Complete Agent Settings state returned to client."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    leo_prompt: AgentPromptConfig
    maya_prompt: AgentPromptConfig
    voice_settings: VoiceSettingsConfig
    voices: list[VoiceCatalogItem]
