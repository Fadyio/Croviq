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
    NINA = "nina"

class AgentPromptConfig(BaseModel):
    """Creator-editable working prompt configuration for an agent."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    agent_id: AgentId = Field(
        ..., description="Target agent identifier (alex, leo, maya, or nina)"
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
    MY_VOICE = "my_voice"


class VoiceReplicationStatus(StrEnum):
    """Capability / operational state for Gemini 3.1 Flash TTS My Voice replication."""

    AVAILABLE = "available"
    BLOCKED = "blocked"
    CONSENT_REQUIRED = "consent_required"
    EXPIRED = "expired"


GOOGLE_VOICE_CONSENT_PHRASE_EN: str = (
    "I am the owner of this voice and have consented to the creation of a synthetic model of my voice through the use of Google Cloud."
)


class VoiceReplicationConfig(BaseModel):
    """My Voice configuration for creator voice replication."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    status: VoiceReplicationStatus = Field(
        default=VoiceReplicationStatus.CONSENT_REQUIRED,
        description="Replication access and lifecycle status",
    )
    voice_key: str | None = Field(
        default=None,
        description="Encrypted/persisted Vertex Voices API voice key (expires in 7 days)",
    )
    key_expires_at: datetime | None = Field(
        default=None,
        description="Expiration datetime for the replicated voice key (7-day maximum TTL)",
    )
    consent_recorded: bool = Field(
        default=False,
        description="Whether creator consent audio has been verified with exact required phrase",
    )
    source_sample_start_ms: int | None = Field(
        default=None,
        description="Start offset in source video of clean 10-30s speech sample",
    )
    source_sample_end_ms: int | None = Field(
        default=None,
        description="End offset in source video of clean 10-30s speech sample",
    )
    blocked_reason: str | None = Field(
        default=None,
        description="Reason why voice replication is blocked (e.g. Google allowlist access required)",
    )
    suggested_action: str | None = Field(
        default=None,
        description="Suggested resolution action when blocked",
    )

    @field_validator("key_expires_at")
    @classmethod
    def check_tz(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return validate_timezone_aware(v)

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
    my_voice: VoiceReplicationConfig | None = Field(
        default=None,
        description="My Voice replication settings and consent status",
    )

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
