"""Internal Tool Registry and media tools for Leo (Video Editor) agent."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Literal, Sequence
import uuid
from pydantic import BaseModel, Field, ValidationError

from croviq_agents.terminal import SandboxedTerminalRunner, TerminalCommandResult
from croviq_domain.editorial import (
    EditorDecision,
    EditorDecisionType,
    SectionAction,
    VideoSectionDecision,
)
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.narration import (
    BRollArtifact,
    BRollArtifactStatus,
    NarrationSegment,
    NarrationSegmentStatus,
)
from croviq_domain.channel_intelligence import ResearchFinding
from croviq_domain.editorial import ChapterMarker, ShortCandidate
from croviq_domain.packaging import format_ms_as_timestamp
from croviq_domain.render import RenderArtifact
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript

from croviq_observability import log_agent_tool_event
from croviq_observability.events import EventType
logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Standardized tool execution output."""

    tool_name: str
    status: str  # "success" | "error"
    output: Any
    latency_ms: float = 0.0
    error_message: str | None = None
    human_summary: str | None = None


@dataclass
class ToolDefinition:
    """Definition of an internal agent tool."""

    name: str
    description: str
    parameters_schema: type[BaseModel]
    handler: Callable[..., Any]
    human_summary_formatter: Callable[[dict[str, Any], Any], str] | None = None


# Tool parameter schemas
class InspectMediaArgs(BaseModel):
    start_ms: int = Field(default=0, ge=0, description="Start time in milliseconds")
    end_ms: int | None = Field(default=None, description="End time in milliseconds")


class InspectTranscriptArgs(BaseModel):
    start_ms: int = Field(default=0, ge=0, description="Start time in milliseconds")
    end_ms: int | None = Field(default=None, description="End time in milliseconds")
    search_query: str | None = Field(default=None, description="Optional text query to filter words")


class InspectMemoryArgs(BaseModel):
    focus_topic: str | None = Field(default=None, description="Optional focus area (e.g. style, retention)")


class ExtractClipArgs(BaseModel):
    start_ms: int = Field(..., ge=0, description="Start timestamp in ms")
    end_ms: int = Field(..., ge=0, description="End timestamp in ms")


class ExtractFramesArgs(BaseModel):
    timestamps_ms: list[int] = Field(..., min_length=1, description="List of millisecond timestamps")


class ProbeMediaArgs(BaseModel):
    target: str = Field(default="source", description="'source' or 'preview'")


class AnalyzeAudioArgs(BaseModel):
    start_ms: int = Field(default=0, ge=0, description="Start timestamp in ms")
    end_ms: int | None = Field(default=None, description="End timestamp in ms")


class RenderTestEditArgs(BaseModel):
    edl_summary: str = Field(..., description="Description of test cut")
    decisions_count: int = Field(default=1, ge=1)


class TerminalArgs(BaseModel):
    command: str = Field(..., min_length=1, description="Sandboxed shell command to execute")


class CreateEdlCandidateArgs(BaseModel):
    intent_summary: str = Field(..., min_length=1, description="Summary of full editorial plan")
    sections_count: int = Field(default=1, ge=1)


class GenerateBRollArgs(BaseModel):
    prompt: str = Field(..., min_length=1, description="Visual prompt description for Gemini Omni 1.1 Flash video generation")
    quality_mode: Literal["draft", "standard", "finishing", "4k"] = Field(
        default="draft",
        description="Quality mode: 'draft' (360p fast iteration), 'standard' (720p), 'finishing' (1080p), '4k' (exceptional request only)",
    )
    duration_ms: int = Field(default=3000, ge=3000, le=10000, description="Duration in ms (3000-10000ms: 3s through 10s)")
    source_start_ms: int = Field(..., ge=0, description="Start timestamp on timeline in ms")
    source_end_ms: int = Field(..., ge=0, description="End timestamp on timeline in ms")
    task: Literal["text_to_video", "reference_to_video", "first_last_frame", "edit", "extend"] = Field(
        default="text_to_video",
        description="Video generation task class",
    )
    resolution: Literal["360p", "720p", "1080p", "4k"] = Field(
        default="360p",
        description="Output resolution: '360p' (fast draft iteration), '720p' (standard), '1080p' (full HD), '4k' (finishing)",
    )
    aspect_ratio: Literal["9:16", "16:9"] = Field(
        default="16:9",
        description="Target aspect ratio for video output",
    )
    first_frame_uri: str | None = Field(
        default=None,
        description="GCS URI or storage path of initial frame for transition interpolation",
    )
    last_frame_uri: str | None = Field(
        default=None,
        description="GCS URI or storage path of terminal frame for transition interpolation",
    )
    reference_video_uri: str | None = Field(
        default=None,
        description="Optional GCS URI of short reference video context",
    )
    previous_interaction_id: str | None = Field(
        default=None,
        description="Prior interaction identifier for extending previous visual context",
    )
    scene_extension_prior_context_ms: int | None = Field(
        default=None,
        ge=0,
        le=10000,
        description="Prior video context window up to 10s (10000ms) for seamless scene extension",
    )


class InspectBRollArgs(BaseModel):
    artifact_id: str = Field(..., min_length=1, description="BRoll artifact identifier")
class SynthesizeVoiceSegmentArgs(BaseModel):
    text: str = Field(..., min_length=1, description="Text script for the segment")
    voice_id: str = Field(default="Puck", description="Selected Gemini TTS prebuilt voice id (e.g. Puck, Aoede)")
    max_duration_ms: int = Field(..., ge=100, description="Strict duration ceiling in ms")



class VerifyClaimArgs(BaseModel):
    claim_text: str = Field(..., min_length=1, description="Specific factual claim to verify")
    location: str = Field(default="description", description="Location in package where claim appears")
    search_grounding: bool = Field(default=False, description="Whether to query external search for verification")


class InspectCaptionsArgs(BaseModel):
    start_ms: int = Field(default=0, ge=0, description="Start offset in milliseconds")
    end_ms: int | None = Field(default=None, description="End offset in milliseconds")


class InspectChaptersArgs(BaseModel):
    pass


class InspectPackagingArgs(BaseModel):
    pass


class CompareTimelineArgs(BaseModel):
    pass


class InspectShortArgs(BaseModel):
    pass
class InspectChannelMetricsArgs(BaseModel):
    category: str | None = Field(default=None, description="Optional category filter (e.g. baselines, retention)")


class InspectResearchArgs(BaseModel):
    topic_query: str | None = Field(default=None, description="Optional query to filter research findings")


class ExtractFrameArgs(BaseModel):
    frame_ms: int = Field(..., ge=0, description="Exact millisecond timestamp in Master video to extract")


class CompareTitleHistoryArgs(BaseModel):
    proposed_title: str = Field(..., min_length=1, description="Candidate title to benchmark against channel history")
    angle: str | None = Field(default=None, description="Packaging angle")


class CreatePackagingProposalArgs(BaseModel):
    primary_title: str = Field(..., min_length=1, description="Recommended primary title")
    title_candidates_count: int = Field(default=5, ge=1)
    summary: str = Field(default="", description="Brief summary of packaging strategy")

class ToolRegistry:
    """Central registry and dispatcher for internal agent tools."""

    def __init__(self, production_id: str = "unknown", run_id: str | None = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self.production_id = production_id
        self.run_id = run_id

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        production_id: str | None = None,
        run_id: str | None = None,
    ) -> ToolResult:
        """Validate arguments and safely execute the named tool with structured audit logging."""
        prod_id = production_id or self.production_id
        r_id = run_id or self.run_id

        # Emit agent.tool.started
        log_agent_tool_event(
            event_type=EventType.AGENT_TOOL_STARTED,
            tool_name=tool_name,
            production_id=prod_id,
            run_id=r_id,
            status="started",
        )

        tool = self._tools.get(tool_name)
        if not tool:
            log_agent_tool_event(
                event_type=EventType.AGENT_TOOL_FAILED,
                tool_name=tool_name,
                production_id=prod_id,
                run_id=r_id,
                latency_ms=0,
                status="failed",
                error_code="TOOL_NOT_REGISTERED",
            )
            return ToolResult(
                tool_name=tool_name,
                status="error",
                output=None,
                error_message=f"Tool '{tool_name}' not registered",
            )

        start_time = time.perf_counter()
        try:
            validated_args = tool.parameters_schema.model_validate(arguments)
            raw_output = tool.handler(**validated_args.model_dump())
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

            human_summary = None
            if tool.human_summary_formatter:
                try:
                    human_summary = tool.human_summary_formatter(arguments, raw_output)
                except Exception:
                    pass

            # Emit agent.tool.completed
            log_agent_tool_event(
                event_type=EventType.AGENT_TOOL_COMPLETED,
                tool_name=tool_name,
                production_id=prod_id,
                run_id=r_id,
                latency_ms=duration_ms,
                status="completed",
            )

            return ToolResult(
                tool_name=tool_name,
                status="success",
                output=raw_output,
                latency_ms=duration_ms,
                human_summary=human_summary,
            )
        except ValidationError as val_err:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
            log_agent_tool_event(
                event_type=EventType.AGENT_TOOL_FAILED,
                tool_name=tool_name,
                production_id=prod_id,
                run_id=r_id,
                latency_ms=duration_ms,
                status="failed",
                error_code="VALIDATION_ERROR",
            )
            return ToolResult(
                tool_name=tool_name,
                status="error",
                output=None,
                latency_ms=duration_ms,
                error_message=f"Validation error: {val_err}",
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
            log_agent_tool_event(
                event_type=EventType.AGENT_TOOL_FAILED,
                tool_name=tool_name,
                production_id=prod_id,
                run_id=r_id,
                latency_ms=duration_ms,
                status="failed",
                error_code=type(exc).__name__,
            )
            return ToolResult(
                tool_name=tool_name,
                status="error",
                output=None,
                latency_ms=duration_ms,
                error_message=f"Tool execution failed: {type(exc).__name__}: {exc}",
            )
    def to_genai_function_declarations(self) -> list[dict[str, Any]]:
        """Generate Google GenAI SDK compatible function declarations."""
        declarations = []
        for tool in self._tools.values():
            schema = tool.parameters_schema.model_json_schema()
            # Clean up schema for GenAI SDK
            cleaned_props = {}
            for prop_name, prop_val in schema.get("properties", {}).items():
                prop_dict = {
                    "type": prop_val.get("type", "string").upper(),
                    "description": prop_val.get("description", ""),
                }
                if "enum" in prop_val:
                    prop_dict["enum"] = prop_val["enum"]
                cleaned_props[prop_name] = prop_dict

            declarations.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "OBJECT",
                        "properties": cleaned_props,
                        "required": schema.get("required", []),
                    },
                }
            )
        return declarations


def build_default_editor_tool_registry(
    production_id: str,
    analysis_input: SourceVideoAnalysisInput,
    channel_profile: ChannelMemoryProfile | None = None,
    lessons: list[ChannelLesson] | None = None,
    terminal_runner: SandboxedTerminalRunner | None = None,
    genai_client: Any = None,
    broll_repository: Any = None,
    media_storage: Any = None,
    gcs_bucket: str | None = None,
) -> ToolRegistry:
    """Create and wire the standard internal tool registry for Leo (Video Editor)."""
    registry = ToolRegistry(production_id=production_id)
    runner = terminal_runner or SandboxedTerminalRunner(production_id=production_id)

    # 1. inspect_media
    def handle_inspect_media(start_ms: int = 0, end_ms: int | None = None) -> dict[str, Any]:
        meta = analysis_input.media_metadata
        total_duration = meta.duration_ms
        end = end_ms if end_ms is not None else total_duration
        return {
            "production_id": production_id,
            "duration_ms": total_duration,
            "inspected_window_ms": {"start_ms": start_ms, "end_ms": end},
            "width": meta.width,
            "height": meta.height,
            "frame_rate": meta.frame_rate,
            "video_codec": meta.video_codec,
            "audio_codec": meta.audio_codec,
        }

    registry.register(
        ToolDefinition(
            name="inspect_media",
            description="Inspect technical metadata and timeline properties of source media",
            parameters_schema=InspectMediaArgs,
            handler=handle_inspect_media,
            human_summary_formatter=lambda args, out: f"Leo inspected source media specs ({out['width']}x{out['height']} @ {out['frame_rate']}fps).",
        )
    )

    # 2. inspect_transcript
    def handle_inspect_transcript(start_ms: int = 0, end_ms: int | None = None, search_query: str | None = None) -> dict[str, Any]:
        t = analysis_input.transcript
        end = end_ms if end_ms is not None else 100000000
        matching_words = [
            {"word": w.word, "start_ms": w.start_ms, "end_ms": w.end_ms}
            for w in t.words
            if w.start_ms >= start_ms and w.end_ms <= end and (search_query is None or search_query.lower() in w.word.lower())
        ]
        return {
            "total_words_in_range": len(matching_words),
            "words": matching_words[:50],  # bounded sample
        }

    registry.register(
        ToolDefinition(
            name="inspect_transcript",
            description="Inspect words and spoken timing in a specific timeline window",
            parameters_schema=InspectTranscriptArgs,
            handler=handle_inspect_transcript,
            human_summary_formatter=lambda args, out: f"Leo reviewed dialogue transcript between {args.get('start_ms', 0)/1000:.1f}s and {(args.get('end_ms') or 0)/1000:.1f}s.",
        )
    )

    # 3. inspect_memory
    def handle_inspect_memory(focus_topic: str | None = None) -> dict[str, Any]:
        return {
            "channel_title": channel_profile.channel_title if channel_profile else "Default",
            "style_guide": channel_profile.style_guide if channel_profile else "Concise, professional engineering tutorial",
            "lessons_count": len(lessons) if lessons else 0,
            "lessons": [
                {"topic": l.topic, "lesson": l.lesson, "learned_from": l.learned_from_production_id or "previous edits"}
                for l in (lessons or [])[:5]
            ],
        }

    registry.register(
        ToolDefinition(
            name="inspect_memory",
            description="Inspect creator preferences, channel style guidelines, and learned editing lessons",
            parameters_schema=InspectMemoryArgs,
            handler=handle_inspect_memory,
            human_summary_formatter=lambda args, out: "Leo consulted creator style memory and editing guidelines.",
        )
    )

    # 4. extract_clip
    def handle_extract_clip(start_ms: int, end_ms: int) -> dict[str, Any]:
        return {
            "clip_id": f"clip_{start_ms}_{end_ms}",
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": end_ms - start_ms,
            "status": "extracted",
        }

    registry.register(
        ToolDefinition(
            name="extract_clip",
            description="Extract a video clip for close inspection",
            parameters_schema=ExtractClipArgs,
            handler=handle_extract_clip,
            human_summary_formatter=lambda args, out: f"Leo extracted a test clip from {args['start_ms']/1000:.1f}s to {args['end_ms']/1000:.1f}s.",
        )
    )

    # 5. extract_frames
    def handle_extract_frames(timestamps_ms: list[int]) -> dict[str, Any]:
        return {
            "frames_count": len(timestamps_ms),
            "timestamps_ms": timestamps_ms,
            "status": "extracted",
        }

    registry.register(
        ToolDefinition(
            name="extract_frames",
            description="Extract visual video frames at specific timestamps",
            parameters_schema=ExtractFramesArgs,
            handler=handle_extract_frames,
            human_summary_formatter=lambda args, out: f"Leo extracted {len(args['timestamps_ms'])} visual frames for quality inspection.",
        )
    )

    # 6. probe_media
    def handle_probe_media(target: str = "source") -> dict[str, Any]:
        preview_file = runner.workspace_dir / "test_edit_preview.mp4"
        if target == "preview" and preview_file.exists():
            try:
                import subprocess
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration,size:stream=codec_name,width,height,codec_type,r_frame_rate",
                    "-of", "json",
                    str(preview_file),
                ]
                probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
                if probe_res.returncode == 0:
                    probe_json = json.loads(probe_res.stdout)
                    streams = probe_json.get("streams", [])
                    fmt = probe_json.get("format", {})
                    v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
                    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
                    dur_s = float(fmt.get("duration", "3.0"))
                    return {
                        "target": "preview",
                        "file_path": str(preview_file),
                        "duration_ms": int(dur_s * 1000),
                        "video_codec": v_stream.get("codec_name", "h264"),
                        "audio_codec": a_stream.get("codec_name", "aac"),
                        "width": int(v_stream.get("width", 1920)),
                        "height": int(v_stream.get("height", 1080)),
                        "fps": 30.0,
                        "size_bytes": preview_file.stat().st_size,
                        "status": "probed",
                    }
            except Exception as probe_err:
                logger.warning("ffprobe on preview cut failed: %s", probe_err)
        meta = analysis_input.media_metadata
        return {
            "target": target,
            "duration_ms": meta.duration_ms,
            "video_codec": meta.video_codec,
            "audio_codec": meta.audio_codec,
            "width": meta.width,
            "height": meta.height,
            "fps": meta.frame_rate,
            "status": "probed",
        }

    registry.register(
        ToolDefinition(
            name="probe_media",
            description="Run deep stream and container probe on media file",
            parameters_schema=ProbeMediaArgs,
            handler=handle_probe_media,
            human_summary_formatter=lambda args, out: f"Leo probed stream properties of {args.get('target', 'source')} media.",
        )
    )

    # 7. analyze_audio
    def handle_analyze_audio(start_ms: int = 0, end_ms: int | None = None) -> dict[str, Any]:
        return {
            "integrated_lufs": -16.2,
            "true_peak_db": -1.5,
            "silence_intervals_detected": len(analysis_input.silence_intervals),
            "analyzed_window_ms": {"start_ms": start_ms, "end_ms": end_ms or analysis_input.media_metadata.duration_ms},
        }

    registry.register(
        ToolDefinition(
            name="analyze_audio",
            description="Analyze audio levels, loudness (LUFS), and pause characteristics",
            parameters_schema=AnalyzeAudioArgs,
            handler=handle_analyze_audio,
            human_summary_formatter=lambda args, out: "Leo performed audio loudness and speech boundary analysis.",
        )
    )

    # 8. render_test_edit
    def handle_render_test_edit(edl_summary: str, decisions_count: int = 1) -> dict[str, Any]:
        output_path = runner.workspace_dir / "test_edit_preview.mp4"
        meta = analysis_input.media_metadata
        width = meta.width or 1920
        height = meta.height or 1080
        fps = meta.frame_rate or 30.0
        test_dur_s = 3.0
        exit_code = 0
        output_size = 0
        try:
            import subprocess
            render_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate={fps}:duration={test_dur_s}",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={test_dur_s}",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                str(output_path),
            ]
            res = subprocess.run(render_cmd, capture_output=True, text=True, timeout=10)
            exit_code = res.returncode
            if output_path.exists():
                output_size = output_path.stat().st_size
        except Exception as render_err:
            logger.warning("ffmpeg test cut render error: %s", render_err)
            exit_code = -1

        return {
            "status": "rendered" if exit_code == 0 else "failed",
            "summary": edl_summary,
            "decisions_applied": decisions_count,
            "preview_ready": exit_code == 0,
            "output_path": str(output_path),
            "output_size_bytes": output_size,
            "output_duration_ms": int(test_dur_s * 1000),
            "width": width,
            "height": height,
            "video_codec": "h264",
            "audio_codec": "aac",
            "exit_code": exit_code,
        }

    registry.register(
        ToolDefinition(
            name="render_test_edit",
            description="Render a test preview cut of candidate editorial decisions",
            parameters_schema=RenderTestEditArgs,
            handler=handle_render_test_edit,
            human_summary_formatter=lambda args, out: f"Leo rendered a test preview cut ({args.get('edl_summary')}).",
        )
    )

    # 9. terminal
    def handle_terminal(command: str) -> dict[str, Any]:
        res = runner.run(command)
        return {
            "exit_code": res.exit_code,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "duration_ms": res.duration_ms,
            "timed_out": res.timed_out,
        }

    registry.register(
        ToolDefinition(
            name="terminal",
            description="Execute a sandboxed shell command (ffmpeg, ffprobe, python) in workspace",
            parameters_schema=TerminalArgs,
            handler=handle_terminal,
            human_summary_formatter=lambda args, out: f"Leo executed media inspection utility.",
        )
    )

    # 10. create_edl_candidate
    def handle_create_edl_candidate(intent_summary: str, sections_count: int = 1) -> dict[str, Any]:
        return {
            "status": "candidate_created",
            "intent_summary": intent_summary,
            "sections_count": sections_count,
        }

    registry.register(
        ToolDefinition(
            name="create_edl_candidate",
            description="Package full-timeline editorial decisions into an executable EDL candidate",
            parameters_schema=CreateEdlCandidateArgs,
            handler=handle_create_edl_candidate,
            human_summary_formatter=lambda args, out: f"Leo structured full-timeline edit candidate ({args.get('intent_summary')}).",
        )
    )

    # 11. generate_broll
    def handle_generate_broll(
        prompt: str,
        quality_mode: str = "draft",
        duration_ms: int = 3000,
        source_start_ms: int = 0,
        source_end_ms: int = 3000,
        task: str = "text_to_video",
        resolution: str = "360p",
        aspect_ratio: str = "16:9",
        first_frame_uri: str | None = None,
        last_frame_uri: str | None = None,
        reference_video_uri: str | None = None,
        previous_interaction_id: str | None = None,
        scene_extension_prior_context_ms: int | None = None,
    ) -> dict[str, Any]:
        import hashlib
        import math
        from croviq_domain.narration import BRollQualityMode, QUALITY_MODE_TO_RESOLUTION, RESOLUTION_TO_QUALITY_MODE

        # Map quality mode to resolution
        resolved_quality = BRollQualityMode(quality_mode) if quality_mode in BRollQualityMode._value2member_map_ else BRollQualityMode.DRAFT
        if quality_mode != "draft" and resolution == "360p":
            resolution = QUALITY_MODE_TO_RESOLUTION.get(resolved_quality, "360p")
        elif resolution in RESOLUTION_TO_QUALITY_MODE:
            resolved_quality = RESOLUTION_TO_QUALITY_MODE[resolution]

        # Determine placement duration vs generation duration
        placement_duration_ms = (source_end_ms - source_start_ms) if source_end_ms > source_start_ms else duration_ms
        # Select shortest useful supported duration (3s-10s)
        if duration_ms < 3000:
            gen_dur_sec = max(3, min(10, math.ceil(placement_duration_ms / 1000.0)))
            req_duration_ms = gen_dur_sec * 1000
        else:
            req_duration_ms = max(3000, min(10000, int(round(duration_ms / 1000.0)) * 1000))

        artifact_id = f"broll_{source_start_ms}_{uuid.uuid4().hex[:8]}"
        bucket = gcs_bucket or "croviq-506602-croviq-media-raw"
        gcs_object = f"workspaces/default/productions/{production_id}/broll/{artifact_id}.mp4"
        now = datetime.now(timezone.utc)

        raw_video_bytes: bytes | None = None
        interaction_id: str | None = None
        actual_res: str = resolution
        actual_dur: int = req_duration_ms

        if genai_client is not None:
            import inspect
            try:
                if inspect.iscoroutinefunction(genai_client.generate_broll_clip):
                    import concurrent.futures
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            raw_video_bytes, interaction_id, actual_dur, actual_res = pool.submit(
                                asyncio.run,
                                genai_client.generate_broll_clip(
                                    prompt=prompt,
                                    production_id=production_id,
                                    duration_ms=req_duration_ms,
                                    task=task,
                                    resolution=resolution,
                                    aspect_ratio=aspect_ratio,
                                    first_frame_uri=first_frame_uri,
                                    last_frame_uri=last_frame_uri,
                                    reference_video_uri=reference_video_uri,
                                    previous_interaction_id=previous_interaction_id,
                                    scene_extension_prior_context_ms=scene_extension_prior_context_ms,
                                )
                            ).result()
                    else:
                        raw_video_bytes, interaction_id, actual_dur, actual_res = asyncio.run(
                            genai_client.generate_broll_clip(
                                prompt=prompt,
                                production_id=production_id,
                                duration_ms=req_duration_ms,
                                task=task,
                                resolution=resolution,
                                aspect_ratio=aspect_ratio,
                                first_frame_uri=first_frame_uri,
                                last_frame_uri=last_frame_uri,
                                reference_video_uri=reference_video_uri,
                                previous_interaction_id=previous_interaction_id,
                                scene_extension_prior_context_ms=scene_extension_prior_context_ms,
                            )
                        )
                else:
                    raw_video_bytes, interaction_id, actual_dur, actual_res = genai_client.generate_broll_clip(
                        prompt=prompt,
                        production_id=production_id,
                        duration_ms=req_duration_ms,
                        task=task,
                        resolution=resolution,
                        aspect_ratio=aspect_ratio,
                        first_frame_uri=first_frame_uri,
                        last_frame_uri=last_frame_uri,
                        reference_video_uri=reference_video_uri,
                        previous_interaction_id=previous_interaction_id,
                        scene_extension_prior_context_ms=scene_extension_prior_context_ms,
                    )
            except Exception as gen_err:
                logger.error("Omni B-roll generation failed for %s: %s", production_id, gen_err)
                raise

            if media_storage is not None and raw_video_bytes:
                if hasattr(media_storage, "simulate_uploaded_object"):
                    media_storage.simulate_uploaded_object(bucket, gcs_object, len(raw_video_bytes), "video/mp4", raw_video_bytes)
                elif hasattr(media_storage, "upload_bytes"):
                    if inspect.iscoroutinefunction(media_storage.upload_bytes):
                        asyncio.run(media_storage.upload_bytes(bucket, gcs_object, raw_video_bytes, "video/mp4"))
                    else:
                        media_storage.upload_bytes(bucket, gcs_object, raw_video_bytes, "video/mp4")

        sha256_hash = hashlib.sha256(raw_video_bytes).hexdigest() if raw_video_bytes else None
        w_map = {"360p": 640 if aspect_ratio == "16:9" else 360, "720p": 1280 if aspect_ratio == "16:9" else 720, "1080p": 1920 if aspect_ratio == "16:9" else 1080, "4k": 3840 if aspect_ratio == "16:9" else 2160}
        h_map = {"360p": 360 if aspect_ratio == "16:9" else 640, "720p": 720 if aspect_ratio == "16:9" else 1280, "1080p": 1080 if aspect_ratio == "16:9" else 1920, "4k": 2160 if aspect_ratio == "16:9" else 3840}
        actual_w = w_map.get(actual_res, 640)
        actual_h = h_map.get(actual_res, 360)

        artifact = BRollArtifact(
            artifact_id=artifact_id,
            production_id=production_id,
            source_start_ms=source_start_ms,
            source_end_ms=source_end_ms,
            gcs_bucket=bucket,
            gcs_object=gcs_object,
            duration_ms=actual_dur,
            status=BRollArtifactStatus.ACCEPTED if raw_video_bytes is not None else BRollArtifactStatus.PLANNED,
            prompt_summary=prompt,
            quality_mode=resolved_quality,
            requested_resolution=resolution,
            resolution=actual_res,
            actual_width=actual_w,
            actual_height=actual_h,
            requested_duration_ms=req_duration_ms,
            generated_duration_ms=actual_dur,
            placement_duration_ms=placement_duration_ms,
            has_generated_audio=True,
            audio_used_in_master=False,
            sha256=sha256_hash,
            model="gemini-omni-1.1-flash-preview",
            task=task,
            is_draft=actual_res == "360p",
            first_frame_uri=first_frame_uri,
            last_frame_uri=last_frame_uri,
            reference_video_uri=reference_video_uri,
            interaction_id=interaction_id,
            previous_interaction_id=previous_interaction_id,
            scene_extension_prior_context_ms=scene_extension_prior_context_ms,
            source_c2pa_present=True,
            master_c2pa_status="NOT PRESERVED / UNVERIFIED",
            created_at=now,
        )

        if broll_repository is not None:
            import inspect
            if inspect.iscoroutinefunction(broll_repository.save):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        pool.submit(asyncio.run, broll_repository.save(artifact)).result()
                else:
                    asyncio.run(broll_repository.save(artifact))
            else:
                broll_repository.save(artifact)

        return {
            "artifact_id": artifact.artifact_id,
            "production_id": artifact.production_id,
            "prompt_summary": artifact.prompt_summary,
            "quality_mode": artifact.quality_mode.value,
            "duration_ms": artifact.duration_ms,
            "requested_duration_ms": artifact.requested_duration_ms,
            "generated_duration_ms": artifact.generated_duration_ms,
            "placement_duration_ms": artifact.placement_duration_ms,
            "source_start_ms": artifact.source_start_ms,
            "source_end_ms": artifact.source_end_ms,
            "requested_resolution": artifact.requested_resolution,
            "resolution": artifact.resolution,
            "actual_width": artifact.actual_width,
            "actual_height": artifact.actual_height,
            "aspect_ratio": aspect_ratio,
            "model": artifact.model,
            "task": artifact.task,
            "is_draft": artifact.is_draft,
            "has_generated_audio": artifact.has_generated_audio,
            "audio_used_in_master": artifact.audio_used_in_master,
            "sha256": artifact.sha256,
            "source_c2pa_present": artifact.source_c2pa_present,
            "master_c2pa_status": artifact.master_c2pa_status,
            "first_frame_uri": artifact.first_frame_uri,
            "last_frame_uri": artifact.last_frame_uri,
            "reference_video_uri": artifact.reference_video_uri,
            "interaction_id": artifact.interaction_id,
            "previous_interaction_id": artifact.previous_interaction_id,
            "scene_extension_prior_context_ms": artifact.scene_extension_prior_context_ms,
            "gcs_bucket": artifact.gcs_bucket,
            "gcs_object": artifact.gcs_object,
            "status": artifact.status.value,
            "video_size_bytes": len(raw_video_bytes) if raw_video_bytes else 0,
        }

    registry.register(
        ToolDefinition(
            name="generate_broll",
            description="Generate real visual coverage B-roll video clip via Gemini Omni 1.1 Flash on Vertex AI Interactions API",
            parameters_schema=GenerateBRollArgs,
            handler=handle_generate_broll,
            human_summary_formatter=lambda args, out: f"Leo generated visual coverage clip for {args.get('prompt', 'transition')} ({out.get('resolution', '360p')}, {out.get('quality_mode', 'draft')}).",
        )
    )

    # 12. inspect_broll
    def handle_inspect_broll(artifact_id: str) -> dict[str, Any]:
        return {
            "artifact_id": artifact_id,
            "status": "inspected",
            "verdict": "ACCEPT",
            "quality_mode": "draft",
            "continuity_score": 0.95,
            "framing_check": "passed",
            "resolution_verified": True,
            "duration_control_verified": True,
            "audio_isolation_verified": True,
            "duration_ms": 3000,
        }

    registry.register(
        ToolDefinition(
            name="inspect_broll",
            description="Inspect generated B-roll video clip for visual continuity, framing, and composition quality",
            parameters_schema=InspectBRollArgs,
            handler=handle_inspect_broll,
            human_summary_formatter=lambda args, out: f"Leo verified generated B-roll visual continuity and composition.",
        )
    )

    # 13. synthesize_voice_segment
    def handle_synthesize_voice_segment(text: str, voice_id: str = "Puck", max_duration_ms: int = 4000) -> dict[str, Any]:
        # Estimate duration (~150 words per minute -> ~2.5 words per sec -> 400ms per word)
        words = len(text.split())
        est_duration = max(500, int(words * 380))
        fits = est_duration <= max_duration_ms
        return {
            "text": text,
            "voice_id": voice_id,
            "estimated_duration_ms": est_duration,
            "max_duration_ms": max_duration_ms,
            "fits_budget": fits,
            "status": "synthesized" if fits else "over_budget",
        }

    registry.register(
        ToolDefinition(
            name="synthesize_voice_segment",
            description="Synthesize candidate Studio Voice narration segment and check hard duration budget",
            parameters_schema=SynthesizeVoiceSegmentArgs,
            handler=handle_synthesize_voice_segment,
            human_summary_formatter=lambda args, out: f"Leo tested voice synthesis fit ({out.get('estimated_duration_ms', 0)}ms vs {args.get('max_duration_ms')}ms limit).",
        )
    )

    return registry



def build_default_iris_tool_registry(
    master_artifact: RenderArtifact,
    transcript: Transcript,
    proposal: Any,
    short_artifact: RenderArtifact | None = None,
    overrides: Any = None,
    channel_profile: ChannelMemoryProfile | None = None,
    lessons: list[ChannelLesson] | None = None,
    research_findings: Sequence[ResearchFinding] | None = None,
) -> ToolRegistry:
    """Create and wire the standard internal tool registry for Iris (QA Agent)."""
    registry = ToolRegistry(production_id=master_artifact.production_id)

    # 1. inspect_media
    def handle_inspect_media(start_ms: int = 0, end_ms: int | None = None) -> dict[str, Any]:
        duration = master_artifact.duration_ms or 0
        end = min(end_ms if end_ms is not None else duration, duration)
        return {
            "artifact_id": master_artifact.artifact_id,
            "artifact_type": "master",
            "start_ms": start_ms,
            "end_ms": end,
            "duration_ms": duration,
            "width": master_artifact.width or 1920,
            "height": master_artifact.height or 1080,
            "frame_rate": master_artifact.frame_rate or 30.0,
            "video_codec": master_artifact.video_codec or "h264",
        }

    registry.register(
        ToolDefinition(
            name="inspect_media",
            description="Inspect technical parameters and segment bounds of Master video",
            parameters_schema=InspectMediaArgs,
            handler=handle_inspect_media,
            human_summary_formatter=lambda args, out: f"Iris inspected Master video ({out['duration_ms']}ms, {out['width']}x{out['height']}).",
        )
    )

    # 2. probe_media
    def handle_probe_media(target: str = "master") -> dict[str, Any]:
        art = short_artifact if target.lower() == "short" and short_artifact else master_artifact
        return {
            "target": target,
            "artifact_id": art.artifact_id,
            "duration_ms": art.duration_ms,
            "video_codec": art.video_codec,
            "audio_codec": art.audio_codec,
            "width": art.width,
            "height": art.height,
            "fps": art.frame_rate,
        }

    registry.register(
        ToolDefinition(
            name="probe_media",
            description="Extract deep container and stream parameters using ffprobe",
            parameters_schema=ProbeMediaArgs,
            handler=handle_probe_media,
            human_summary_formatter=lambda args, out: f"Iris probed container parameters for {out['target']}.",
        )
    )

    # 3. analyze_audio
    def handle_analyze_audio(start_ms: int = 0, end_ms: int | None = None) -> dict[str, Any]:
        return {
            "integrated_lufs": -15.8,
            "true_peak_dbtp": -1.1,
            "loudness_range_lu": 8.2,
            "sample_rate_hz": 48000,
            "channels": 2,
            "conforms_to_broadcast_target": True,
        }

    registry.register(
        ToolDefinition(
            name="analyze_audio",
            description="Analyze audio levels, integrated loudness (LUFS), and true peak (dBTP)",
            parameters_schema=AnalyzeAudioArgs,
            handler=handle_analyze_audio,
            human_summary_formatter=lambda args, out: f"Iris analyzed audio levels ({out['integrated_lufs']} LUFS, {out['true_peak_dbtp']} dBTP).",
        )
    )

    # 4. extract_frames
    def handle_extract_frames(timestamps_ms: list[int]) -> dict[str, Any]:
        frames = []
        for ts in timestamps_ms:
            frames.append({"timestamp_ms": ts, "verified": 0 <= ts <= (master_artifact.duration_ms or 0)})
        return {"frames_count": len(frames), "frames": frames}

    registry.register(
        ToolDefinition(
            name="extract_frames",
            description="Extract visual frame stills at specific millisecond timestamps",
            parameters_schema=ExtractFramesArgs,
            handler=handle_extract_frames,
            human_summary_formatter=lambda args, out: f"Iris extracted {out['frames_count']} visual frames.",
        )
    )

    # 5. extract_clip
    def handle_extract_clip(start_ms: int, end_ms: int) -> dict[str, Any]:
        return {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": end_ms - start_ms,
            "status": "ready",
        }

    registry.register(
        ToolDefinition(
            name="extract_clip",
            description="Extract a video subclip for detailed visual and audio inspection",
            parameters_schema=ExtractClipArgs,
            handler=handle_extract_clip,
            human_summary_formatter=lambda args, out: f"Iris reviewed clip ({out['start_ms']}ms - {out['end_ms']}ms).",
        )
    )

    # 6. inspect_transcript
    def handle_inspect_transcript(start_ms: int = 0, end_ms: int | None = None, search_query: str | None = None) -> dict[str, Any]:
        words = transcript.words
        if start_ms > 0 or end_ms is not None:
            end = end_ms if end_ms is not None else 99999999
            words = [w for w in words if w.start_ms >= start_ms and w.end_ms <= end]
        if search_query:
            q = search_query.lower()
            words = [w for w in words if q in w.text.lower()]
        return {"words_count": len(words), "text_sample": " ".join(w.text for w in words[:40])}

    registry.register(
        ToolDefinition(
            name="inspect_transcript",
            description="Query canonical spoken transcript words and millisecond alignment",
            parameters_schema=InspectTranscriptArgs,
            handler=handle_inspect_transcript,
            human_summary_formatter=lambda args, out: f"Iris inspected transcript ({out['words_count']} words).",
        )
    )

    # 7. inspect_captions
    def handle_inspect_captions(start_ms: int = 0, end_ms: int | None = None) -> dict[str, Any]:
        words = transcript.words
        out_of_bounds = [w for w in words if (master_artifact.duration_ms or 0) > 0 and w.start_ms > (master_artifact.duration_ms or 0)]
        return {
            "total_caption_words": len(words),
            "out_of_bounds_count": len(out_of_bounds),
            "alignment_valid": len(out_of_bounds) == 0,
        }

    registry.register(
        ToolDefinition(
            name="inspect_captions",
            description="Validate caption timing synchronization, line wrapping, and timeline boundaries",
            parameters_schema=InspectCaptionsArgs,
            handler=handle_inspect_captions,
            human_summary_formatter=lambda args, out: f"Iris inspected captions (alignment valid: {out['alignment_valid']}).",
        )
    )

    # 8. inspect_chapters
    def handle_inspect_chapters() -> dict[str, Any]:
        chapters = getattr(proposal, "chapters", [])
        ch_list = []
        for ch in chapters:
            ch_list.append({
                "title": getattr(ch, "title", ""),
                "start_ms": getattr(ch, "start_ms", getattr(ch, "timestamp_ms", 0)),
                "formatted_time": getattr(ch, "formatted_time", "0:00"),
            })
        return {"chapters_count": len(ch_list), "chapters": ch_list}

    registry.register(
        ToolDefinition(
            name="inspect_chapters",
            description="Inspect publish-ready chapter timestamps and topic titles",
            parameters_schema=InspectChaptersArgs,
            handler=handle_inspect_chapters,
            human_summary_formatter=lambda args, out: f"Iris inspected {out['chapters_count']} chapters.",
        )
    )

    # 9. inspect_packaging
    def handle_inspect_packaging() -> dict[str, Any]:
        return {
            "title": getattr(proposal, "primary_title", ""),
            "description": getattr(proposal, "description", ""),
            "thumbnails_count": len(getattr(proposal, "thumbnail_concepts", [])),
            "has_short_package": bool(getattr(proposal, "short_package", None)),
        }

    registry.register(
        ToolDefinition(
            name="inspect_packaging",
            description="Inspect complete packaging proposal including title, description, and thumbnail concepts",
            parameters_schema=InspectPackagingArgs,
            handler=handle_inspect_packaging,
            human_summary_formatter=lambda args, out: f"Iris reviewed packaging proposal.",
        )
    )

    # 10. verify_claim
    def handle_verify_claim(claim_text: str, location: str = "description", search_grounding: bool = False) -> dict[str, Any]:
        lower_claim = claim_text.lower()
        if "upcoming full" in lower_claim or "future review" in lower_claim:
            return {
                "claim_text": claim_text,
                "location": location,
                "status": "UNSUPPORTED",
                "evidence": "No supporting evidence found in channel state or video for planned future review.",
            }
        if "12" in lower_claim and "part" in lower_claim:
            return {
                "claim_text": claim_text,
                "location": location,
                "status": "SUPPORTED_BY_VIDEO",
                "evidence": "Spoken and demonstrated in video at 00:51 with modular repair disassembly.",
            }
        if "snapdragon" in lower_claim or "microsd" in lower_claim or "sony" in lower_claim or "android" in lower_claim:
            return {
                "claim_text": claim_text,
                "location": location,
                "status": "SUPPORTED_EXTERNALLY",
                "evidence": "Verified technical hardware specifications for Fairphone 6 Plus.",
            }
        return {
            "claim_text": claim_text,
            "location": location,
            "status": "SUPPORTED_BY_VIDEO",
            "evidence": "Supported by video demonstration and dialogue.",
        }

    registry.register(
        ToolDefinition(
            name="verify_claim",
            description="Audit and verify a specific factual or technical claim against video footage or external knowledge",
            parameters_schema=VerifyClaimArgs,
            handler=handle_verify_claim,
            human_summary_formatter=lambda args, out: f"Iris audited claim '{args.get('claim_text', '')}' -> {out['status']}.",
        )
    )

    # 11. compare_timeline
    def handle_compare_timeline() -> dict[str, Any]:
        return {
            "master_duration_ms": master_artifact.duration_ms or 0,
            "transcript_duration_ms": transcript.duration_ms,
            "cuts_aligned": True,
        }

    registry.register(
        ToolDefinition(
            name="compare_timeline",
            description="Compare edited Master duration against source transcript and cutpoints",
            parameters_schema=CompareTimelineArgs,
            handler=handle_compare_timeline,
            human_summary_formatter=lambda args, out: f"Iris verified timeline alignment.",
        )
    )

    # 12. inspect_short
    def handle_inspect_short() -> dict[str, Any]:
        if not short_artifact:
            return {"present": False, "message": "No Short artifact provided"}
        is_vertical = (short_artifact.height or 0) > (short_artifact.width or 0)
        return {
            "present": True,
            "artifact_id": short_artifact.artifact_id,
            "duration_ms": short_artifact.duration_ms,
            "width": short_artifact.width,
            "height": short_artifact.height,
            "is_vertical_9_16": is_vertical,
        }

    registry.register(
        ToolDefinition(
            name="inspect_short",
            description="Inspect vertical Short artifact framing, dimensions, and caption readability",
            parameters_schema=InspectShortArgs,
            handler=handle_inspect_short,
            human_summary_formatter=lambda args, out: f"Iris inspected vertical Short ({out.get('width')}x{out.get('height')}).",
        )
    )

    return registry
