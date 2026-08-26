"""Media storage and signed URL management module for Croviq."""

from croviq_api.media.dependencies import (
    get_fake_media_storage,
    get_google_media_storage,
    get_media_storage,
)
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.media.logging import log_media_upload_event
from croviq_api.media.storage import (
    MediaStorage,
    ObjectMetadata,
    SignedUploadTarget,
)

__all__ = [
    "FakeMediaStorage",
    "GoogleMediaStorage",
    "MediaStorage",
    "ObjectMetadata",
    "SignedUploadTarget",
    "get_fake_media_storage",
    "get_google_media_storage",
    "get_media_storage",
    "log_media_upload_event",
]
