"""Edit Decision List (EDL) repository interface and implementations (Firestore Native and In-Memory)."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import os
import time
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.edl import EditDecisionList, EdlRevisionHistoryEntry
from croviq_observability import log_firestore_event


_global_edl_repo: "EDLRepository | None" = None

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
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    return datetime.now(timezone.utc)


class EDLRepository(ABC):
    """Abstract repository for EditDecisionList persistence."""

    @abstractmethod
    async def save_edl(self, edl: EditDecisionList) -> None:
        """Persist an EditDecisionList entity."""
        pass

    @abstractmethod
    async def get_edl(self, production_id: str, edl_id: str) -> EditDecisionList | None:
        """Retrieve a specific EditDecisionList by ID."""
        pass

    @abstractmethod
    async def delete_by_production_id(self, production_id: str) -> bool:
        """Delete EDL records for a production."""
        pass

    @abstractmethod
    async def get_latest_edl(self, production_id: str) -> EditDecisionList | None:
        """Retrieve the most recent active EditDecisionList for a production."""
        pass

    @abstractmethod
    async def save_revision_history(self, entry: EdlRevisionHistoryEntry) -> None:
        """Persist an EDL revision history entry for undo."""
        pass

    @abstractmethod
    async def get_latest_revision_history(self, production_id: str) -> EdlRevisionHistoryEntry | None:
        """Retrieve the most recent revision history entry for a production."""
        pass

    @abstractmethod
    async def pop_latest_revision_history(self, production_id: str) -> EdlRevisionHistoryEntry | None:
        """Remove and return the most recent revision history entry for a production."""
        pass

    @abstractmethod
    async def list_revision_history(self, production_id: str) -> list[EdlRevisionHistoryEntry]:
        """List all revision history entries for a production."""
        pass

    def _deserialize_edl(self, doc_data: dict[str, Any]) -> EditDecisionList:
        """Deserialize raw Firestore dictionary into canonical EditDecisionList domain model."""
        payload = deepcopy(doc_data)
        if "created_at" in payload:
            payload["created_at"] = parse_datetime(payload["created_at"])
        return EditDecisionList.model_validate(payload)


class InMemoryEDLRepository(EDLRepository):
    """In-memory mock EDL repository for tests and local development."""

    def __init__(self) -> None:
        # Key: (production_id, edl_id) -> EditDecisionList
        self._by_id: dict[tuple[str, str], EditDecisionList] = {}
        # Key: production_id -> list of edl_id
        self._by_production: dict[str, list[str]] = {}
        # Key: production_id -> list of EdlRevisionHistoryEntry
        self._history: dict[str, list[EdlRevisionHistoryEntry]] = {}
    async def save_edl(self, edl: EditDecisionList) -> None:
        key = (edl.production_id, edl.edl_id)
        self._by_id[key] = edl
        if edl.production_id not in self._by_production:
            self._by_production[edl.production_id] = []
        if edl.edl_id not in self._by_production[edl.production_id]:
            self._by_production[edl.production_id].append(edl.edl_id)

    async def get_edl(self, production_id: str, edl_id: str) -> EditDecisionList | None:
        return self._by_id.get((production_id, edl_id))

    async def get_latest_edl(self, production_id: str) -> EditDecisionList | None:
        edl_ids = self._by_production.get(production_id, [])
        if not edl_ids:
            return None
        # Return the most recently saved
        latest_id = edl_ids[-1]
        return self._by_id.get((production_id, latest_id))

    async def delete_by_production_id(self, production_id: str) -> bool:
        edl_ids = self._by_production.pop(production_id, None)
        if edl_ids:
            for edl_id in edl_ids:
                self._by_id.pop((production_id, edl_id), None)
            return True
        return False


    async def save_revision_history(self, entry: EdlRevisionHistoryEntry) -> None:
        if entry.production_id not in self._history:
            self._history[entry.production_id] = []
        self._history[entry.production_id].append(deepcopy(entry))

    async def get_latest_revision_history(self, production_id: str) -> EdlRevisionHistoryEntry | None:
        entries = self._history.get(production_id, [])
        if not entries:
            return None
        return deepcopy(entries[-1])

    async def pop_latest_revision_history(self, production_id: str) -> EdlRevisionHistoryEntry | None:
        entries = self._history.get(production_id, [])
        if not entries:
            return None
        return deepcopy(entries.pop())

    async def list_revision_history(self, production_id: str) -> list[EdlRevisionHistoryEntry]:
        entries = self._history.get(production_id, [])
        return [deepcopy(e) for e in entries]
    def clear(self) -> None:
        self._by_id.clear()
        self._by_production.clear()
        self._history.clear()

class FirestoreEDLRepository(EDLRepository):
    """Production EDL repository persisting to Google Cloud Firestore Native mode."""

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

    def _edls_subcollection(self, production_id: str) -> Any:
        return (
            self.client
            .collection("productions")
            .document(production_id)
            .collection("edls")
        )

    async def save_edl(self, edl: EditDecisionList) -> None:
        start_time = time.perf_counter()
        coll = self._edls_subcollection(edl.production_id)
        doc_ref = coll.document(edl.edl_id)

        data = edl.model_dump(mode="json")
        data["created_at"] = edl.created_at.isoformat()

        try:
            await doc_ref.set(data)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.write",
                collection=f"productions/{edl.production_id}/edls",
                operation="set",
                document_id=edl.edl_id,
                status=200,
                latency_ms=latency_ms,
                message=f"Persisted EDL {edl.edl_id}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{edl.production_id}/edls",
                operation="set",
                document_id=edl.edl_id,
                status=500,
                latency_ms=latency_ms,
                error_code=str(exc),
            )
            raise

    async def get_edl(self, production_id: str, edl_id: str) -> EditDecisionList | None:
        start_time = time.perf_counter()
        coll = self._edls_subcollection(production_id)
        doc_ref = coll.document(edl_id)

        try:
            snap = await doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            if not snap.exists:
                log_firestore_event(
                    event_type="firestore.read",
                    collection=f"productions/{production_id}/edls",
                    operation="get",
                    document_id=edl_id,
                    status=404,
                    latency_ms=latency_ms,
                )
                return None
            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/edls",
                operation="get",
                document_id=edl_id,
                status=200,
                latency_ms=latency_ms,
            )
            return self._deserialize_edl(snap.to_dict())
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/edls",
                operation="get",
                document_id=edl_id,
                status=500,
                latency_ms=latency_ms,
                error_code=str(exc),
            )
            raise

    async def get_latest_edl(self, production_id: str) -> EditDecisionList | None:
        start_time = time.perf_counter()
        coll = self._edls_subcollection(production_id)

        try:
            query = coll.order_by("created_at", direction="DESCENDING").limit(1)
            docs = [doc async for doc in query.stream()]
            latency_ms = (time.perf_counter() - start_time) * 1000
            if not docs:
                log_firestore_event(
                    event_type="firestore.read",
                    collection=f"productions/{production_id}/edls",
                    operation="query",
                    document_id="latest",
                    status=404,
                    latency_ms=latency_ms,
                )
                return None
            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/edls",
                operation="query",
                document_id=docs[0].id,
                status=200,
                latency_ms=latency_ms,
            )
            return self._deserialize_edl(docs[0].to_dict())
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/edls",
                operation="query",
                document_id="latest",
                status=500,
                latency_ms=latency_ms,
                error_code=str(exc),
            )
            raise

    async def delete_by_production_id(self, production_id: str) -> bool:
        coll_ref = (
            self.client
            .collection("productions")
            .document(production_id)
            .collection("edls")
        )
        docs = [doc async for doc in coll_ref.stream()]
        for doc in docs:
            await doc.reference.delete()
        return len(docs) > 0

    def _history_subcollection(self, production_id: str) -> Any:
        return (
            self.client
            .collection("productions")
            .document(production_id)
            .collection("edl_history")
        )

    async def save_revision_history(self, entry: EdlRevisionHistoryEntry) -> None:
        coll = self._history_subcollection(entry.production_id)
        doc_ref = coll.document(entry.history_id)
        data = entry.model_dump(mode="json")
        data["created_at"] = entry.created_at.isoformat()
        await doc_ref.set(data)

    async def get_latest_revision_history(self, production_id: str) -> EdlRevisionHistoryEntry | None:
        coll = self._history_subcollection(production_id)
        query = coll.order_by("created_at", direction="DESCENDING").limit(1)
        docs = [d async for d in query.stream()]
        if not docs:
            return None
        data = docs[0].to_dict()
        if "created_at" in data:
            data["created_at"] = parse_datetime(data["created_at"])
        return EdlRevisionHistoryEntry.model_validate(data)

    async def pop_latest_revision_history(self, production_id: str) -> EdlRevisionHistoryEntry | None:
        coll = self._history_subcollection(production_id)
        query = coll.order_by("created_at", direction="DESCENDING").limit(1)
        docs = [d async for d in query.stream()]
        if not docs:
            return None
        doc = docs[0]
        data = doc.to_dict()
        await doc.reference.delete()
        if "created_at" in data:
            data["created_at"] = parse_datetime(data["created_at"])
        return EdlRevisionHistoryEntry.model_validate(data)

    async def list_revision_history(self, production_id: str) -> list[EdlRevisionHistoryEntry]:
        coll = self._history_subcollection(production_id)
        query = coll.order_by("created_at")
        entries = []
        async for doc in query.stream():
            data = doc.to_dict()
            if "created_at" in data:
                data["created_at"] = parse_datetime(data["created_at"])
            entries.append(EdlRevisionHistoryEntry.model_validate(data))
        return entries


def get_default_edl_repository() -> EDLRepository:
    """Factory for default EDLRepository instance."""
    global _global_edl_repo
    if _global_edl_repo is None:
        settings = get_settings()
        if settings.is_production:
            if not settings.gcp_project_id and not os.getenv("FIRESTORE_EMULATOR_HOST"):
                raise RuntimeError(
                    "Production mode requires FirestoreEDLRepository with valid gcp_project_id."
                )
            _global_edl_repo = FirestoreEDLRepository(project_id=settings.gcp_project_id)
        elif settings.environment == "staging" or os.getenv("USE_FIRESTORE") == "true":
            _global_edl_repo = FirestoreEDLRepository(project_id=settings.gcp_project_id)
        else:
            _global_edl_repo = InMemoryEDLRepository()
    return _global_edl_repo


def get_edl_repository() -> EDLRepository:
    """FastAPI dependency provider for EDLRepository."""
    return get_default_edl_repository()


def set_edl_repository(repo: EDLRepository | None) -> None:
    """Override the global EDL repository instance for test isolation."""
    global _global_edl_repo
    _global_edl_repo = repo
