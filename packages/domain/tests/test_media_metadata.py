import pytest
from pydantic import ValidationError

from croviq_domain.media_metadata import MediaMetadata


def test_media_metadata_valid():
    meta = MediaMetadata(
        duration_ms=240000,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        rotation=0,
        size_bytes=52428800,
    )
    assert meta.duration_ms == 240000
    assert meta.width == 1920
    assert meta.height == 1080
    assert meta.frame_rate == 30.0
    assert meta.video_codec == "h264"
    assert meta.audio_codec == "aac"
    assert meta.audio_sample_rate == 48000
    assert meta.audio_channels == 2
    assert meta.rotation == 0
    assert meta.size_bytes == 52428800
    assert meta.is_audio_only is False


def test_media_metadata_audio_only():
    meta = MediaMetadata(
        duration_ms=60000,
        width=0,
        height=0,
        frame_rate=0.0,
        video_codec="none",
        audio_codec="flac",
        audio_sample_rate=16000,
        audio_channels=1,
        size_bytes=2000000,
    )
    assert meta.is_audio_only is True


def test_media_metadata_validation_errors():
    # Negative duration
    with pytest.raises(ValidationError):
        MediaMetadata(
            duration_ms=-10,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            size_bytes=1000,
        )

    # Invalid rotation
    with pytest.raises(ValidationError):
        MediaMetadata(
            duration_ms=1000,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            rotation=45,
            size_bytes=1000,
        )

    # Zero or negative size_bytes
    with pytest.raises(ValidationError):
        MediaMetadata(
            duration_ms=1000,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            size_bytes=0,
        )
