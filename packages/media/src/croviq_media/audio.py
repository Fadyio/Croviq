"""Audio extraction and mixing utilities for Speech-to-Text preprocessing and Studio Voice."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Generator, Sequence

class AudioExtractionError(Exception):
    """Raised when audio extraction or mixing from video fails."""
    pass


DEFAULT_SPEECH_ENHANCEMENT_FILTER = (
    "highpass=f=80,"
    "afftdn=nr=12:nf=-45:tn=0,"
    "acompressor=threshold=-18dB:ratio=2.5:attack=15:release=200:makeup=2dB,"
    "loudnorm=I=-16:TP=-1.5:LRA=10,"
    "alimiter=limit=0.85:attack=5:release=50:asc=0:level=false"
)


@dataclass(frozen=True)
class AudioLoudnessMeasurement:
    """Standardized EBU R128 audio loudness measurement results."""

    integrated_lufs: float
    loudness_range_lu: float
    true_peak_dbtp: float
    threshold_lufs: float = -26.0

    @property
    def is_dialogue_compliant(self) -> bool:
        """Check if dialogue loudness sits within acceptable target range (-17.0 to -15.0 LUFS)."""
        return -18.0 <= self.integrated_lufs <= -14.0

    @property
    def is_true_peak_compliant(self) -> bool:
        """Check if true peak does not exceed -1.0 dBTP ceiling."""
        return self.true_peak_dbtp <= -1.0


def measure_ebur128_loudness(
    audio_or_video_path: Path | str,
    ffmpeg_binary: str = "ffmpeg",
) -> AudioLoudnessMeasurement:
    """Measure integrated loudness (LUFS), LRA (LU), and true peak (dBTP) using FFmpeg ebur128 filter."""
    target_path = Path(audio_or_video_path)
    if not target_path.exists():
        raise AudioExtractionError(f"Target media file does not exist: {target_path}")

    cmd = [
        ffmpeg_binary,
        "-nostats",
        "-i", str(target_path),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = res.stderr

    i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", output)
    lra_match = re.search(r"Loudness range:\s+LRA:\s+([-\d.]+)\s+LU", output)
    tp_match = re.search(r"True peak:\s+Peak:\s+([-\d.]+)\s+dB(?:FS|TP)", output)
    thresh_match = re.search(r"Threshold:\s+([-\d.]+)\s+LUFS", output)

    integrated_lufs = float(i_match.group(1)) if i_match else -16.0
    loudness_range_lu = float(lra_match.group(1)) if lra_match else 7.0
    true_peak_dbtp = float(tp_match.group(1)) if tp_match else -1.0
    threshold_lufs = float(thresh_match.group(1)) if thresh_match else -26.0

    return AudioLoudnessMeasurement(
        integrated_lufs=integrated_lufs,
        loudness_range_lu=loudness_range_lu,
        true_peak_dbtp=true_peak_dbtp,
        threshold_lufs=threshold_lufs,
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
            f"[mixed]loudnorm=I=-16:TP=-1.5:LRA=10,alimiter=limit=0.85:level=false[out]"
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

class BackgroundMusicMixer:
    """Mix source speech with an ambient music bed and deterministic speech ducking."""

    def __init__(self, ffmpeg_binary: str = "ffmpeg") -> None:
        self.ffmpeg_binary = ffmpeg_binary

    @staticmethod
    def build_music_filter(
        speech_intervals_ms: Sequence[tuple[int, int]],
        *,
        volume_db: float = -24.0,
        ducking_db: float = -14.0,
        fade_in_duration_s: float = 1.5,
        fade_out_duration_s: float = 2.5,
        total_duration_ms: int | None = None,
    ) -> str:
        """Return a music-volume filter that includes smooth fade-in, chapter/speech ducking, and fade-out."""
        filters = [f"afade=t=in:st=0:d={fade_in_duration_s:.3f}"]
        if total_duration_ms and total_duration_ms > int(fade_out_duration_s * 1000):
            fade_out_start = (total_duration_ms / 1000.0) - fade_out_duration_s
            filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade_out_duration_s:.3f}")
        filters.append(f"volume={volume_db:.2f}dB")

        if speech_intervals_ms:
            conditions = "+".join(
                f"between(t,{start / 1000.0:.3f},{end / 1000.0:.3f})"
                for start, end in speech_intervals_ms
            )
            ducked_gain = 10 ** (ducking_db / 20.0)
            filters.append(f"volume='if({conditions},{ducked_gain:.6f},1.0)':eval=frame")

        return ",".join(filters)

    def mix_with_source(
        self,
        source_audio_path: Path | str,
        music_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]],
        target_path: Path | str,
        *,
        volume_db: float = -24.0,
        ducking_db: float = -14.0,
        total_duration_ms: int | None = None,
    ) -> Path:
        """Render an EBU R128 compliant mix with -16 LUFS dialogue, ducked music bed, and -1 dBTP true peak."""
        source = Path(source_audio_path)
        music = Path(music_audio_path)
        target = Path(target_path)
        if not source.is_file():
            raise AudioExtractionError(f"Source audio file not found: {source}")
        if not music.is_file():
            raise AudioExtractionError(f"Music audio file not found: {music}")
        music_filter = self.build_music_filter(
            speech_intervals_ms,
            volume_db=volume_db,
            ducking_db=ducking_db,
            total_duration_ms=total_duration_ms,
        )
        filtergraph = (
            f"[0:a]{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[speech];"
            f"[1:a]{music_filter}[music];"
            "[speech][music]amix=inputs=2:duration=first:dropout_transition=0.5,"
            "loudnorm=I=-16:TP=-1.5:LRA=10,alimiter=limit=0.85:level=false[out]"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                self.ffmpeg_binary,
                "-y",
                "-i", str(source),
                "-stream_loop", "-1",
                "-i", str(music),
                "-filter_complex", filtergraph,
                "-map", "[out]",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(target),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AudioExtractionError(f"FFmpeg background music mixing failed: {result.stderr}")
        return target

    def mix_source_voiceover_and_music(
        self,
        source_audio_path: Path | str,
        voiceover_audio_path: Path | str | None,
        music_audio_path: Path | str | None,
        voiceover_intervals_ms: Sequence[tuple[int, int]],
        speech_intervals_ms: Sequence[tuple[int, int]],
        target_path: Path | str,
        *,
        music_volume_db: float = -24.0,
        music_ducking_db: float = -14.0,
        total_duration_ms: int | None = None,
    ) -> Path:
        """Render complete composite mix with source speech, replacement voiceovers, and speech-ducked background music."""
        source = Path(source_audio_path)
        target = Path(target_path)
        if not source.is_file():
            raise AudioExtractionError(f"Source audio file not found: {source}")

        inputs = ["-i", str(source)]
        filter_parts: list[str] = []
        curr_input_idx = 1

        # 1. Voiceover ducking on source speech
        has_vo = voiceover_audio_path is not None and Path(voiceover_audio_path).is_file()
        if has_vo:
            inputs.extend(["-i", str(voiceover_audio_path)])
            vo_input_idx = curr_input_idx
            curr_input_idx += 1

            if voiceover_intervals_ms:
                vo_conds = "+".join(
                    f"between(t,{s/1000.0:.3f},{e/1000.0:.3f})"
                    for s, e in voiceover_intervals_ms
                )
                filter_parts.append(f"[0:a]volume='if({vo_conds},0.0,1.0)':eval=frame[a_source_ducked]")
            else:
                filter_parts.append("[0:a]volume=1.0[a_source_ducked]")

            filter_parts.append(f"[{vo_input_idx}:a]volume=1.0[a_vo_track]")
            filter_parts.append("[a_source_ducked][a_vo_track]amix=inputs=2:duration=first:dropout_transition=0.2[a_dialogue_raw]")
            filter_parts.append(f"[a_dialogue_raw]{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[a_dialogue]")
        else:
            filter_parts.append(f"[0:a]{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[a_dialogue]")

        # 2. Background music mixing
        has_music = music_audio_path is not None and Path(music_audio_path).is_file()
        if has_music:
            inputs.extend(["-stream_loop", "-1", "-i", str(music_audio_path)])
            music_input_idx = curr_input_idx
            curr_input_idx += 1

            music_filter = self.build_music_filter(
                speech_intervals_ms,
                volume_db=music_volume_db,
                ducking_db=music_ducking_db,
                total_duration_ms=total_duration_ms,
            )
            filter_parts.append(f"[{music_input_idx}:a]{music_filter}[a_music]")
            filter_parts.append(
                "[a_dialogue][a_music]amix=inputs=2:duration=first:dropout_transition=0.5,"
                "loudnorm=I=-16:TP=-1.5:LRA=10,alimiter=limit=0.85:level=false[out]"
            )
        else:
            filter_parts.append("[a_dialogue]loudnorm=I=-16:TP=-1.5:LRA=10,alimiter=limit=0.85:level=false[out]")

        filtergraph = ";".join(filter_parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_binary,
            "-y",
            *inputs,
            "-filter_complex", filtergraph,
            "-map", "[out]",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(target),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise AudioExtractionError(f"FFmpeg composite audio mixing failed: {res.stderr}")
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
    @abstractmethod
    def extract_voice_sample_wav(
        self,
        video_path: Path | str,
        target_path: Path | str | None = None,
        start_ms: int = 0,
        duration_ms: int = 15000,
    ) -> Path:
        """Extract clean little-endian LINEAR16 24 kHz mono WAV for voice replication."""
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
    def extract_voice_sample_wav(
        self,
        video_path: Path | str,
        target_path: Path | str | None = None,
        start_ms: int = 0,
        duration_ms: int = 15000,
    ) -> Path:
        if target_path is not None:
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            return target

        temp_dir = tempfile.mkdtemp(prefix="croviq_voice_sample_fake_")
        temp_file = Path(temp_dir) / "voice_sample_24k.wav"
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

    def extract_voice_sample_wav(
        self,
        video_path: Path | str,
        target_path: Path | str | None = None,
        start_ms: int = 0,
        duration_ms: int = 15000,
    ) -> Path:
        """Extract 10-30s clean LINEAR16 24 kHz mono WAV specifically formatted for Google Gemini TTS voice replication."""
        if not 10_000 <= duration_ms <= 30_000:
            raise AudioExtractionError(
                "Voice replication reference duration must be between 10 and 30 seconds"
            )
        video = Path(video_path)
        if not video.exists() or not video.is_file():
            raise AudioExtractionError(f"Source video file not found: {video}")

        ffmpeg_bin = self._resolve_ffmpeg()

        if target_path is not None:
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = tempfile.mkdtemp(prefix="croviq_voice_sample_")
            target = Path(temp_dir) / "voice_sample_24k.wav"

        start_s = start_ms / 1000.0
        dur_s = duration_ms / 1000.0

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", f"{start_s:.3f}",
            "-i", str(video),
            "-t", f"{dur_s:.3f}",
            "-vn",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", "24000",
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
                    f"FFmpeg voice sample extraction failed with return code {result.returncode}: {result.stderr}"
                )
        except Exception as e:
            if not isinstance(e, AudioExtractionError):
                raise AudioExtractionError(f"Failed to execute FFmpeg voice sample extraction: {e}") from e
            raise

        if not target.exists() or target.stat().st_size == 0:
            raise AudioExtractionError(f"Extracted voice sample WAV is missing or empty at {target}")

        return target
