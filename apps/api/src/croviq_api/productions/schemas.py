"""API schemas for Production and Media Upload operations."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from croviq_domain.production import Production


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
