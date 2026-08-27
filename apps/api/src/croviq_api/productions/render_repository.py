"""Render artifact repository interface and implementations (Firestore Native and In-Memory)."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import os
import time
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_observability import log_firestore_event


_global_render_repo: "RenderRepository | None" = None


def parse_datetime(raw: Any) -> datetime:
    """Parse datetime from Firestore timestamp or ISO string to UTC datetime."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw
    if hasattr(raw, "to_datetime"):
        dt = raw.to_datetime()
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class RenderRepository(ABC):
    """Abstract repository for RenderArtifact persistence."""

    @abstractmethod
    async def save_render_artifact(self, artifact: RenderArtifact) -> None:
        """Persist or update a RenderArtifact."""
        pass

    @abstractmethod
    async def get_render_artifact(
        self,
        production_id: str,
        artifact_id: str,
    ) -> RenderArtifact | None:
        """Retrieve a specific RenderArtifact by its artifact_id."""
        pass

    @abstractmethod
    async def get_render_artifact_by_type(
        self,
        production_id: str,
        edl_id: str,
        artifact_type: ArtifactType | str,
    ) -> RenderArtifact | None:
        """Retrieve the completed or latest RenderArtifact for a specific (production_id, edl_id, artifact_type)."""
        pass

    @abstractmethod
    async def list_render_artifacts(
        self,
        production_id: str,
    ) -> list[RenderArtifact]:
        """List all RenderArtifact records associated with a production."""
        pass

    @abstractmethod
    async def delete_by_production_id(self, production_id: str) -> int:
        """Delete all render artifacts for a production. Returns count of deleted artifacts."""
        pass
    async def list_renders_by_production(self, production_id: str) -> list[RenderArtifact]:
        """Alias for list_render_artifacts."""
        return await self.list_render_artifacts(production_id)


    def _deserialize_render_artifact(self, data: dict[str, Any]) -> RenderArtifact:
        """Deserialize raw Firestore dictionary into validated RenderArtifact."""
        payload = deepcopy(data)
        if "artifact_type" in payload and isinstance(payload["artifact_type"], str):
            payload["artifact_type"] = payload["artifact_type"].upper()
        if "status" in payload and isinstance(payload["status"], str):
            payload["status"] = payload["status"].lower()
        if "created_at" in payload and payload["created_at"]:
            payload["created_at"] = parse_datetime(payload["created_at"])
        if "completed_at" in payload and payload["completed_at"]:
            payload["completed_at"] = parse_datetime(payload["completed_at"])
        valid_keys = set(RenderArtifact.model_fields.keys())
        filtered = {k: v for k, v in payload.items() if k in valid_keys}
        return RenderArtifact.model_validate(filtered)

class InMemoryRenderRepository(RenderRepository):
    """In-memory mock RenderRepository for unit testing and local development."""

    def __init__(self) -> None:
        self._by_production: dict[str, dict[str, RenderArtifact]] = {}

    async def save_render_artifact(self, artifact: RenderArtifact) -> None:
        if artifact.production_id not in self._by_production:
            self._by_production[artifact.production_id] = {}
        self._by_production[artifact.production_id][artifact.artifact_id] = deepcopy(artifact)

    async def get_render_artifact(
        self,
        production_id: str,
        artifact_id: str,
    ) -> RenderArtifact | None:
        prod_renders = self._by_production.get(production_id, {})
        artifact = prod_renders.get(artifact_id)
        return deepcopy(artifact) if artifact else None

    async def get_render_artifact_by_type(
        self,
        production_id: str,
        edl_id: str,
        artifact_type: ArtifactType | str,
    ) -> RenderArtifact | None:
        type_str = artifact_type.value if isinstance(artifact_type, ArtifactType) else str(artifact_type)
        prod_renders = self._by_production.get(production_id, {})
        matching = [
            a for a in prod_renders.values()
            if a.edl_id == edl_id and a.artifact_type == type_str
        ]
        if not matching:
            return None
        # Prefer completed status, otherwise newest created_at
        completed = [a for a in matching if a.status == ArtifactStatus.completed]
        if completed:
            completed.sort(key=lambda a: a.created_at, reverse=True)
            return deepcopy(completed[0])
        matching.sort(key=lambda a: a.created_at, reverse=True)
        return deepcopy(matching[0])

    async def list_render_artifacts(
        self,
        production_id: str,
    ) -> list[RenderArtifact]:
        prod_renders = self._by_production.get(production_id, {})
        artifacts = list(prod_renders.values())
        artifacts.sort(key=lambda a: a.created_at, reverse=True)
        return deepcopy(artifacts)

    async def delete_by_production_id(self, production_id: str) -> int:
        prod_renders = self._by_production.pop(production_id, {})
        return len(prod_renders)

    def clear(self) -> None:
        self._by_production.clear()


class FirestoreRenderRepository(RenderRepository):
    """Production RenderRepository persisting to Google Cloud Firestore Native mode."""

    def __init__(self, project_id: str | None = None, database: str = "(default)") -> None:
        self._project_id = project_id
        self._database = database
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            from google.cloud.firestore import AsyncClient
            kwargs: dict[str, Any] = {}
            project = self._project_id or get_settings().gcp_project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
            if project:
                kwargs["project"] = project
            if self._database and self._database != "(default)":
                kwargs["database"] = self._database
            self._client = AsyncClient(**kwargs)
        return self._client

    def _renders_subcollection(self, production_id: str) -> Any:
        return (
            self.client
            .collection("productions")
            .document(production_id)
            .collection("renders")
        )

    async def save_render_artifact(self, artifact: RenderArtifact) -> None:
        start_time = time.perf_counter()
        coll = self._renders_subcollection(artifact.production_id)
        doc_ref = coll.document(artifact.artifact_id)

        data = artifact.model_dump(mode="json")
        data["created_at"] = artifact.created_at.isoformat()
        if artifact.completed_at:
            data["completed_at"] = artifact.completed_at.isoformat()

        try:
            await doc_ref.set(data)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.write",
                collection=f"productions/{artifact.production_id}/renders",
                operation="set",
                document_id=artifact.artifact_id,
                status=200,
                latency_ms=latency_ms,
                message=f"Persisted RenderArtifact {artifact.artifact_id} ({artifact.artifact_type})",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{artifact.production_id}/renders",
                operation="set",
                document_id=artifact.artifact_id,
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_write_error",
                message=f"Firestore write error for render artifact {artifact.artifact_id}: {type(exc).__name__}",
                exception=exc,
            )
            raise
    async def get_render_artifact(
        self,
        production_id: str,
        artifact_id: str,
    ) -> RenderArtifact | None:
        start_time = time.perf_counter()
        coll = self._renders_subcollection(production_id)
        doc_ref = coll.document(artifact_id)

        try:
            snap = await doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            if not snap.exists:
                log_firestore_event(
                    event_type="firestore.read",
                    collection=f"productions/{production_id}/renders",
                    operation="get",
                    document_id=artifact_id,
                    status=404,
                    latency_ms=latency_ms,
                )
                return None

            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/renders",
                operation="get",
                document_id=artifact_id,
                status=200,
                latency_ms=latency_ms,
            )
            return self._deserialize_render_artifact(snap.to_dict())
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/renders",
                operation="get",
                document_id=artifact_id,
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_read_error",
                message=f"Firestore read error for render artifact {artifact_id}: {type(exc).__name__}",
                exception=exc,
            )
            raise
    async def get_render_artifact_by_type(
        self,
        production_id: str,
        edl_id: str,
        artifact_type: ArtifactType | str,
    ) -> RenderArtifact | None:
        start_time = time.perf_counter()
        type_str = artifact_type.value if isinstance(artifact_type, ArtifactType) else str(artifact_type)
        coll = self._renders_subcollection(production_id)

        try:
            # Query by edl_id and artifact_type
            query = coll.where("edl_id", "==", edl_id).where("artifact_type", "==", type_str)
            snaps = [doc async for doc in query.stream()]
            latency_ms = (time.perf_counter() - start_time) * 1000

            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/renders",
                operation="query",
                document_id=f"edl:{edl_id}_type:{type_str}",
                status=200,
                latency_ms=latency_ms,
            )

            if not snaps:
                return None

            artifacts = [self._deserialize_render_artifact(s.to_dict()) for s in snaps]
            completed = [a for a in artifacts if a.status == ArtifactStatus.completed]
            if completed:
                completed.sort(key=lambda a: a.created_at, reverse=True)
                return completed[0]
            artifacts.sort(key=lambda a: a.created_at, reverse=True)
            return artifacts[0]
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/renders",
                operation="query",
                document_id=f"edl:{edl_id}_type:{type_str}",
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_query_error",
                message=f"Firestore query error for render artifact {edl_id}/{type_str}: {type(exc).__name__}",
                exception=exc,
            )
            raise
    async def list_render_artifacts(
        self,
        production_id: str,
    ) -> list[RenderArtifact]:
        start_time = time.perf_counter()
        coll = self._renders_subcollection(production_id)

        try:
            snaps = [doc async for doc in coll.stream()]
            latency_ms = (time.perf_counter() - start_time) * 1000

            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/renders",
                operation="list",
                document_id=f"all_{len(snaps)}",
                status=200,
                latency_ms=latency_ms,
            )

            artifacts = [self._deserialize_render_artifact(s.to_dict()) for s in snaps]
            artifacts.sort(key=lambda a: a.created_at, reverse=True)
            return artifacts
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/renders",
                operation="list",
                document_id="all",
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_list_error",
                message=f"Firestore list error for renders: {type(exc).__name__}",
                exception=exc,
            )
            raise

    async def delete_by_production_id(self, production_id: str) -> int:
        coll = (
            self.client
            .collection("productions")
            .document(production_id)
            .collection("renders")
        )
        snaps = [doc async for doc in coll.stream()]
        for s in snaps:
            await s.reference.delete()
        return len(snaps)

def get_default_render_repository() -> RenderRepository:
    """Factory for default RenderRepository instance."""
    global _global_render_repo
    if _global_render_repo is None:
        settings = get_settings()
        if settings.environment in ("production", "staging") or os.getenv("USE_FIRESTORE") == "true":
            _global_render_repo = FirestoreRenderRepository(
                project_id=settings.gcp_project_id,
            )
        else:
            _global_render_repo = InMemoryRenderRepository()
    return _global_render_repo

def get_render_repository() -> RenderRepository:
    """FastAPI dependency provider for RenderRepository."""
    return get_default_render_repository()


def set_render_repository(repo: RenderRepository | None) -> None:
    """Override global RenderRepository instance for testing isolation."""
    global _global_render_repo
    _global_render_repo = repo
