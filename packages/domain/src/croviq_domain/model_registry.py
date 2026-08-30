"""Canonical Model Registry & Capability Status Contract.

Defines the verified implementation and live upstream status for all AI models in Croviq.
UI surfaces and documentation must strictly adhere to the statuses declared here.
"""

from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class ModelImplementationStatus(StrEnum):
    """Implementation readiness of a model inside Croviq codebase."""

    IMPLEMENTED = "IMPLEMENTED"
    PLANNING_ONLY = "PLANNING_ONLY"
    BLOCKED = "BLOCKED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class UpstreamVerificationStatus(StrEnum):
    """Live Google-side verification status observed in production / Cloud Run."""

    YES = "YES"
    NO = "NO"
    UNSUPPORTED = "UNSUPPORTED"


class ModelCapabilityEntry(BaseModel):
    """Capability specification and verification record for a model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    model_id: str = Field(..., description="Canonical Google / Vertex AI model identifier")
    feature: str = Field(..., description="Croviq product feature powered by this model")
    code_path: str = Field(..., description="Primary code path / service invoking the model")
    implemented: ModelImplementationStatus = Field(..., description="Implementation status in codebase")
    live_upstream_proven: UpstreamVerificationStatus = Field(..., description="Google-side call proof status")
    last_verified_at: str = Field(..., description="ISO 8601 date string of last verification")
    draft_360p_verified: bool = Field(default=False, description="Whether 360p draft resolution control is verified")
    duration_control_verified: bool = Field(default=False, description="Whether duration control (3s-10s) is verified")
    audio_isolation_verified: bool = Field(default=False, description="Whether audio isolation (video-only B-roll) is verified")
    notes: str = Field(default="", description="Technical context or API constraints")


CANONICAL_MODEL_REGISTRY: list[ModelCapabilityEntry] = [
    ModelCapabilityEntry(
        model_id="gemini-3.7-flash",
        feature="Multimodal Reasoning & Editorial Decisions",
        code_path="croviq_agents.client.GoogleGenAIClient",
        implemented=ModelImplementationStatus.IMPLEMENTED,
        live_upstream_proven=UpstreamVerificationStatus.YES,
        last_verified_at="2026-08-29",
        notes="Multimodal video analysis, Leo editorial decisions, and Alex grounded research.",
    ),
    ModelCapabilityEntry(
        model_id="gemini-3.5-transcribe-preview",
        feature="Speech Transcription",
        code_path="croviq_media.transcript.GeminiTranscriptionService",
        implemented=ModelImplementationStatus.IMPLEMENTED,
        live_upstream_proven=UpstreamVerificationStatus.YES,
        last_verified_at="2026-08-29",
        notes="Word-level timestamped transcription on Vertex AI with audio input and text output tokens.",
    ),
    ModelCapabilityEntry(
        model_id="gemini-3.1-flash-tts-preview",
        feature="Studio Voice Narration Synthesis",
        code_path="croviq_agents.client.GoogleGenAIClient.synthesize_studio_voice",
        implemented=ModelImplementationStatus.IMPLEMENTED,
        live_upstream_proven=UpstreamVerificationStatus.YES,
        last_verified_at="2026-08-29",
        notes="Direct generate_content TTS call on Vertex AI returning 24kHz PCM audio adhering to hard duration budget.",
    ),
    ModelCapabilityEntry(
        model_id="gemini-omni-1.1-flash-preview",
        feature="B-Roll Video Generation & Visual Coverage",
        code_path="croviq_agents.client.GoogleGenAIClient.generate_broll_clip",
        implemented=ModelImplementationStatus.IMPLEMENTED,
        live_upstream_proven=UpstreamVerificationStatus.YES,
        last_verified_at="2026-08-29",
        draft_360p_verified=True,
        duration_control_verified=True,
        audio_isolation_verified=True,
        notes="Gemini Omni 1.1 Flash is operated through Vertex AI Interactions API (POST /v1beta1/projects/{project}/locations/global/interactions) for text-to-video, reference-to-video, and visual coverage B-roll.",
    ),
    ModelCapabilityEntry(
        model_id="lyria-3-pro-preview",
        feature="Background Music Generation (Long-form)",
        code_path="croviq_agents.client.GoogleGenAIClient.generate_background_music",
        implemented=ModelImplementationStatus.IMPLEMENTED,
        live_upstream_proven=UpstreamVerificationStatus.YES,
        last_verified_at="2026-08-30",
        duration_control_verified=True,
        notes="Google Lyria 3 Pro preview generates up to 184 seconds of minimal, subtle, modern instrumental background music with exact duration control.",
    ),
    ModelCapabilityEntry(
        model_id="lyria-3-clip-preview",
        feature="Background Music Generation (Short Clip)",
        code_path="croviq_agents.client.GoogleGenAIClient.generate_background_music",
        implemented=ModelImplementationStatus.IMPLEMENTED,
        live_upstream_proven=UpstreamVerificationStatus.YES,
        last_verified_at="2026-08-30",
        duration_control_verified=True,
        notes="Google Lyria 3 Clip preview generates 30-second music assets for short video formats.",
    ),
]


def get_model_capability(model_id: str) -> ModelCapabilityEntry | None:
    """Retrieve capability record for a specific model ID."""
    for entry in CANONICAL_MODEL_REGISTRY:
        if entry.model_id == model_id:
            return entry
    return None
