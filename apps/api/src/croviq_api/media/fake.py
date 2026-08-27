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
        expiry_seconds: int = 1800,
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

    async def upload_object_from_path(
        self,
        bucket: str,
        object_name: str,
        source_path: Path,
        content_type: str = "video/mp4",
    ) -> ObjectMetadata:
        if not source_path.exists() or not source_path.is_file():
            raise MediaStorageError(f"Source file not found for upload: {source_path}")
        content = source_path.read_bytes()
        key = f"{bucket}/{object_name}"
        metadata = ObjectMetadata(
            bucket=bucket,
            object_name=object_name,
            exists=True,
            size_bytes=len(content),
            content_type=content_type,
            updated_at=datetime.now(timezone.utc),
        )
        self._objects[key] = metadata
        self._contents[key] = content
        return metadata

    async def delete_object(
        self,
        bucket: str,
        object_name: str,
    ) -> bool:
        key = f"{bucket}/{object_name}"
        existed = key in self._objects or key in self._contents
        self._objects.pop(key, None)
        self._contents.pop(key, None)
        return existed

    async def delete_prefix(
        self,
        bucket: str,
        prefix: str,
    ) -> int:
        prefix_key = f"{bucket}/{prefix}"
        matching_keys = [k for k in self._objects if k.startswith(prefix_key)]
        for k in matching_keys:
            self._objects.pop(k, None)
            self._contents.pop(k, None)
        # Also check any contents that might have been populated directly
        matching_contents = [k for k in self._contents if k.startswith(prefix_key) and k not in matching_keys]
        for k in matching_contents:
            self._contents.pop(k, None)
        return len(matching_keys) + len(matching_contents)

    def clear(self) -> None:
        """Clear all stored in-memory mock objects."""
        self._objects.clear()
        self._contents.clear()
