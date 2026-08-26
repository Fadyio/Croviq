"""In-memory fake implementation of MediaStorage for unit testing and local development."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from croviq_api.media.storage import (
    MediaStorage,
    MediaStorageError,
    ObjectMetadata,
    SignedReadTarget,
    SignedUploadTarget,
)


class FakeMediaStorage(MediaStorage):
    """In-memory simulated media storage provider."""

    def __init__(self, base_url: str = "http://localhost:8080/fake-media-storage") -> None:
        self.base_url = base_url
        self._objects: dict[str, ObjectMetadata] = {}
        self._contents: dict[str, bytes] = {}

    def simulate_uploaded_object(
        self,
        bucket: str,
        object_name: str,
        size_bytes: int,
        content_type: str,
        content: bytes | None = None,
    ) -> None:
        """Test helper to simulate an object successfully uploaded directly to storage."""
        key = f"{bucket}/{object_name}"
        self._objects[key] = ObjectMetadata(
            bucket=bucket,
            object_name=object_name,
            exists=True,
            size_bytes=size_bytes,
            content_type=content_type,
            updated_at=datetime.now(timezone.utc),
        )
        self._contents[key] = content if content is not None else b"fake private source media"

    async def generate_signed_upload_target(
        self,
        bucket: str,
        object_name: str,
        content_type: str,
        expiry_seconds: int = 1800,
    ) -> SignedUploadTarget:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)
        upload_url = f"{self.base_url}/{bucket}/{object_name}?token=mock_v4_signature"
        return SignedUploadTarget(
            upload_url=upload_url,
            method="PUT",
            required_headers={"Content-Type": content_type},
            expires_at=expires_at,
        )

    async def generate_signed_read_target(
        self,
        bucket: str,
        object_name: str,
        expiry_seconds: int = 3600,
    ) -> SignedReadTarget:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)
        read_url = f"{self.base_url}/{bucket}/{object_name}?token=mock_v4_signed_read"
        return SignedReadTarget(
            read_url=read_url,
            expires_at=expires_at,
        )

    async def get_object_metadata(
        self,
        bucket: str,
        object_name: str,
    ) -> ObjectMetadata:
        key = f"{bucket}/{object_name}"
        if key in self._objects:
            return self._objects[key]
        return ObjectMetadata(
            bucket=bucket,
            object_name=object_name,
            exists=False,
            size_bytes=0,
            content_type="",
            updated_at=None,
        )

    async def download_object_to_path(
        self,
        bucket: str,
        object_name: str,
        target_path: Path,
    ) -> Path:
        key = f"{bucket}/{object_name}"
        content = self._contents.get(key)
        if content is None:
            metadata = self._objects.get(key)
            if metadata is None:
                content = b"fake private source media"
            else:
                content = b"fake private source media"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return target_path

    def clear(self) -> None:
        """Clear all stored in-memory mock objects."""
        self._objects.clear()
        self._contents.clear()
