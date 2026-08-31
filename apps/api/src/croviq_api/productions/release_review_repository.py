"""Release review repository interface and implementations (Firestore Native and In-Memory) (Issue #33)."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import os
import time
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.release_review import (
    ClaimSupportStatus,
    ClaimVerification,
    ReleaseChecklist,
    ReleaseIssue,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseReview,
    ReleaseVerdict,
    ThumbnailEvaluation,
)
from croviq_observability import log_firestore_event


_global_release_review_repo: "ReleaseReviewRepository | None" = None


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


class ReleaseReviewRepository(ABC):
    """Abstract repository for ReleaseReview persistence."""

    @abstractmethod
    async def save_release_review(self, review: ReleaseReview) -> None:
        """Persist or update a ReleaseReview record."""
        pass

    @abstractmethod
    async def get_release_review(self, production_id: str, review_id: str) -> ReleaseReview | None:
        """Retrieve a specific ReleaseReview by production and review ID."""
        pass

    @abstractmethod
    async def get_latest_release_review(
        self, production_id: str, preview_mode: str | None = None
    ) -> ReleaseReview | None:
        """Retrieve the most recent ReleaseReview for a production, optionally filtered by preview mode."""
        pass

    @abstractmethod
    async def list_release_reviews(self, production_id: str) -> list[ReleaseReview]:
        """List all ReleaseReviews recorded for a production."""
        pass

    @abstractmethod
    async def delete_by_production_id(self, production_id: str) -> int:
        """Delete all release reviews for a production."""
        pass

    @staticmethod
    def _to_dict(review: ReleaseReview) -> dict[str, Any]:
        """Serialize ReleaseReview domain model to Firestore-compatible dictionary."""
        data = review.model_dump()
        data["created_at"] = review.created_at.isoformat()
        if "issues" in data and isinstance(data["issues"], list):
            data["issues"] = [
                iss if isinstance(iss, dict) else iss.model_dump() for iss in data["issues"]
            ]
        if "claim_verifications" in data and isinstance(data["claim_verifications"], list):
            data["claim_verifications"] = [
                c if isinstance(c, dict) else c.model_dump() for c in data["claim_verifications"]
            ]
        if "thumbnail_evaluations" in data and isinstance(data["thumbnail_evaluations"], list):
            data["thumbnail_evaluations"] = [
                t if isinstance(t, dict) else t.model_dump() for t in data["thumbnail_evaluations"]
            ]
        if "quality_breakdown" in data and isinstance(data["quality_breakdown"], dict):
            pass
        if "grammar_breakdown" in data and isinstance(data["grammar_breakdown"], dict):
            pass
        if "confidence_breakdown" in data and isinstance(data["confidence_breakdown"], dict):
            pass
        if "reese_metadata" in data and isinstance(data["reese_metadata"], dict):
            pass
        return data
    @staticmethod
    def _from_dict(data: dict[str, Any]) -> ReleaseReview:
        """Deserialize Firestore document dictionary to ReleaseReview domain model."""
        filtered = dict(data)
        if "created_at" in filtered:
            filtered["created_at"] = parse_datetime(filtered["created_at"])
        if "issues" in filtered and isinstance(filtered["issues"], list):
            filtered["issues"] = [
                ReleaseIssue.model_validate(iss) if isinstance(iss, dict) else iss
                for iss in filtered["issues"]
            ]
        if "claim_verifications" in filtered and isinstance(filtered["claim_verifications"], list):
            filtered["claim_verifications"] = [
                ClaimVerification.model_validate(c) if isinstance(c, dict) else c
                for c in filtered["claim_verifications"]
            ]
        if "thumbnail_evaluations" in filtered and isinstance(filtered["thumbnail_evaluations"], list):
            filtered["thumbnail_evaluations"] = [
                ThumbnailEvaluation.model_validate(t) if isinstance(t, dict) else t
                for t in filtered["thumbnail_evaluations"]
            ]
        if "checklist" in filtered and isinstance(filtered["checklist"], dict):
            filtered["checklist"] = ReleaseChecklist.model_validate(filtered["checklist"])
        if "quality_breakdown" in filtered and isinstance(filtered["quality_breakdown"], dict):
            filtered["quality_breakdown"] = QualityScoreBreakdown.model_validate(filtered["quality_breakdown"])
        if "grammar_breakdown" in filtered and isinstance(filtered["grammar_breakdown"], dict):
            filtered["grammar_breakdown"] = GrammarScoreBreakdown.model_validate(filtered["grammar_breakdown"])
        if "confidence_breakdown" in filtered and isinstance(filtered["confidence_breakdown"], dict):
            filtered["confidence_breakdown"] = ConfidenceScoreBreakdown.model_validate(filtered["confidence_breakdown"])
        if "reese_metadata" in filtered and isinstance(filtered["reese_metadata"], dict):
            filtered["reese_metadata"] = ReeseMetadataRecommendation.model_validate(filtered["reese_metadata"])
        return ReleaseReview.model_validate(filtered)


class InMemoryReleaseReviewRepository(ReleaseReviewRepository):
    """In-memory mock ReleaseReviewRepository for unit testing and local development."""

    def __init__(self) -> None:
        self._by_production: dict[str, dict[str, ReleaseReview]] = {}

    async def save_release_review(self, review: ReleaseReview) -> None:
        if review.production_id not in self._by_production:
            self._by_production[review.production_id] = {}
        self._by_production[review.production_id][review.review_id] = deepcopy(review)

    async def get_release_review(self, production_id: str, review_id: str) -> ReleaseReview | None:
        prod_reviews = self._by_production.get(production_id, {})
        review = prod_reviews.get(review_id)
        return deepcopy(review) if review else None

    async def get_latest_release_review(
        self, production_id: str, preview_mode: str | None = None
    ) -> ReleaseReview | None:
        prod_reviews = self._by_production.get(production_id, {})
        if not prod_reviews:
            return None
        candidate_reviews = list(prod_reviews.values())
        if preview_mode:
            candidate_reviews = [
                r for r in candidate_reviews
                if getattr(r, "preview_mode", "final_mix") == preview_mode
            ]
        if not candidate_reviews:
            return None
        sorted_reviews = sorted(
            candidate_reviews,
            key=lambda r: r.created_at,
            reverse=True,
        )
        return deepcopy(sorted_reviews[0])
    async def list_release_reviews(self, production_id: str) -> list[ReleaseReview]:
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


class FirestoreReleaseReviewRepository(ReleaseReviewRepository):
    """Production ReleaseReviewRepository persisting to Google Cloud Firestore Native mode."""

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

    async def save_release_review(self, review: ReleaseReview) -> None:
        client = self._get_client()
        start = time.perf_counter()
        doc_ref = (
            client.collection("productions")
            .document(review.production_id)
            .collection("release_reviews")
            .document(review.review_id)
        )
        payload = self._to_dict(review)
        try:
            doc_ref.set(payload)
            latency_ms = (time.perf_counter() - start) * 1000.0
            log_firestore_event(
                event_type="firestore.write",
                operation="set",
                collection=f"productions/{review.production_id}/release_reviews",
                document_id=review.review_id,
                latency_ms=latency_ms,
                status=200,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            log_firestore_event(
                event_type="firestore.error",
                operation="set",
                collection=f"productions/{review.production_id}/release_reviews",
                document_id=review.review_id,
                latency_ms=latency_ms,
                status=500,
                error_code=str(exc),
            )
            raise

    async def get_release_review(self, production_id: str, review_id: str) -> ReleaseReview | None:
        client = self._get_client()
        start = time.perf_counter()
        doc_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("release_reviews")
            .document(review_id)
        )
        try:
            snap = doc_ref.get()
            latency_ms = (time.perf_counter() - start) * 1000.0
            if not snap.exists:
                log_firestore_event(
                    event_type="firestore.read",
                    operation="get",
                    collection=f"productions/{production_id}/release_reviews",
                    document_id=review_id,
                    latency_ms=latency_ms,
                    status=404,
                )
                return None
            data = snap.to_dict() or {}
            log_firestore_event(
                event_type="firestore.read",
                operation="get",
                collection=f"productions/{production_id}/release_reviews",
                document_id=review_id,
                latency_ms=latency_ms,
                status=200,
            )
            return self._from_dict(data)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            log_firestore_event(
                event_type="firestore.error",
                operation="get",
                collection=f"productions/{production_id}/release_reviews",
                document_id=review_id,
                latency_ms=latency_ms,
                status=500,
                error_code=str(exc),
            )
            raise

    async def get_latest_release_review(
        self, production_id: str, preview_mode: str | None = None
    ) -> ReleaseReview | None:
        client = self._get_client()
        start = time.perf_counter()
        coll_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("release_reviews")
        )
        try:
            query = coll_ref.order_by("created_at", direction="DESCENDING")
            docs = list(query.stream())
            latency_ms = (time.perf_counter() - start) * 1000.0
            if not docs:
                log_firestore_event(
                    event_type="firestore.read",
                    operation="query",
                    collection=f"productions/{production_id}/release_reviews",
                    latency_ms=latency_ms,
                    status=404,
                )
                return None
            matching_docs = docs
            if preview_mode:
                matching_docs = [
                    d for d in docs
                    if (d.to_dict() or {}).get("preview_mode") == preview_mode
                ]
            if not matching_docs:
                return None
            data = matching_docs[0].to_dict() or {}
            log_firestore_event(
                event_type="firestore.read",
                operation="query",
                collection=f"productions/{production_id}/release_reviews",
                document_id=matching_docs[0].id,
                latency_ms=latency_ms,
                status=200,
            )
            return self._from_dict(data)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            log_firestore_event(
                event_type="firestore.error",
                operation="query",
                collection=f"productions/{production_id}/release_reviews",
                latency_ms=latency_ms,
                status=500,
                error_code=str(exc),
            )
            raise

    async def list_release_reviews(self, production_id: str) -> list[ReleaseReview]:
        client = self._get_client()
        start = time.perf_counter()
        coll_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("release_reviews")
        )
        try:
            query = coll_ref.order_by("created_at", direction="DESCENDING")
            docs = list(query.stream())
            latency_ms = (time.perf_counter() - start) * 1000.0
            log_firestore_event(
                event_type="firestore.read",
                operation="list",
                collection=f"productions/{production_id}/release_reviews",
                latency_ms=latency_ms,
                status=200,
            )
            return [self._from_dict(d.to_dict() or {}) for d in docs]
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            log_firestore_event(
                event_type="firestore.error",
                operation="list",
                collection=f"productions/{production_id}/release_reviews",
                latency_ms=latency_ms,
                status=500,
                error_code=str(exc),
            )
            raise

    async def delete_by_production_id(self, production_id: str) -> int:
        client = self._get_client()
        coll_ref = (
            client.collection("productions")
            .document(production_id)
            .collection("release_reviews")
        )
        docs = list(coll_ref.stream())
        for doc in docs:
            doc.reference.delete()
        return len(docs)


def get_default_release_review_repository() -> ReleaseReviewRepository:
    """Dependency provider returning singleton ReleaseReviewRepository instance."""
    global _global_release_review_repo
    if _global_release_review_repo is None:
        settings = get_settings()
        if settings.environment == "test":
            _global_release_review_repo = InMemoryReleaseReviewRepository()
        else:
            _global_release_review_repo = FirestoreReleaseReviewRepository(
                project_id=settings.gcp_project_id
            )
    return _global_release_review_repo


def get_release_review_repository() -> ReleaseReviewRepository:
    return get_default_release_review_repository()


def set_release_review_repository(repo: ReleaseReviewRepository | None) -> None:
    global _global_release_review_repo
    _global_release_review_repo = repo
