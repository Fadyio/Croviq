"""Google Cloud Storage implementation of MediaStorage using keyless Cloud Run identity."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from google.cloud import storage
import google.auth
from google.auth.transport import requests as auth_requests

from croviq_api.media.storage import (
    MediaStorage,
    MediaStorageError,
    ObjectMetadata,
    SignedReadTarget,
    SignedUploadTarget,
)


class GoogleMediaStorage(MediaStorage):
    """Production Google Cloud Storage media provider utilizing IAM signBlob V4 signing."""

    def __init__(
        self,
        project_id: str | None = None,
        service_account_email: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.service_account_email = service_account_email
        self._client: storage.Client | None = None

    def _get_client(self) -> storage.Client:
        if self._client is None:
            self._client = storage.Client(project=self.project_id)
        return self._client

    async def generate_signed_upload_target(
        self,
        bucket: str,
        object_name: str,
        content_type: str,
        expiry_seconds: int = 1800,
    ) -> SignedUploadTarget:
        """Generate a short-lived V4 signed PUT URL via Cloud Run identity / signBlob."""
        # Run blocking GCS client call in threadpool
        return await asyncio.to_thread(
            self._generate_signed_upload_target_sync,
            bucket,
            object_name,
            content_type,
            expiry_seconds,
        )

    def _generate_signed_upload_target_sync(
        self,
        bucket: str,
        object_name: str,
        content_type: str,
        expiry_seconds: int,
    ) -> SignedUploadTarget:
        client = self._get_client()
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(object_name)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)

        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            if hasattr(credentials, "refresh") and hasattr(credentials, "valid") and not credentials.valid:
                request = auth_requests.Request()
                credentials.refresh(request)
        except Exception:
            credentials = getattr(client, "_credentials", None)

        sa_email = self.service_account_email
        if not sa_email and credentials and hasattr(credentials, "service_account_email") and credentials.service_account_email != "default":
            sa_email = credentials.service_account_email
        kwargs: dict = {
            "version": "v4",
            "expiration": timedelta(seconds=expiry_seconds),
            "method": "PUT",
            "content_type": content_type,
        }

        if sa_email:
            kwargs["service_account_email"] = sa_email
        if credentials:
            kwargs["credentials"] = credentials
            if hasattr(credentials, "token") and credentials.token:
                kwargs["access_token"] = credentials.token

        signed_url = blob.generate_signed_url(**kwargs)

        return SignedUploadTarget(
            upload_url=signed_url,
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
        """Generate a short-lived V4 signed GET URL for browser playback via Cloud Run identity."""
        return await asyncio.to_thread(
            self._generate_signed_read_target_sync,
            bucket,
            object_name,
            expiry_seconds,
        )

    def _generate_signed_read_target_sync(
        self,
        bucket: str,
        object_name: str,
        expiry_seconds: int,
    ) -> SignedReadTarget:
        client = self._get_client()
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(object_name)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)

        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            if hasattr(credentials, "refresh") and hasattr(credentials, "valid") and not credentials.valid:
                request = auth_requests.Request()
                credentials.refresh(request)
        except Exception:
            credentials = getattr(client, "_credentials", None)

        sa_email = self.service_account_email
        if not sa_email and credentials and hasattr(credentials, "service_account_email") and credentials.service_account_email != "default":
            sa_email = credentials.service_account_email

        kwargs: dict = {
            "version": "v4",
            "expiration": timedelta(seconds=expiry_seconds),
            "method": "GET",
        }

        if sa_email:
            kwargs["service_account_email"] = sa_email
        if credentials:
            kwargs["credentials"] = credentials
            if hasattr(credentials, "token") and credentials.token:
                kwargs["access_token"] = credentials.token

        signed_url = blob.generate_signed_url(**kwargs)

        return SignedReadTarget(
            read_url=signed_url,
            expires_at=expires_at,
        )

    async def get_object_metadata(
        self,
        bucket: str,
        object_name: str,
    ) -> ObjectMetadata:
        """Inspect and return metadata for an object in Google Cloud Storage."""
        return await asyncio.to_thread(
            self._get_object_metadata_sync,
            bucket,
            object_name,
        )

    def _get_object_metadata_sync(
        self,
        bucket: str,
        object_name: str,
    ) -> ObjectMetadata:
        client = self._get_client()
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.get_blob(object_name)

        if blob is None:
            return ObjectMetadata(
                bucket=bucket,
                object_name=object_name,
                exists=False,
                size_bytes=0,
                content_type="",
                updated_at=None,
            )

        return ObjectMetadata(
            bucket=bucket,
            object_name=object_name,
            exists=True,
            size_bytes=blob.size or 0,
            content_type=blob.content_type or "",
            updated_at=blob.updated,
        )

    async def download_object_to_path(
        self,
        bucket: str,
        object_name: str,
        target_path: Path,
    ) -> Path:
        """Download a private GCS object to a local temporary file using Cloud Run identity."""
        return await asyncio.to_thread(
            self._download_object_to_path_sync,
            bucket,
            object_name,
            target_path,
        )

    def _download_object_to_path_sync(
        self,
        bucket: str,
        object_name: str,
        target_path: Path,
    ) -> Path:
        client = self._get_client()
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(object_name)
        if not blob.exists():
            raise MediaStorageError(f"storage object not found: gs://{bucket}/{object_name}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(target_path))
        return target_path
