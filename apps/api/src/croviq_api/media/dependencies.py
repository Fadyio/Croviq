"""FastAPI dependency injection for MediaStorage provider."""

from functools import lru_cache
from croviq_api.config import get_settings
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.media.storage import MediaStorage

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
