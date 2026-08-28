"""Repository for YouTubePublishJob persistence and deterministic idempotency lookups."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.publish import YouTubePublishJob
from croviq_observability import log_firestore_event

logger = logging.getLogger(__name__)


class PublishJobRepository(ABC):
    """Abstract interface for persisting and querying YouTubePublishJob instances."""

    @abstractmethod
    async def get_by_id(self, publish_job_id: str) -> YouTubePublishJob | None:
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, idempotency_key: str) -> YouTubePublishJob | None:
        pass

    @abstractmethod
    async def get_latest_by_production_id(self, production_id: str) -> YouTubePublishJob | None:
        pass

    @abstractmethod
    async def list_by_production_id(self, production_id: str) -> list[YouTubePublishJob]:
        pass

    @abstractmethod
    async def save(self, job: YouTubePublishJob) -> YouTubePublishJob:
        pass

    @abstractmethod
    async def delete_by_production_id(self, production_id: str) -> int:
        pass


class InMemoryPublishJobRepository(PublishJobRepository):
    """In-memory repository for unit testing and local non-cloud execution."""

    def __init__(self) -> None:
        self._jobs: dict[str, YouTubePublishJob] = {}

    async def get_by_id(self, publish_job_id: str) -> YouTubePublishJob | None:
        return self._jobs.get(publish_job_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> YouTubePublishJob | None:
        for job in self._jobs.values():
            if job.idempotency_key == idempotency_key:
                return job
        return None

    async def get_latest_by_production_id(self, production_id: str) -> YouTubePublishJob | None:
        jobs = [j for j in self._jobs.values() if j.production_id == production_id]
        if not jobs:
            return None
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[0]

    async def list_by_production_id(self, production_id: str) -> list[YouTubePublishJob]:
        return [j for j in self._jobs.values() if j.production_id == production_id]

    async def save(self, job: YouTubePublishJob) -> YouTubePublishJob:
        self._jobs[job.publish_job_id] = job
        return job

    async def delete_by_production_id(self, production_id: str) -> int:
        keys_to_del = [k for k, v in self._jobs.items() if v.production_id == production_id]
        for k in keys_to_del:
            del self._jobs[k]
        return len(keys_to_del)


class FirestorePublishJobRepository(PublishJobRepository):
    """Production Firestore repository for YouTubePublishJob persistence."""

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

    async def get_by_id(self, publish_job_id: str) -> YouTubePublishJob | None:
        db = self._get_db()
        doc = db.collection("youtube_publish_jobs").document(publish_job_id).get()
        if not doc.exists:
            return None
        return YouTubePublishJob.model_validate(doc.to_dict())

    async def get_by_idempotency_key(self, idempotency_key: str) -> YouTubePublishJob | None:
        db = self._get_db()
        docs = list(
            db.collection("youtube_publish_jobs")
            .where("idempotency_key", "==", idempotency_key)
            .limit(1)
            .stream()
        )
        if not docs:
            return None
        return YouTubePublishJob.model_validate(docs[0].to_dict())

    async def get_latest_by_production_id(self, production_id: str) -> YouTubePublishJob | None:
        jobs = await self.list_by_production_id(production_id)
        if not jobs:
            return None
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[0]

    async def list_by_production_id(self, production_id: str) -> list[YouTubePublishJob]:
        db = self._get_db()
        docs = (
            db.collection("youtube_publish_jobs")
            .where("production_id", "==", production_id)
            .stream()
        )
        return [YouTubePublishJob.model_validate(doc.to_dict()) for doc in docs]

    async def save(self, job: YouTubePublishJob) -> YouTubePublishJob:
        db = self._get_db()
        doc_ref = db.collection("youtube_publish_jobs").document(job.publish_job_id)
        doc_ref.set(job.model_dump(mode="json"))

        log_firestore_event(
            event_type="firestore.write",
            collection="youtube_publish_jobs",
            operation="set",
            document_id=job.publish_job_id,
            status=200,
        )
        return job

    async def delete_by_production_id(self, production_id: str) -> int:
        db = self._get_db()
        docs = list(
            db.collection("youtube_publish_jobs")
            .where("production_id", "==", production_id)
            .stream()
        )
        for doc in docs:
            doc.reference.delete()
        return len(docs)


_global_publish_job_repo: PublishJobRepository | None = None


def get_publish_job_repository() -> PublishJobRepository:
    global _global_publish_job_repo
    if _global_publish_job_repo is None:
        if get_settings().is_production:
            _global_publish_job_repo = FirestorePublishJobRepository()
        else:
            _global_publish_job_repo = InMemoryPublishJobRepository()
    return _global_publish_job_repo


def set_publish_job_repository(repo: PublishJobRepository | None) -> None:
    global _global_publish_job_repo
    _global_publish_job_repo = repo
