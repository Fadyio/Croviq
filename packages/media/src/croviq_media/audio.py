"""Audio extraction and mixing utilities for Speech-to-Text preprocessing and Studio Voice."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Generator, Sequence


class AudioExtractionError(Exception):
    """Raised when audio extraction or mixing from video fails."""
    pass


DEFAULT_SPEECH_ENHANCEMENT_FILTER = (
    "highpass=f=80,"
    "afftdn=nr=12:nf=-45:tn=0,"
    "acompressor=threshold=-18dB:ratio=2.5:attack=15:release=200:makeup=2dB,"
    "loudnorm=I=-16:TP=-1.0:LRA=10"
)


class SpeechEnhancementPipeline:
    """Deterministic, FFmpeg-native speech audio enhancement and loudness mastering pipeline."""

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


class StudioVoiceAudioMixer:
    """Mixes synthesized Studio Voice narration track with ambient background audio, ducking original speech."""

    def __init__(self, ffmpeg_binary: str = "ffmpeg") -> None:
        self.ffmpeg_binary = ffmpeg_binary

    def build_ducking_filter(self, speech_intervals_ms: Sequence[tuple[int, int]]) -> str:
        """Construct volume expression filter muting source audio during spoken narration intervals."""
        if not speech_intervals_ms:
            return "volume=1.0"
        conditions = [
            f"between(t,{start_ms / 1000.0:.3f},{end_ms / 1000.0:.3f})"
            for start_ms, end_ms in speech_intervals_ms
        ]
        combined = "+".join(conditions)
        return f"volume='if({combined}, 0.05, 1.0)':eval=frame"

    def mix_narration_with_ambient(
        self,
        source_audio_path: Path | str,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]],
        target_path: Path | str,
    ) -> Path:
        """Render composite audio with ducked source speech and normalized narration."""
        source = Path(source_audio_path)
        narr = Path(narration_audio_path)
        target = Path(target_path)

        if not source.exists():
            raise AudioExtractionError(f"Source audio file not found: {source}")
        if not narr.exists():
            raise AudioExtractionError(f"Narration audio file not found: {narr}")

        duck_filter = self.build_ducking_filter(speech_intervals_ms)
        filtergraph = (
            f"[0:a]{duck_filter}[ducked];"
            f"[1:a]volume=1.0[narr];"
            f"[ducked][narr]amix=inputs=2:duration=first:dropout_transition=0.2[mixed];"
            f"[mixed]loudnorm=I=-16:TP=-1.0:LRA=10[out]"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_binary,
            "-y",
            "-i", str(source),
            "-i", str(narr),
            "-filter_complex", filtergraph,
            "-map", "[out]",
            "-c:a", "aac",
            "-b:a", "192k",
            str(target),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise AudioExtractionError(f"FFmpeg audio mixing failed: {res.stderr}")
        return target


class AudioExtractor(ABC):
    """Abstract interface for extracting audio streams from video files."""

    @abstractmethod
    def extract_speech_audio(
        self,
        video_path: Path | str,
        target_path: Path | str | None = None,
        sample_rate: int = 16000,
    ) -> Path:
        """Extract a single-channel 16kHz WAV audio stream from the source video."""
        pass

    @contextmanager
    def temporary_speech_audio(
        self,
        video_path: Path | str,
        sample_rate: int = 16000,
    ) -> Generator[Path, None, None]:
        """Context manager yielding a temporary WAV audio file, cleaned up deterministically upon exit."""
        temp_dir = tempfile.mkdtemp(prefix="croviq_audio_")
        temp_file = Path(temp_dir) / "extracted_speech.wav"
        try:
            extracted = self.extract_speech_audio(
                video_path=video_path,
                target_path=temp_file,
                sample_rate=sample_rate,
            )
            yield extracted
        finally:
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)


class FakeAudioExtractor(AudioExtractor):
    """In-memory or mock audio extractor for unit tests."""

    def extract_speech_audio(
        self,
        video_path: Path | str,
        target_path: Path | str | None = None,
        sample_rate: int = 16000,
    ) -> Path:
        if target_path is not None:
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            return target

        temp_dir = tempfile.mkdtemp(prefix="croviq_audio_fake_")
        temp_file = Path(temp_dir) / "extracted_speech.wav"
        temp_file.touch()
        return temp_file


class FFmpegAudioExtractor(AudioExtractor):
    """Production implementation of AudioExtractor leveraging FFmpeg."""

    def __init__(self, ffmpeg_binary: str = "ffmpeg") -> None:
        self.ffmpeg_binary = ffmpeg_binary

    def _resolve_ffmpeg(self) -> str:
        resolved = shutil.which(self.ffmpeg_binary)
        if resolved is None:
            raise AudioExtractionError(f"FFmpeg binary '{self.ffmpeg_binary}' not found on PATH")
        return resolved

    def extract_speech_audio(
        self,
        video_path: Path | str,
        target_path: Path | str | None = None,
        sample_rate: int = 16000,
    ) -> Path:
        video = Path(video_path)
        if not video.exists() or not video.is_file():
            raise AudioExtractionError(f"Source video file not found: {video}")

        ffmpeg_bin = self._resolve_ffmpeg()

        if target_path is not None:
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = tempfile.mkdtemp(prefix="croviq_audio_extract_")
            target = Path(temp_dir) / "speech_16k.wav"

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(video),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            str(target),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise AudioExtractionError(
                    f"FFmpeg failed with return code {result.returncode}: {result.stderr}"
                )
        except Exception as e:
            if not isinstance(e, AudioExtractionError):
                raise AudioExtractionError(f"Failed to execute FFmpeg audio extraction: {e}") from e
            raise

        if not target.exists() or target.stat().st_size == 0:
            raise AudioExtractionError(f"Extracted audio file is missing or empty at {target}")

        return target
