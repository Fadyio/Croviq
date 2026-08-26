"""Editorial repository interface and implementations (Firestore Native and In-Memory)."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import os
import time
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.editorial import (
    AgentActivity,
    DirectorReview,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
)
from croviq_observability import log_firestore_event


def parse_datetime(raw: Any) -> datetime:
    """Parse datetime from Firestore timestamp or ISO string to UTC datetime."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if hasattr(raw, "to_datetime"):
        dt = raw.to_datetime()
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if isinstance(raw, str):
        cleaned = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class EditorialRepository(ABC):
    """Abstract repository for EditorialRun, EditorProposal, DirectorReview, and AgentActivity persistence."""

    @abstractmethod
    async def get_latest_editorial_run(self, production_id: str) -> EditorialRun | None:
        """Retrieve the latest EditorialRun for a production."""
        pass

    @abstractmethod
    async def get_editorial_run_by_id(self, production_id: str, run_id: str) -> EditorialRun | None:
        """Retrieve an EditorialRun by ID."""
        pass

    @abstractmethod
    async def save_editorial_run(self, run: EditorialRun) -> EditorialRun:
        """Create or update an EditorialRun record."""
        pass

    @abstractmethod
    async def get_editor_proposal(self, production_id: str, proposal_id: str) -> EditorProposal | None:
        """Retrieve an EditorProposal by ID."""
        pass

    @abstractmethod
    async def save_editor_proposal(self, proposal: EditorProposal, proposal_id: str | None = None) -> str:
        """Persist an EditorProposal and return its unique identifier."""
        pass

    @abstractmethod
    async def get_director_review(self, production_id: str, review_id: str) -> DirectorReview | None:
        """Retrieve a DirectorReview by ID."""
        pass

    @abstractmethod
    async def save_director_review(self, review: DirectorReview, review_id: str | None = None) -> str:
        """Persist a DirectorReview and return its unique identifier."""
        pass

    @abstractmethod
    async def list_activities(
        self, production_id: str, run_id: str | None = None
    ) -> list[AgentActivity]:
        """List all AgentActivity records for a production, optionally filtered by run ID."""
        pass

    @abstractmethod
    async def save_activities(self, activities: list[AgentActivity]) -> None:
        """Batch persist AgentActivity records."""
        pass


class InMemoryEditorialRepository(EditorialRepository):
    """In-memory mock repository for tests and local execution."""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, EditorialRun]] = {}  # prod_id -> {run_id: EditorialRun}
        self._proposals: dict[str, dict[str, EditorProposal]] = {}  # prod_id -> {proposal_id: EditorProposal}
        self._reviews: dict[str, dict[str, DirectorReview]] = {}  # prod_id -> {review_id: DirectorReview}
        self._activities: dict[str, list[AgentActivity]] = {}  # prod_id -> [AgentActivity]

    async def get_latest_editorial_run(self, production_id: str) -> EditorialRun | None:
        runs = self._runs.get(production_id, {})
        if not runs:
            return None
        sorted_runs = sorted(runs.values(), key=lambda r: r.started_at, reverse=True)
        return deepcopy(sorted_runs[0])

    async def get_editorial_run_by_id(self, production_id: str, run_id: str) -> EditorialRun | None:
        run = self._runs.get(production_id, {}).get(run_id)
        return deepcopy(run) if run else None

    async def save_editorial_run(self, run: EditorialRun) -> EditorialRun:
        if run.production_id not in self._runs:
            self._runs[run.production_id] = {}
        self._runs[run.production_id][run.run_id] = deepcopy(run)
        return deepcopy(run)

    async def get_editor_proposal(self, production_id: str, proposal_id: str) -> EditorProposal | None:
        prop = self._proposals.get(production_id, {}).get(proposal_id)
        return deepcopy(prop) if prop else None

    async def save_editor_proposal(self, proposal: EditorProposal, proposal_id: str | None = None) -> str:
        pid = proposal_id or f"prop_{len(self._proposals.get(proposal.production_id, {})) + 1}"
        if proposal.production_id not in self._proposals:
            self._proposals[proposal.production_id] = {}
        self._proposals[proposal.production_id][pid] = deepcopy(proposal)
        return pid

    async def get_director_review(self, production_id: str, review_id: str) -> DirectorReview | None:
        rev = self._reviews.get(production_id, {}).get(review_id)
        return deepcopy(rev) if rev else None

    async def save_director_review(self, review: DirectorReview, review_id: str | None = None) -> str:
        rid = review_id or f"rev_{len(self._reviews.get(review.production_id, {})) + 1}"
        if review.production_id not in self._reviews:
            self._reviews[review.production_id] = {}
        self._reviews[review.production_id][rid] = deepcopy(review)
        return rid

    async def list_activities(
        self, production_id: str, run_id: str | None = None
    ) -> list[AgentActivity]:
        acts = self._activities.get(production_id, [])
        if run_id:
            acts = [a for a in acts if a.run_id == run_id]
        return [deepcopy(a) for a in sorted(acts, key=lambda a: a.created_at)]

    async def save_activities(self, activities: list[AgentActivity]) -> None:
        for a in activities:
            if a.production_id not in self._activities:
                self._activities[a.production_id] = []
            self._activities[a.production_id].append(deepcopy(a))

    def clear(self) -> None:
        self._runs.clear()
        self._proposals.clear()
        self._reviews.clear()
        self._activities.clear()


class FirestoreEditorialRepository(EditorialRepository):
    """Production Editorial repository persisting to Google Cloud Firestore Native mode."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import firebase_admin
            from firebase_admin import firestore

            try:
                firebase_admin.get_app()
            except ValueError:
                settings = get_settings()
                options = {"projectId": settings.gcp_project_id} if settings.gcp_project_id else None
                firebase_admin.initialize_app(options=options)
            self._client = firestore.client()
        return self._client

    async def get_latest_editorial_run(self, production_id: str) -> EditorialRun | None:
        start_time = time.perf_counter()
        db = self._get_client()
        coll_ref = (
            db.collection("productions")
            .document(production_id)
            .collection("editorial_runs")
            .order_by("started_at", direction="DESCENDING")
            .limit(1)
        )
        try:
            docs = list(coll_ref.stream())
            latency_ms = (time.perf_counter() - start_time) * 1000
            if not docs:
                log_firestore_event("firestore.read", "editorial_runs", "query", status=200, latency_ms=latency_ms)
                return None
            data = docs[0].to_dict()
            data["run_id"] = docs[0].id
            data["started_at"] = parse_datetime(data.get("started_at"))
            if data.get("completed_at"):
                data["completed_at"] = parse_datetime(data["completed_at"])
            log_firestore_event("firestore.read", "editorial_runs", "query", document_id=docs[0].id, status=200, latency_ms=latency_ms)
            return EditorialRun.model_validate(data)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "editorial_runs", "query", status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

    async def get_editorial_run_by_id(self, production_id: str, run_id: str) -> EditorialRun | None:
        start_time = time.perf_counter()
        db = self._get_client()
        doc_ref = db.collection("productions").document(production_id).collection("editorial_runs").document(run_id)
        try:
            doc = doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            if not doc.exists:
                log_firestore_event("firestore.read", "editorial_runs", "get", document_id=run_id, status=404, latency_ms=latency_ms)
                return None
            data = doc.to_dict() or {}
            data["run_id"] = doc.id
            data["started_at"] = parse_datetime(data.get("started_at"))
            if data.get("completed_at"):
                data["completed_at"] = parse_datetime(data["completed_at"])
            log_firestore_event("firestore.read", "editorial_runs", "get", document_id=run_id, status=200, latency_ms=latency_ms)
            return EditorialRun.model_validate(data)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "editorial_runs", "get", document_id=run_id, status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

    async def save_editorial_run(self, run: EditorialRun) -> EditorialRun:
        start_time = time.perf_counter()
        db = self._get_client()
        doc_ref = db.collection("productions").document(run.production_id).collection("editorial_runs").document(run.run_id)
        payload = run.model_dump(mode="json")
        try:
            doc_ref.set(payload, merge=True)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.write", "editorial_runs", "set", document_id=run.run_id, status=200, latency_ms=latency_ms)
            return run
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "editorial_runs", "set", document_id=run.run_id, status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

    async def get_editor_proposal(self, production_id: str, proposal_id: str) -> EditorProposal | None:
        start_time = time.perf_counter()
        db = self._get_client()
        doc_ref = db.collection("productions").document(production_id).collection("editor_proposals").document(proposal_id)
        try:
            doc = doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            if not doc.exists:
                log_firestore_event("firestore.read", "editor_proposals", "get", document_id=proposal_id, status=404, latency_ms=latency_ms)
                return None
            data = doc.to_dict() or {}
            log_firestore_event("firestore.read", "editor_proposals", "get", document_id=proposal_id, status=200, latency_ms=latency_ms)
            return EditorProposal.model_validate(data)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "editor_proposals", "get", document_id=proposal_id, status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

    async def save_editor_proposal(self, proposal: EditorProposal, proposal_id: str | None = None) -> str:
        start_time = time.perf_counter()
        db = self._get_client()
        coll_ref = db.collection("productions").document(proposal.production_id).collection("editor_proposals")
        pid = proposal_id or coll_ref.document().id
        doc_ref = coll_ref.document(pid)
        payload = proposal.model_dump(mode="json")
        try:
            doc_ref.set(payload)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.write", "editor_proposals", "create", document_id=pid, status=201, latency_ms=latency_ms)
            return pid
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "editor_proposals", "create", document_id=pid, status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

    async def get_director_review(self, production_id: str, review_id: str) -> DirectorReview | None:
        start_time = time.perf_counter()
        db = self._get_client()
        doc_ref = db.collection("productions").document(production_id).collection("director_reviews").document(review_id)
        try:
            doc = doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            if not doc.exists:
                log_firestore_event("firestore.read", "director_reviews", "get", document_id=review_id, status=404, latency_ms=latency_ms)
                return None
            data = doc.to_dict() or {}
            log_firestore_event("firestore.read", "director_reviews", "get", document_id=review_id, status=200, latency_ms=latency_ms)
            return DirectorReview.model_validate(data)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "director_reviews", "get", document_id=review_id, status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

    async def save_director_review(self, review: DirectorReview, review_id: str | None = None) -> str:
        start_time = time.perf_counter()
        db = self._get_client()
        coll_ref = db.collection("productions").document(review.production_id).collection("director_reviews")
        rid = review_id or coll_ref.document().id
        doc_ref = coll_ref.document(rid)
        payload = review.model_dump(mode="json")
        try:
            doc_ref.set(payload)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.write", "director_reviews", "create", document_id=rid, status=201, latency_ms=latency_ms)
            return rid
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "director_reviews", "create", document_id=rid, status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

    async def list_activities(
        self, production_id: str, run_id: str | None = None
    ) -> list[AgentActivity]:
        start_time = time.perf_counter()
        db = self._get_client()
        coll_ref = db.collection("productions").document(production_id).collection("agent_activities")
        if run_id:
            query = coll_ref.where("run_id", "==", run_id).order_by("created_at")
        else:
            query = coll_ref.order_by("created_at")
        try:
            docs = list(query.stream())
            latency_ms = (time.perf_counter() - start_time) * 1000
            activities: list[AgentActivity] = []
            for doc in docs:
                data = doc.to_dict()
                data["activity_id"] = doc.id
                data["created_at"] = parse_datetime(data.get("created_at"))
                activities.append(AgentActivity.model_validate(data))
            log_firestore_event("firestore.read", "agent_activities", "query", status=200, latency_ms=latency_ms)
            return activities
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "agent_activities", "query", status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

    async def save_activities(self, activities: list[AgentActivity]) -> None:
        if not activities:
            return
        start_time = time.perf_counter()
        db = self._get_client()
        batch = db.batch()
        for act in activities:
            doc_ref = (
                db.collection("productions")
                .document(act.production_id)
                .collection("agent_activities")
                .document(act.activity_id)
            )
            payload = act.model_dump(mode="json")
            batch.set(doc_ref, payload)
        try:
            batch.commit()
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.write", "agent_activities", "batch_set", document_id=f"batch_{len(activities)}", status=200, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event("firestore.error", "agent_activities", "batch_set", status=500, latency_ms=latency_ms, error_code=str(exc))
            raise

_global_editorial_repo: EditorialRepository | None = None


def get_default_editorial_repository() -> EditorialRepository:
    """Factory for default EditorialRepository instance."""
    global _global_editorial_repo
    if _global_editorial_repo is None:
        env = os.getenv("CROVIQ_ENV") or os.getenv("ENVIRONMENT", "development")
        if env == "production":
            _global_editorial_repo = FirestoreEditorialRepository()
        else:
            _global_editorial_repo = InMemoryEditorialRepository()
    return _global_editorial_repo


def get_editorial_repository() -> EditorialRepository:
    """FastAPI dependency provider for EditorialRepository."""
    return get_default_editorial_repository()


def set_editorial_repository(repo: EditorialRepository | None) -> None:
    """Override the global editorial repository instance (useful for test isolation)."""
    global _global_editorial_repo
    _global_editorial_repo = repo
