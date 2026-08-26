from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service health status")
    service: str = Field(default="croviq-api", description="Service identifier")
    git_sha: str = Field(description="Current git commit SHA or environment identifier")


class DemoAccessRestrictedResponse(BaseModel):
    error_code: str = Field(default="demo_access_restricted", description="Error code identifier")
    message: str = Field(
        default="This Croviq demo is restricted to an approved account.",
        description="User-facing error explanation",
    )


class ClientAuthEventBase(BaseModel):
    """Client-supplied auth telemetry with no free-form payload fields."""

    model_config = ConfigDict(extra="forbid")
    firebase_uid: str | None = None
    git_sha: str | None = None


class AuthLoginAttemptEvent(ClientAuthEventBase):
    event_type: Literal["auth.login_attempt"]


class AuthLoginFailedEvent(ClientAuthEventBase):
    event_type: Literal["auth.login_failed"]
    error_code: Literal["invalid_credentials", "demo_access_restricted"] | None = None


class AuthSessionRestoredEvent(ClientAuthEventBase):
    event_type: Literal["auth.session.restored"]


class AuthTokenRefreshedEvent(ClientAuthEventBase):
    event_type: Literal["auth.token.refreshed"]


class AuthTokenRefreshFailedEvent(ClientAuthEventBase):
    event_type: Literal["auth.token_refresh_failed"]
    error_code: str | None = None


class AuthSessionLostEvent(ClientAuthEventBase):
    event_type: Literal["auth.session_lost"]
    error_code: str | None = None


class AuthExplicitLogoutEvent(ClientAuthEventBase):
    event_type: Literal["auth.explicit_logout"]


class ClientErrorEvent(ClientAuthEventBase):
    event_type: Literal["client.error"]
    error_code: str | None = None
    message: str | None = None

ClientAuthEvent = Annotated[
    AuthLoginAttemptEvent
    | AuthLoginFailedEvent
    | AuthSessionRestoredEvent
    | AuthTokenRefreshedEvent
    | AuthTokenRefreshFailedEvent
    | AuthSessionLostEvent
    | AuthExplicitLogoutEvent
    | ClientErrorEvent,
    Field(discriminator="event_type"),
]
