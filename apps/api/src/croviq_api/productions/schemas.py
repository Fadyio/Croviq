"""API schemas for Production and Media Upload operations."""

from datetime import datetime
from typing import Any, Literal
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
from croviq_domain.packaging import (
    CreatorPackageOverrides,
    PackagingChapter,
    PackagingProposal,
    ShortPackage,
    ThumbnailConcept,
)
from croviq_domain.transcript import Transcript
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.render_review import EditorSelfReview, RenderReview
from croviq_domain.narration import BRollArtifact, StudioVoiceResult
from croviq_domain.release_review import (
    ClaimSupportStatus,
    ClaimVerification,
    ReleaseChecklist,
    ReleaseIssue,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseReview,
    ReleaseStatus,
    ReleaseVerdict,
    ThumbnailEvaluation,
)
from croviq_domain.publish import (
    PublishJobStatus,
    ThumbnailArtifact,
    ThumbnailUploadStatus,
    YouTubePublishJob,
)
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


class ReviewPreviewResponse(BaseModel):
    """Response returned upon completing post-render preview review and Master render gating."""

    model_config = ConfigDict(
        extra="forbid",
    )

    production_id: str = Field(
        ...,
        description="Canonical unique production identifier",
    )
    review: RenderReview = Field(
        ...,
        description="Maya's post-render review record",
    )
    self_review: EditorSelfReview | None = Field(
        default=None,
        description="Leo's post-render self-review record",
    )
    master_artifact: RenderArtifactResponse | None = Field(
        default=None,
        description="Master render artifact if approved and rendered",
    )
    second_review: RenderReview | None = Field(
        default=None,
        description="Second post-render review if bounded correction was performed",
    )
    status: str = Field(
        ...,
        description="Current workflow status (complete, needs_manual_review, correcting, approved)",
    )
    activities: list[AgentActivity] = Field(
        default_factory=list,
        description="Product-facing agent activity messages emitted during review and correction",
    )


class RenderReviewDetailResponse(BaseModel):
    """Response containing latest and historical post-render reviews for a production."""

    model_config = ConfigDict(
        extra="forbid",
    )

    production_id: str = Field(
        ...,
        description="Canonical unique production identifier",
    )
    review: RenderReview | None = Field(
        default=None,
        description="Most recent post-render review record",
    )
    reviews: list[RenderReview] = Field(
        default_factory=list,
        description="All post-render review records for this production",
    )
    needs_manual_review: bool = Field(
        default=False,
        description="Whether production requires manual human review after exhausted bounded correction",
    )
class ProductionPlaybackResponse(BaseModel):
    """Playback URLs for all available media outputs of a production."""

    model_config = ConfigDict(extra="forbid")

    production_id: str = Field(..., description="Unique production identifier")
    playback_url: str | None = Field(default=None, description="Original source media playback URL")
    expires_at: datetime | None = Field(default=None, description="Expiration timestamp for signed URLs")
    rendered_preview_url: str | None = Field(default=None, description="Edited preview video playback URL")
    master_url: str | None = Field(default=None, description="Master video playback URL")
    studio_voice_preview_url: str | None = Field(default=None, description="Studio Voice video playback URL")
    short_playback_url: str | None = Field(default=None, description="Social Short video playback URL")

class StudioVoiceGenerationResponse(BaseModel):
    """Response returned upon generating Studio Voice narration for a production."""

    model_config = ConfigDict(extra="forbid")

    production_id: str = Field(..., description="Unique production identifier")
    result: StudioVoiceResult = Field(..., description="Aggregated Studio Voice result and segment details")
    studio_voice_preview_url: str | None = Field(default=None, description="Signed playback URL for Studio Voice preview")


class BRollListResponse(BaseModel):
    """Response listing generated B-roll artifacts for a production."""

    model_config = ConfigDict(extra="forbid")

    production_id: str = Field(..., description="Unique production identifier")
    artifacts: list[BRollArtifact] = Field(default_factory=list, description="List of generated B-roll clips")


class DeleteProductionResponse(BaseModel):
    """Response returned upon successful deletion of a production and all associated media storage objects."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="deleted", description="Operational status ('deleted')")
    production_id: str = Field(..., description="Unique production identifier")
    deleted_storage_objects_count: int = Field(default=0, description="Count of GCS media storage objects deleted")
    deleted_at: datetime = Field(..., description="UTC timestamp of the deletion")


class GeneratePackagingRequest(BaseModel):
    """Request payload to generate packaging proposal for a production."""

    model_config = ConfigDict(extra="forbid")

    force_regenerate: bool = Field(
        default=False,
        description="Whether to bypass cached proposal and generate a fresh packaging proposal",
    )


class UpdatePackagingOverridesRequest(BaseModel):
    """Request payload to update creator-selected packaging overrides."""

    model_config = ConfigDict(extra="forbid")

    selected_title: str | None = Field(default=None, description="Creator selected title")
    custom_title: str | None = Field(default=None, description="Creator custom title override")
    custom_description: str | None = Field(default=None, description="Creator custom description override")
    custom_chapters: list[PackagingChapter] | None = Field(default=None, description="Creator custom chapters override")
    custom_short_title: str | None = Field(default=None, description="Creator custom Short title override")
    custom_short_description: str | None = Field(default=None, description="Creator custom Short description override")
    selected_thumbnail_concept_id: str | None = Field(default=None, description="Selected thumbnail concept ID")


class PackagingDetailResponse(BaseModel):
    """Publish-ready packaging details including creator metadata and media references."""

    model_config = ConfigDict(extra="forbid")

    production_id: str = Field(..., description="Unique production identifier")
    proposal: PackagingProposal | None = Field(default=None, description="Latest packaging proposal if present")
    overrides: CreatorPackageOverrides | None = Field(default=None, description="Creator-defined package overrides")
    effective_title: str = Field(..., description="Active title to publish")
    effective_description: str = Field(default="", description="Active description to publish")
    effective_chapters: list[PackagingChapter] = Field(default_factory=list, description="Active canonical video chapters")
    effective_short_package: ShortPackage | None = Field(default=None, description="Active vertical Short packaging")
    effective_thumbnail_concept_id: str | None = Field(default=None, description="Active selected thumbnail concept ID")
    master_artifact: RenderArtifactResponse | None = Field(default=None, description="Master video artifact details")
    short_artifact: RenderArtifactResponse | None = Field(default=None, description="Short video artifact details")
    master_url: str | None = Field(default=None, description="Signed playback URL for master video")
    short_url: str | None = Field(default=None, description="Signed playback URL for short video")
    has_master: bool = Field(default=False, description="Whether an approved master video artifact exists")
    has_short: bool = Field(default=False, description="Whether a vertical Short video artifact exists")
    status: str = Field(default="completed", description="Packaging readiness status ('completed' or 'needs_master')")
    generated_at: datetime | None = Field(default=None, description="UTC timestamp of last proposal generation")


class GenerateReleaseReviewRequest(BaseModel):
    """Request payload to execute Iris QA review."""

    model_config = ConfigDict(extra="forbid")

    force_regenerate: bool = Field(
        default=False,
        description="Whether to bypass cached review and execute a fresh Iris QA pass",
    )


class ReleaseReviewDetailResponse(BaseModel):
    """Comprehensive release evaluation, checklist, media playback, and publishing readiness."""

    model_config = ConfigDict(extra="forbid")

    production_id: str = Field(..., description="Unique production identifier")
    review: ReleaseReview | None = Field(default=None, description="Latest Iris QA release review")
    release_status: str = Field(..., description="Creator-facing release pipeline status")
    release_ready: bool = Field(default=False, description="Whether output satisfies all release gate conditions")
    checklist: ReleaseChecklist | None = Field(default=None, description="Compact release verification checklist")
    master_artifact: RenderArtifactResponse | None = Field(default=None, description="Master video artifact details")
    short_artifact: RenderArtifactResponse | None = Field(default=None, description="Short video artifact details")
    master_url: str | None = Field(default=None, description="Signed playback URL for master video")
    short_url: str | None = Field(default=None, description="Signed playback URL for short video")
    has_master: bool = Field(default=False, description="Whether approved Master video artifact exists")
    has_short: bool = Field(default=False, description="Whether vertical Short video artifact exists")
    has_packaging: bool = Field(default=False, description="Whether packaging proposal exists")
    generated_at: datetime | None = Field(default=None, description="UTC timestamp of review generation")
    release_fingerprint: str | None = Field(default=None, description="SHA-256 cryptographic release fingerprint locking immutable pipeline inputs")



class PublishPreparationResponse(BaseModel):
    """Pre-publish parameters, channel verification, and suggested metadata for confirmation drawer."""

    model_config = ConfigDict(extra="forbid")

    production_id: str = Field(..., description="Production identifier")
    channel_title: str = Field(..., description="Connected YouTube channel title or 'Croviq Sample Channel'")
    channel_avatar_url: str = Field(default="", description="Channel avatar icon URL")
    is_sample_channel: bool = Field(default=False, description="True if using synthetic sample channel that cannot publish")
    can_publish: bool = Field(default=False, description="True if a real YouTube channel is connected")
    has_upload_access: bool = Field(default=False, description="True if youtube.upload OAuth scope is granted")
    master_duration_ms: int | None = Field(default=None, description="Master video duration in milliseconds")
    master_title: str = Field(..., description="Master video title")
    suggested_title: str = Field(..., description="Active title candidate or creator override")
    suggested_description: str = Field(..., description="Active description with embedded chapters")
    suggested_chapters: list[PackagingChapter] = Field(default_factory=list, description="Verified YouTube chapters")
    suggested_tags: list[str] = Field(default_factory=list, description="Keywords for YouTube tags")
    suggested_category_id: str = Field(default="28", description="Default category ID (28 = Science & Technology)")
    suggested_synthetic_media: bool = Field(default=False, description="Suggested synthetic media disclosure based on Studio Voice/BRoll")
    verified_thumbnail_frames: list[dict[str, Any]] = Field(default_factory=list, description="Verified thumbnail frame candidates")
    has_short: bool = Field(default=False, description="Whether an approved vertical Short artifact exists")
    short_title: str | None = Field(default=None, description="Short title candidate")
    short_description: str | None = Field(default=None, description="Short description candidate")
    release_ready: bool = Field(default=False, description="Whether Iris has approved the release (verdict PASS)")

    release_fingerprint: str | None = Field(default=None, description="SHA-256 release fingerprint locking release inputs")

class PublishRequest(BaseModel):
    """Creator-confirmed request payload to trigger YouTube publication."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    requested_privacy: Literal["private", "unlisted", "public"] = Field(
        default="private",
        description="Target privacy status (default private)",
    )
    made_for_kids: bool = Field(
        default=False,
        description="Creator-confirmed declaration: is content made for kids? (COPPA)",
    )
    contains_synthetic_media: bool = Field(
        default=False,
        description="Creator-confirmed declaration: does content contain altered or synthetic media?",
    )
    selected_title: str | None = Field(
        default=None,
        max_length=100,
        description="Optional custom title override (validated <= 100 characters)",
    )
    selected_description: str | None = Field(
        default=None,
        max_length=5000,
        description="Optional custom description override (validated <= 5000 bytes)",
    )
    selected_tags: list[str] | None = Field(
        default=None,
        description="Optional tags list override",
    )
    category_id: str = Field(
        default="28",
        description="YouTube category ID (default 28)",
    )
    thumbnail_frame_ms: int | None = Field(
        default=None,
        ge=0,
        description="Selected timeline millisecond offset for extracting thumbnail still image",
    )
    upload_short: bool = Field(
        default=False,
        description="Whether to also upload the approved vertical Short as a separate video",
    )


class PublishJobDetailResponse(BaseModel):
    """Active publish job state, remote video IDs, upload progress, and audit restrictions."""

    model_config = ConfigDict(extra="forbid")

    job: YouTubePublishJob | None = Field(default=None, description="Current or latest YouTube publish job")
    can_publish: bool = Field(default=False, description="True if real YouTube channel is connected")
    has_upload_access: bool = Field(default=False, description="True if youtube.upload OAuth scope is granted")
    status_message: str = Field(default="", description="Creator-facing status or restriction message")
    is_sample_channel: bool = Field(default=False, description="True if synthetic sample channel is active")
