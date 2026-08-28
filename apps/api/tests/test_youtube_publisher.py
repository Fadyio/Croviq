"""Unit and integration tests for YouTube Data API v3 publisher client and privacy audit detection."""

import asyncio
from pathlib import Path
import pytest
import tempfile

from croviq_api.channels.youtube_publisher import (
    FakeYouTubePublishClient,
    GoogleYouTubePublishClient,
    YouTubeAuthExpiredError,
    YouTubePermissionError,
    YouTubePublishClient,
    YouTubePublishError,
    YouTubeQuotaExceededError,
    YouTubeThumbnailError,
    YouTubeVideoMetadata,
    YouTubeVideoResource,
    validate_youtube_metadata,
)


def test_validate_youtube_metadata_success() -> None:
    meta = YouTubeVideoMetadata(
        title="Valid Title Under 100 Chars",
        description="Valid description under 5000 bytes.\n\n0:00 Intro",
        tags=["AI", "Croviq"],
        category_id="28",
        privacy_status="private",
        made_for_kids=False,
        contains_synthetic_media=True,
    )
    validate_youtube_metadata(meta)

def test_validate_youtube_metadata_rejects_long_title() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        YouTubeVideoMetadata(
            title="X" * 101,  # 101 characters
            description="Description",
            tags=[],
            category_id="28",
            privacy_status="private",
        )

def test_validate_youtube_metadata_rejects_multibyte_description_over_5000_bytes() -> None:
    # 1500 4-byte unicode characters = 6000 bytes (under 5000 chars, but over 5000 bytes)
    multibyte_desc = "🚀" * 1500
    meta = YouTubeVideoMetadata(
        title="Valid Title",
        description=multibyte_desc,
        tags=[],
        category_id="28",
        privacy_status="private",
    )
    with pytest.raises(ValueError, match="5000 bytes"):
        validate_youtube_metadata(meta)


@pytest.mark.asyncio
async def test_fake_youtube_publisher_resumable_upload_and_progress() -> None:
    client = FakeYouTubePublishClient()
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp_path.write_bytes(b"dummy video bytes payload for upload" * 1000)

    progress_events: list[tuple[int, int]] = []

    async def on_progress(uploaded: int, total: int) -> None:
        progress_events.append((uploaded, total))

    meta = YouTubeVideoMetadata(
        title="How We Built Croviq",
        description="Full story.\n\n0:00 Intro\n1:00 Demo",
        tags=["AI", "Engineering"],
        category_id="28",
        privacy_status="private",
        made_for_kids=False,
        contains_synthetic_media=True,
    )

    resource = await client.upload_video(
        access_token="valid_access_token",
        media_path=tmp_path,
        metadata=meta,
        progress_callback=on_progress,
    )

    assert resource.video_id != ""
    assert resource.title == "How We Built Croviq"
    assert resource.privacy_status == "private"
    assert resource.audit_restriction_detected is False
    assert len(progress_events) > 0
    assert progress_events[-1][0] == progress_events[-1][1]

    # Clean up
    tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_fake_youtube_publisher_detects_privacy_audit_restriction() -> None:
    client = FakeYouTubePublishClient(simulate_audit_restriction=True)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp_path.write_bytes(b"video bytes")

    meta = YouTubeVideoMetadata(
        title="Public Release Attempt",
        description="Public description",
        tags=[],
        category_id="28",
        privacy_status="public",  # Creator requested public
    )

    resource = await client.upload_video(
        access_token="valid_access_token",
        media_path=tmp_path,
        metadata=meta,
    )

    assert resource.privacy_status == "private"  # Restricted by YouTube
    assert resource.audit_restriction_detected is True

    tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_fake_youtube_publisher_thumbnail_upload() -> None:
    client = FakeYouTubePublishClient()

    # Success with image <= 2MB
    image_bytes = b"jpeg_header_and_data" * 100
    thumb_res = await client.set_thumbnail(
        access_token="valid_access_token",
        video_id="yt_vid_123",
        image_bytes=image_bytes,
        content_type="image/jpeg",
    )
    assert thumb_res["success"] is True

    # Rejection with image > 2MB
    oversized = b"x" * (2 * 1024 * 1024 + 1)
    with pytest.raises(YouTubeThumbnailError, match="2MB"):
        await client.set_thumbnail(
            access_token="valid_access_token",
            video_id="yt_vid_123",
            image_bytes=oversized,
        )


@pytest.mark.asyncio
async def test_fake_youtube_publisher_simulates_errors() -> None:
    auth_client = FakeYouTubePublishClient(simulate_error="401")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp_path.write_bytes(b"bytes")

    meta = YouTubeVideoMetadata(title="Test", description="Desc", privacy_status="private")

    with pytest.raises(YouTubeAuthExpiredError, match="Reconnect YouTube"):
        await auth_client.upload_video(
            access_token="expired_token",
            media_path=tmp_path,
            metadata=meta,
        )

    quota_client = FakeYouTubePublishClient(simulate_error="403_quota")
    with pytest.raises(YouTubeQuotaExceededError, match="YouTube upload quota reached"):
        await quota_client.upload_video(
            access_token="token",
            media_path=tmp_path,
            metadata=meta,
        )

    perm_client = FakeYouTubePublishClient(simulate_error="403_scope")
    with pytest.raises(YouTubePermissionError, match="Publishing permission not granted"):
        await perm_client.upload_video(
            access_token="token",
            media_path=tmp_path,
            metadata=meta,
        )

    tmp_path.unlink(missing_ok=True)
