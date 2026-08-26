import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from croviq_domain.production import (
    MAX_UPLOAD_SIZE_BYTES,
    DEFAULT_SIGNED_URL_EXPIRY_SECONDS,
    ALLOWED_MEDIA_TYPES,
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
    build_source_media_gcs_object_path,
    sanitize_filename,
    validate_media_file,
)


def test_constants():
    assert MAX_UPLOAD_SIZE_BYTES == 1_073_741_824  # 1 GB (1,073,741,824 bytes)
    assert MAX_UPLOAD_SIZE_BYTES == 1 * 1024 * 1024 * 1024
    assert DEFAULT_SIGNED_URL_EXPIRY_SECONDS == 1800  # 30 minutes
    assert "video/mp4" in ALLOWED_MEDIA_TYPES
    assert "video/quicktime" in ALLOWED_MEDIA_TYPES
    assert "video/webm" in ALLOWED_MEDIA_TYPES

def test_sanitize_filename():
    assert sanitize_filename("my_video.mp4") == "my_video.mp4"
    assert sanitize_filename("../../../etc/passwd.mp4") == "passwd.mp4"
    assert sanitize_filename("..\\..\\secret.mov") == "secret.mov"
    assert sanitize_filename("a/b/c/clip 01 (final).webm") == "clip_01_final.webm"
    assert sanitize_filename("???!!!.mp4") == "source_media.mp4"
    assert sanitize_filename("") == "source_media.bin"


def test_validate_media_file_valid():
    mime, ext = validate_media_file(
        filename="tutorial.mp4",
        content_type="video/mp4",
        size_bytes=100_000_000,
    )
    assert mime == "video/mp4"
    assert ext == ".mp4"

    mime, ext = validate_media_file(
        filename="take_01.mov",
        content_type="video/quicktime",
        size_bytes=500_000_000,
    )
    assert mime == "video/quicktime"
    assert ext == ".mov"

    mime, ext = validate_media_file(
        filename="screen.webm",
        content_type="video/webm",
        size_bytes=1_000_000,
    )
    assert mime == "video/webm"
    assert ext == ".webm"


def test_validate_media_file_invalid_type():
    with pytest.raises(ValueError, match="Unsupported content type"):
        validate_media_file(
            filename="image.png",
            content_type="image/png",
            size_bytes=1_000_000,
        )


def test_validate_media_file_mismatched_extension():
    with pytest.raises(ValueError, match="Extension .* does not match"):
        validate_media_file(
            filename="video.mp4",
            content_type="video/webm",
            size_bytes=1_000_000,
        )


def test_validate_media_file_boundary_1gb_accepted():
    mime, ext = validate_media_file(
        filename="full_limit.mp4",
        content_type="video/mp4",
        size_bytes=1_073_741_824,  # Exactly 1 GB (accepted)
    )
    assert mime == "video/mp4"
    assert ext == ".mp4"


def test_validate_media_file_boundary_over_1gb_rejected():
    with pytest.raises(ValueError, match="exceeds maximum allowed size of 1073741824 bytes \\(1 GB\\)"):
        validate_media_file(
            filename="over_limit.mp4",
            content_type="video/mp4",
            size_bytes=1_073_741_825,  # 1 GB + 1 byte (rejected)
        )


def test_validate_media_file_size_exceeded():
    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        validate_media_file(
            filename="huge.mp4",
            content_type="video/mp4",
            size_bytes=MAX_UPLOAD_SIZE_BYTES + 1,
        )


def test_validate_media_file_zero_or_negative_size():
    with pytest.raises(ValueError, match="must be greater than 0"):
        validate_media_file(
            filename="empty.mp4",
            content_type="video/mp4",
            size_bytes=0,
        )

def test_build_source_media_gcs_object_path():
    path = build_source_media_gcs_object_path(
        workspace_id="ws_123",
        production_id="prod_456",
        upload_id="upl_789",
        filename="../../test demo.mp4",
    )
    assert path == "workspaces/ws_123/productions/prod_456/source/upl_789/test_demo.mp4"


def test_source_media_model():
    now = datetime.now(timezone.utc)
    source = SourceMedia(
        upload_id="upl_123",
        original_filename="raw_interview.mp4",
        content_type="video/mp4",
        size_bytes=150_000_000,
        gcs_bucket="croviq-506602-croviq-media-raw",
        gcs_object="workspaces/ws_1/productions/p_1/source/upl_123/raw_interview.mp4",
        status=SourceMediaStatus.PENDING,
        created_at=now,
    )
    assert source.upload_id == "upl_123"
    assert source.status == SourceMediaStatus.PENDING
    assert source.uploaded_at is None

    # Update to uploaded
    uploaded_now = datetime.now(timezone.utc)
    source_uploaded = source.model_copy(
        update={"status": SourceMediaStatus.UPLOADED, "uploaded_at": uploaded_now}
    )
    assert source_uploaded.status == SourceMediaStatus.UPLOADED
    assert source_uploaded.uploaded_at == uploaded_now


def test_production_model():
    now = datetime.now(timezone.utc)
    source = SourceMedia(
        upload_id="upl_123",
        original_filename="raw_interview.mp4",
        content_type="video/mp4",
        size_bytes=150_000_000,
        gcs_bucket="croviq-506602-croviq-media-raw",
        gcs_object="workspaces/ws_1/productions/p_1/source/upl_123/raw_interview.mp4",
        status=SourceMediaStatus.PENDING,
        created_at=now,
    )
    prod = Production(
        production_id="prod_123",
        workspace_id="ws_123",
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id="user_123",
        source_media=source,
        status=ProductionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    assert prod.production_id == "prod_123"
    assert prod.status == ProductionStatus.PENDING
    assert prod.source_media.upload_id == "upl_123"


def test_production_timezone_validation():
    naive_dt = datetime(2026, 8, 26, 12, 0, 0)
    with pytest.raises(ValidationError):
        Production(
            production_id="prod_123",
            workspace_id="ws_123",
            channel_id="croviq_syn_ai_eng_01",
            owner_user_id="user_123",
            status=ProductionStatus.PENDING,
            created_at=naive_dt,
            updated_at=naive_dt,
        )
