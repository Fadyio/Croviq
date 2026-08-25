from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from croviq_domain.validators import validate_timezone_aware


class User(BaseModel):
    """Canonical User identity model for Croviq."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    user_id: str = Field(
        ...,
        min_length=1,
        description="Unique user identifier (e.g. Firebase UID / Google sub)",
    )
    email: EmailStr = Field(
        ...,
        description="Canonical user email address",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        description="User display name",
    )
    avatar_url: str | None = Field(
        default=None,
        description="Profile avatar image URL",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the user was created (UTC)",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the user was last updated (UTC)",
    )

    @field_validator("created_at", "updated_at")
    @classmethod
    def check_timezone_aware(cls, v: datetime) -> datetime:
        return validate_timezone_aware(v)
