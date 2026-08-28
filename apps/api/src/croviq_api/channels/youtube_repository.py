"""Repository and secure server-side persistence for YouTube OAuth connections and CSRF state."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
import secrets
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from croviq_api.config import get_settings
from croviq_domain.validators import validate_timezone_aware


class YouTubeConnection(BaseModel):
    """Server-side persisted YouTube channel OAuth connection.

    Tokens and credentials are NEVER exposed to browser client responses.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    workspace_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    channel_id: str = Field(..., min_length=1)
    channel_title: str = Field(..., min_length=1)
    avatar_url: str = Field(default="")
    subscriber_count: int = Field(default=0, ge=0)
    access_token: str = Field(..., min_length=1)
    refresh_token: str | None = None
    token_expiry: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
    connected_at: datetime
    last_sync_at: datetime

    @field_validator("token_expiry", "connected_at", "last_sync_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return validate_timezone_aware(value) if value is not None else None


class YouTubeConnectionPublicSummary(BaseModel):
    """Public non-sensitive connection information returned to creator client."""

    model_config = ConfigDict(extra="forbid")

    connected: bool
    channel_id: str | None = None
    channel_title: str | None = None
    avatar_url: str | None = None
    subscriber_count: int | None = None
    last_sync_at: datetime | None = None
    has_monetary_access: bool = False


class YouTubeOAuthState(BaseModel):
    """State payload for CSRF protection during OAuth 2.0 authorization code flow."""

    model_config = ConfigDict(extra="forbid")

    state_token: str = Field(..., min_length=16)
    workspace_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    redirect_uri: str = Field(..., min_length=1)
    include_monetary: bool = False
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return validate_timezone_aware(value)

    def is_expired(self, max_age_seconds: int = 600) -> bool:
        now = datetime.now(UTC)
        return (now - self.created_at).total_seconds() > max_age_seconds


class YouTubeConnectionRepository(ABC):
    @abstractmethod
    async def get_connection(self, workspace_id: str) -> YouTubeConnection | None:
        pass

    @abstractmethod
    async def save_connection(self, connection: YouTubeConnection) -> YouTubeConnection:
        pass

    @abstractmethod
    async def delete_connection(self, workspace_id: str) -> bool:
        pass

    @abstractmethod
    async def create_oauth_state(
        self,
        workspace_id: str,
        user_id: str,
        redirect_uri: str,
        include_monetary: bool = False,
    ) -> str:
        pass

    @abstractmethod
    async def verify_and_consume_oauth_state(self, state_token: str) -> YouTubeOAuthState | None:
        pass


class InMemoryYouTubeConnectionRepository(YouTubeConnectionRepository):
    def __init__(self) -> None:
        self._connections: dict[str, YouTubeConnection] = {}
        self._states: dict[str, YouTubeOAuthState] = {}

    async def get_connection(self, workspace_id: str) -> YouTubeConnection | None:
        return self._connections.get(workspace_id)

    async def save_connection(self, connection: YouTubeConnection) -> YouTubeConnection:
        self._connections[connection.workspace_id] = connection
        return connection

    async def delete_connection(self, workspace_id: str) -> bool:
        if workspace_id in self._connections:
            del self._connections[workspace_id]
            return True
        return False

    async def create_oauth_state(
        self,
        workspace_id: str,
        user_id: str,
        redirect_uri: str,
        include_monetary: bool = False,
    ) -> str:
        token = secrets.token_urlsafe(32)
        self._states[token] = YouTubeOAuthState(
            state_token=token,
            workspace_id=workspace_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            include_monetary=include_monetary,
            created_at=datetime.now(UTC),
        )
        return token

    async def verify_and_consume_oauth_state(self, state_token: str) -> YouTubeOAuthState | None:
        state = self._states.pop(state_token, None)
        if state is None or state.is_expired():
            return None
        return state


class FirestoreYouTubeConnectionRepository(YouTubeConnectionRepository):
    def __init__(self, project_id: str | None = None) -> None:
        self.project_id = project_id or get_settings().gcp_project_id
        self._db: Any = None

    def _get_db(self) -> Any:
        if self._db is None:
            import firebase_admin
            from firebase_admin import firestore

            try:
                firebase_admin.get_app()
            except ValueError:
                firebase_admin.initialize_app(options={"projectId": self.project_id})
            self._db = firestore.client()
        return self._db

    def _connection_ref(self, workspace_id: str) -> Any:
        return (
            self._get_db()
            .collection("workspaces")
            .document(workspace_id)
            .collection("integrations")
            .document("youtube_connection")
        )

    def _states_collection(self) -> Any:
        return self._get_db().collection("youtube_oauth_states")

    async def get_connection(self, workspace_id: str) -> YouTubeConnection | None:
        doc = self._connection_ref(workspace_id).get()
        if not doc.exists:
            return None
        return YouTubeConnection.model_validate(doc.to_dict())

    async def save_connection(self, connection: YouTubeConnection) -> YouTubeConnection:
        self._connection_ref(connection.workspace_id).set(connection.model_dump(mode="json"))
        return connection

    async def delete_connection(self, workspace_id: str) -> bool:
        self._connection_ref(workspace_id).delete()
        return True

    async def create_oauth_state(
        self,
        workspace_id: str,
        user_id: str,
        redirect_uri: str,
        include_monetary: bool = False,
    ) -> str:
        token = secrets.token_urlsafe(32)
        state = YouTubeOAuthState(
            state_token=token,
            workspace_id=workspace_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            include_monetary=include_monetary,
            created_at=datetime.now(UTC),
        )
        self._states_collection().document(token).set(state.model_dump(mode="json"))
        return token

    async def verify_and_consume_oauth_state(self, state_token: str) -> YouTubeOAuthState | None:
        doc_ref = self._states_collection().document(state_token)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        doc_ref.delete()
        state = YouTubeOAuthState.model_validate(data)
        if state.is_expired():
            return None
        return state


_global_youtube_repo: YouTubeConnectionRepository | None = None


def get_youtube_connection_repository() -> YouTubeConnectionRepository:
    global _global_youtube_repo
    if _global_youtube_repo is None:
        if get_settings().is_production:
            _global_youtube_repo = FirestoreYouTubeConnectionRepository()
        else:
            _global_youtube_repo = InMemoryYouTubeConnectionRepository()
    return _global_youtube_repo


def set_youtube_connection_repository(repo: YouTubeConnectionRepository | None) -> None:
    global _global_youtube_repo
    _global_youtube_repo = repo
