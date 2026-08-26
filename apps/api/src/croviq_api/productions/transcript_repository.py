"""Transcript repository interface and implementations (Firestore Native and In-Memory)."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import time
import os
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.transcript import (
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from croviq_observability import log_firestore_event


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


class TranscriptRepository(ABC):
    """Abstract repository for Transcript entity persistence."""

    @abstractmethod
    async def save_transcript(self, transcript: Transcript) -> Transcript:
        """Create or replace a transcript document."""
        pass

    @abstractmethod
    async def get_transcript(self, transcript_id: str) -> Transcript | None:
        """Fetch transcript by transcript_id."""
        pass

    @abstractmethod
    async def get_transcript_by_production_id(self, production_id: str) -> Transcript | None:
        """Fetch transcript by production_id."""
        pass

    def transcript_to_dict(self, transcript: Transcript) -> dict[str, Any]:
        """Serialize Transcript model to Firestore-compatible dictionary."""
        return transcript.model_dump(mode="json")

    def transcript_from_dict(self, data: dict[str, Any]) -> Transcript:
        """Deserialize Firestore document dictionary to canonical Transcript model."""
        payload = deepcopy(data)
        if "created_at" in payload:
            payload["created_at"] = parse_datetime(payload["created_at"])
        return Transcript.model_validate(payload)


class InMemoryTranscriptRepository(TranscriptRepository):
    """In-memory mock repository for testing and local execution."""

    def __init__(self) -> None:
        self._transcripts: dict[str, Transcript] = {}
        self._by_production: dict[str, str] = {}

    async def save_transcript(self, transcript: Transcript) -> Transcript:
        self._transcripts[transcript.transcript_id] = transcript
        self._by_production[transcript.production_id] = transcript.transcript_id
        return transcript

    async def get_transcript(self, transcript_id: str) -> Transcript | None:
        return self._transcripts.get(transcript_id)

    async def get_transcript_by_production_id(self, production_id: str) -> Transcript | None:
        t_id = self._by_production.get(production_id)
        if t_id and t_id in self._transcripts:
            return self._transcripts[t_id]
        return None

    def clear(self) -> None:
        self._transcripts.clear()
        self._by_production.clear()


class FirestoreTranscriptRepository(TranscriptRepository):
    """Production Transcript repository persisting to Google Cloud Firestore Native mode."""

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

    async def save_transcript(self, transcript: Transcript) -> Transcript:
        start_time = time.perf_counter()
        try:
            doc_ref = self.client.collection("transcripts").document(
                transcript.transcript_id
            )
            data = self.transcript_to_dict(transcript)
            await doc_ref.set(data)
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.write",
                collection="transcripts",
                operation="create",
                document_id=transcript.transcript_id,
                status=201,
                latency_ms=latency_ms,
                message=f"Saved transcript record {transcript.transcript_id} for production {transcript.production_id}",
            )
            return transcript
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection="transcripts",
                operation="create",
                document_id=transcript.transcript_id,
                status=500,
                latency_ms=latency_ms,
                exception=exc,
                error_code="firestore_save_transcript_error",
                message=f"Firestore save error for transcript {transcript.transcript_id}: {type(exc).__name__}",
            )
            raise

    async def get_transcript(self, transcript_id: str) -> Transcript | None:
        start_time = time.perf_counter()
        try:
            doc_ref = self.client.collection("transcripts").document(transcript_id)
            doc = await doc_ref.get()
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection="transcripts",
                operation="get",
                document_id=transcript_id,
                status=200,
                latency_ms=latency_ms,
                message=f"Fetched transcript {transcript_id}",
            )
            if doc.exists:
                return self.transcript_from_dict(doc.to_dict())
            return None
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection="transcripts",
                operation="get",
                document_id=transcript_id,
                status=500,
                latency_ms=latency_ms,
                exception=exc,
                error_code="firestore_get_transcript_error",
                message=f"Firestore get error for transcript {transcript_id}: {type(exc).__name__}",
            )
            raise

    async def get_transcript_by_production_id(self, production_id: str) -> Transcript | None:
        start_time = time.perf_counter()
        try:
            query = (
                self.client.collection("transcripts")
                .where("production_id", "==", production_id)
                .limit(1)
            )
            docs = [doc async for doc in query.stream()]
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.read",
                collection="transcripts",
                operation="query",
                status=200,
                latency_ms=latency_ms,
                message=f"Queried transcript by production_id {production_id}",
            )
            if docs:
                return self.transcript_from_dict(docs[0].to_dict())
            return None
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log_firestore_event(
                event_type="firestore.error",
                collection="transcripts",
                operation="query",
                status=500,
                latency_ms=latency_ms,
                exception=exc,
                error_code="firestore_query_transcript_error",
                message=f"Firestore query error for production {production_id}: {type(exc).__name__}",
            )
            raise


_global_transcript_repo: TranscriptRepository | None = None


def get_default_transcript_repository() -> TranscriptRepository:
    """Factory for default TranscriptRepository instance."""
    global _global_transcript_repo
    if _global_transcript_repo is None:
        settings = get_settings()
        if settings.environment in ("production", "staging") or os.getenv("USE_FIRESTORE") == "true":
            _global_transcript_repo = FirestoreTranscriptRepository(
                project_id=settings.gcp_project_id
            )
        else:
            _global_transcript_repo = InMemoryTranscriptRepository()
    return _global_transcript_repo


def get_transcript_repository() -> TranscriptRepository:
    """FastAPI dependency provider for TranscriptRepository."""
    return get_default_transcript_repository()


def set_transcript_repository(repo: TranscriptRepository | None) -> None:
    """Override the global transcript repository instance (useful for test isolation)."""
    global _global_transcript_repo
    _global_transcript_repo = repo
