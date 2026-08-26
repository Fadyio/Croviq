"""Unit tests for MediaStorage implementations (FakeMediaStorage and GoogleMediaStorage)."""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from croviq_api.media.fake import FakeMediaStorage
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.media.storage import MediaStorageError


@pytest.mark.asyncio
async def test_fake_media_storage_upload_and_download(tmp_path: Path):
    storage = FakeMediaStorage()

    test_file = tmp_path / "test_render.mp4"
    test_content = b"fake render mp4 content for testing"
    test_file.write_bytes(test_content)

    meta = await storage.upload_object_from_path(
        bucket="croviq-506602-croviq-media-raw",
        object_name="workspaces/ws_1/productions/prod_1/renders/edl_1/preview.mp4",
        source_path=test_file,
        content_type="video/mp4",
    )

    assert meta.exists is True
    assert meta.bucket == "croviq-506602-croviq-media-raw"
    assert meta.object_name == "workspaces/ws_1/productions/prod_1/renders/edl_1/preview.mp4"
    assert meta.size_bytes == len(test_content)
    assert meta.content_type == "video/mp4"

    # Inspect metadata
    inspected = await storage.get_object_metadata(
        bucket="croviq-506602-croviq-media-raw",
        object_name="workspaces/ws_1/productions/prod_1/renders/edl_1/preview.mp4",
    )
    assert inspected.exists is True
    assert inspected.size_bytes == len(test_content)

    # Download
    download_target = tmp_path / "downloaded.mp4"
    await storage.download_object_to_path(
        bucket="croviq-506602-croviq-media-raw",
        object_name="workspaces/ws_1/productions/prod_1/renders/edl_1/preview.mp4",
        target_path=download_target,
    )
    assert download_target.exists()
    assert download_target.read_bytes() == test_content


@pytest.mark.asyncio
async def test_fake_media_storage_upload_missing_file(tmp_path: Path):
    storage = FakeMediaStorage()
    non_existent = tmp_path / "non_existent.mp4"

    with pytest.raises(MediaStorageError, match="Source file not found"):
        await storage.upload_object_from_path(
            bucket="croviq-506602-croviq-media-raw",
            object_name="test.mp4",
            source_path=non_existent,
        )


@pytest.mark.asyncio
async def test_google_media_storage_upload_missing_file_raises(tmp_path: Path):
    storage = GoogleMediaStorage(project_id="croviq-506602")
    non_existent = tmp_path / "missing.mp4"

    with pytest.raises(MediaStorageError, match="Source file not found"):
        await storage.upload_object_from_path(
            bucket="croviq-506602-croviq-media-raw",
            object_name="test.mp4",
            source_path=non_existent,
        )
