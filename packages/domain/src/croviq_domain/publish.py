"""Canonical domain models for deterministic YouTube Publishing and ThumbnailArtifact persistence."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class PublishJobStatus(StrEnum):
    """Lifecycle status of an external YouTube publishing job."""

    PENDING = "pending"
    AUTH_REQUIRED = "auth_required"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThumbnailUploadStatus(StrEnum):
    """Lifecycle status of custom thumbnail upload to YouTube."""

    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


def build_publish_idempotency_key(
    production_id: str,
    release_review_id: str,
    master_artifact_id: str,
    package_version: int | str,
    attempt: int = 1,
) -> str:
    """Build deterministic idempotency key for YouTube publication.

    Guarantees duplicate requests or retries never trigger duplicate remote video creations.
    """
    if not production_id or not production_id.strip():
        raise ValueError("production_id must be non-empty")
    if not release_review_id or not release_review_id.strip():
        raise ValueError("release_review_id must be non-empty")
    if not master_artifact_id or not master_artifact_id.strip():
        raise ValueError("master_artifact_id must be non-empty")

    return f"{production_id}:{release_review_id}:{master_artifact_id}:{package_version}:attempt_{attempt}"


def build_thumbnail_artifact_gcs_path(
    workspace_id: str,
    production_id: str,
    artifact_id: str,
    ext: str = "jpg",
) -> str:
    """Build canonical GCS object path for a private thumbnail image artifact."""
    if not workspace_id or not workspace_id.strip():
        raise ValueError("workspace_id must be non-empty")
    if not production_id or not production_id.strip():
        raise ValueError("production_id must be non-empty")
    if not artifact_id or not artifact_id.strip():
        raise ValueError("artifact_id must be non-empty")

    normalized_ext = ext.lstrip(".").lower()
    return f"workspaces/{workspace_id}/productions/{production_id}/thumbnails/{artifact_id}.{normalized_ext}"


class ThumbnailArtifact(BaseModel):
    """Canonical domain model representing an extracted still image thumbnail asset."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    artifact_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for thumbnail artifact (e.g. thumb_...)",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Associated production ID",
    )
    source_frame_ms: int = Field(
        ...,
        ge=0,
        description="Master video timeline millisecond offset of extracted frame",
    )
    gcs_bucket: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Private GCS bucket storing thumbnail image",
    )
    gcs_object: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="GCS object path of thumbnail image",
    )
    width: int = Field(
        ...,
        ge=1,
        description="Image width in pixels",
    )
    height: int = Field(
        ...,
        ge=1,
        description="Image height in pixels",
    )
    size_bytes: int = Field(
        ...,
        ge=1,
        le=2 * 1024 * 1024,  # Maximum 2MB allowed by YouTube Data API thumbnails.set
        description="Image file size in bytes (must be <= 2MB for YouTube API)",
    )
    content_type: str = Field(
        default="image/jpeg",
        description="MIME type (image/jpeg or image/png)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )

    @field_validator("created_at")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime:
        return validate_timezone_aware(v)


class YouTubePublishJob(BaseModel):
    """Canonical domain model for tracking YouTube publishing execution and lifecycle."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    publish_job_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for publish job (e.g. pub_...)",
    )
    production_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Associated production ID",
    )
    workspace_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Workspace tenant ID",
    )
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Initiating user ID",
    )
    connection_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Connected channel integration identifier",
    )
    channel_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Target YouTube channel ID",
    )
    release_review_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Approved Iris ReleaseReview ID",
    )
    package_version: int = Field(
        default=1,
        ge=1,
        description="Frozen package version number",
    )
    artifact_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Master RenderArtifact ID uploaded to YouTube",
    )
    artifact_type: str = Field(
        default="MASTER",
        description="Artifact type (MASTER)",
    )
    status: PublishJobStatus = Field(
        default=PublishJobStatus.PENDING,
        description="Current lifecycle status",
    )
    requested_privacy: str = Field(
        default="private",
        description="Creator requested privacy (private, unlisted, public)",
    )
    actual_privacy: str | None = Field(
        default=None,
        description="Actual privacy status confirmed by YouTube response",
    )
    master_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of published Master media",
    )
    master_duration_ms: int | None = Field(
        default=None,
        description="Duration in milliseconds of published Master media",
    )
    master_size_bytes: int | None = Field(
        default=None,
        description="File size in bytes of published Master media",
    )
    release_fingerprint: str | None = Field(
        default=None,
        description="Verified release fingerprint at publish time",
    )
    youtube_video_id: str | None = Field(
        default=None,
        description="Remote YouTube video ID returned after videos.insert",
    )
    youtube_url: str | None = Field(
        default=None,
        description="Canonical watch URL (https://youtu.be/{video_id})",
    )
    thumbnail_status: ThumbnailUploadStatus = Field(
        default=ThumbnailUploadStatus.PENDING,
        description="Thumbnail upload status",
    )
    thumbnail_artifact_id: str | None = Field(
        default=None,
        description="ThumbnailArtifact ID uploaded to thumbnails.set",
    )
    bytes_uploaded: int = Field(
        default=0,
        ge=0,
        description="Actual bytes uploaded so far",
    )
    total_bytes: int = Field(
        default=0,
        ge=0,
        description="Total media payload size in bytes",
    )
    progress_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Calculated upload progress percentage (0.0 - 100.0)",
    )
    error_code: str | None = Field(
        default=None,
        description="Standardized error code if failed",
    )
    error_message: str | None = Field(
        default=None,
        description="Creator-facing error explanation if failed",
    )
    is_synthetic_media: bool = Field(
        default=False,
        description="Creator-confirmed synthetic media disclosure (status.containsSyntheticMedia)",
    )
    made_for_kids: bool = Field(
        default=False,
        description="Creator-confirmed COPPA declaration (status.selfDeclaredMadeForKids)",
    )
    category_id: str = Field(
        default="28",
        description="YouTube category ID (default 28 for Science & Technology)",
    )
    selected_title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Final title for videos.insert (validated <= 100 characters)",
    )
    description: str = Field(
        ...,
        max_length=5000,
        description="Final description with embedded chapters (validated <= 5000 bytes)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for videos.insert",
    )
    audit_restriction_detected: bool = Field(
        default=False,
        description="True if YouTube restricted upload to private due to unverified API project audit status",
    )
    short_requested: bool = Field(
        default=False,
        description="True if separate Short upload was also selected",
    )
    short_artifact_id: str | None = Field(
        default=None,
        description="Short RenderArtifact ID if short upload requested",
    )
    short_publish_job_id: str | None = Field(
        default=None,
        description="Child publish job ID for Short upload",
    )
    short_youtube_video_id: str | None = Field(
        default=None,
        description="Remote YouTube video ID of uploaded Short",
    )
    short_youtube_url: str | None = Field(
        default=None,
        description="Canonical watch URL for Short",
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Deterministic idempotency key preventing duplicate uploads",
    )
    started_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when remote upload started",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when publication succeeded or failed",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last state update timestamp",
    )

    @field_validator("created_at", "updated_at", "started_at", "completed_at")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime | None:
        return validate_timezone_aware(v) if v is not None else None

    def mark_uploading(self, total_bytes: int) -> "YouTubePublishJob":
        now = datetime.now(timezone.utc)
        return self.model_copy(
            update={
                "status": PublishJobStatus.UPLOADING,
                "total_bytes": total_bytes,
                "bytes_uploaded": 0,
                "progress_percent": 0.0,
                "started_at": self.started_at or now,
                "updated_at": now,
            }
        )

    def update_progress(self, bytes_uploaded: int) -> "YouTubePublishJob":
        now = datetime.now(timezone.utc)
        pct = 0.0
        if self.total_bytes > 0:
            pct = min(100.0, round((bytes_uploaded / self.total_bytes) * 100.0, 1))
        return self.model_copy(
            update={
                "bytes_uploaded": bytes_uploaded,
                "progress_percent": pct,
                "updated_at": now,
            }
        )

    def mark_video_created(
        self,
        youtube_video_id: str,
        actual_privacy: str,
        audit_restriction_detected: bool = False,
    ) -> "YouTubePublishJob":
        now = datetime.now(timezone.utc)
        return self.model_copy(
            update={
                "status": PublishJobStatus.PROCESSING,
                "youtube_video_id": youtube_video_id,
                "youtube_url": f"https://youtu.be/{youtube_video_id}",
                "actual_privacy": actual_privacy,
                "audit_restriction_detected": audit_restriction_detected,
                "progress_percent": 100.0,
                "updated_at": now,
            }
        )

    def mark_completed(
        self,
        thumbnail_status: ThumbnailUploadStatus = ThumbnailUploadStatus.COMPLETED,
        short_youtube_video_id: str | None = None,
    ) -> "YouTubePublishJob":
        now = datetime.now(timezone.utc)
        updates: dict[str, Any] = {
            "status": PublishJobStatus.COMPLETED,
            "thumbnail_status": thumbnail_status,
            "progress_percent": 100.0,
            "completed_at": now,
            "updated_at": now,
        }
        if short_youtube_video_id:
            updates["short_youtube_video_id"] = short_youtube_video_id
            updates["short_youtube_url"] = f"https://youtu.be/{short_youtube_video_id}"
        return self.model_copy(update=updates)

    def mark_failed(self, error_code: str, error_message: str) -> "YouTubePublishJob":
        now = datetime.now(timezone.utc)
        return self.model_copy(
            update={
                "status": PublishJobStatus.FAILED,
                "error_code": error_code,
                "error_message": error_message,
                "completed_at": now,
                "updated_at": now,
            }
        )

    def mark_cancelled(self) -> "YouTubePublishJob":
        now = datetime.now(timezone.utc)
        return self.model_copy(
            update={
                "status": PublishJobStatus.CANCELLED,
                "completed_at": now,
                "updated_at": now,
            }
        )
