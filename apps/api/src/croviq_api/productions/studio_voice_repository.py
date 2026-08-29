"""Repository for Studio Voice results and generated narration segments."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import os
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.narration import StudioVoiceResult
from croviq_observability import log_firestore_event

logger = logging.getLogger(__name__)


class StudioVoiceRepository(ABC):
    """Abstract interface for persisting StudioVoiceResult and NarrationSegments."""

    @abstractmethod
    async def get_by_production_id(self, production_id: str) -> StudioVoiceResult | None:
        pass

    @abstractmethod
    async def save(self, result: StudioVoiceResult) -> StudioVoiceResult:
        pass

    @abstractmethod
    async def delete_by_production_id(self, production_id: str) -> bool:
        pass


class InMemoryStudioVoiceRepository(StudioVoiceRepository):
    """In-memory repository for unit tests and local non-cloud execution."""

    def __init__(self) -> None:
        self._results: dict[str, StudioVoiceResult] = {}

    async def get_by_production_id(self, production_id: str) -> StudioVoiceResult | None:
        return self._results.get(production_id)

    async def save(self, result: StudioVoiceResult) -> StudioVoiceResult:
        self._results[result.production_id] = result
        return result

    async def delete_by_production_id(self, production_id: str) -> bool:
        return self._results.pop(production_id, None) is not None


class FirestoreStudioVoiceRepository(StudioVoiceRepository):
    """Production Firestore repository for Studio Voice persistence."""

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

    async def get_by_production_id(self, production_id: str) -> StudioVoiceResult | None:
        db = self._get_db()
        doc_ref = db.collection("productions").document(production_id).collection("studio_voice").document("result")
        doc = doc_ref.get()
        if doc.exists:
            return StudioVoiceResult.model_validate(doc.to_dict())
        return None

    async def save(self, result: StudioVoiceResult) -> StudioVoiceResult:
        db = self._get_db()
        doc_ref = db.collection("productions").document(result.production_id).collection("studio_voice").document("result")
        doc_ref.set(result.model_dump(mode="json"))
        return result

    async def delete_by_production_id(self, production_id: str) -> bool:
        db = self._get_db()
        doc_ref = db.collection("productions").document(production_id).collection("studio_voice").document("result")
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.delete()
            return True
        return False


_global_studio_voice_repo: StudioVoiceRepository | None = None


def get_default_studio_voice_repository() -> StudioVoiceRepository:
    global _global_studio_voice_repo
    if _global_studio_voice_repo is None:
        settings = get_settings()
        if settings.is_production:
            if not settings.gcp_project_id and not os.getenv("FIRESTORE_EMULATOR_HOST"):
                raise RuntimeError(
                    "Production mode requires FirestoreStudioVoiceRepository with valid gcp_project_id."
                )
            _global_studio_voice_repo = FirestoreStudioVoiceRepository(project_id=settings.gcp_project_id)
        elif settings.environment == "staging" or os.getenv("USE_FIRESTORE") == "true":
            _global_studio_voice_repo = FirestoreStudioVoiceRepository(project_id=settings.gcp_project_id)
        else:
            _global_studio_voice_repo = InMemoryStudioVoiceRepository()
    return _global_studio_voice_repo


def get_studio_voice_repository() -> StudioVoiceRepository:
    return get_default_studio_voice_repository()


def set_studio_voice_repository(repo: StudioVoiceRepository | None) -> None:
    global _global_studio_voice_repo
    _global_studio_voice_repo = repo
