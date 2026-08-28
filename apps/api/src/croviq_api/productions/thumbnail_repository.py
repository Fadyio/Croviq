"""Repository for ThumbnailArtifact assets generated from master video frames."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import os
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.publish import ThumbnailArtifact
from croviq_observability import log_firestore_event

logger = logging.getLogger(__name__)


class ThumbnailRepository(ABC):
    """Abstract interface for persisting and querying ThumbnailArtifacts."""

    @abstractmethod
    async def get_by_id(self, production_id: str, artifact_id: str) -> ThumbnailArtifact | None:
        pass

    @abstractmethod
    async def list_by_production_id(self, production_id: str) -> list[ThumbnailArtifact]:
        pass

    @abstractmethod
    async def get_latest_by_production_id(self, production_id: str) -> ThumbnailArtifact | None:
        pass

    @abstractmethod
    async def save(self, artifact: ThumbnailArtifact) -> ThumbnailArtifact:
        pass

    @abstractmethod
    async def delete_by_production_id(self, production_id: str) -> int:
        pass


class InMemoryThumbnailRepository(ThumbnailRepository):
    """In-memory repository for unit tests and local non-cloud execution."""

    def __init__(self) -> None:
        self._artifacts: dict[str, list[ThumbnailArtifact]] = {}

    async def get_by_id(self, production_id: str, artifact_id: str) -> ThumbnailArtifact | None:
        arts = self._artifacts.get(production_id, [])
        for a in arts:
            if a.artifact_id == artifact_id:
                return a
        return None

    async def list_by_production_id(self, production_id: str) -> list[ThumbnailArtifact]:
        return list(self._artifacts.get(production_id, []))

    async def get_latest_by_production_id(self, production_id: str) -> ThumbnailArtifact | None:
        arts = self._artifacts.get(production_id, [])
        if not arts:
            return None
        return sorted(arts, key=lambda a: a.created_at, reverse=True)[0]

    async def save(self, artifact: ThumbnailArtifact) -> ThumbnailArtifact:
        if artifact.production_id not in self._artifacts:
            self._artifacts[artifact.production_id] = []
        # Replace if existing or append
        existing = [a for a in self._artifacts[artifact.production_id] if a.artifact_id != artifact.artifact_id]
        existing.append(artifact)
        self._artifacts[artifact.production_id] = existing
        return artifact

    async def delete_by_production_id(self, production_id: str) -> int:
        arts = self._artifacts.pop(production_id, [])
        return len(arts)


class FirestoreThumbnailRepository(ThumbnailRepository):
    """Production Firestore repository for ThumbnailArtifact persistence."""

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

    async def get_by_id(self, production_id: str, artifact_id: str) -> ThumbnailArtifact | None:
        db = self._get_db()
        doc_ref = (
            db.collection("productions")
            .document(production_id)
            .collection("thumbnail_artifacts")
            .document(artifact_id)
        )
        doc = doc_ref.get()
        if not doc.exists:
            return None
        return ThumbnailArtifact.model_validate(doc.to_dict())

    async def list_by_production_id(self, production_id: str) -> list[ThumbnailArtifact]:
        db = self._get_db()
        coll_ref = (
            db.collection("productions")
            .document(production_id)
            .collection("thumbnail_artifacts")
        )
        docs = coll_ref.stream()
        return [ThumbnailArtifact.model_validate(doc.to_dict()) for doc in docs]

    async def get_latest_by_production_id(self, production_id: str) -> ThumbnailArtifact | None:
        arts = await self.list_by_production_id(production_id)
        if not arts:
            return None
        return sorted(arts, key=lambda a: a.created_at, reverse=True)[0]

    async def save(self, artifact: ThumbnailArtifact) -> ThumbnailArtifact:
        db = self._get_db()
        doc_ref = (
            db.collection("productions")
            .document(artifact.production_id)
            .collection("thumbnail_artifacts")
            .document(artifact.artifact_id)
        )
        doc_ref.set(artifact.model_dump(mode="json"))

        log_firestore_event(
            "thumbnail_artifact_saved",
            production_id=artifact.production_id,
            artifact_id=artifact.artifact_id,
            size_bytes=artifact.size_bytes,
        )
        return artifact

    async def delete_by_production_id(self, production_id: str) -> int:
        db = self._get_db()
        coll_ref = (
            db.collection("productions")
            .document(production_id)
            .collection("thumbnail_artifacts")
        )
        docs = list(coll_ref.stream())
        for doc in docs:
            doc.reference.delete()
        return len(docs)


_global_thumbnail_repo: ThumbnailRepository | None = None


def get_thumbnail_repository() -> ThumbnailRepository:
    global _global_thumbnail_repo
    if _global_thumbnail_repo is None:
        if get_settings().is_production:
            _global_thumbnail_repo = FirestoreThumbnailRepository()
        else:
            _global_thumbnail_repo = InMemoryThumbnailRepository()
    return _global_thumbnail_repo


def set_thumbnail_repository(repo: ThumbnailRepository | None) -> None:
    global _global_thumbnail_repo
    _global_thumbnail_repo = repo
