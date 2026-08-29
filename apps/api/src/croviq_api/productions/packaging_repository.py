"""Packaging repository interface and implementations (Firestore Native and In-Memory) (Issue #32)."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import os
import time
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.packaging import CreatorPackageOverrides, PackagingChapter, PackagingProposal, ThumbnailConcept, TitleAngle, TitleCandidate
from croviq_observability import log_firestore_event


_global_packaging_repo: "PackagingRepository | None" = None


def parse_datetime(raw: Any) -> datetime:
    """Parse datetime from Firestore timestamp or ISO string to UTC datetime."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw
    if hasattr(raw, "to_datetime"):
        dt = raw.to_datetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    if isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class PackagingRepository(ABC):
    """Abstract repository for PackagingProposal and CreatorPackageOverrides persistence."""

    @abstractmethod
    async def save_packaging_proposal(self, proposal: PackagingProposal) -> None:
        """Persist or update a packaging proposal."""
        pass

    @abstractmethod
    async def get_packaging_proposal(
        self, production_id: str, proposal_id: str
    ) -> PackagingProposal | None:
        """Retrieve a specific packaging proposal by ID."""
        pass

    @abstractmethod
    async def get_latest_packaging_proposal(
        self, production_id: str
    ) -> PackagingProposal | None:
        """Retrieve the most recent packaging proposal for a production."""
        pass

    @abstractmethod
    async def list_packaging_proposals(
        self, production_id: str
    ) -> list[PackagingProposal]:
        """List all packaging proposals for a production."""
        pass

    @abstractmethod
    async def save_package_overrides(
        self, production_id: str, overrides: CreatorPackageOverrides
    ) -> None:
        """Persist or update creator package overrides."""
        pass

    @abstractmethod
    async def get_package_overrides(
        self, production_id: str
    ) -> CreatorPackageOverrides | None:
        """Retrieve creator package overrides for a production."""
        pass

    @abstractmethod
    async def delete_by_production_id(self, production_id: str) -> int:
        """Delete all packaging data for a production."""
        pass

    def _deserialize_proposal(self, data: dict[str, Any]) -> PackagingProposal:
        """Deserialize raw Firestore dictionary into validated PackagingProposal."""
        payload = deepcopy(data)
        payload["created_at"] = parse_datetime(payload.get("created_at"))
        return PackagingProposal.model_validate(payload)

    def _deserialize_overrides(self, data: dict[str, Any]) -> CreatorPackageOverrides:
        """Deserialize raw Firestore dictionary into validated CreatorPackageOverrides."""
        payload = deepcopy(data)
        payload["updated_at"] = parse_datetime(payload.get("updated_at"))
        return CreatorPackageOverrides.model_validate(payload)


class InMemoryPackagingRepository(PackagingRepository):
    """In-memory mock PackagingRepository for unit tests and local development."""

    def __init__(self) -> None:
        # {production_id: {proposal_id: PackagingProposal}}
        self._proposals: dict[str, dict[str, PackagingProposal]] = {}
        # {production_id: CreatorPackageOverrides}
        self._overrides: dict[str, CreatorPackageOverrides] = {}

    async def save_packaging_proposal(self, proposal: PackagingProposal) -> None:
        if proposal.production_id not in self._proposals:
            self._proposals[proposal.production_id] = {}
        self._proposals[proposal.production_id][proposal.proposal_id] = deepcopy(proposal)

    async def get_packaging_proposal(
        self, production_id: str, proposal_id: str
    ) -> PackagingProposal | None:
        prod_proposals = self._proposals.get(production_id, {})
        proposal = prod_proposals.get(proposal_id)
        return deepcopy(proposal) if proposal else None

    async def get_latest_packaging_proposal(
        self, production_id: str
    ) -> PackagingProposal | None:
        prod_proposals = self._proposals.get(production_id, {})
        if not prod_proposals:
            return None
        sorted_proposals = sorted(
            prod_proposals.values(),
            key=lambda p: p.created_at,
            reverse=True,
        )
        return deepcopy(sorted_proposals[0])

    async def list_packaging_proposals(
        self, production_id: str
    ) -> list[PackagingProposal]:
        prod_proposals = self._proposals.get(production_id, {})
        return [deepcopy(p) for p in sorted(prod_proposals.values(), key=lambda p: p.created_at, reverse=True)]

    async def save_package_overrides(
        self, production_id: str, overrides: CreatorPackageOverrides
    ) -> None:
        self._overrides[production_id] = deepcopy(overrides)

    async def get_package_overrides(
        self, production_id: str
    ) -> CreatorPackageOverrides | None:
        overrides = self._overrides.get(production_id)
        return deepcopy(overrides) if overrides else None

    async def delete_by_production_id(self, production_id: str) -> int:
        count = len(self._proposals.pop(production_id, {}))
        self._overrides.pop(production_id, None)
        return count

    def clear(self) -> None:
        self._proposals.clear()
        self._overrides.clear()


class FirestorePackagingRepository(PackagingRepository):
    """Production PackagingRepository persisting to Google Cloud Firestore Native mode."""

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

    def _proposals_subcollection(self, production_id: str) -> Any:
        return (
            self.client
            .collection("productions")
            .document(production_id)
            .collection("packaging_proposals")
        )

    def _overrides_doc_ref(self, production_id: str) -> Any:
        return (
            self.client
            .collection("productions")
            .document(production_id)
            .collection("packaging")
            .document("overrides")
        )

    async def save_packaging_proposal(self, proposal: PackagingProposal) -> None:
        start_time = time.perf_counter()
        coll = self._proposals_subcollection(proposal.production_id)
        doc_ref = coll.document(proposal.proposal_id)

        data = proposal.model_dump(mode="json")
        data["created_at"] = proposal.created_at.isoformat()

        try:
            await doc_ref.set(data)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.write",
                collection=f"productions/{proposal.production_id}/packaging_proposals",
                operation="set",
                document_id=proposal.proposal_id,
                status=200,
                latency_ms=latency_ms,
                message=f"Persisted PackagingProposal {proposal.proposal_id}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{proposal.production_id}/packaging_proposals",
                operation="set",
                document_id=proposal.proposal_id,
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_write_error",
                message=f"Firestore write error for packaging proposal {proposal.proposal_id}: {type(exc).__name__}",
                exception=exc,
            )
            raise

    async def get_packaging_proposal(
        self, production_id: str, proposal_id: str
    ) -> PackagingProposal | None:
        start_time = time.perf_counter()
        coll = self._proposals_subcollection(production_id)
        doc_ref = coll.document(proposal_id)

        try:
            snap = await doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/packaging_proposals",
                operation="get",
                document_id=proposal_id,
                status=200 if snap.exists else 404,
                latency_ms=latency_ms,
            )
            if not snap.exists:
                return None
            return self._deserialize_proposal(snap.to_dict())
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/packaging_proposals",
                operation="get",
                document_id=proposal_id,
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_read_error",
                exception=exc,
            )
            raise

    async def get_latest_packaging_proposal(
        self, production_id: str
    ) -> PackagingProposal | None:
        start_time = time.perf_counter()
        coll = self._proposals_subcollection(production_id)

        try:
            query = coll.order_by("created_at", direction="DESCENDING").limit(1)
            docs = [d async for d in query.stream()]
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/packaging_proposals",
                operation="query",
                status=200 if docs else 404,
                latency_ms=latency_ms,
            )
            if not docs:
                return None
            return self._deserialize_proposal(docs[0].to_dict())
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/packaging_proposals",
                operation="query",
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_query_error",
                exception=exc,
            )
            raise

    async def list_packaging_proposals(
        self, production_id: str
    ) -> list[PackagingProposal]:
        start_time = time.perf_counter()
        coll = self._proposals_subcollection(production_id)

        try:
            query = coll.order_by("created_at", direction="DESCENDING")
            docs = [d async for d in query.stream()]
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/packaging_proposals",
                operation="query",
                status=200,
                latency_ms=latency_ms,
            )
            return [self._deserialize_proposal(d.to_dict()) for d in docs]
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/packaging_proposals",
                operation="query",
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_query_error",
                exception=exc,
            )
            raise

    async def save_package_overrides(
        self, production_id: str, overrides: CreatorPackageOverrides
    ) -> None:
        start_time = time.perf_counter()
        doc_ref = self._overrides_doc_ref(production_id)

        data = overrides.model_dump(mode="json")
        data["updated_at"] = overrides.updated_at.isoformat()

        try:
            await doc_ref.set(data)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.write",
                collection=f"productions/{production_id}/packaging",
                operation="set",
                document_id="overrides",
                status=200,
                latency_ms=latency_ms,
                message=f"Persisted CreatorPackageOverrides for {production_id}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/packaging",
                operation="set",
                document_id="overrides",
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_write_error",
                exception=exc,
            )
            raise

    async def get_package_overrides(
        self, production_id: str
    ) -> CreatorPackageOverrides | None:
        start_time = time.perf_counter()
        doc_ref = self._overrides_doc_ref(production_id)

        try:
            snap = await doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection=f"productions/{production_id}/packaging",
                operation="get",
                document_id="overrides",
                status=200 if snap.exists else 404,
                latency_ms=latency_ms,
            )
            if not snap.exists:
                return None
            return self._deserialize_overrides(snap.to_dict())
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection=f"productions/{production_id}/packaging",
                operation="get",
                document_id="overrides",
                status=500,
                latency_ms=latency_ms,
                error_code="firestore_read_error",
                exception=exc,
            )
            raise

    async def delete_by_production_id(self, production_id: str) -> int:
        coll = self._proposals_subcollection(production_id)
        snaps = [d async for d in coll.stream()]
        for snap in snaps:
            await snap.reference.delete()
        overrides_ref = self._overrides_doc_ref(production_id)
        await overrides_ref.delete()
        return len(snaps)


def get_default_packaging_repository() -> PackagingRepository:
    """Dependency provider returning singleton PackagingRepository instance."""
    global _global_packaging_repo
    if _global_packaging_repo is None:
        settings = get_settings()
        if settings.is_production:
            if not settings.gcp_project_id and not os.getenv("FIRESTORE_EMULATOR_HOST"):
                raise RuntimeError(
                    "Production mode requires FirestorePackagingRepository with valid gcp_project_id."
                )
            _global_packaging_repo = FirestorePackagingRepository(project_id=settings.gcp_project_id)
        elif settings.firestore_emulator_host or (settings.gcp_project_id and os.getenv("USE_FIRESTORE") == "true"):
            _global_packaging_repo = FirestorePackagingRepository(project_id=settings.gcp_project_id)
        else:
            _global_packaging_repo = InMemoryPackagingRepository()
    return _global_packaging_repo

def get_packaging_repository() -> PackagingRepository:
    return get_default_packaging_repository()


def set_packaging_repository(repo: PackagingRepository | None) -> None:
    global _global_packaging_repo
    _global_packaging_repo = repo
