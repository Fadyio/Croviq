"""Render review repository interface and implementations (Firestore Native and In-Memory)."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import os
import time
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.render_review import RenderReview, RenderReviewIssue
from croviq_observability import log_firestore_event


_global_render_review_repo: "RenderReviewRepository | None" = None


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


class RenderReviewRepository(ABC):
    """Abstract repository for RenderReview persistence."""

    @abstractmethod
    async def save_render_review(self, review: RenderReview) -> None:
        """Persist or update a post-render review record."""
        pass

    @abstractmethod
    async def get_render_review(self, production_id: str, review_id: str) -> RenderReview | None:
        """Retrieve a specific RenderReview by production and review ID."""
        pass

    @abstractmethod
    async def get_latest_render_review(self, production_id: str) -> RenderReview | None:
        """Retrieve the most recent RenderReview for a production."""
        pass

    @abstractmethod
    async def get_render_review_by_preview(
        self, production_id: str, edl_id: str, preview_artifact_id: str
    ) -> RenderReview | None:
        """Retrieve an existing RenderReview matching the exact EDL and preview artifact for idempotency."""
        pass

    @abstractmethod
    async def list_render_reviews(self, production_id: str) -> list[RenderReview]:
        """List all RenderReviews recorded for a production."""
        pass

    @abstractmethod
    async def delete_by_production_id(self, production_id: str) -> int:
        """Delete all render reviews for a production."""
        pass

    @staticmethod
    def _to_dict(review: RenderReview) -> dict[str, Any]:
        """Serialize RenderReview domain model to Firestore-compatible dictionary."""
        data = review.model_dump()
        data["created_at"] = review.created_at.isoformat()
        if "issues" in data and isinstance(data["issues"], list):
            data["issues"] = [
                iss if isinstance(iss, dict) else iss.model_dump() for iss in data["issues"]
            ]
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> RenderReview:
        """Deserialize Firestore document dictionary to RenderReview domain model."""
        filtered = dict(data)
        if "created_at" in filtered:
            filtered["created_at"] = parse_datetime(filtered["created_at"])
        if "issues" in filtered and isinstance(filtered["issues"], list):
            filtered["issues"] = [
                RenderReviewIssue.model_validate(iss) if isinstance(iss, dict) else iss
                for iss in filtered["issues"]
            ]
        return RenderReview.model_validate(filtered)


class InMemoryRenderReviewRepository(RenderReviewRepository):
    """In-memory mock RenderReviewRepository for unit testing and local development."""

    def __init__(self) -> None:
        self._by_production: dict[str, dict[str, RenderReview]] = {}

    async def save_render_review(self, review: RenderReview) -> None:
        if review.production_id not in self._by_production:
            self._by_production[review.production_id] = {}
        self._by_production[review.production_id][review.review_id] = deepcopy(review)

    async def get_render_review(self, production_id: str, review_id: str) -> RenderReview | None:
        prod_reviews = self._by_production.get(production_id, {})
        review = prod_reviews.get(review_id)
        return deepcopy(review) if review else None

    async def get_latest_render_review(self, production_id: str) -> RenderReview | None:
        prod_reviews = self._by_production.get(production_id, {})
        if not prod_reviews:
            return None
        sorted_reviews = sorted(
            prod_reviews.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return deepcopy(sorted_reviews[0])

    async def get_render_review_by_preview(
        self, production_id: str, edl_id: str, preview_artifact_id: str
    ) -> RenderReview | None:
        prod_reviews = self._by_production.get(production_id, {})
        for r in prod_reviews.values():
            if r.edl_id == edl_id and r.preview_artifact_id == preview_artifact_id:
                return deepcopy(r)
        return None

    async def list_render_reviews(self, production_id: str) -> list[RenderReview]:
        prod_reviews = self._by_production.get(production_id, {})
        sorted_reviews = sorted(
            prod_reviews.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return [deepcopy(r) for r in sorted_reviews]

    async def delete_by_production_id(self, production_id: str) -> int:
        prod_reviews = self._by_production.pop(production_id, {})
        return len(prod_reviews)

    def clear(self) -> None:
        self._by_production.clear()


class FirestoreRenderReviewRepository(RenderReviewRepository):
    """Production RenderReviewRepository persisting to Google Cloud Firestore Native mode."""

    def __init__(self, project_id: str | None = None, database: str = "(default)") -> None:
        self._project_id = project_id
        self._database = database
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import firebase_admin
            from firebase_admin import firestore

            try:
                app = firebase_admin.get_app()
            except ValueError:
                app = firebase_admin.initialize_app(
                    options={"projectId": self._project_id} if self._project_id else None
                )
            self._client = firestore.client(app=app)
        return self._client

    async def save_render_review(self, review: RenderReview) -> None:
        client = self._get_client()
        start = time.perf_counter()
        doc_ref = (
            client.collection("productions")
            .document(review.production_id)
            .collection("render_reviews")
            .document(review.review_id)
        )
        data = self._to_dict(review)
        try:
            doc_ref.set(data)
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.write",
                operation="set",
                collection=f"productions/{review.production_id}/render_reviews",
                document_id=review.review_id,
                latency_ms=duration_ms,
                status=200,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.error",
                operation="set",
                collection=f"productions/{review.production_id}/render_reviews",
                document_id=review.review_id,
                latency_ms=duration_ms,
                status=500,
                error_code=str(exc),
            )
            raise
    async def get_render_review(self, production_id: str, review_id: str) -> RenderReview | None:
        client = self._get_client()
        start = time.perf_counter()
        doc_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("render_reviews")
            .document(review_id)
        )

        try:
            snapshot = doc_ref.get()
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.read",
                operation="get",
                collection=f"productions/{production_id}/render_reviews",
                document_id=review_id,
                latency_ms=duration_ms,
                status=200 if snapshot.exists else 404,
            )
            if snapshot.exists:
                return self._from_dict(snapshot.to_dict())
            return None
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.error",
                operation="get",
                collection=f"productions/{production_id}/render_reviews",
                document_id=review_id,
                latency_ms=duration_ms,
                status=500,
                error_code=str(exc),
            )
            raise

    async def get_latest_render_review(self, production_id: str) -> RenderReview | None:
        client = self._get_client()
        start = time.perf_counter()
        col_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("render_reviews")
            .order_by("created_at", direction="DESCENDING")
            .limit(1)
        )

        try:
            docs = list(col_ref.stream())
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.read",
                operation="query",
                collection=f"productions/{production_id}/render_reviews",
                document_id="latest",
                latency_ms=duration_ms,
                status=200,
            )
            if docs:
                return self._from_dict(docs[0].to_dict())
            return None
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.error",
                operation="query",
                collection=f"productions/{production_id}/render_reviews",
                document_id="latest",
                latency_ms=duration_ms,
                status=500,
                error_code=str(exc),
            )
            raise

    async def get_render_review_by_preview(
        self, production_id: str, edl_id: str, preview_artifact_id: str
    ) -> RenderReview | None:
        client = self._get_client()
        start = time.perf_counter()
        col_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("render_reviews")
            .where("edl_id", "==", edl_id)
            .where("preview_artifact_id", "==", preview_artifact_id)
            .limit(1)
        )

        try:
            docs = list(col_ref.stream())
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.read",
                operation="query",
                collection=f"productions/{production_id}/render_reviews",
                document_id=f"by_preview_{preview_artifact_id}",
                latency_ms=duration_ms,
                status=200,
            )
            if docs:
                return self._from_dict(docs[0].to_dict())
            return None
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.error",
                operation="query",
                collection=f"productions/{production_id}/render_reviews",
                document_id=f"by_preview_{preview_artifact_id}",
                latency_ms=duration_ms,
                status=500,
                error_code=str(exc),
            )
            raise

    async def list_render_reviews(self, production_id: str) -> list[RenderReview]:
        client = self._get_client()
        start = time.perf_counter()
        col_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("render_reviews")
            .order_by("created_at", direction="DESCENDING")
        )

        try:
            docs = list(col_ref.stream())
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.read",
                operation="query",
                collection=f"productions/{production_id}/render_reviews",
                document_id="all",
                latency_ms=duration_ms,
                status=200,
            )
            return [self._from_dict(d.to_dict()) for d in docs]
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log_firestore_event(
                event_type="firestore.error",
                operation="query",
                collection=f"productions/{production_id}/render_reviews",
                document_id="all",
                latency_ms=duration_ms,
                status=500,
                error_code=str(exc),
            )
            raise

    async def delete_by_production_id(self, production_id: str) -> int:
        client = self._get_client()
        col_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("render_reviews")
        )
        docs = [doc async for doc in col_ref.stream()]
        for doc in docs:
            await doc.reference.delete()
        return len(docs)


def get_default_render_review_repository() -> RenderReviewRepository:
    """Factory for default RenderReviewRepository instance."""
    global _global_render_review_repo
    if _global_render_review_repo is None:
        settings = get_settings()
        if settings.environment in ("production", "staging") or os.getenv("USE_FIRESTORE") == "true":
            _global_render_review_repo = FirestoreRenderReviewRepository(
                project_id=settings.gcp_project_id,
            )
        else:
            _global_render_review_repo = InMemoryRenderReviewRepository()
    return _global_render_review_repo


def get_render_review_repository() -> RenderReviewRepository:
    """FastAPI dependency provider for RenderReviewRepository."""
    return get_default_render_review_repository()


def set_render_review_repository(repo: RenderReviewRepository | None) -> None:
    """Override global RenderReviewRepository instance for testing isolation."""
    global _global_render_review_repo
    _global_render_review_repo = repo
