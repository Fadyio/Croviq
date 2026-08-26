from pathlib import Path
import pytest
import subprocess

from croviq_media.audio import (
    AudioExtractionError,
    AudioExtractor,
    FakeAudioExtractor,
    FFmpegAudioExtractor,
)


@pytest.fixture
def sample_video_path(tmp_path: Path) -> Path:
    video_file = tmp_path / "test_video.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=size=320x240:rate=30:duration=1",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=1:sample_rate=44100",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-ac", "2",
        str(video_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        pytest.skip(f"ffmpeg not available or failed: {res.stderr}")
    return video_file


def test_fake_audio_extractor(tmp_path: Path):
    fake = FakeAudioExtractor()
    out = tmp_path / "extracted.wav"
    result = fake.extract_speech_audio("fake.mp4", target_path=out)
    assert result.exists()
    assert result == out


def test_fake_audio_extractor_context_manager(tmp_path: Path):
    fake = FakeAudioExtractor()
    with fake.temporary_speech_audio("fake.mp4") as audio_path:
        assert audio_path.exists()
        captured_path = audio_path
    assert not captured_path.exists()


def test_ffmpeg_audio_extractor(sample_video_path: Path, tmp_path: Path):
    extractor = FFmpegAudioExtractor()
    out_audio = tmp_path / "speech_audio.wav"
    result = extractor.extract_speech_audio(sample_video_path, target_path=out_audio, sample_rate=16000)

    assert result.exists()
    assert result == out_audio
    assert result.stat().st_size > 0

    # Verify extracted audio properties with ffprobe
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "stream=codec_name,sample_rate,channels",
        "-of", "json",
        str(result),
    ]
    probe = subprocess.run(cmd, capture_output=True, text=True)
    assert "pcm_s16le" in probe.stdout
    assert "16000" in probe.stdout
    assert '"channels": 1' in probe.stdout


def test_ffmpeg_audio_extractor_context_manager(sample_video_path: Path):
    extractor = FFmpegAudioExtractor()
    with extractor.temporary_speech_audio(sample_video_path, sample_rate=16000) as audio_path:
        assert audio_path.exists()
        assert audio_path.stat().st_size > 0
        captured_path = audio_path

    # Cleaned up deterministically after context exit
    assert not captured_path.exists()


def test_ffmpeg_audio_extractor_nonexistent_source(tmp_path: Path):
    extractor = FFmpegAudioExtractor()
    nonexistent = tmp_path / "does_not_exist.mp4"
    with pytest.raises(AudioExtractionError, match="not found"):
        extractor.extract_speech_audio(nonexistent)
