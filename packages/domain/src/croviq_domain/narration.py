"""Canonical domain models for Narration, Studio Voice, and B-roll artifacts."""

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class NarrationSegmentStatus(StrEnum):
    """Status of a narration segment synthesis."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class NarrationSegment(BaseModel):
    """Minimal canonical narration segment representation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    segment_id: str = Field(..., min_length=1, description="Unique segment identifier")
    production_id: str = Field(..., min_length=1, description="Associated production identifier")
    source_start_ms: int = Field(..., ge=0, description="Start timestamp on source timeline in ms")
    source_end_ms: int = Field(..., ge=0, description="End timestamp on source timeline in ms")
    available_duration_ms: int = Field(..., ge=0, description="Strict maximum duration budget in ms")
    original_text: str = Field(..., min_length=1, description="Original spoken transcript text")
    rewritten_text: str = Field(..., min_length=1, description="Leo's editorial rewritten text")
    voice_id: str = Field(..., min_length=1, description="Selected Studio Voice identifier")
    generated_duration_ms: int = Field(default=0, ge=0, description="Actual measured TTS audio duration in ms")
    status: NarrationSegmentStatus = Field(default=NarrationSegmentStatus.PENDING)
    audio_artifact_reference: str | None = Field(default=None, description="GCS object or storage key")
    attempts: int = Field(default=1, ge=1, le=5, description="Number of TTS synthesis/rewrite attempts")
    tempo_adjustment: float = Field(default=1.0, ge=0.9, le=1.1, description="Applied tempo multiplier (max 3-5%)")

    @model_validator(mode="after")
    def validate_budget_and_times(self) -> "NarrationSegment":
        if self.source_end_ms < self.source_start_ms:
            raise ValueError("source_end_ms must be >= source_start_ms")
        expected_window = self.source_end_ms - self.source_start_ms
        if self.available_duration_ms == 0 and expected_window > 0:
            self.available_duration_ms = expected_window
        return self


class StudioVoiceResult(BaseModel):
    """Aggregated Studio Voice generation result for a production."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    production_id: str = Field(..., min_length=1)
    voice_id: str = Field(..., min_length=1)
    narration_mode: str = Field(default="studio_voice")
    segments: list[NarrationSegment] = Field(default_factory=list)
    total_segments: int = Field(default=0, ge=0)
    accepted_segments: int = Field(default=0, ge=0)
    all_within_budget: bool = Field(default=True)
    gcs_bucket: str | None = Field(default=None)
    gcs_object: str | None = Field(default=None)
    status: str = Field(default="completed")
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)

    @field_validator("created_at", "updated_at")
    @classmethod
    def check_tz(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)


class BRollArtifactStatus(StrEnum):
    """Lifecycle status of a B-roll planning or media asset."""

    PENDING = "pending"
    PLANNED = "planned"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class BRollQualityMode(StrEnum):
    """Explicit quality modes for Gemini Omni video generation."""

    DRAFT = "draft"
    STANDARD = "standard"
    FINISHING = "finishing"
    FOUR_K = "4k"


QUALITY_MODE_TO_RESOLUTION: dict[BRollQualityMode, str] = {
    BRollQualityMode.DRAFT: "360p",
    BRollQualityMode.STANDARD: "720p",
    BRollQualityMode.FINISHING: "1080p",
    BRollQualityMode.FOUR_K: "4k",
}

RESOLUTION_TO_QUALITY_MODE: dict[str, BRollQualityMode] = {
    "360p": BRollQualityMode.DRAFT,
    "720p": BRollQualityMode.STANDARD,
    "1080p": BRollQualityMode.FINISHING,
    "4k": BRollQualityMode.FOUR_K,
}


class BRollArtifact(BaseModel):
    """Canonical B-roll planning, media generation, and coverage recommendation artifact."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    artifact_id: str = Field(..., min_length=1, description="Unique artifact identifier")
    production_id: str = Field(..., min_length=1, description="Associated production identifier")
    decision_id: str | None = Field(default=None, description="Optional associated editor decision id")
    source_start_ms: int = Field(..., ge=0, description="Start time on source timeline in ms")
    source_end_ms: int = Field(..., ge=0, description="End time on source timeline in ms")
    gcs_bucket: str = Field(..., min_length=1)
    gcs_object: str = Field(..., min_length=1)
    duration_ms: int = Field(..., ge=0, description="Target clip duration in ms (~2000-10000ms)")
    status: BRollArtifactStatus = Field(default=BRollArtifactStatus.ACCEPTED)
    prompt_summary: str = Field(default="", description="Human summary of B-roll visual intent")
    quality_mode: BRollQualityMode = Field(default=BRollQualityMode.DRAFT, description="Generation quality mode")
    requested_resolution: str = Field(default="360p", description="Requested output resolution: 360p, 720p, 1080p, 4k")
    resolution: str = Field(default="360p", description="Output resolution: 360p, 720p, 1080p, 4k")
    actual_width: int | None = Field(default=None, description="Actual output video width in pixels")
    actual_height: int | None = Field(default=None, description="Actual output video height in pixels")
    requested_duration_ms: int = Field(default=3000, description="Requested generation duration in ms (3000-10000ms)")
    generated_duration_ms: int | None = Field(default=None, description="Actual generated video duration in ms from Omni")
    placement_duration_ms: int = Field(default=3000, description="Exact target EDL placement duration in ms")
    has_generated_audio: bool = Field(default=True, description="Whether the generated Omni asset contains an audio stream")
    audio_used_in_master: bool = Field(default=False, description="Whether generated Omni audio enters master mix (default: False / video-only)")
    sha256: str | None = Field(default=None, description="SHA256 hex digest of the raw generated video bytes")
    model: str = Field(default="gemini-omni-1.1-flash-preview", description="Model ID")
    task: str = Field(default="text_to_video", description="Interactions video generation task")
    is_draft: bool = Field(default=True, description="True if generated at 360p draft resolution")
    first_frame_uri: str | None = Field(default=None, description="Initial keyframe URI for transition interpolation")
    last_frame_uri: str | None = Field(default=None, description="Terminal keyframe URI for transition interpolation")
    reference_video_uri: str | None = Field(default=None, description="Optional video reference URI")
    interaction_id: str | None = Field(default=None, description="Interaction ID returned by Google Interactions API")
    previous_interaction_id: str | None = Field(default=None, description="Previous interaction ID for scene extension or continuation")
    scene_extension_prior_context_ms: int | None = Field(default=None, description="Scene extension prior context in ms")
    source_c2pa_present: bool = Field(default=True, description="Whether raw Omni source asset contains C2PA/JUMBF credentials")
    master_c2pa_status: str = Field(default="NOT PRESERVED / UNVERIFIED", description="C2PA provenance status of the final composed master")
    created_at: datetime = Field(...)

    @field_validator("created_at")
    @classmethod
    def check_tz(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)
