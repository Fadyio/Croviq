"""MediaInspector abstraction and FFprobe implementation for extracting deterministic media parameters."""

from abc import ABC, abstractmethod
import json
from pathlib import Path
import shutil
import subprocess

from croviq_domain.media_metadata import MediaMetadata


class MediaInspectionError(Exception):
    """Raised when media inspection fails or ffprobe fails."""
    pass


class MediaInspector(ABC):
    """Abstract interface for extracting technical parameters from source media."""

    @abstractmethod
    def inspect_media(self, file_path: Path | str) -> MediaMetadata:
        """Extract deterministic media metadata from local media file."""
        pass


class FakeMediaInspector(MediaInspector):
    """In-memory simulated media inspector for deterministic unit tests."""

    def __init__(self, default_metadata: MediaMetadata | None = None) -> None:
        self._custom_metadata: dict[str, MediaMetadata] = {}
        self._default_metadata = default_metadata or MediaMetadata(
            duration_ms=60000,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            rotation=0,
            size_bytes=10485760,
        )

    def set_metadata(self, file_path: Path | str, metadata: MediaMetadata) -> None:
        self._custom_metadata[str(file_path)] = metadata

    def inspect_media(self, file_path: Path | str) -> MediaMetadata:
        key = str(file_path)
        if key in self._custom_metadata:
            return self._custom_metadata[key]
        return self._default_metadata


class FFprobeMediaInspector(MediaInspector):
    """Production implementation of MediaInspector leveraging ffprobe subprocess."""

    def __init__(self, ffprobe_binary: str = "ffprobe") -> None:
        self.ffprobe_binary = ffprobe_binary

    def _resolve_binary(self) -> str:
        bin_path = shutil.which(self.ffprobe_binary)
        if not bin_path:
            raise MediaInspectionError(
                f"ffprobe binary '{self.ffprobe_binary}' not found in PATH"
            )
        return bin_path

    def inspect_media(self, file_path: Path | str) -> MediaMetadata:
        path = Path(file_path)
        if not path.exists():
            raise MediaInspectionError(f"Media file not found at '{path}'")

        ffprobe_bin = self._resolve_binary()
        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-show_entries",
            "format=duration,size:"
            "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,tags:"
            "stream_side_data=rotation",
            "-of", "json",
            str(path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e:
            raise MediaInspectionError(f"Failed to execute ffprobe: {e}") from e

        if result.returncode != 0:
            raise MediaInspectionError(
                f"FFprobe failed with returncode {result.returncode}: {result.stderr.strip()}"
            )

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise MediaInspectionError(f"Failed to parse ffprobe JSON output: {e}") from e

        format_info = data.get("format", {})
        streams = data.get("streams", [])

        # Parse duration
        duration_sec = 0.0
        if "duration" in format_info:
            try:
                duration_sec = float(format_info["duration"])
            except (ValueError, TypeError):
                duration_sec = 0.0

        # Parse size
        size_bytes = 0
        if "size" in format_info:
            try:
                size_bytes = int(format_info["size"])
            except (ValueError, TypeError):
                size_bytes = 0
        if size_bytes <= 0 and path.exists():
            size_bytes = path.stat().st_size

        video_stream = None
        audio_stream = None

        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_stream is None:
                video_stream = stream
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = stream

        # Fallback to video duration if format duration was 0
        if duration_sec <= 0.0 and video_stream and "duration" in video_stream:
            try:
                duration_sec = float(video_stream["duration"])
            except (ValueError, TypeError):
                pass
        # Or audio duration
        if duration_sec <= 0.0 and audio_stream and "duration" in audio_stream:
            try:
                duration_sec = float(audio_stream["duration"])
            except (ValueError, TypeError):
                pass

        duration_ms = max(1, int(round(duration_sec * 1000)))

        # Video properties
        width = 0
        height = 0
        frame_rate = 0.0
        video_codec = "none"
        rotation = 0

        if video_stream:
            width = int(video_stream.get("width", 0) or 0)
            height = int(video_stream.get("height", 0) or 0)
            video_codec = str(video_stream.get("codec_name", "unknown"))

            # Calculate frame rate from r_frame_rate (e.g. "30/1" or "30000/1001")
            r_fps = video_stream.get("r_frame_rate", "0/0")
            if "/" in r_fps:
                num, den = r_fps.split("/", 1)
                try:
                    num_f = float(num)
                    den_f = float(den)
                    if den_f > 0:
                        frame_rate = round(num_f / den_f, 3)
                except (ValueError, ZeroDivisionError):
                    frame_rate = 0.0
            else:
                try:
                    frame_rate = float(r_fps)
                except ValueError:
                    frame_rate = 0.0

            # Check rotation in side_data_list or tags
            side_data_list = video_stream.get("side_data_list", [])
            for side_data in side_data_list:
                if "rotation" in side_data:
                    try:
                        rot_val = int(side_data["rotation"])
                        if rot_val in (0, 90, 180, 270):
                            rotation = rot_val
                        elif rot_val in (-90, 270):
                            rotation = 270
                        elif rot_val in (-180, 180):
                            rotation = 180
                        elif rot_val in (-270, 90):
                            rotation = 90
                    except (ValueError, TypeError):
                        pass

            tags = video_stream.get("tags", {})
            if "rotate" in tags and rotation == 0:
                try:
                    rot_val = int(tags["rotate"])
                    if rot_val in (0, 90, 180, 270):
                        rotation = rot_val
                except (ValueError, TypeError):
                    pass

        # Audio properties
        audio_codec = None
        audio_sample_rate = None
        audio_channels = None

        if audio_stream:
            audio_codec = str(audio_stream.get("codec_name", "unknown"))
            if "sample_rate" in audio_stream:
                try:
                    audio_sample_rate = int(audio_stream["sample_rate"])
                except (ValueError, TypeError):
                    pass
            if "channels" in audio_stream:
                try:
                    audio_channels = int(audio_stream["channels"])
                except (ValueError, TypeError):
                    pass

        return MediaMetadata(
            duration_ms=duration_ms,
            width=width,
            height=height,
            frame_rate=frame_rate,
            video_codec=video_codec,
            audio_codec=audio_codec,
            audio_sample_rate=audio_sample_rate,
            audio_channels=audio_channels,
            rotation=rotation,
            size_bytes=max(1, size_bytes),
        )
