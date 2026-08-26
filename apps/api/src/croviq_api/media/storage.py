"""Abstract interface and contracts for media storage operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SignedUploadTarget:
    """Represents a pre-signed direct upload target."""

    upload_url: str
    method: str
    required_headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class ObjectMetadata:
    """Represents inspected metadata of an object in storage."""

    bucket: str
    object_name: str
    exists: bool
    size_bytes: int = 0
    content_type: str = ""
    updated_at: datetime | None = None


class MediaStorage(ABC):
    """Abstract interface for media storage and V4 signed URL operations."""

    @abstractmethod
    async def generate_signed_upload_target(
        self,
        bucket: str,
        object_name: str,
        content_type: str,
        expiry_seconds: int = 1800,
    ) -> SignedUploadTarget:
        """Generate a short-lived V4 signed upload target for direct browser upload."""
        pass

    @abstractmethod
    async def get_object_metadata(
        self,
        bucket: str,
        object_name: str,
    ) -> ObjectMetadata:
        """Inspect and return metadata for an object in storage."""
        pass
