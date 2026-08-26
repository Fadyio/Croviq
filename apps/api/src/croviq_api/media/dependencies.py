"""FastAPI dependency injection for MediaStorage provider."""

from functools import lru_cache
from croviq_api.config import get_settings
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.media.storage import MediaStorage
from croviq_media.inspector import (
    FakeMediaInspector,
    FFprobeMediaInspector,
    MediaInspector,
)
from croviq_media.transcript import (
    FakeTranscriptionService,
    GoogleSpeechTranscriptionService,
    TranscriptionService,
)
_fake_media_storage_instance: FakeMediaStorage | None = None


def get_fake_media_storage() -> FakeMediaStorage:
    """Return singleton fake media storage instance for testing and local development."""
    global _fake_media_storage_instance
    if _fake_media_storage_instance is None:
        _fake_media_storage_instance = FakeMediaStorage()
    return _fake_media_storage_instance


@lru_cache(maxsize=1)
def get_google_media_storage() -> GoogleMediaStorage:
    """Return cached production Google Cloud Storage provider instance."""
    settings = get_settings()
    return GoogleMediaStorage(
        project_id=settings.gcp_project_id,
        service_account_email=settings.api_runtime_service_account,
    )


def get_media_storage() -> MediaStorage:
    """Resolve active MediaStorage provider based on environment configuration."""
    settings = get_settings()
    if settings.media_storage_provider == "google":
        return get_google_media_storage()
    return get_fake_media_storage()


_custom_transcription_service: TranscriptionService | None = None
_custom_media_inspector: MediaInspector | None = None


def get_transcription_service() -> TranscriptionService:
    """Resolve active TranscriptionService provider based on environment configuration."""
    global _custom_transcription_service
    if _custom_transcription_service is not None:
        return _custom_transcription_service

    settings = get_settings()
    if settings.speech_service_provider == "google" and settings.gcp_project_id:
        return GoogleSpeechTranscriptionService(
            project_id=settings.gcp_project_id,
            location=settings.speech_location,
            recognizer_id=settings.speech_recognizer_id,
        )
    return FakeTranscriptionService()


def set_transcription_service(service: TranscriptionService | None) -> None:
    """Override transcription service instance for tests."""
    global _custom_transcription_service
    _custom_transcription_service = service


def get_media_inspector() -> MediaInspector:
    """Resolve active MediaInspector provider."""
    global _custom_media_inspector
    if _custom_media_inspector is not None:
        return _custom_media_inspector
    return FFprobeMediaInspector()


def set_media_inspector(inspector: MediaInspector | None) -> None:
    """Override media inspector instance for tests."""
    global _custom_media_inspector
    _custom_media_inspector = inspector
