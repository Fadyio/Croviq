from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

from croviq_domain.brand_kit import BrandKit
from croviq_domain.validators import validate_timezone_aware


class Workspace(BaseModel):
    """Canonical Workspace tenant container model for Croviq."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    workspace_id: str = Field(
        ...,
        min_length=1,
        description="Unique workspace identifier",
    )
    owner_user_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the user who owns this workspace",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Workspace / channel display name",
    )
    channel_description: str | None = Field(
        default=None,
        description="Description of the YouTube channel or production context",
    )
    brand_kit: BrandKit = Field(
        default_factory=BrandKit,
        description="Workspace brand kit configuration",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the workspace was created (UTC)",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the workspace was last updated (UTC)",
    )

    @field_validator("created_at", "updated_at")
    @classmethod
    def check_timezone_aware(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)
