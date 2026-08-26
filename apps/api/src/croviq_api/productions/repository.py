"""Production repository interface and implementations (Firestore Native and In-Memory)."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import time
import os
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.production import (
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
)
from croviq_observability import log_firestore_event


def parse_datetime(raw: Any) -> datetime:
    """Parse datetime from Firestore timestamp or ISO string to UTC datetime."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, str):
        cleaned = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


class ProductionRepository(ABC):
    """Abstract repository for Production entity persistence."""

    @abstractmethod
    async def create_production(self, production: Production) -> Production:
        """Persist a new Production record."""
        pass

    @abstractmethod
    async def get_production(self, production_id: str) -> Production | None:
        """Retrieve a Production record by its unique identifier."""
        pass

    @abstractmethod
    async def get_production_by_upload_id(self, upload_id: str) -> Production | None:
        """Retrieve a Production record by its associated source media upload identifier."""
        pass

    @abstractmethod
    async def list_productions(
        self, workspace_id: str, limit: int = 20
    ) -> list[Production]:
        """List recent Productions belonging to a workspace."""
        pass

    @abstractmethod
    async def update_production(self, production: Production) -> Production:
        """Update an existing Production record."""
        pass

    @staticmethod
    def production_to_dict(production: Production) -> dict[str, Any]:
        """Serialize a Production domain model to Firestore-compatible dictionary."""
        data: dict[str, Any] = {
            "production_id": production.production_id,
            "workspace_id": production.workspace_id,
            "channel_id": production.channel_id,
            "owner_user_id": production.owner_user_id,
            "status": production.status.value,
            "created_at": production.created_at.isoformat(),
            "updated_at": production.updated_at.isoformat(),
        }
        if production.source_media is not None:
            sm = production.source_media
            data["source_media"] = {
                "upload_id": sm.upload_id,
                "original_filename": sm.original_filename,
                "content_type": sm.content_type,
                "size_bytes": sm.size_bytes,
                "gcs_bucket": sm.gcs_bucket,
                "gcs_object": sm.gcs_object,
                "status": sm.status.value,
                "created_at": sm.created_at.isoformat(),
                "uploaded_at": sm.uploaded_at.isoformat() if sm.uploaded_at else None,
            }
            data["upload_id"] = sm.upload_id
        return data

    @staticmethod
    def production_from_dict(data: dict[str, Any]) -> Production:
        """Deserialize a Production domain model from Firestore dictionary."""
        source_media: SourceMedia | None = None
        if data.get("source_media"):
            sm_data = data["source_media"]
            source_media = SourceMedia(
                upload_id=sm_data["upload_id"],
                original_filename=sm_data["original_filename"],
                content_type=sm_data["content_type"],
                size_bytes=int(sm_data["size_bytes"]),
                gcs_bucket=sm_data["gcs_bucket"],
                gcs_object=sm_data["gcs_object"],
                status=SourceMediaStatus(sm_data["status"]),
                created_at=parse_datetime(sm_data["created_at"]),
                uploaded_at=(
                    parse_datetime(sm_data["uploaded_at"])
                    if sm_data.get("uploaded_at")
                    else None
                ),
            )

        return Production(
            production_id=data["production_id"],
            workspace_id=data["workspace_id"],
            channel_id=data["channel_id"],
            owner_user_id=data["owner_user_id"],
            source_media=source_media,
            status=ProductionStatus(data["status"]),
            created_at=parse_datetime(data["created_at"]),
            updated_at=parse_datetime(data["updated_at"]),
        )


class InMemoryProductionRepository(ProductionRepository):
    """In-memory mock repository for tests and local non-cloud execution."""

    def __init__(self) -> None:
        self._productions: dict[str, Production] = {}

    async def create_production(self, production: Production) -> Production:
        self._productions[production.production_id] = deepcopy(production)
        return deepcopy(production)

    async def get_production(self, production_id: str) -> Production | None:
        if production_id in self._productions:
            return deepcopy(self._productions[production_id])
        return None

    async def get_production_by_upload_id(self, upload_id: str) -> Production | None:
        for prod in self._productions.values():
            if prod.source_media and prod.source_media.upload_id == upload_id:
                return deepcopy(prod)
        return None

    async def list_productions(
        self, workspace_id: str, limit: int = 20
    ) -> list[Production]:
        matched = [
            deepcopy(p)
            for p in self._productions.values()
            if p.workspace_id == workspace_id
        ]
        # Sort newest first by created_at
        matched.sort(key=lambda p: p.created_at, reverse=True)
        return matched[:limit]

    async def update_production(self, production: Production) -> Production:
        self._productions[production.production_id] = deepcopy(production)
        return deepcopy(production)

    def clear(self) -> None:
        self._productions.clear()


class FirestoreProductionRepository(ProductionRepository):
    """Production repository persisting to Google Cloud Firestore Native mode."""

    def __init__(
        self, project_id: str | None = None, database: str = "(default)"
    ) -> None:
        self._project_id = project_id
        self._database = database
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            from google.cloud.firestore import AsyncClient

            kwargs: dict[str, Any] = {}
            if self._project_id:
                kwargs["project"] = self._project_id
            if self._database and self._database != "(default)":
                kwargs["database"] = self._database

            self._client = AsyncClient(**kwargs)
        return self._client

    async def create_production(self, production: Production) -> Production:
        start_time = time.perf_counter()
        try:
            doc_ref = self.client.collection("productions").document(
                production.production_id
            )
            data = self.production_to_dict(production)
            await doc_ref.set(data)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.write",
                collection="productions",
                operation="create",
                document_id=production.production_id,
                status=201,
                latency_ms=latency_ms,
                message=f"Created production record {production.production_id}",
            )
            return production
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection="productions",
                operation="create",
                document_id=production.production_id,
                status=500,
                latency_ms=latency_ms,
                exception=exc,
                error_code="firestore_create_error",
                message=f"Firestore create error for production {production.production_id}: {type(exc).__name__}",
            )
            raise

    async def get_production(self, production_id: str) -> Production | None:
        start_time = time.perf_counter()
        try:
            doc_ref = self.client.collection("productions").document(production_id)
            doc = await doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection="productions",
                operation="get",
                document_id=production_id,
                status=200,
                latency_ms=latency_ms,
                message=f"Fetched production {production_id}",
            )
            if doc.exists:
                return self.production_from_dict(doc.to_dict())
            return None
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection="productions",
                operation="get",
                document_id=production_id,
                status=500,
                latency_ms=latency_ms,
                exception=exc,
                error_code="firestore_get_error",
                message=f"Firestore get error for production {production_id}: {type(exc).__name__}",
            )
            raise

    async def get_production_by_upload_id(self, upload_id: str) -> Production | None:
        start_time = time.perf_counter()
        try:
            query = (
                self.client.collection("productions")
                .where("upload_id", "==", upload_id)
                .limit(1)
            )
            docs = [doc async for doc in query.stream()]
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection="productions",
                operation="query",
                status=200,
                latency_ms=latency_ms,
                message=f"Queried production by upload_id {upload_id}",
            )
            if docs:
                return self.production_from_dict(docs[0].to_dict())
            return None
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection="productions",
                operation="query",
                status=500,
                latency_ms=latency_ms,
                exception=exc,
                error_code="firestore_query_error",
                message=f"Firestore query error for upload_id {upload_id}: {type(exc).__name__}",
            )
            raise

    async def list_productions(
        self, workspace_id: str, limit: int = 20
    ) -> list[Production]:
        start_time = time.perf_counter()
        try:
            query = (
                self.client.collection("productions")
                .where("workspace_id", "==", workspace_id)
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
            )
            docs = [doc async for doc in query.stream()]
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection="productions",
                operation="list",
                status=200,
                latency_ms=latency_ms,
                message=f"Listed productions for workspace {workspace_id}",
            )
            return [self.production_from_dict(doc.to_dict()) for doc in docs]
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection="productions",
                operation="list",
                status=500,
                latency_ms=latency_ms,
                exception=exc,
                error_code="firestore_list_error",
                message=f"Firestore list error for workspace {workspace_id}: {type(exc).__name__}",
            )
            raise

    async def update_production(self, production: Production) -> Production:
        start_time = time.perf_counter()
        try:
            doc_ref = self.client.collection("productions").document(
                production.production_id
            )
            data = self.production_to_dict(production)
            await doc_ref.set(data)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.write",
                collection="productions",
                operation="update",
                document_id=production.production_id,
                status=200,
                latency_ms=latency_ms,
                message=f"Updated production record {production.production_id}",
            )
            return production
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection="productions",
                operation="update",
                document_id=production.production_id,
                status=500,
                latency_ms=latency_ms,
                exception=exc,
                error_code="firestore_update_error",
                message=f"Firestore update error for production {production.production_id}: {type(exc).__name__}",
            )
            raise


_global_production_repo: ProductionRepository | None = None


def get_default_production_repository() -> ProductionRepository:
    """Factory for default ProductionRepository instance."""
    global _global_production_repo
    if _global_production_repo is None:
        settings = get_settings()
        if settings.environment in ("production", "staging") or os.getenv("USE_FIRESTORE") == "true":
            _global_production_repo = FirestoreProductionRepository(
                project_id=settings.gcp_project_id
            )
        else:
            _global_production_repo = InMemoryProductionRepository()
    return _global_production_repo


def get_production_repository() -> ProductionRepository:
    """FastAPI dependency provider for ProductionRepository."""
    return get_default_production_repository()


def set_production_repository(repo: ProductionRepository | None) -> None:
    """Override the global repository instance (useful for test isolation)."""
    global _global_production_repo
    _global_production_repo = repo
