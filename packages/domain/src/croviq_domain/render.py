"""Canonical domain models for deterministic video rendering and RenderArtifact persistence."""

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator

from croviq_domain.validators import validate_timezone_aware


class ArtifactType(StrEnum):
    """Supported render artifact types."""

    SOURCE = "SOURCE"
    PREVIEW = "PREVIEW"
    MASTER = "MASTER"
    SHORT = "SHORT"
    VOICEOVER_PREVIEW = "VOICEOVER_PREVIEW"
    STUDIO_VOICE_PREVIEW = "STUDIO_VOICE_PREVIEW"
    STUDIO_VOICE_MASTER = "STUDIO_VOICE_MASTER"
    FINAL_MIX = "FINAL_MIX"


class ArtifactStatus(StrEnum):
    """Lifecycle status of a render artifact."""

    pending = "pending"
    rendering = "rendering"
    completed = "completed"
    failed = "failed"


def build_render_artifact_gcs_object_path(
    workspace_id: str,
    production_id: str,
    edl_id: str,
    artifact_type: ArtifactType | str,
) -> str:
    """Build canonical GCS object path for a private rendered media artifact.

    Layout:
    workspaces/{workspace_id}/productions/{production_id}/renders/{edl_id}/preview.mp4
    workspaces/{workspace_id}/productions/{production_id}/renders/{edl_id}/master.mp4
    """
    if not workspace_id or not workspace_id.strip():
        raise ValueError("workspace_id must be non-empty")
    if not production_id or not production_id.strip():
        raise ValueError("production_id must be non-empty")
    if not edl_id or not edl_id.strip():
        raise ValueError("edl_id must be non-empty")

    type_val = artifact_type.value if isinstance(artifact_type, ArtifactType) else str(artifact_type)
    type_normalized = type_val.lower()
    return f"workspaces/{workspace_id}/productions/{production_id}/renders/{edl_id}/{type_normalized}.mp4"


class RenderArtifact(BaseModel):
    """Canonical RenderArtifact model representing a rendered media artifact."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        frozen=False,
    )

    artifact_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the render artifact (e.g. art_...)",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Identifier of the associated production",
    )
    edl_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Identifier of the source Edit Decision List",
    )
    artifact_type: ArtifactType = Field(
        ...,
        description="Type of artifact: PREVIEW or MASTER",
    )
    status: ArtifactStatus = Field(
        default=ArtifactStatus.pending,
        description="Lifecycle status: pending, rendering, completed, failed",
    )
    gcs_bucket: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="GCS bucket storing the private rendered media object",
    )
    gcs_object: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="GCS object path of the rendered media file",
    )
    content_type: str = Field(
        default="video/mp4",
        min_length=1,
        max_length=128,
        description="MIME content type of the rendered media file",
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Exact file size in bytes verified after render",
    )
    sha256: str | None = Field(
        default=None,
        description="SHA-256 hash of the rendered media file verified after render",
    )
    duration_ms: int | None = Field(
        default=None,
        ge=0,
        description="Exact media duration in milliseconds verified via ffprobe",
    )
    width: int | None = Field(
        default=None,
        ge=1,
        description="Video stream width in pixels",
    )
    height: int | None = Field(
        default=None,
        ge=1,
        description="Video stream height in pixels",
    )
    frame_rate: float | None = Field(
        default=None,
        ge=0.0,
        description="Video stream frame rate (fps)",
    )
    video_codec: str | None = Field(
        default=None,
        max_length=64,
        description="Video codec name verified via ffprobe (e.g. h264)",
    )
    audio_codec: str | None = Field(
        default=None,
        max_length=64,
        description="Audio codec name verified via ffprobe (e.g. aac)",
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the render artifact record was initialized",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when rendering and metadata verification completed",
    )
    failure_code: str | None = Field(
        default=None,
        max_length=256,
        description="Error code or message if rendering failed",
    )
    edl_version: int | None = Field(
        default=None,
        description="EDL version from which this artifact was rendered",
    )
    voice_id: str | None = Field(
        default=None,
        description="Studio voice ID used in the render",
    )
    voiceover_artifact_id: str | None = Field(
        default=None,
        description="Source voiceover artifact ID included in this render",
    )
    music_gcs_object: str | None = Field(
        default=None,
        description="Background music GCS object included in this render",
    )
    music_volume_db: float | None = Field(
        default=None,
        description="Background music volume in dB configured at render time",
    )
    music_ducking_db: float | None = Field(
        default=None,
        description="Speech ducking attenuation in dB configured at render time",
    )
    music_is_muted: bool | None = Field(
        default=None,
        description="Whether background music was muted at render time",
    )

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return validate_timezone_aware(v)
        return v
