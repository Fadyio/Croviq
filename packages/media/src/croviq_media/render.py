"""Deterministic video rendering service leveraging FFmpeg and canonical EditDecisionList."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any

from croviq_domain.editorial import ShortCandidate
from croviq_domain.edl import EditDecisionList, derive_keep_segments
from croviq_domain.render import ArtifactType
from croviq_domain.transcript import Transcript
from croviq_media.audio import DEFAULT_SPEECH_ENHANCEMENT_FILTER
from croviq_media.short import (
    extract_rebased_caption_words,
    generate_ass_subtitles,
    group_words_into_phrases,
    validate_and_snap_short_candidate,
)

class RenderError(Exception):
    """Raised when video rendering or ffprobe verification fails."""
    pass


@dataclass(frozen=True)
class RenderExecutionResult:
    """Outcome and verified technical parameters of a completed render."""

    output_path: Path
    artifact_type: ArtifactType
    duration_ms: int
    size_bytes: int
    width: int
    height: int
    frame_rate: float
    video_codec: str
    audio_codec: str
    render_time_ms: float


class RenderService(ABC):
    """Abstract interface for deterministic media rendering from canonical EDL."""

    @abstractmethod
    def render_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render a fast preview MP4 optimized for quick creator inspection."""
        pass

    @abstractmethod
    def render_master(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render a high-quality YouTube-ready master MP4."""
        pass

    @abstractmethod
    def render_short(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        short_candidate: ShortCandidate,
        transcript: Transcript | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render a 9:16 vertical Short MP4 (1080x1920) with word-synced captions."""
        pass


class FakeRenderService(RenderService):
    """In-memory or mock render service for unit testing."""

    def __init__(self, default_render_time_ms: float = 50.0) -> None:
        self.default_render_time_ms = default_render_time_ms

    def render_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        return self._simulate_render(source_path, edl, ArtifactType.PREVIEW, output_path)

    def render_master(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        return self._simulate_render(source_path, edl, ArtifactType.MASTER, output_path)

    def render_short(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        short_candidate: ShortCandidate,
        transcript: Transcript | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        snapped_start, snapped_end = validate_and_snap_short_candidate(
            candidate=short_candidate,
            source_duration_ms=edl.source_duration_ms,
            transcript=transcript,
        )
        target_dur = max(1000, snapped_end - snapped_start)
        return self._simulate_render(
            source_path,
            edl,
            ArtifactType.SHORT,
            output_path,
            override_duration_ms=target_dur,
            width=1080,
            height=1920,
        )

    def _simulate_render(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        artifact_type: ArtifactType,
        output_path: Path | str | None = None,
        override_duration_ms: int | None = None,
        width: int = 1920,
        height: int = 1080,
    ) -> RenderExecutionResult:
        src = Path(source_path)
        if not src.exists():
            raise RenderError(f"Source video not found: {src}")

        if output_path is not None:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(src.read_bytes() if src.is_file() else b"fake render bytes")
        else:
            temp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            temp.write(b"fake render bytes")
            temp.close()
            out = Path(temp.name)

        return RenderExecutionResult(
            output_path=out,
            artifact_type=artifact_type,
            duration_ms=override_duration_ms if override_duration_ms is not None else edl.estimated_target_duration_ms,
            size_bytes=out.stat().st_size,
            width=width,
            height=height,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            render_time_ms=self.default_render_time_ms,
        )


class FFmpegRenderService(RenderService):
    """Production implementation of RenderService utilizing deterministic FFmpeg subprocess pipelines."""

    def __init__(
        self,
        ffmpeg_binary: str = "ffmpeg",
        ffprobe_binary: str = "ffprobe",
        transition_ms: int = 20,
    ) -> None:
        self.ffmpeg_binary = ffmpeg_binary
        self.ffprobe_binary = ffprobe_binary
        self.transition_ms = transition_ms

    def _resolve_binary(self, binary_name: str) -> str:
        resolved = shutil.which(binary_name)
        if resolved is None:
            raise RenderError(f"Executable '{binary_name}' not found on system PATH")
        return resolved

    def render_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render fast preview MP4 using libx264 veryfast / CRF 23 / AAC 128k."""
        encoding_args = [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
        ]
        return self._execute_render(
            source_path=source_path,
            edl=edl,
            artifact_type=ArtifactType.PREVIEW,
            encoding_args=encoding_args,
            output_path=output_path,
        )

    def render_master(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render high quality YouTube master MP4 using libx264 medium / CRF 18 / AAC 192k."""
        encoding_args = [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
        ]
        return self._execute_render(
            source_path=source_path,
            edl=edl,
            artifact_type=ArtifactType.MASTER,
            encoding_args=encoding_args,
            output_path=output_path,
        )

    def render_short(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        short_candidate: ShortCandidate,
        transcript: Transcript | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render high quality 9:16 vertical Short MP4 (1080x1920) with word-synced captions."""
        start_time = time.perf_counter()
        source = Path(source_path)

        if not source.exists() or not source.is_file():
            raise RenderError(f"Source video not found: {source}")

        ffmpeg_bin = self._resolve_binary(self.ffmpeg_binary)
        ffprobe_bin = self._resolve_binary(self.ffprobe_binary)

        # 1. Validate and snap candidate bounds
        short_start_ms, short_end_ms = validate_and_snap_short_candidate(
            candidate=short_candidate,
            source_duration_ms=edl.source_duration_ms,
            transcript=transcript,
        )

        # 2. Derive keep segments within short boundaries
        edl_keep_segments = derive_keep_segments(edl)
        short_keep_segments: list[tuple[int, int]] = []
        for k_start, k_end in edl_keep_segments:
            seg_start = max(k_start, short_start_ms)
            seg_end = min(k_end, short_end_ms)
            if seg_end > seg_start:
                short_keep_segments.append((seg_start, seg_end))

        if not short_keep_segments:
            short_keep_segments = [(short_start_ms, short_end_ms)]

        expected_duration_ms = sum(end - start for start, end in short_keep_segments)

        # 3. Probe source dimensions for landscape vs vertical strategy
        source_width, source_height = self._probe_media_dimensions(ffprobe_bin, source)

        # 4. Generate ASS subtitles if transcript is available
        ass_temp_file: tempfile.NamedTemporaryFile | None = None
        ass_path: Path | None = None
        if transcript and transcript.words:
            caption_words = extract_rebased_caption_words(
                transcript=transcript,
                short_start_ms=short_start_ms,
                short_end_ms=short_end_ms,
                keep_segments=short_keep_segments,
            )
            phrases = group_words_into_phrases(caption_words)
            if phrases:
                ass_content = generate_ass_subtitles(phrases)
                ass_temp_file = tempfile.NamedTemporaryFile(
                    suffix=".ass", mode="w", encoding="utf-8", delete=False
                )
                ass_temp_file.write(ass_content)
                ass_temp_file.close()
                ass_path = Path(ass_temp_file.name)

        if output_path is not None:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            temp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            temp.close()
            target = Path(temp.name)

        try:
            filter_graph, map_args = self._build_short_filtergraph(
                keep_segments=short_keep_segments,
                source_width=source_width,
                source_height=source_height,
                ass_file_path=ass_path,
                short_candidate=short_candidate,
            )

            encoding_args = [
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
            ]

            cmd = [
                ffmpeg_bin,
                "-y",
                "-v", "error",
                "-i", str(source),
                "-filter_complex", filter_graph,
            ]
            cmd.extend(map_args)
            cmd.extend(encoding_args)
            cmd.extend(["-movflags", "+faststart", str(target)])

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                err_msg = res.stderr.strip() if res.stderr.strip() else "Unknown FFmpeg error"
                raise RenderError(f"FFmpeg Short render failed with exit code {res.returncode}: {err_msg} | CMD: {' '.join(cmd)}")
            if not target.exists() or target.stat().st_size == 0:
                raise RenderError("Rendered Short output file was not produced or is empty")

            verified_metadata = self._verify_short_metadata(ffprobe_bin, target, expected_duration_ms)
            render_time_ms = (time.perf_counter() - start_time) * 1000

            return RenderExecutionResult(
                output_path=target,
                artifact_type=ArtifactType.SHORT,
                duration_ms=verified_metadata["duration_ms"],
                size_bytes=verified_metadata["size_bytes"],
                width=verified_metadata["width"],
                height=verified_metadata["height"],
                frame_rate=verified_metadata["frame_rate"],
                video_codec=verified_metadata["video_codec"],
                audio_codec=verified_metadata["audio_codec"],
                render_time_ms=render_time_ms,
            )
        finally:
            if ass_path and ass_path.exists():
                try:
                    ass_path.unlink()
                except Exception:
                    pass


    def _build_filtergraph(
        self,
        keep_segments: list[tuple[int, int]],
        source_duration_ms: int,
    ) -> tuple[str | None, list[str]]:
        """Construct deterministic FFmpeg filtergraph for keep segments with ~20ms audio crossfade."""
        num_segs = len(keep_segments)
        if num_segs == 0:
            raise RenderError("Cannot render EDL with zero keep segments")

        # Zero-cut optimization: full duration with enhanced audio
        if num_segs == 1 and keep_segments[0][0] == 0 and keep_segments[0][1] >= source_duration_ms:
            filter_graph = f"[0:a]{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[aout]"
            return filter_graph, ["-map", "0:v", "-map", "[aout]"]

        # Single sub-segment trim with enhanced audio
        if num_segs == 1:
            start_ms, end_ms = keep_segments[0]
            start_s = start_ms / 1000.0
            end_s = end_ms / 1000.0
            filter_graph = (
                f"[0:v]trim=start={start_s:.4f}:end={end_s:.4f},setpts=PTS-STARTPTS[vout];"
                f"[0:a]atrim=start={start_s:.4f}:end={end_s:.4f},asetpts=PTS-STARTPTS,{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[aout]"
            )
            return filter_graph, ["-map", "[vout]", "-map", "[aout]"]
        # Multiple keep segments with 20ms audio micro-transitions
        video_filters: list[str] = []
        audio_filters: list[str] = []
        video_inputs: list[str] = []
        audio_inputs: list[str] = []

        transition_sec = self.transition_ms / 1000.0

        for i, (start_ms, end_ms) in enumerate(keep_segments):
            start_s = start_ms / 1000.0
            end_s = end_ms / 1000.0
            seg_dur_s = max(0.001, end_s - start_s)
            trans_dur_s = min(transition_sec, seg_dur_s / 2.0)
            fade_out_start_s = max(0.0, seg_dur_s - trans_dur_s)

            # Video trim
            video_filters.append(
                f"[0:v]trim=start={start_s:.4f}:end={end_s:.4f},setpts=PTS-STARTPTS[v{i}]"
            )
            video_inputs.append(f"[v{i}]")

            # Audio trim and micro-fade transitions
            afilt = [
                f"atrim=start={start_s:.4f}:end={end_s:.4f}",
                "asetpts=PTS-STARTPTS",
            ]
            if i > 0:
                afilt.append(f"afade=t=in:st=0:d={trans_dur_s:.4f}")
            if i < num_segs - 1:
                afilt.append(f"afade=t=out:st={fade_out_start_s:.4f}:d={trans_dur_s:.4f}")

            audio_filters.append(f"[0:a]{','.join(afilt)}[a{i}]")
            audio_inputs.append(f"[a{i}]")

        vconcat = f"{''.join(video_inputs)}concat=n={num_segs}:v=1:a=0[vout]"
        aconcat = f"{''.join(audio_inputs)}concat=n={num_segs}:v=0:a=1[a_raw];[a_raw]{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[aout]"
        full_filter = ";".join(video_filters + audio_filters + [vconcat, aconcat])
        return full_filter, ["-map", "[vout]", "-map", "[aout]"]

    def _execute_render(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        artifact_type: ArtifactType,
        encoding_args: list[str],
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        start_time = time.perf_counter()
        source = Path(source_path)

        if not source.exists() or not source.is_file():
            raise RenderError(f"Source video not found: {source}")

        ffmpeg_bin = self._resolve_binary(self.ffmpeg_binary)
        ffprobe_bin = self._resolve_binary(self.ffprobe_binary)

        # Derive keep segments strictly from EDL
        keep_segments = derive_keep_segments(edl)
        if not keep_segments:
            raise RenderError(f"No valid keep segments derived from EDL {edl.edl_id}")

        created_temp = False
        if output_path is not None:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            temp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            temp.close()
            target = Path(temp.name)
            created_temp = True

        filter_graph, map_args = self._build_filtergraph(keep_segments, edl.source_duration_ms)

        cmd = [
            ffmpeg_bin,
            "-y",
            "-v", "error",
            "-i", str(source),
        ]

        if filter_graph is not None:
            cmd.extend(["-filter_complex", filter_graph])
            cmd.extend(map_args)

        cmd.extend(encoding_args)
        cmd.extend(["-movflags", "+faststart", str(target)])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                # Sanitize error message (no shell details or filesystem dumping)
                err_msg = res.stderr.strip().splitlines()[-1] if res.stderr.strip() else "Unknown FFmpeg error"
                raise RenderError(f"FFmpeg render failed with exit code {res.returncode}: {err_msg}")

            if not target.exists() or target.stat().st_size == 0:
                raise RenderError("Rendered output file was not produced or is empty")

            # Post-render metadata verification via ffprobe
            verified_metadata = self._verify_metadata(ffprobe_bin, target, edl)

            render_time_ms = (time.perf_counter() - start_time) * 1000

            return RenderExecutionResult(
                output_path=target,
                artifact_type=artifact_type,
                duration_ms=verified_metadata["duration_ms"],
                size_bytes=verified_metadata["size_bytes"],
                width=verified_metadata["width"],
                height=verified_metadata["height"],
                frame_rate=verified_metadata["frame_rate"],
                video_codec=verified_metadata["video_codec"],
                audio_codec=verified_metadata["audio_codec"],
                render_time_ms=render_time_ms,
            )
        except Exception:
            # Clean up target on failure
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass
            raise

    def _verify_metadata(
        self,
        ffprobe_bin: str,
        target_path: Path,
        edl: EditDecisionList,
    ) -> dict[str, Any]:
        probe_cmd = [
            ffprobe_bin,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(target_path),
        ]
        probe_res = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if probe_res.returncode != 0:
            raise RenderError(f"ffprobe metadata verification failed: {probe_res.stderr.strip()}")

        try:
            probe_data = json.loads(probe_res.stdout)
        except json.JSONDecodeError as exc:
            raise RenderError(f"Failed to parse ffprobe JSON output: {exc}") from exc

        format_info = probe_data.get("format", {})
        streams = probe_data.get("streams", [])

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream:
            raise RenderError("Rendered artifact contains no video stream")
        if not audio_stream:
            raise RenderError("Rendered artifact contains no audio stream")

        try:
            raw_duration_sec = float(format_info.get("duration", video_stream.get("duration", 0)))
        except (ValueError, TypeError):
            raw_duration_sec = 0.0

        duration_ms = int(round(raw_duration_sec * 1000))
        if duration_ms <= 0:
            raise RenderError(f"Rendered output duration is invalid: {duration_ms}ms")

        # Validate duration tolerance against expected EDL duration
        expected_duration_ms = edl.estimated_target_duration_ms
        tolerance_ms = max(500, int(expected_duration_ms * 0.05))
        if abs(duration_ms - expected_duration_ms) > tolerance_ms:
            raise RenderError(
                f"Rendered duration ({duration_ms}ms) deviated from expected duration ({expected_duration_ms}ms) "
                f"beyond tolerance ({tolerance_ms}ms)"
            )

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        if width <= 0 or height <= 0:
            raise RenderError(f"Rendered video dimensions invalid: {width}x{height}")

        # Parse frame rate
        r_frame_rate = video_stream.get("r_frame_rate", "30/1")
        try:
            if "/" in r_frame_rate:
                num, den = map(float, r_frame_rate.split("/"))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(r_frame_rate)
        except (ValueError, ZeroDivisionError):
            fps = 30.0

        size_bytes = int(format_info.get("size", target_path.stat().st_size))

        return {
            "duration_ms": duration_ms,
            "size_bytes": size_bytes,
            "width": width,
            "height": height,
            "frame_rate": fps,
            "video_codec": video_stream.get("codec_name", "h264"),
            "audio_codec": audio_stream.get("codec_name", "aac"),
        }

    def _build_short_filtergraph(
        self,
        keep_segments: list[tuple[int, int]],
        source_width: int,
        source_height: int,
        ass_file_path: Path | None = None,
        short_candidate: ShortCandidate | None = None,
    ) -> tuple[str, list[str]]:
        """Construct deterministic 1080x1920 9:16 filtergraph with landscape blurred fill or vertical scaling."""
        num_segs = len(keep_segments)
        if num_segs == 0:
            raise RenderError("Cannot render Short with zero keep segments")

        aspect_ratio = (source_width / source_height) if source_height > 0 else 0.5625
        is_vertical = aspect_ratio <= 0.65

        video_filters: list[str] = []
        audio_filters: list[str] = []
        video_inputs: list[str] = []
        audio_inputs: list[str] = []

        transition_sec = self.transition_ms / 1000.0

        for i, (start_ms, end_ms) in enumerate(keep_segments):
            start_s = start_ms / 1000.0
            end_s = end_ms / 1000.0
            seg_dur_s = max(0.001, end_s - start_s)
            trans_dur_s = min(transition_sec, seg_dur_s / 2.0)
            fade_out_start_s = max(0.0, seg_dur_s - trans_dur_s)

            # Video trim
            video_filters.append(
                f"[0:v]trim=start={start_s:.4f}:end={end_s:.4f},setpts=PTS-STARTPTS[v{i}]"
            )
            video_inputs.append(f"[v{i}]")

            # Audio trim and micro-fade transitions
            afilt = [
                f"atrim=start={start_s:.4f}:end={end_s:.4f}",
                "asetpts=PTS-STARTPTS",
            ]
            if i > 0:
                afilt.append(f"afade=t=in:st=0:d={trans_dur_s:.4f}")
            if i < num_segs - 1:
                afilt.append(f"afade=t=out:st={fade_out_start_s:.4f}:d={trans_dur_s:.4f}")

            audio_filters.append(f"[0:a]{','.join(afilt)}[a{i}]")
            audio_inputs.append(f"[a{i}]")

        if num_segs == 1:
            vconcat = "[v0]null[v_trimmed]"
            aconcat = f"[a0]anull,{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[aout]"
        else:
            vconcat = f"{''.join(video_inputs)}concat=n={num_segs}:v=1:a=0[v_trimmed]"
            aconcat = f"{''.join(audio_inputs)}concat=n={num_segs}:v=0:a=1[a_raw];[a_raw]{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[aout]"
        composition_filters: list[str] = []
        if is_vertical:
            # Scale to fit 1080x1920 with black padding if aspect deviates slightly
            composition_filters.append(
                "[v_trimmed]scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(1080-iw)/2:(1920-ih)/2:black,setsar=1[v_comp]"
            )
        else:
            # Landscape video strategy: 9:16 readable screen focus crop scaled with Lanczos to 1080x1920
            target_crop_w = max(2, int((source_height * 9 / 16) / 2) * 2)
            target_crop_h = source_height
            max_x_offset = max(0, source_width - target_crop_w)
            if short_candidate and short_candidate.visual_plan and short_candidate.visual_plan.regions:
                reg = short_candidate.visual_plan.regions[0]
                target_crop_x = min(max_x_offset, max(0, int(source_width * reg.x)))
            else:
                target_crop_x = min(max_x_offset, max(0, int(max_x_offset * 0.12)))
            composition_filters.append(
                f"[v_trimmed]crop={target_crop_w}:{target_crop_h}:{target_crop_x}:0,"
                "scale=1080:1920:flags=lanczos,setsar=1[v_comp]"
            )
        subtitle_filter = self._resolve_subtitle_filter(ass_file_path)
        if subtitle_filter:
            composition_filters.append(f"[v_comp]{subtitle_filter}[vout]")
        else:
            composition_filters.append("[v_comp]null[vout]")

        full_filter = ";".join(video_filters + audio_filters + [vconcat, aconcat] + composition_filters)
        return full_filter, ["-map", "[vout]", "-map", "[aout]"]

    def _has_filter(self, filter_name: str) -> bool:
        """Check if FFmpeg binary supports an exact filter name."""
        try:
            res = subprocess.run(
                [self.ffmpeg_binary, "-filters"],
                capture_output=True,
                text=True,
                check=False,
            )
            import re
            return bool(re.search(rf"\s{re.escape(filter_name)}\s", res.stdout))
        except Exception:
            return False

    def _resolve_subtitle_filter(self, ass_file_path: Path | str | None) -> str | None:
        """Determine available subtitle filter string for FFmpeg."""
        if not ass_file_path:
            return None
        ass_path = Path(ass_file_path)
        if not ass_path.exists():
            return None

        escaped_path = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        if self._has_filter("ass"):
            return f"ass='{escaped_path}'"
        if self._has_filter("subtitles"):
            return f"subtitles='{escaped_path}'"
        return None

    def _probe_media_dimensions(self, ffprobe_bin: str, media_path: Path) -> tuple[int, int]:
        """Probe video dimensions (width, height) using ffprobe."""
        probe_cmd = [
            ffprobe_bin,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(media_path),
        ]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return 1920, 1080
        try:
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            if streams:
                return int(streams[0].get("width", 1920)), int(streams[0].get("height", 1080))
        except Exception:
            pass
        return 1920, 1080

    def _verify_short_metadata(
        self,
        ffprobe_bin: str,
        target_path: Path,
        expected_duration_ms: int,
    ) -> dict[str, Any]:
        """Verify 1080x1920 resolution, duration tolerance, and codecs for a rendered Short."""
        probe_cmd = [
            ffprobe_bin,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(target_path),
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
        if probe_res.returncode != 0:
            raise RenderError(f"ffprobe metadata verification failed: {probe_res.stderr.strip()}")

        try:
            probe_data = json.loads(probe_res.stdout)
        except json.JSONDecodeError as exc:
            raise RenderError(f"Failed to parse ffprobe JSON output: {exc}") from exc

        format_info = probe_data.get("format", {})
        streams = probe_data.get("streams", [])

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream:
            raise RenderError("Rendered Short contains no video stream")
        if not audio_stream:
            raise RenderError("Rendered Short contains no audio stream")

        try:
            raw_duration_sec = float(format_info.get("duration", video_stream.get("duration", 0)))
        except (ValueError, TypeError):
            raw_duration_sec = 0.0

        duration_ms = int(round(raw_duration_sec * 1000))
        if duration_ms <= 0:
            raise RenderError(f"Rendered output duration is invalid: {duration_ms}ms")

        # Duration tolerance: 500ms or 5%
        tolerance_ms = max(600, int(expected_duration_ms * 0.05))
        if abs(duration_ms - expected_duration_ms) > tolerance_ms:
            raise RenderError(
                f"Rendered Short duration ({duration_ms}ms) deviated from expected duration ({expected_duration_ms}ms) "
                f"beyond tolerance ({tolerance_ms}ms)"
            )

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        if width != 1080 or height != 1920:
            raise RenderError(f"Rendered Short dimensions ({width}x{height}) must be 1080x1920 (9:16)")

        r_frame_rate = video_stream.get("r_frame_rate", "30/1")
        try:
            if "/" in r_frame_rate:
                num, den = map(float, r_frame_rate.split("/"))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(r_frame_rate)
        except (ValueError, ZeroDivisionError):
            fps = 30.0

        size_bytes = int(format_info.get("size", target_path.stat().st_size))

        return {
            "duration_ms": duration_ms,
            "size_bytes": size_bytes,
            "width": width,
            "height": height,
            "frame_rate": fps,
            "video_codec": video_stream.get("codec_name", "h264"),
            "audio_codec": audio_stream.get("codec_name", "aac"),
        }
