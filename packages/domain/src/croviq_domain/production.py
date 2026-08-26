import os
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from croviq_domain.validators import validate_timezone_aware

# Canonical maximum upload file size: 1 GB (1,073,741,824 bytes) (approved)
MAX_UPLOAD_SIZE_BYTES: int = 1_073_741_824

# Canonical signed URL expiry: 30 minutes (1800 seconds) (approved)
DEFAULT_SIGNED_URL_EXPIRY_SECONDS: int = 1800
# Canonical allowed media MIME types and their valid extensions
ALLOWED_MEDIA_TYPES: dict[str, list[str]] = {
    "video/mp4": [".mp4", ".m4v"],
    "video/quicktime": [".mov"],
    "video/webm": [".webm"],
}


class ProductionStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"


class SourceMediaStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"


def sanitize_filename(filename: str) -> str:
    """Sanitize raw upload filename into a safe base filename.

    Prevents directory traversal, removes dangerous characters, and preserves extension.
    """
    if not filename or not filename.strip():
        return "source_media.bin"

    # Take basename only to prevent directory traversal
    clean = Path(filename).name.strip()
    # Replace backslashes if present
    clean = clean.replace("\\", "/")
    clean = Path(clean).name

    stem = Path(clean).stem
    ext = Path(clean).suffix.lower()

    # Replace any character other than alphanumeric, underscore, and hyphen with underscore
    safe_stem = re.sub(r"[^\w\-]+", "_", stem).strip("_")
    if not safe_stem:
        safe_stem = "source_media"

    if ext:
        safe_ext = re.sub(r"[^\w\.]+", "", ext)
        return f"{safe_stem}{safe_ext}"
    return safe_stem


def validate_media_file(
    filename: str,
    content_type: str,
    size_bytes: int,
) -> tuple[str, str]:
    """Validate media file metadata for raw uploads.

    Returns:
        tuple[str, str]: normalized (content_type, extension)
    """
    if size_bytes <= 0:
        raise ValueError("File size must be greater than 0 bytes")
    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"File size {size_bytes} exceeds maximum allowed size of {MAX_UPLOAD_SIZE_BYTES} bytes (1 GB)"
        )

    norm_content_type = content_type.strip().lower()
    if norm_content_type not in ALLOWED_MEDIA_TYPES:
        allowed = ", ".join(ALLOWED_MEDIA_TYPES.keys())
        raise ValueError(
            f"Unsupported content type '{content_type}'. Allowed types: {allowed}"
        )

    valid_extensions = ALLOWED_MEDIA_TYPES[norm_content_type]
    ext = Path(filename).suffix.lower()
    if not ext or ext not in valid_extensions:
        allowed_exts = ", ".join(valid_extensions)
        raise ValueError(
            f"Extension '{ext}' does not match content type '{content_type}'. Allowed: {allowed_exts}"
        )

    return norm_content_type, ext


def build_source_media_gcs_object_path(
    workspace_id: str,
    production_id: str,
    upload_id: str,
    filename: str,
) -> str:
    """Build canonical GCS object path for raw source media.

    Format: workspaces/{workspace_id}/productions/{production_id}/source/{upload_id}/{safe_filename}
    """
    safe_name = sanitize_filename(filename)
    return f"workspaces/{workspace_id}/productions/{production_id}/source/{upload_id}/{safe_name}"


class SourceMedia(BaseModel):
    """Canonical SourceMedia model representing raw uploaded video metadata."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    upload_id: str = Field(
        ...,
        min_length=1,
        description="Unique upload identifier",
    )
    original_filename: str = Field(
        ...,
        min_length=1,
        description="Original user-provided filename",
    )
    content_type: str = Field(
        ...,
        description="MIME content type of the media file",
    )
    size_bytes: int = Field(
        ...,
        gt=0,
        description="Declared or verified size of the media file in bytes",
    )
    gcs_bucket: str = Field(
        ...,
        min_length=1,
        description="Target Google Cloud Storage bucket name",
    )
    gcs_object: str = Field(
        ...,
        min_length=1,
        description="Target Google Cloud Storage object path",
    )
    status: SourceMediaStatus = Field(
        default=SourceMediaStatus.PENDING,
        description="Upload lifecycle status",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the upload record was created (UTC)",
    )
    uploaded_at: datetime | None = Field(
        default=None,
        description="Timestamp when the media upload was verified and completed (UTC)",
    )

    @field_validator("created_at")
    @classmethod
    def check_created_at_timezone(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)

    @field_validator("uploaded_at")
    @classmethod
    def check_uploaded_at_timezone(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            return validate_timezone_aware(v)
        return v


class Production(BaseModel):
    """Canonical Production model representing a content production lifecycle."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    production_id: str = Field(
        ...,
        min_length=1,
        description="Unique production identifier",
    )
    workspace_id: str = Field(
        ...,
        min_length=1,
        description="Workspace tenant identifier",
    )
    channel_id: str = Field(
        ...,
        min_length=1,
        description="Associated YouTube or Sample Channel identifier",
    )
    owner_user_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the user who owns this production",
    )
    source_media: SourceMedia | None = Field(
        default=None,
        description="Raw source media metadata associated with this production",
    )
    status: ProductionStatus = Field(
        default=ProductionStatus.PENDING,
        description="Current production status",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the production was created (UTC)",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the production was last updated (UTC)",
    )

    @field_validator("created_at", "updated_at")
    @classmethod
    def check_timezone_aware(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)
