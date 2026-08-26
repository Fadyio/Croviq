"""Google Cloud Storage implementation of MediaStorage using keyless Cloud Run identity."""

import asyncio
from datetime import datetime, timedelta, timezone
from google.cloud import storage
import google.auth
from google.auth.transport import requests as auth_requests

from croviq_api.media.storage import MediaStorage, ObjectMetadata, SignedUploadTarget


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

        credentials = client.credentials
        sa_email = self.service_account_email

        # If credentials need refreshing, refresh them
        if hasattr(credentials, "refresh") and hasattr(credentials, "valid") and not credentials.valid:
            try:
                request = auth_requests.Request()
                credentials.refresh(request)
            except Exception:
                pass

        if not sa_email and hasattr(credentials, "service_account_email") and credentials.service_account_email != "default":
            sa_email = credentials.service_account_email

        kwargs = {
            "version": "v4",
            "expiration": timedelta(seconds=expiry_seconds),
            "method": "PUT",
            "content_type": content_type,
        }

        if sa_email:
            kwargs["service_account_email"] = sa_email
            if hasattr(credentials, "token") and credentials.token:
                kwargs["access_token"] = credentials.token

        signed_url = blob.generate_signed_url(**kwargs)

        return SignedUploadTarget(
            upload_url=signed_url,
            method="PUT",
            required_headers={"Content-Type": content_type},
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
