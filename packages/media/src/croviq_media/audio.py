"""Audio extraction utilities for Speech-to-Text preprocessing with deterministic temp cleanup."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Generator


class AudioExtractionError(Exception):
    """Raised when audio extraction from video fails."""
    pass

DEFAULT_SPEECH_ENHANCEMENT_FILTER = (
    "highpass=f=80,"
    "afftdn=nr=10:nf=-25:tn=1,"
    "acompressor=threshold=-18dB:ratio=2.5:attack=20:release=250:makeup=2dB,"
    "loudnorm=I=-16:TP=-1.5:LRA=11,"
    "alimiter=limit=0.8414:attack=5:release=50:asc=1:level=0"
)


class SpeechEnhancementPipeline:
    """Deterministic, FFmpeg-native speech audio enhancement and loudness mastering pipeline.

    Applies conservative highpass rumble filter, broadband adaptive noise reduction,
    light dynamic speech compression, EBU R128 (-16 LUFS) loudness normalization,
    and brickwall peak limiting (<= -1.5 dBTP) without third-party services.
    """

    def __init__(
        self,
        filter_chain: str = DEFAULT_SPEECH_ENHANCEMENT_FILTER,
        ffmpeg_binary: str = "ffmpeg",
    ) -> None:
        self.filter_chain = filter_chain
        self.ffmpeg_binary = ffmpeg_binary

    def get_filter_chain(self) -> str:
        """Return the composite FFmpeg audio filter string."""
        return self.filter_chain

    def build_audio_filter_graph(
        self,
        input_label: str = "0:a",
        output_label: str = "aout",
    ) -> str:
        """Construct FFmpeg filtergraph segment connecting input stream label to output stream label."""
        return f"[{input_label}]{self.filter_chain}[{output_label}]"

class AudioExtractor(ABC):
    """Abstract interface for extracting audio streams from video files."""

    @abstractmethod
    def extract_speech_audio(
        self,
        source_video_path: Path | str,
        target_path: Path | str | None = None,
        sample_rate: int = 16000,
    ) -> Path:
        """Extract a speech-optimized audio file (e.g. 16kHz mono WAV) from video."""
        pass

    @contextmanager
    def temporary_speech_audio(
        self,
        source_video_path: Path | str,
        sample_rate: int = 16000,
    ) -> Generator[Path, None, None]:
        """Context manager yielding temporary speech audio path and deterministically deleting it upon exit."""
        temp_dir = tempfile.mkdtemp(prefix="croviq_audio_")
        target_file = Path(temp_dir) / "speech_audio.wav"
        try:
            extracted_path = self.extract_speech_audio(
                source_video_path,
                target_path=target_file,
                sample_rate=sample_rate,
            )
            yield extracted_path
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass


class FakeAudioExtractor(AudioExtractor):
    """In-memory or mock audio extractor for unit tests."""

    def extract_speech_audio(
        self,
        source_video_path: Path | str,
        target_path: Path | str | None = None,
        sample_rate: int = 16000,
    ) -> Path:
        if target_path:
            out = Path(target_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"RIFF_FAKE_AUDIO_DATA")
            return out
        temp_file = Path(tempfile.mktemp(prefix="fake_audio_", suffix=".wav"))
        temp_file.write_bytes(b"RIFF_FAKE_AUDIO_DATA")
        return temp_file


class FFmpegAudioExtractor(AudioExtractor):
    """Production implementation of AudioExtractor leveraging FFmpeg."""

    def __init__(self, ffmpeg_binary: str = "ffmpeg") -> None:
        self.ffmpeg_binary = ffmpeg_binary

    def _resolve_binary(self) -> str:
        bin_path = shutil.which(self.ffmpeg_binary)
        if not bin_path:
            raise AudioExtractionError(
                f"ffmpeg binary '{self.ffmpeg_binary}' not found in PATH"
            )
        return bin_path

    def extract_speech_audio(
        self,
        source_video_path: Path | str,
        target_path: Path | str | None = None,
        sample_rate: int = 16000,
    ) -> Path:
        source = Path(source_video_path)
        if not source.exists():
            raise AudioExtractionError(f"Source video not found at '{source}'")

        if target_path is not None:
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            temp_fd, temp_name = tempfile.mkstemp(prefix="croviq_speech_", suffix=".wav")
            import os
            os.close(temp_fd)
            target = Path(temp_name)

        ffmpeg_bin = self._resolve_binary()
        # -vn: disable video recording
        # -acodec pcm_s16le: 16-bit PCM WAV (lossless, standard for STT)
        # -ar 16000: 16kHz speech sample rate
        # -ac 1: mono audio
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(source),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", "1",
            str(target),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e:
            raise AudioExtractionError(f"Failed to execute ffmpeg: {e}") from e

        if result.returncode != 0:
            raise AudioExtractionError(
                f"FFmpeg failed with returncode {result.returncode}: {result.stderr.strip()}"
            )

        if not target.exists() or target.stat().st_size == 0:
            raise AudioExtractionError(
                f"FFmpeg produced zero-byte or missing output at '{target}'"
            )

        return target
