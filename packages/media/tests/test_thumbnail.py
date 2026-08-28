"""Unit tests for ThumbnailExtractor service and deterministic frame extraction."""

from pathlib import Path
import pytest
import tempfile

from croviq_media.thumbnail import (
    FakeThumbnailExtractor,
    FFmpegThumbnailExtractor,
    ThumbnailExtractionError,
    ThumbnailExtractionResult,
    ThumbnailExtractor,
)


def test_fake_thumbnail_extractor_basic() -> None:
    extractor = FakeThumbnailExtractor(default_width=1920, default_height=1080, default_size_bytes=500000)
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as out_tmp:
        out_path = Path(out_tmp.name)

    result = extractor.extract_thumbnail_frame(
        source_media_path="dummy_master.mp4",
        frame_ms=15000,
        output_path=out_path,
    )

    assert result.output_path == out_path
    assert result.width == 1920
    assert result.height == 1080
    assert result.size_bytes == 500000
    assert result.size_bytes <= 2 * 1024 * 1024
    assert result.content_type == "image/jpeg"
    assert out_path.exists()
    assert out_path.stat().st_size > 0

    out_path.unlink(missing_ok=True)


def test_thumbnail_extractor_rejects_missing_source() -> None:
    extractor = FFmpegThumbnailExtractor()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as out_tmp:
        out_path = Path(out_tmp.name)

    with pytest.raises(ThumbnailExtractionError, match="Source media file not found"):
        extractor.extract_thumbnail_frame(
            source_media_path="/non/existent/path/video.mp4",
            frame_ms=1000,
            output_path=out_path,
        )

    out_path.unlink(missing_ok=True)
