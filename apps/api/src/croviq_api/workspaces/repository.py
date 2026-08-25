"""Workspace repository interface and implementations (Firestore Native and In-Memory)."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
import os

from croviq_api.config import get_settings
from croviq_domain.brand_kit import BrandKit
from croviq_domain.user import User
from croviq_domain.workspace import Workspace


def parse_datetime(raw: Any) -> datetime:
    """Parse datetime from Firestore timestamp or ISO string to UTC datetime."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, str):
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


class WorkspaceRepository(ABC):
    """Abstract repository for Workspace and User persistence."""

    def user_from_dict(self, data: dict[str, Any]) -> User:
        return User(
            user_id=data["user_id"],
            email=data["email"],
            display_name=data["display_name"],
            avatar_url=data.get("avatar_url"),
            created_at=parse_datetime(data["created_at"]),
            updated_at=parse_datetime(data["updated_at"]),
        )

    def workspace_from_dict(self, data: dict[str, Any]) -> Workspace:
        brand_kit_data = data.get("brand_kit", {})
        brand_kit = BrandKit(**brand_kit_data) if isinstance(brand_kit_data, dict) else BrandKit()
        return Workspace(
            workspace_id=data["workspace_id"],
            owner_user_id=data["owner_user_id"],
            name=data["name"],
            channel_description=data.get("channel_description"),
            brand_kit=brand_kit,
            created_at=parse_datetime(data["created_at"]),
            updated_at=parse_datetime(data["updated_at"]),
        )

    @abstractmethod
    async def get_user_workspace(self, owner_user_id: str) -> Workspace | None:
        """Get the workspace owned by the given user ID."""
        ...

    @abstractmethod
    async def get_workspace_by_id(self, workspace_id: str) -> Workspace | None:
        """Get workspace by its unique identifier."""
        ...

    @abstractmethod
    async def create_workspace(self, workspace: Workspace) -> Workspace:
        """Persist a new workspace."""
        ...

    @abstractmethod
    async def save_user(self, user: User) -> User:
        """Persist or update user entity."""
        ...

    @abstractmethod
    async def get_user(self, user_id: str) -> User | None:
        """Get user entity by UID."""
        ...

    async def get_or_create_default_workspace(
        self, user: User, default_name: str = "Croviq Demo Workspace"
    ) -> tuple[Workspace, bool]:
        """Look up workspace belonging to verified uid; if none exists, create default workspace.

        Returns (workspace, was_created).
        """
        await self.save_user(user)
        existing = await self.get_user_workspace(user.user_id)
        if existing is not None:
            return existing, False

        now = datetime.now(timezone.utc)
        workspace_id = f"ws_{user.user_id}"
        workspace = Workspace(
            workspace_id=workspace_id,
            owner_user_id=user.user_id,
            name=default_name,
            channel_description=None,
            brand_kit=BrandKit(),
            created_at=now,
            updated_at=now,
        )
        created = await self.create_workspace(workspace)
        return created, True


class InMemoryWorkspaceRepository(WorkspaceRepository):
    """In-memory mock repository for tests and local non-cloud execution."""

    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.workspaces: dict[str, dict[str, Any]] = {}

    async def get_user_workspace(self, owner_user_id: str) -> Workspace | None:
        for ws_data in self.workspaces.values():
            if ws_data.get("owner_user_id") == owner_user_id:
                return self.workspace_from_dict(ws_data)
        return None

    async def get_workspace_by_id(self, workspace_id: str) -> Workspace | None:
        if workspace_id in self.workspaces:
            return self.workspace_from_dict(self.workspaces[workspace_id])
        return None

    async def create_workspace(self, workspace: Workspace) -> Workspace:
        self.workspaces[workspace.workspace_id] = {
            "workspace_id": workspace.workspace_id,
            "owner_user_id": workspace.owner_user_id,
            "name": workspace.name,
            "channel_description": workspace.channel_description,
            "brand_kit": workspace.brand_kit.model_dump(),
            "created_at": workspace.created_at.isoformat(),
            "updated_at": workspace.updated_at.isoformat(),
        }
        return workspace

    async def save_user(self, user: User) -> User:
        self.users[user.user_id] = {
            "user_id": user.user_id,
            "email": str(user.email),
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }
        return user

    async def get_user(self, user_id: str) -> User | None:
        if user_id in self.users:
            return self.user_from_dict(self.users[user_id])
        return None


class FirestoreWorkspaceRepository(WorkspaceRepository):
    """Production repository persisting to Google Cloud Firestore Native mode."""

    def __init__(self, project_id: str | None = None, database: str = "(default)") -> None:
        self._project_id = project_id
        self._database = database
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            from google.cloud.firestore import AsyncClient

            if self._project_id:
                self._client = AsyncClient(project=self._project_id, database=self._database)
            else:
                self._client = AsyncClient(database=self._database)
        return self._client

    async def get_user_workspace(self, owner_user_id: str) -> Workspace | None:
        query = (
            self.client.collection("workspaces")
            .where("owner_user_id", "==", owner_user_id)
            .limit(1)
        )
        docs = [doc async for doc in query.stream()]
        if docs:
            return self.workspace_from_dict(docs[0].to_dict())
        return None

    async def get_workspace_by_id(self, workspace_id: str) -> Workspace | None:
        doc_ref = self.client.collection("workspaces").document(workspace_id)
        doc = await doc_ref.get()
        if doc.exists:
            return self.workspace_from_dict(doc.to_dict())
        return None

    async def create_workspace(self, workspace: Workspace) -> Workspace:
        doc_ref = self.client.collection("workspaces").document(workspace.workspace_id)
        data = {
            "workspace_id": workspace.workspace_id,
            "owner_user_id": workspace.owner_user_id,
            "name": workspace.name,
            "channel_description": workspace.channel_description,
            "brand_kit": workspace.brand_kit.model_dump(),
            "created_at": workspace.created_at.isoformat(),
            "updated_at": workspace.updated_at.isoformat(),
        }
        await doc_ref.set(data)
        return workspace

    async def save_user(self, user: User) -> User:
        doc_ref = self.client.collection("users").document(user.user_id)
        data = {
            "user_id": user.user_id,
            "email": str(user.email),
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }
        await doc_ref.set(data, merge=True)
        return user

    async def get_user(self, user_id: str) -> User | None:
        doc_ref = self.client.collection("users").document(user_id)
        doc = await doc_ref.get()
        if doc.exists:
            return self.user_from_dict(doc.to_dict())
        return None


_global_workspace_repo: WorkspaceRepository | None = None


def get_default_workspace_repository() -> WorkspaceRepository:
    """Factory for default WorkspaceRepository instance."""
    global _global_workspace_repo
    if _global_workspace_repo is not None:
        return _global_workspace_repo

    settings = get_settings()
    # In cloud environments or if USE_FIRESTORE is set, use Firestore Native repository
    if settings.environment in ("production", "staging") or os.getenv("USE_FIRESTORE") == "true":
        _global_workspace_repo = FirestoreWorkspaceRepository(project_id=settings.gcp_project_id)
    else:
        # Development / test fallback to in-memory repository
        _global_workspace_repo = InMemoryWorkspaceRepository()

    return _global_workspace_repo


def get_workspace_repository() -> WorkspaceRepository:
    """FastAPI dependency provider for WorkspaceRepository."""
    return get_default_workspace_repository()


def set_workspace_repository(repo: WorkspaceRepository | None) -> None:
    """Override the global repository instance (useful for test isolation)."""
    global _global_workspace_repo
    _global_workspace_repo = repo
