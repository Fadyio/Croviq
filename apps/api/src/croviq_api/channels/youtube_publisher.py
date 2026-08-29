"""YouTube Data API v3 client for deterministic video publishing and thumbnail assignment.

Supports least-privilege resumable video upload via youtube.upload, thumbnail setting,
and automated YouTube API compliance audit restriction detection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any
import uuid

import httpx
from pydantic import BaseModel, ConfigDict, Field

from croviq_api.config import get_settings

logger = logging.getLogger(__name__)

YOUTUBE_RESUMABLE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
YOUTUBE_THUMBNAIL_SET_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

MAX_TITLE_CHARS = 100
MAX_DESCRIPTION_BYTES = 5000
MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024  # 2MB YouTube API limit
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunk size for resumable upload


class YouTubePublishError(Exception):
    """Base exception for YouTube publishing errors."""
    pass


class YouTubeAuthExpiredError(YouTubePublishError):
    """Raised when OAuth token is expired or revoked (HTTP 401)."""
    pass


class YouTubePermissionError(YouTubePublishError):
    """Raised when OAuth token lacks youtube.upload scope (HTTP 403 insufficientPermissions)."""
    pass


class YouTubeQuotaExceededError(YouTubePublishError):
    """Raised when YouTube API quota is exceeded (HTTP 403 quotaExceeded)."""
    pass


class YouTubeThumbnailError(YouTubePublishError):
    """Raised when thumbnail upload fails or violates constraints."""
    pass


class YouTubeVideoMetadata(BaseModel):
    """Metadata payload submitted during videos.insert."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=5000)
    tags: list[str] = Field(default_factory=list)
    category_id: str = Field(default="28")
    privacy_status: str = Field(default="private")
    made_for_kids: bool = False
    contains_synthetic_media: bool = False


class YouTubeVideoResource(BaseModel):
    """Standardized representation of an uploaded YouTube video."""

    model_config = ConfigDict(extra="forbid")

    video_id: str
    title: str
    description: str
    privacy_status: str
    channel_id: str
    watch_url: str
    audit_restriction_detected: bool = False


def validate_youtube_metadata(metadata: YouTubeVideoMetadata) -> None:
    """Validate title character length and description byte length before making remote API calls."""
    if len(metadata.title) > MAX_TITLE_CHARS:
        raise ValueError(
            f"YouTube title exceeds maximum allowed length of {MAX_TITLE_CHARS} characters (got {len(metadata.title)})."
        )
    description_bytes = len(metadata.description.encode("utf-8"))
    if description_bytes > MAX_DESCRIPTION_BYTES:
        raise ValueError(
            f"YouTube description exceeds maximum allowed length of {MAX_DESCRIPTION_BYTES} bytes (got {description_bytes} bytes)."
        )


class YouTubePublishClient(ABC):
    """Abstract interface for YouTube Data API v3 video publication."""

    @abstractmethod
    async def upload_video(
        self,
        access_token: str,
        media_path: Path | str,
        metadata: YouTubeVideoMetadata,
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> YouTubeVideoResource:
        """Perform authenticated resumable upload of master video to YouTube."""
        pass

    @abstractmethod
    async def set_thumbnail(
        self,
        access_token: str,
        video_id: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """Upload custom thumbnail for a YouTube video via thumbnails.set."""
        pass

    @abstractmethod
    async def get_video_status(
        self,
        access_token: str,
        video_id: str,
    ) -> dict[str, Any]:
        """Retrieve video resource status from YouTube Data API."""
        pass


class GoogleYouTubePublishClient(YouTubePublishClient):
    """Production implementation of YouTubePublishClient using Google YouTube Data API v3."""

    def __init__(self, timeout_seconds: float = 60.0) -> None:
        self.timeout_seconds = timeout_seconds

    def _translate_error(self, status_code: int, response_text: str) -> Exception:
        try:
            data = json.loads(response_text)
            error_data = data.get("error", {})
            errors = error_data.get("errors", [])
            reasons = [e.get("reason", "") for e in errors]
        except Exception:
            reasons = []

        if status_code == 401:
            return YouTubeAuthExpiredError("Reconnect YouTube: authorization has expired or was revoked.")
        if status_code == 403:
            if "quotaExceeded" in reasons:
                return YouTubeQuotaExceededError("YouTube upload quota reached. Please retry tomorrow.")
            if "insufficientPermissions" in reasons or "forbidden" in reasons:
                return YouTubePermissionError("Publishing permission not granted. Please grant upload access.")
            return YouTubePermissionError(f"YouTube publishing permission error: {response_text}")
        if status_code == 429:
            return YouTubePublishError("YouTube rate limit reached. Please wait a moment and retry.")
        if 500 <= status_code < 600:
            return YouTubePublishError("YouTube is temporarily unavailable. Please retry shortly.")
        return YouTubePublishError(f"YouTube API upload error (HTTP {status_code}): {response_text}")

    async def upload_video(
        self,
        access_token: str,
        media_path: Path | str,
        metadata: YouTubeVideoMetadata,
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> YouTubeVideoResource:
        validate_youtube_metadata(metadata)
        path = Path(media_path)
        if not path.exists():
            raise FileNotFoundError(f"Source video media not found at '{path}'")

        file_size = path.stat().st_size
        if file_size <= 0:
            raise ValueError(f"Video media file at '{path}' is empty.")

        # 1. Initiate Resumable Upload Session
        init_body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": metadata.privacy_status,
                "selfDeclaredMadeForKids": metadata.made_for_kids,
                "containsSyntheticMedia": metadata.contains_synthetic_media,
            },
        }

        init_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(file_size),
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            init_resp = await client.post(
                YOUTUBE_RESUMABLE_UPLOAD_URL,
                headers=init_headers,
                json=init_body,
            )

            if init_resp.status_code != 200:
                raise self._translate_error(init_resp.status_code, init_resp.text)

            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                raise YouTubePublishError("YouTube API did not return resumable upload session Location URL.")

            # 2. Upload Video Bytes in chunks or full stream
            bytes_uploaded = 0
            with open(path, "rb") as f:
                while bytes_uploaded < file_size:
                    chunk = f.read(DEFAULT_CHUNK_SIZE)
                    if not chunk:
                        break
                    chunk_len = len(chunk)
                    start_byte = bytes_uploaded
                    end_byte = bytes_uploaded + chunk_len - 1

                    chunk_headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "video/mp4",
                        "Content-Length": str(chunk_len),
                        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                    }

                    chunk_resp = await client.put(
                        upload_url,
                        headers=chunk_headers,
                        content=chunk,
                    )

                    if chunk_resp.status_code in (200, 201):
                        # Upload complete! Parse video resource
                        video_data = chunk_resp.json()
                        video_id = video_data.get("id", "")
                        snippet = video_data.get("snippet", {})
                        status_obj = video_data.get("status", {})
                        actual_privacy = status_obj.get("privacyStatus", metadata.privacy_status)

                        audit_restricted = (
                            metadata.privacy_status in ("public", "unlisted")
                            and actual_privacy == "private"
                        )

                        if progress_callback:
                            await progress_callback(file_size, file_size)

                        return YouTubeVideoResource(
                            video_id=video_id,
                            title=snippet.get("title", metadata.title),
                            description=snippet.get("description", metadata.description),
                            privacy_status=actual_privacy,
                            channel_id=snippet.get("channelId", ""),
                            watch_url=f"https://youtu.be/{video_id}",
                            audit_restriction_detected=audit_restricted,
                        )
                    elif chunk_resp.status_code == 308:
                        # Resume incomplete, continue next chunk
                        bytes_uploaded += chunk_len
                        if progress_callback:
                            await progress_callback(bytes_uploaded, file_size)
                    else:
                        raise self._translate_error(chunk_resp.status_code, chunk_resp.text)

        raise YouTubePublishError("YouTube upload stream terminated before receiving final confirmation.")

    async def set_thumbnail(
        self,
        access_token: str,
        video_id: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        if len(image_bytes) > MAX_THUMBNAIL_BYTES:
            raise YouTubeThumbnailError(
                f"Thumbnail size ({len(image_bytes)} bytes) exceeds YouTube limit of {MAX_THUMBNAIL_BYTES} bytes (2MB)."
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": content_type,
        }
        url = f"{YOUTUBE_THUMBNAIL_SET_URL}?videoId={video_id}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, headers=headers, content=image_bytes)
            if resp.status_code not in (200, 201):
                raise self._translate_error(resp.status_code, resp.text)
            return resp.json()

    async def get_video_status(
        self,
        access_token: str,
        video_id: str,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"part": "snippet,status,contentDetails", "id": video_id}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(YOUTUBE_VIDEOS_URL, headers=headers, params=params)
            if resp.status_code != 200:
                raise self._translate_error(resp.status_code, resp.text)
            return resp.json()


class FakeYouTubePublishClient(YouTubePublishClient):
    """In-memory simulated YouTube publisher client for unit testing and local development."""

    def __init__(
        self,
        simulate_audit_restriction: bool = False,
        simulate_error: str | None = None,
    ) -> None:
        self.simulate_audit_restriction = simulate_audit_restriction
        self.simulate_error = simulate_error
        self.uploaded_videos: list[dict[str, Any]] = []
        self.thumbnails_set: dict[str, bytes] = {}

    async def upload_video(
        self,
        access_token: str,
        media_path: Path | str,
        metadata: YouTubeVideoMetadata,
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> YouTubeVideoResource:
        validate_youtube_metadata(metadata)

        if self.simulate_error == "401":
            raise YouTubeAuthExpiredError("Reconnect YouTube: authorization has expired or was revoked.")
        if self.simulate_error == "403_quota":
            raise YouTubeQuotaExceededError("YouTube upload quota reached. Please retry tomorrow.")
        if self.simulate_error == "403_scope":
            raise YouTubePermissionError("Publishing permission not granted. Please grant upload access.")
        if self.simulate_error == "500":
            raise YouTubePublishError("YouTube is temporarily unavailable. Please retry shortly.")

        path = Path(media_path)
        file_size = path.stat().st_size if path.exists() else 1024 * 1024

        # Simulate upload progress ticks
        if progress_callback:
            await progress_callback(int(file_size * 0.3), file_size)
            await progress_callback(int(file_size * 0.7), file_size)
            await progress_callback(file_size, file_size)

        video_id = f"yt_vid_{uuid.uuid4().hex[:11]}"
        actual_privacy = metadata.privacy_status
        audit_restricted = False

        if self.simulate_audit_restriction and metadata.privacy_status in ("public", "unlisted"):
            actual_privacy = "private"
            audit_restricted = True

        record = {
            "video_id": video_id,
            "title": metadata.title,
            "description": metadata.description,
            "privacy_status": actual_privacy,
            "channel_id": "UC_connected_creator",
            "audit_restriction_detected": audit_restricted,
        }
        self.uploaded_videos.append(record)

        return YouTubeVideoResource(
            video_id=video_id,
            title=metadata.title,
            description=metadata.description,
            privacy_status=actual_privacy,
            channel_id="UC_connected_creator",
            watch_url=f"https://youtu.be/{video_id}",
            audit_restriction_detected=audit_restricted,
        )

    async def set_thumbnail(
        self,
        access_token: str,
        video_id: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        if len(image_bytes) > MAX_THUMBNAIL_BYTES:
            raise YouTubeThumbnailError(
                f"Thumbnail size ({len(image_bytes)} bytes) exceeds YouTube limit of {MAX_THUMBNAIL_BYTES} bytes (2MB)."
            )

        if self.simulate_error == "thumbnail_fail":
            raise YouTubeThumbnailError("Failed to upload thumbnail to YouTube.")

        self.thumbnails_set[video_id] = image_bytes
        return {"success": True, "videoId": video_id}

    async def get_video_status(
        self,
        access_token: str,
        video_id: str,
    ) -> dict[str, Any]:
        for vid in self.uploaded_videos:
            if vid["video_id"] == video_id:
                return {
                    "items": [
                        {
                            "id": video_id,
                            "snippet": {
                                "title": vid["title"],
                                "channelId": vid["channel_id"],
                            },
                            "status": {
                                "privacyStatus": vid["privacy_status"],
                                "uploadStatus": "uploaded",
                            },
                        }
                    ]
                }
        return {"items": []}


_global_youtube_publish_client: YouTubePublishClient | None = None


def get_youtube_publish_client() -> YouTubePublishClient:
    global _global_youtube_publish_client
    if _global_youtube_publish_client is not None:
        if get_settings().is_production and isinstance(_global_youtube_publish_client, FakeYouTubePublishClient):
            raise RuntimeError("Production mode strictly forbids FakeYouTubePublishClient overrides.")
        return _global_youtube_publish_client

    if _global_youtube_publish_client is None:
        if get_settings().is_production:
            _global_youtube_publish_client = GoogleYouTubePublishClient()
        else:
            _global_youtube_publish_client = FakeYouTubePublishClient()
    return _global_youtube_publish_client

def set_youtube_publish_client(client: YouTubePublishClient | None) -> None:
    global _global_youtube_publish_client
    _global_youtube_publish_client = client
