"""Canonical domain models for Agent Settings, Prompt Versioning, and Voice Configuration."""

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator

from croviq_domain.validators import validate_timezone_aware


class AgentId(StrEnum):
    """Supported Croviq agents."""

    LEO = "leo"
    MAYA = "maya"
    ALEX = "alex"


class AgentPromptConfig(BaseModel):
    """Creator-editable working prompt configuration for an agent."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    agent_id: AgentId = Field(
        ..., description="Target agent identifier (alex, leo, or maya)"
    )
    prompt_text: str = Field(
        ..., min_length=1, description="Complete agent working prompt text"
    )
    version: int = Field(default=1, ge=1, description="Monotonically increasing version number")
    updated_at: datetime = Field(..., description="Timestamp when the prompt was last updated")
    is_custom: bool = Field(default=False, description="Whether this prompt differs from system default")

    @field_validator("updated_at")
    @classmethod
    def check_tz(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class NarrationMode(StrEnum):
    """Narration audio mode."""

    ORIGINAL = "original"
    ENHANCED_ORIGINAL = "enhanced_original"
    STUDIO_VOICE = "studio_voice"


class VoiceCatalogItem(BaseModel):
    """Studio Voice catalog entry."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    voice_id: str = Field(..., min_length=1, description="Voice identifier")
    display_name: str = Field(..., min_length=1, description="Human readable voice name")
    gender: str = Field(default="neutral", description="Voice characteristic (female, male, neutral)")
    language_code: str = Field(default="en-US", description="Primary BCP-47 language code")
    description: str | None = Field(default=None, description="Brief tone or style description")


class VoiceSettingsConfig(BaseModel):
    """Creator-configured narration and Studio Voice settings."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    narration_mode: NarrationMode = Field(
        default=NarrationMode.ORIGINAL,
        description="Selected narration playback mode",
    )
    selected_voice: str = Field(
        default="Puck",
        min_length=1,
        description="Selected Studio Voice catalog voice identifier (Gemini TTS prebuilt voice)",
    )
    language: str = Field(
        default="en-US",
        min_length=2,
        description="Language code for synthesis",
    )
    updated_at: datetime = Field(..., description="Timestamp when settings were updated")

    @field_validator("updated_at")
    @classmethod
    def check_tz(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class VoiceSampleRequest(BaseModel):
    """Request to preview audio for a specific Studio Voice."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    voice_id: str = Field(..., min_length=1, description="Voice identifier to sample")
    sample_text: str = Field(
        default="Welcome to Croviq. I'll make your video clear, concise, and easy to follow.",
        min_length=1,
        max_length=500,
        description="Neutral fixed sample script",
    )


class VoiceSampleResponse(BaseModel):
    """Generated audio preview for voice audition."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    voice_id: str = Field(..., min_length=1)
    sample_text: str = Field(..., min_length=1)
    audio_base64: str = Field(..., min_length=1, description="Base64-encoded audio payload")
    content_type: str = Field(default="audio/mp3")
