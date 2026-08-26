"""API schemas for Production and Media Upload operations."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from croviq_domain.editorial import (
    AgentActivity,
    DirectorReview,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
)
from croviq_domain.edl import EditDecisionList

from croviq_domain.production import Production
from croviq_domain.transcript import Transcript
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact

class CreateUploadRequest(BaseModel):
    """Request payload to initiate a direct GCS media upload."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original name of the video file to upload",
        examples=["github_actions_tutorial.mp4"],
    )
    content_type: str = Field(
        ...,
        description="MIME content type of the video file (e.g. video/mp4, video/quicktime, video/webm)",
        examples=["video/mp4"],
    )
    size_bytes: int = Field(
        ...,
        gt=0,
        description="Declared size of the file in bytes (must be <= 1 GB)",
        examples=[104857600],
    )
    channel_id: str = Field(
        ...,
        min_length=1,
        description="Canonical channel identifier for this production (e.g. croviq_syn_ai_eng_01)",
        examples=["croviq_syn_ai_eng_01"],
    )


class CreateUploadResponse(BaseModel):
    """Response returned upon successfully registering an upload and generating a signed PUT URL."""

    model_config = ConfigDict(
        extra="forbid",
    )

    production_id: str = Field(
        ...,
        description="Unique identifier of the created Production record",
    )
    upload_id: str = Field(
        ...,
        description="Unique identifier of the source media upload",
    )
    upload_url: str = Field(
        ...,
        description="Pre-signed V4 Google Cloud Storage PUT URL for direct browser upload",
    )
    method: str = Field(
        default="PUT",
        description="HTTP method to use when uploading media directly to storage",
    )
    required_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Required HTTP headers (such as Content-Type) to send with the upload request",
    )
    expires_at: datetime = Field(
        ...,
        description="Timestamp when the pre-signed upload URL expires (UTC)",
    )


class ProductionListResponse(BaseModel):
    """Response returned when listing recent productions."""

    model_config = ConfigDict(
        extra="forbid",
    )

    productions: list[Production] = Field(
        default_factory=list,
        description="List of recent Production records",
    )
    total: int = Field(
        ...,
        description="Total number of productions returned",
    )


class TranscribeProductionResponse(BaseModel):
    """Response returned upon successfully transcribing a production's source media."""

    model_config = ConfigDict(
        extra="forbid",
    )
    status: Literal["completed", "already_transcribed"] = Field(
        ...,
        description="Transcription status ('completed' or 'already_transcribed')",
        examples=["completed"],
    )
    transcript_id: str = Field(
        ...,
        description="Unique identifier of the generated or retrieved transcript",
    )
    production_id: str = Field(
        ...,
        description="Identifier of the associated Production",
    )
    duration_ms: int = Field(
        ...,
        description="Total duration of the transcript in milliseconds",
    )
    word_count: int = Field(
        ...,
        description="Total number of word tokens in the transcript",
    )
    segment_count: int = Field(
        ...,
        description="Total number of phrase segments in the transcript",
    )
    language_code: str = Field(
        ...,
        description="Language code used for transcription",
    )
    transcript: Transcript = Field(
        ...,
        description="Full word-aligned transcript object",
    )


class AnalyzeProductionResponse(BaseModel):
    """Response returned when editorial analysis is completed."""

    model_config = ConfigDict(
        extra="forbid",
    )

    run_id: str = Field(
        ...,
        description="Unique identifier for the editorial run",
    )
    production_id: str = Field(
        ...,
        description="Associated production entity identifier",
    )
    status: EditorialRunStatus = Field(
        ...,
        description="Operational status of the run",
    )
    editor_proposal_id: str | None = Field(
        default=None,
        description="Identifier of the generated EditorProposal record",
    )
    director_review_id: str | None = Field(
        default=None,
        description="Identifier of the generated DirectorReview record",
    )
    started_at: datetime = Field(
        ...,
        description="Run start timestamp in UTC",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Run completion timestamp in UTC",
    )


class EditorialRunDetailResponse(BaseModel):
    """Detailed response for inspecting an editorial run, including proposal, review, and activities."""

    model_config = ConfigDict(
        extra="forbid",
    )

    run: EditorialRun = Field(
        ...,
        description="Operational record for the editorial run",
    )
    proposal: EditorProposal | None = Field(
        default=None,
        description="Leo's structured dialogue proposal",
    )
    review: DirectorReview | None = Field(
        default=None,
        description="Maya's structured director review",
    )
    activities: list[AgentActivity] = Field(
        default_factory=list,
        description="Product-facing agent activities generated during the run",
    )


class AssembleEDLResponse(BaseModel):
    """Response returned upon successfully assembling a canonical Edit Decision List."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    edl_id: str = Field(
        ...,
        description="Unique identifier for the assembled Edit Decision List",
    )
    production_id: str = Field(
        ...,
        description="Associated Production entity identifier",
    )
    version: int = Field(
        ...,
        description="Monotonically increasing version number for this production's EDL",
    )
    cut_count: int = Field(
        ...,
        description="Number of executable cut instructions (SAFE + NEEDS_COVERAGE)",
    )
    coverage_marker_count: int = Field(
        ...,
        description="Number of visual coverage markers (B-roll + jump cut covers)",
    )
    source_duration_ms: int = Field(
        ...,
        description="Total duration of the source video in milliseconds",
    )
    total_removed_duration_ms: int = Field(
        ...,
        description="Total duration removed by safe cuts in milliseconds",
    )
    estimated_target_duration_ms: int = Field(
        ...,
        description="Estimated final master video duration in milliseconds",
    )
    status: str = Field(
        default="READY",
        description="EDL readiness status for deterministic rendering",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the EDL was assembled in UTC",
    )


class EDLDetailResponse(BaseModel):
    """Detailed response for inspecting an EditDecisionList along with derived renderable segments."""

    model_config = ConfigDict(
        extra="forbid",
    )

    edl: EditDecisionList = Field(
        ...,
        description="Canonical EditDecisionList domain entity",
    )
    keep_segments: list[tuple[int, int]] = Field(
        ...,
        description="Ordered list of contiguous (start_ms, end_ms) media intervals to KEEP for master video render",
    )


class ProductionPlaybackResponse(BaseModel):
    """Response containing a short-lived signed GET URL for browser source video playback."""

    model_config = ConfigDict(
        extra="forbid",
    )

    production_id: str = Field(
        ...,
        description="Canonical unique production identifier",
    )
    playback_url: str = Field(
        ...,
        description="Short-lived keyless signed GET URL for browser video playback",
    )
    expires_at: datetime = Field(
        ...,
        description="UTC expiration timestamp of the signed playback URL",
    )


class RenderArtifactResponse(BaseModel):
    """Product-level response for a rendered media artifact."""

    model_config = ConfigDict(
        extra="forbid",
    )

    artifact_id: str = Field(
        ...,
        description="Canonical unique render artifact identifier",
    )
    production_id: str = Field(
        ...,
        description="Identifier of the associated production",
    )
    edl_id: str = Field(
        ...,
        description="Identifier of the source Edit Decision List",
    )
    artifact_type: ArtifactType = Field(
        ...,
        description="Type of rendered artifact: PREVIEW or MASTER",
    )
    status: ArtifactStatus = Field(
        ...,
        description="Lifecycle status: pending, rendering, completed, failed",
    )
    content_type: str = Field(
        default="video/mp4",
        description="MIME content type of the rendered media file",
    )
    size_bytes: int | None = Field(
        default=None,
        description="Verified file size in bytes",
    )
    duration_ms: int | None = Field(
        default=None,
        description="Verified media duration in milliseconds",
    )
    width: int | None = Field(
        default=None,
        description="Video stream width in pixels",
    )
    height: int | None = Field(
        default=None,
        description="Video stream height in pixels",
    )
    frame_rate: float | None = Field(
        default=None,
        description="Video stream frame rate (fps)",
    )
    video_codec: str | None = Field(
        default=None,
        description="Video codec name (e.g. h264)",
    )
    audio_codec: str | None = Field(
        default=None,
        description="Audio codec name (e.g. aac)",
    )
    playback_url: str | None = Field(
        default=None,
        description="Short-lived keyless signed GET URL for browser video playback if completed",
    )
    playback_expires_at: datetime | None = Field(
        default=None,
        description="UTC expiration timestamp of the signed playback URL if available",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the render record was initialized in UTC",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Timestamp when rendering completed in UTC",
    )
    failure_code: str | None = Field(
        default=None,
        description="Error code or failure reason if render failed",
    )

    @classmethod
    def from_domain(
        cls,
        artifact: RenderArtifact,
        playback_url: str | None = None,
        playback_expires_at: datetime | None = None,
    ) -> "RenderArtifactResponse":
        """Construct a product-level response from a canonical RenderArtifact domain model."""
        return cls(
            artifact_id=artifact.artifact_id,
            production_id=artifact.production_id,
            edl_id=artifact.edl_id,
            artifact_type=artifact.artifact_type,
            status=artifact.status,
            content_type=artifact.content_type,
            size_bytes=artifact.size_bytes,
            duration_ms=artifact.duration_ms,
            width=artifact.width,
            height=artifact.height,
            frame_rate=artifact.frame_rate,
            video_codec=artifact.video_codec,
            audio_codec=artifact.audio_codec,
            playback_url=playback_url,
            playback_expires_at=playback_expires_at,
            created_at=artifact.created_at,
            completed_at=artifact.completed_at,
            failure_code=artifact.failure_code,
        )


class RenderListResponse(BaseModel):
    """Response returning all render artifacts for a production."""

    model_config = ConfigDict(
        extra="forbid",
    )

    production_id: str = Field(
        ...,
        description="Canonical unique production identifier",
    )
    renders: list[RenderArtifactResponse] = Field(
        ...,
        description="List of all render artifacts associated with the production",
    )
