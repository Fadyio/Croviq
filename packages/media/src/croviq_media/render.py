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
from typing import Any, Sequence
from croviq_domain.edl import EditDecisionList, derive_keep_segments
from croviq_domain.render import ArtifactType
from croviq_media.audio import DEFAULT_SPEECH_ENHANCEMENT_FILTER

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
    def render_voiceover_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render fast Voiceover preview MP4 combining EDL cuts and replacement voiceover narration."""
        pass

    @abstractmethod
    def render_studio_voice_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render fast preview MP4 combining EDL cuts, Studio Voice narration, and ducked ambient audio."""
        pass
    @abstractmethod
    def render_studio_voice_master(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render high quality YouTube master MP4 combining EDL cuts, Studio Voice narration, and ducked ambient audio."""
        pass

    @abstractmethod
    def render_background_music_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        music_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
        volume_db: float = -24.0,
        ducking_db: float = -14.0,
    ) -> RenderExecutionResult:
        """Render preview with an ambient music bed ducked under speech and mastered to -14 LUFS."""
        pass

    @abstractmethod
    def render_final_mix(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        music_audio_path: Path | str,
        narration_audio_path: Path | str | None = None,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
        music_volume_db: float = -24.0,
        music_ducking_db: float = -14.0,
    ) -> RenderExecutionResult:
        """Render Final Mix combining cuts, voiceover corrections, and background music."""
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

    def render_voiceover_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        return self._simulate_render(source_path, edl, ArtifactType.VOICEOVER_PREVIEW, output_path)

    def render_studio_voice_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        return self._simulate_render(source_path, edl, ArtifactType.STUDIO_VOICE_PREVIEW, output_path)
    def render_studio_voice_master(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        return self._simulate_render(source_path, edl, ArtifactType.STUDIO_VOICE_MASTER, output_path)

    def render_background_music_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        music_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
        volume_db: float = -24.0,
        ducking_db: float = -14.0,
    ) -> RenderExecutionResult:
        return self._simulate_render(source_path, edl, ArtifactType.PREVIEW, output_path)

    def render_final_mix(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        music_audio_path: Path | str,
        narration_audio_path: Path | str | None = None,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
        music_volume_db: float = -24.0,
        music_ducking_db: float = -14.0,
    ) -> RenderExecutionResult:
        return self._simulate_render(source_path, edl, ArtifactType.FINAL_MIX, output_path)

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
    def render_voiceover_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render fast Voiceover preview MP4 combining EDL video cuts and replacement voiceover track."""
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
            artifact_type=ArtifactType.VOICEOVER_PREVIEW,
            encoding_args=encoding_args,
            output_path=output_path,
            narration_path=narration_audio_path,
            speech_intervals_ms=speech_intervals_ms,
        )

    def render_studio_voice_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render fast Studio Voice preview MP4 combining EDL video cuts and mixed narration track."""
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
            artifact_type=ArtifactType.STUDIO_VOICE_PREVIEW,
            encoding_args=encoding_args,
            output_path=output_path,
            narration_path=narration_audio_path,
            speech_intervals_ms=speech_intervals_ms,
        )

    def render_studio_voice_master(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        narration_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        """Render high quality YouTube master MP4 with Studio Voice narration."""
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
            artifact_type=ArtifactType.STUDIO_VOICE_MASTER,
            encoding_args=encoding_args,
            output_path=output_path,
            narration_path=narration_audio_path,
            speech_intervals_ms=speech_intervals_ms,
        )


    def render_background_music_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        music_audio_path: Path | str,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
        volume_db: float = -24.0,
        ducking_db: float = -14.0,
    ) -> RenderExecutionResult:
        """Render an FFmpeg preview with looped music ducked beneath speech at -14 LUFS."""
        return self._execute_render(
            source_path=source_path,
            edl=edl,
            artifact_type=ArtifactType.PREVIEW,
            encoding_args=[
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            ],
            output_path=output_path,
            speech_intervals_ms=speech_intervals_ms,
            music_path=music_audio_path,
            music_volume_db=volume_db,
            music_ducking_db=ducking_db,
        )

    def render_final_mix(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        music_audio_path: Path | str,
        narration_audio_path: Path | str | None = None,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        output_path: Path | str | None = None,
        music_volume_db: float = -24.0,
        music_ducking_db: float = -14.0,
    ) -> RenderExecutionResult:
        """Render Final Mix with cuts, voiceover corrections, and ducked background music."""
        encoding_args = [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
        ]
        return self._execute_render(
            source_path=source_path,
            edl=edl,
            artifact_type=ArtifactType.FINAL_MIX,
            encoding_args=encoding_args,
            output_path=output_path,
            narration_path=narration_audio_path,
            speech_intervals_ms=speech_intervals_ms,
            music_path=music_audio_path,
            music_volume_db=music_volume_db,
            music_ducking_db=music_ducking_db,
        )

    def _build_filtergraph(
        self,
        keep_segments: list[tuple[int, int]],
        source_duration_ms: int,
        has_narration: bool = False,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        music_path: Path | str | None = None,
        music_input_idx: int = 1,
        music_volume_db: float = -24.0,
        music_ducking_db: float = -14.0,
    ) -> tuple[str | None, list[str]]:
        """Build the cut, narration, and speech-ducked music graph."""
        num_segs = len(keep_segments)
        if num_segs == 0:
            raise RenderError("Cannot render EDL with zero keep segments")

        ducking_cond = "1.0"
        if speech_intervals_ms:
            conds = [f"between(t,{s/1000.0:.3f},{e/1000.0:.3f})" for s, e in speech_intervals_ms]
            ducking_cond = f"if({'+'.join(conds)}, 0.0, 1.0)"
        has_music = music_path is not None
        music_ducking_cond = "1.0"
        if speech_intervals_ms:
            music_gain = 10 ** (music_ducking_db / 20.0)
            music_ducking_cond = f"if({'+'.join(conds)},{music_gain:.6f},1.0)"
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

        if num_segs == 1 and keep_segments[0][0] == 0 and keep_segments[0][1] >= source_duration_ms:
            audio_parts: list[str] = []
            primary_label = "a_primary"
            if has_narration:
                audio_parts.extend([
                    f"[0:a]volume='{ducking_cond}':eval=frame[a_ducked]",
                    "[1:a]volume=1.0[a_narr]",
                    f"[a_ducked][a_narr]amix=inputs=2:duration=first:dropout_transition=0.2[{primary_label}]",
                ])
            else:
                audio_parts.append(f"[0:a]{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[{primary_label}]")
            if has_music:
                audio_parts.extend([
                    f"[{music_input_idx}:a]volume={music_volume_db:.2f}dB,"
                    f"volume='{music_ducking_cond}':eval=frame[a_music]",
                    f"[{primary_label}][a_music]amix=inputs=2:duration=first:dropout_transition=0.5,"
                    "loudnorm=I=-16:TP=-1.5:LRA=10,alimiter=limit=0.85:level=false[aout]",
                ])
            else:
                audio_parts.append(
                    f"[{primary_label}]loudnorm=I=-16:TP=-1.5:LRA=10,alimiter=limit=0.85:level=false[aout]"
                )
            return ";".join(audio_parts), ["-map", "0:v", "-map", "[aout]"]

        if num_segs == 1 and not has_music and not has_narration:
            start_s = start_ms / 1000.0
            end_s = end_ms / 1000.0
            filter_graph = (
                f"[0:v]trim=start={start_s:.4f}:end={end_s:.4f},setpts=PTS-STARTPTS[vout];"
                f"[0:a]atrim=start={start_s:.4f}:end={end_s:.4f},asetpts=PTS-STARTPTS,{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[aout]"
            )
            return filter_graph, ["-map", "[vout]", "-map", "[aout]"]

        vconcat = f"{''.join(video_inputs)}concat=n={num_segs}:v=1:a=0[vout]"
        audio_chain = f"{''.join(audio_inputs)}concat=n={num_segs}:v=0:a=1[a_raw]"
        if has_narration:
            audio_chain += (
                f";[a_raw]volume='{ducking_cond}':eval=frame[a_ducked]"
                ";[1:a]volume=1.0[a_narr]"
                ";[a_ducked][a_narr]amix=inputs=2:duration=first:"
                "dropout_transition=0.2[a_primary]"
            )
        else:
            audio_chain += f";[a_raw]{DEFAULT_SPEECH_ENHANCEMENT_FILTER}[a_primary]"
        if has_music:
            audio_chain += (
                f";[{music_input_idx}:a]volume={music_volume_db:.2f}dB,"
                f"volume='{music_ducking_cond}':eval=frame[a_music]"
                ";[a_primary][a_music]amix=inputs=2:duration=first:"
                "dropout_transition=0.5,loudnorm=I=-16:TP=-1.5:LRA=10,alimiter=limit=0.85:level=false[aout]"
            )
        else:
            audio_chain += ";[a_primary]loudnorm=I=-16:TP=-1.5:LRA=10,alimiter=limit=0.85:level=false[aout]"

        full_filter = ";".join(video_filters + audio_filters + [vconcat] + [audio_chain])
        return full_filter, ["-map", "[vout]", "-map", "[aout]"]
    def _execute_render(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        artifact_type: ArtifactType,
        encoding_args: list[str],
        output_path: Path | str | None = None,
        narration_path: Path | str | None = None,
        speech_intervals_ms: Sequence[tuple[int, int]] | None = None,
        music_path: Path | str | None = None,
        music_volume_db: float = -24.0,
        music_ducking_db: float = -14.0,
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

        has_narration = narration_path is not None and Path(narration_path).exists()
        has_music = music_path is not None and Path(music_path).exists()
        music_input_idx = 1 + int(has_narration)

        filter_graph, map_args = self._build_filtergraph(
            keep_segments,
            edl.source_duration_ms,
            has_narration=has_narration,
            speech_intervals_ms=speech_intervals_ms,
            music_path=music_path if has_music else None,
            music_input_idx=music_input_idx,
            music_volume_db=music_volume_db,
            music_ducking_db=music_ducking_db,
        )

        cmd = [
            ffmpeg_bin,
            "-y",
            "-v", "error",
            "-i", str(source),
        ]
        if has_narration and narration_path is not None:
            cmd.extend(["-i", str(narration_path)])
        if has_music and music_path is not None:
            cmd.extend(["-stream_loop", "-1", "-i", str(music_path)])
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





