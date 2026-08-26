from pathlib import Path
import pytest
import subprocess

from croviq_domain.media_metadata import MediaMetadata
from croviq_media.inspector import (
    FakeMediaInspector,
    FFprobeMediaInspector,
    MediaInspectionError,
    MediaInspector,
)


@pytest.fixture
def sample_video_path(tmp_path: Path) -> Path:
    """Generate a minimal 1-second synthetic MP4 video file using ffmpeg for testing."""
    video_file = tmp_path / "test_video.mp4"
    # Generate 1-second synthetic test video: 320x240, 30fps, with sine wave 44100Hz audio
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=size=320x240:rate=30:duration=1",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=1:sample_rate=44100",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-ac", "1",
        str(video_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        pytest.skip(f"ffmpeg not available or failed: {res.stderr}")
    return video_file


@pytest.fixture
def sample_audio_path(tmp_path: Path) -> Path:
    """Generate a minimal 1-second synthetic WAV audio file using ffmpeg."""
    audio_file = tmp_path / "test_audio.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=1:sample_rate=16000",
        "-c:a", "pcm_s16le",
        "-ac", "1",
        str(audio_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        pytest.skip(f"ffmpeg not available or failed: {res.stderr}")
    return audio_file


def test_fake_media_inspector():
    fake = FakeMediaInspector()
    fake.set_metadata(
        "mock_video.mp4",
        MediaMetadata(
            duration_ms=5000,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            size_bytes=1000000,
        ),
    )
    meta = fake.inspect_media("mock_video.mp4")
    assert meta.duration_ms == 5000
    assert meta.width == 1920
    assert meta.frame_rate == 30.0


def test_fake_media_inspector_default():
    fake = FakeMediaInspector()
    meta = fake.inspect_media("any_file.mp4")
    assert meta.duration_ms > 0
    assert meta.width == 1920
    assert meta.video_codec == "h264"


def test_ffprobe_media_inspector_video(sample_video_path: Path):
    inspector = FFprobeMediaInspector()
    meta = inspector.inspect_media(sample_video_path)

    assert meta.duration_ms >= 900  # ~1000ms
    assert meta.width == 320
    assert meta.height == 240
    assert abs(meta.frame_rate - 30.0) < 0.1
    assert "h264" in meta.video_codec.lower()
    assert meta.audio_codec is not None
    assert meta.audio_sample_rate == 44100
    assert meta.audio_channels == 1
    assert meta.size_bytes > 0
    assert meta.is_audio_only is False


def test_ffprobe_media_inspector_audio(sample_audio_path: Path):
    inspector = FFprobeMediaInspector()
    meta = inspector.inspect_media(sample_audio_path)

    assert meta.duration_ms >= 900
    assert meta.is_audio_only is True
    assert meta.audio_sample_rate == 16000
    assert meta.audio_channels == 1
    assert meta.size_bytes > 0


def test_ffprobe_media_inspector_nonexistent_file(tmp_path: Path):
    inspector = FFprobeMediaInspector()
    nonexistent = tmp_path / "does_not_exist.mp4"
    with pytest.raises(MediaInspectionError, match="not found"):
        inspector.inspect_media(nonexistent)


def test_ffprobe_media_inspector_corrupted_file(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.mp4"
    corrupt_file.write_text("not a video file")
    inspector = FFprobeMediaInspector()
    with pytest.raises(MediaInspectionError, match="FFprobe failed"):
        inspector.inspect_media(corrupt_file)
