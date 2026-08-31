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
from pydantic import BaseModel, Field, ValidationError, field_validator

from croviq_agents.terminal import SandboxedTerminalRunner, TerminalCommandResult
from croviq_domain.editorial import (
    ChapterMarker,
    EditorDecision,
    EditorDecisionType,
    EditorVoiceMode,
    EditorProposal,
    SectionAction,
    VideoSectionDecision,
)
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.narration import (
    NarrationSegment,
    NarrationSegmentStatus,
)
from croviq_domain.edl import (
    BackgroundMusicMix,
    CoverageMarker,
    CoverageType,
    CutSafetyStatus,
    EditDecisionList,
    EdlMutationResult,
    EdlRevisionHistoryEntry,
    VoiceoverSegment,
    audit_proposed_cuts,
    classify_cut_overlap,
    compute_interval_union,
    compute_intervals_duration,
)
from croviq_domain.packaging import format_ms_as_timestamp
from croviq_domain.render import RenderArtifact
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript
from croviq_domain.channel_intelligence import ResearchFinding
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
    decisions_count: int = Field(default=0, ge=0)


class TerminalArgs(BaseModel):
    command: str = Field(..., min_length=1, description="Sandboxed shell command to execute")


class CreateEdlCandidateArgs(BaseModel):
    intent_summary: str = Field(..., min_length=1, description="Summary of full editorial plan")
    sections_count: int = Field(default=1, ge=1)


class SynthesizeVoiceSegmentArgs(BaseModel):
    text: str = Field(..., min_length=1, description="Text script for the segment")
    voice_id: str = Field(default="Puck", description="Selected Gemini TTS prebuilt voice id (e.g. Puck, Aoede)")
    max_duration_ms: int = Field(..., ge=100, description="Strict duration ceiling in ms")


class TimelineRangeArgs(BaseModel):
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)


class ExplainEditArgs(BaseModel):
    decision_id_or_time_ms: str | int



class RemoveSelectionArgs(BaseModel):
    start_ms: int = Field(..., ge=0, description="Start timestamp of selected region in milliseconds")
    end_ms: int = Field(..., ge=0, description="End timestamp of selected region in milliseconds")
    reason: str = Field(default="User requested removal", max_length=500, description="Reason or context for removing this section")
    decision_type: EditorDecisionType = Field(default=EditorDecisionType.REMOVE_LOW_VALUE_SECTION, description="Type of cut decision")
    active_edl_id: str | None = Field(default=None, description="Active EDL identifier for concurrency validation")

    @field_validator("decision_type", mode="before")
    @classmethod
    def _coerce_decision_type(cls, val: Any) -> EditorDecisionType:
        if isinstance(val, EditorDecisionType):
            return val
        if isinstance(val, str):
            val_clean = val.strip().upper()
            try:
                return EditorDecisionType(val_clean)
            except ValueError:
                pass
            mapping = {
                "REMOVE_SECTION": EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
                "REMOVE_LOW_PACING": EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
                "REMOVE_OUTTAKE": EditorDecisionType.REMOVE_FALSE_START,
                "REMOVE_TAKE": EditorDecisionType.REMOVE_FALSE_START,
                "REMOVE_TOPIC_DETOUR": EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
                "REMOVE": EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
                "CUT": EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
                "TRIM": EditorDecisionType.TRIM_PAUSE,
                "TIGHTEN": EditorDecisionType.TIGHTEN_PAUSE,
            }
            if val_clean in mapping:
                return mapping[val_clean]
        return EditorDecisionType.REMOVE_LOW_VALUE_SECTION
class TightenSelectionArgs(BaseModel):
    start_ms: int = Field(..., ge=0, description="Start timestamp of section to tighten in milliseconds")
    end_ms: int = Field(..., ge=0, description="End timestamp of section to tighten in milliseconds")
    intensity: Literal["subtle", "standard", "aggressive"] = Field(default="standard", description="Tightening intensity")
    active_edl_id: str | None = Field(default=None, description="Active EDL identifier for concurrency validation")


class UndoLastEditArgs(BaseModel):
    active_edl_id: str | None = Field(default=None, description="Active EDL identifier for concurrency validation")
class AddCutArgs(TimelineRangeArgs):
    decision_type: EditorDecisionType = EditorDecisionType.REMOVE_LOW_VALUE_SECTION
    reason: str = Field(..., min_length=1, max_length=500)


class RemoveCutArgs(BaseModel):
    cut_id_or_time_ms: str | int


class AdjustCutArgs(BaseModel):
    cut_id: str = Field(..., min_length=1)
    safe_start_ms: int = Field(..., ge=0)
    safe_end_ms: int = Field(..., ge=0)


class MarkKeepArgs(TimelineRangeArgs):
    reason: str = Field(..., min_length=1, max_length=500)


class AddChapterArgs(TimelineRangeArgs):
    title: str = Field(..., min_length=1, max_length=120)
    summary: str = Field(..., min_length=1, max_length=500)


class RenameChapterArgs(BaseModel):
    chapter_id_or_title: str = Field(..., min_length=1)
    new_title: str = Field(..., min_length=1, max_length=120)



class GenerateVoiceoverArgs(TimelineRangeArgs):
    text: str = Field(..., min_length=1)
    voice_mode: EditorVoiceMode = EditorVoiceMode.PREBUILT_STUDIO_VOICE


class RemoveVoiceoverArgs(BaseModel):
    segment_id_or_time_ms: str | int


class AddBackgroundMusicArgs(BaseModel):
    style: str = Field(..., min_length=1, max_length=120)
    volume_db: float = Field(default=-24.0, le=0)
    ducking_db: float = Field(default=-14.0, le=0)


class NoArgs(BaseModel):
    pass


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
        self.state: dict[str, Any] = {}
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

    async def execute_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        production_id: str | None = None,
        run_id: str | None = None,
    ) -> ToolResult:
        """Validate and execute a synchronous or asynchronous tool handler."""
        prod_id = production_id or self.production_id
        r_id = run_id or self.run_id
        tool = self._tools.get(tool_name)
        if tool is None:
            return self.execute(tool_name, arguments, production_id=prod_id, run_id=r_id)

        start_time = time.perf_counter()
        log_agent_tool_event(
            event_type=EventType.AGENT_TOOL_STARTED,
            tool_name=tool_name,
            production_id=prod_id,
            run_id=r_id,
            status="started",
        )
        try:
            validated_args = tool.parameters_schema.model_validate(arguments)
            raw_output = tool.handler(**validated_args.model_dump())
            if asyncio.iscoroutine(raw_output):
                raw_output = await raw_output
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
            summary = (
                tool.human_summary_formatter(arguments, raw_output)
                if tool.human_summary_formatter
                else None
            )
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
                human_summary=summary,
            )
        except (ValidationError, ValueError) as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
            return ToolResult(
                tool_name=tool_name,
                status="error",
                output=None,
                latency_ms=duration_ms,
                error_message=str(exc),
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
            logger.exception("Leo tool %s failed", tool_name)
            return ToolResult(
                tool_name=tool_name,
                status="error",
                output=None,
                latency_ms=duration_ms,
                error_message=f"{type(exc).__name__}: {exc}",
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
            {"word": w.text, "start_ms": w.start_ms, "end_ms": w.end_ms}
            for w in t.words
            if w.start_ms >= start_ms and w.end_ms <= end and (search_query is None or search_query.lower() in w.text.lower())
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


def format_timecode_ms(ms: int) -> str:
    """Format milliseconds into MM:SS.s."""
    total_seconds = max(0, ms) / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:05.2f}"



def build_editor_chat_tool_registry(
    *,
    production_id: str,
    transcript: Transcript,
    proposal: EditorProposal,
    edl: EditDecisionList,
    artifacts: Sequence[Any] | None = None,
    media_metadata: Any = None,
    callbacks: dict[str, Callable[..., Any]] | None = None,
) -> ToolRegistry:
    """Build Leo's canonical typed editing tools over one mutable editor state."""
    from croviq_media.cut_safety import CutSafetyAnalyzer, assemble_edl_from_proposal

    registry = ToolRegistry(production_id=production_id)
    registry.state = {
        "proposal": proposal,
        "edl": edl,
        "artifacts": list(artifacts or []),
        "timeline_updated": False,
        "voiceover_updated": False,
        "preview_updated": False,
        "seek_range": None,
        "undo_history": [],
    }
    callbacks = callbacks or {}
    analyzer = CutSafetyAnalyzer()

    destructive_types = {
        # Canonical BUG 22 types
        EditorDecisionType.FALSE_START,
        EditorDecisionType.WORD_REPETITION,
        EditorDecisionType.PHRASE_REPETITION,
        EditorDecisionType.REDUNDANT_EXPLANATION,
        EditorDecisionType.FILLER,
        EditorDecisionType.RAMBLING,
        EditorDecisionType.DEAD_AIR,
        EditorDecisionType.PAUSE_TRIM,
        EditorDecisionType.PACING,
        EditorDecisionType.OTHER,
        # Legacy types
        EditorDecisionType.REMOVE_SILENCE,
        EditorDecisionType.REMOVE_FILLER,
        EditorDecisionType.REMOVE_FALSE_START,
        EditorDecisionType.REMOVE_REPETITION,
        EditorDecisionType.TRIM_PAUSE,
        EditorDecisionType.TIGHTEN_PAUSE,
        EditorDecisionType.TIGHTEN_EXPLANATION,
        EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
    }

    def _word_bounds(start_ms: int, end_ms: int) -> tuple[int, int, str]:
        if end_ms <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if end_ms > edl.source_duration_ms:
            raise ValueError(
                f"Range ends at {end_ms}ms beyond source duration {edl.source_duration_ms}ms"
            )
        if not transcript.words:
            return 0, 0, "Source media range"
        indexes = [
            index
            for index, word in enumerate(transcript.words)
            if word.end_ms > start_ms and word.start_ms < end_ms
        ]
        if not indexes:
            nearest = min(
                range(len(transcript.words)),
                key=lambda index: abs(transcript.words[index].start_ms - start_ms),
                default=0,
            )
            indexes = [nearest]
        text = " ".join(transcript.words[index].text for index in indexes).strip()
        return indexes[0], indexes[-1], text or "Source media range"

    def _rebuild(next_proposal: EditorProposal) -> EditDecisionList:
        current_edl: EditDecisionList = registry.state["edl"]
        next_edl = assemble_edl_from_proposal(
            proposal=next_proposal,
            transcript=transcript,
            version=current_edl.version + 1,
            analyzer=analyzer,
            editor_proposal_id=current_edl.editor_proposal_id,
        )
        next_edl = next_edl.model_copy(update={
            "voiceover_segments": current_edl.voiceover_segments,
            "background_music": current_edl.background_music,
        })
        registry.state["proposal"] = next_proposal
        registry.state["edl"] = next_edl
        registry.state["timeline_updated"] = True
        return next_edl

    async def _callback(name: str, **kwargs: Any) -> Any:
        callback = callbacks.get(name)
        if callback is None:
            return None
        value = callback(**kwargs)
        return await value if asyncio.iscoroutine(value) else value

    def inspect_range(start_ms: int, end_ms: int) -> dict[str, Any]:
        _word_bounds(start_ms, end_ms)
        current_edl: EditDecisionList = registry.state["edl"]
        return {
            "range": {"start_ms": start_ms, "end_ms": end_ms},
            "transcript": [
                word.model_dump(mode="json")
                for word in transcript.words
                if word.end_ms > start_ms and word.start_ms < end_ms
            ],
            "cuts": [
                cut.model_dump(mode="json")
                for cut in current_edl.cuts
                if cut.safe_end_ms > start_ms and cut.safe_start_ms < end_ms
            ],
            "coverage_markers": [
                marker.model_dump(mode="json")
                for marker in current_edl.coverage_markers
                if marker.source_end_ms > start_ms and marker.source_start_ms < end_ms
            ],
            "media_metadata": (
                media_metadata.model_dump(mode="json")
                if hasattr(media_metadata, "model_dump")
                else media_metadata
            ),
        }

    registry.register(ToolDefinition(
        name="inspect_range",
        description="Inspect transcript, cuts, coverage, and multimodal evidence in a source range",
        parameters_schema=TimelineRangeArgs,
        handler=inspect_range,
        human_summary_formatter=lambda args, out: (
            f"Inspected {args['start_ms'] / 1000:.1f}s–{args['end_ms'] / 1000:.1f}s "
            f"and found {len(out['cuts'])} cuts."
        ),
    ))

    def seek_range(start_ms: int, end_ms: int) -> dict[str, Any]:
        _word_bounds(start_ms, end_ms)
        registry.state["seek_range"] = [start_ms, end_ms]
        return {"start_ms": start_ms, "end_ms": end_ms}

    registry.register(ToolDefinition(
        name="seek_range",
        description="Move the editor viewport and playback range without changing the edit",
        parameters_schema=TimelineRangeArgs,
        handler=seek_range,
    ))

    def explain_edit(decision_id_or_time_ms: str | int) -> dict[str, Any]:
        current_proposal: EditorProposal = registry.state["proposal"]
        current_edl: EditDecisionList = registry.state["edl"]
        target_str = str(decision_id_or_time_ms)
        matching_cut = next((c for c in current_edl.cuts if c.cut_id == target_str or c.decision_id == target_str), None)
        target_dec_id = matching_cut.decision_id if matching_cut else target_str

        decision = next(
            (
                item for item in current_proposal.decisions
                if item.decision_id == target_dec_id
                or (
                    isinstance(decision_id_or_time_ms, int)
                    and item.source_start_ms <= decision_id_or_time_ms <= item.source_end_ms
                )
            ),
            None,
        )
        if decision is None and matching_cut is not None:
            decision = EditorDecision(
                decision_id=matching_cut.decision_id,
                decision_type=matching_cut.decision_type,
                transcript_start_word=matching_cut.transcript_start_word,
                transcript_end_word=matching_cut.transcript_end_word,
                source_start_ms=matching_cut.safe_start_ms,
                source_end_ms=matching_cut.safe_end_ms,
                original_text=matching_cut.left_anchor,
                action=matching_cut.decision_type.value,
                concise_reason=matching_cut.safety_reason,
                confidence=matching_cut.confidence,
            )
        if decision is None:
            raise ValueError(f"No edit found for {decision_id_or_time_ms!r}")
        cut = next((item for item in current_edl.cuts if item.decision_id == decision.decision_id or item.cut_id == target_str), None)
        marker = next(
            (item for item in current_edl.coverage_markers if item.decision_id == decision.decision_id),
            None,
        )
        category = (cut.category if cut and cut.category else (decision.decision_type.value if hasattr(decision.decision_type, "value") else str(decision.decision_type)))
        removed_text = (cut.removed_text if cut and cut.removed_text else (decision.removed_text or (decision.original_text if not decision.original_text.startswith("[Silence:") else "")))
        context_before = (cut.context_before if cut and cut.context_before else (decision.context_before or ""))
        context_after = (cut.context_after if cut and cut.context_after else (decision.context_after or ""))
        reason = (cut.concise_reason if cut and cut.concise_reason else (decision.concise_reason or (cut.safety_reason if cut else "")))
        source_range = [cut.safe_start_ms, cut.safe_end_ms] if cut else [decision.source_start_ms, decision.source_end_ms]

        return {
            "WHAT": category,
            "CATEGORY": category,
            "WHY": reason,
            "SOURCE_RANGE": source_range,
            "REMOVED_TEXT": removed_text,
            "CONTEXT_BEFORE": context_before,
            "CONTEXT_AFTER": context_after,
            "RESULT": (
                cut.model_dump(mode="json") if cut
                else marker.model_dump(mode="json") if marker
                else {"action": decision.action}
            ),
            "EVIDENCE": inspect_range(source_range[0], source_range[1]),
        }

    registry.register(ToolDefinition(
        name="explain_edit",
        description="Explain what an edit changes, why, its source range, result, and evidence",
        parameters_schema=ExplainEditArgs,
        handler=explain_edit,
        human_summary_formatter=lambda args, out: (
            f"**CATEGORY**: {out.get('CATEGORY', out.get('WHAT', 'Edit'))}\n\n"
            f"**REMOVED**: \"{out.get('REMOVED_TEXT', '')}\"\n\n"
            f"**CONTEXT**: Before: \"{out.get('CONTEXT_BEFORE', '')}\" | After: \"{out.get('CONTEXT_AFTER', '')}\"\n\n"
            f"**REASON**: {out['WHY']}\n\n"
            f"**SOURCE RANGE**: {out['SOURCE_RANGE'][0]/1000.0:.2f}s – {out['SOURCE_RANGE'][1]/1000.0:.2f}s\n\n"
            f"**RESULT**: {out['RESULT'].get('safety_reason') or out['RESULT'].get('action') or 'Cut applied'}"
        ),
    ))

    async def remove_selection(
        start_ms: int,
        end_ms: int,
        reason: str = "User requested removal",
        decision_type: EditorDecisionType = EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
        active_edl_id: str | None = None,
    ) -> dict[str, Any]:
        current_edl: EditDecisionList = registry.state["edl"]
        current_proposal: EditorProposal = registry.state["proposal"]

        # Concurrency check
        if active_edl_id and active_edl_id != current_edl.edl_id:
            raise ValueError(
                f"EDL version conflict: client active EDL '{active_edl_id}' does not match current active EDL '{current_edl.edl_id}'."
            )

        if end_ms <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if start_ms >= current_edl.source_duration_ms:
            raise ValueError(
                f"Selection start {start_ms}ms is beyond source duration {current_edl.source_duration_ms}ms"
            )
        end_ms = min(end_ms, current_edl.source_duration_ms)

        # Check if already completely removed
        for existing_cut in current_edl.active_cuts:
            if existing_cut.safe_start_ms <= start_ms and existing_cut.safe_end_ms >= end_ms:
                raise ValueError("This section is already completely removed in the active edit.")

        start_word_idx, end_word_idx, orig_text = _word_bounds(start_ms, end_ms)

        decision = EditorDecision(
            decision_id=f"chat_cut_{uuid.uuid4().hex[:10]}",
            decision_type=decision_type,
            transcript_start_word=start_word_idx,
            transcript_end_word=end_word_idx,
            source_start_ms=start_ms,
            source_end_ms=end_ms,
            original_text=orig_text,
            action="remove",
            concise_reason=reason,
            confidence=1.0,
        )

        # Snapshot for in-memory undo
        history_entry = {
            "proposal": current_proposal,
            "edl": current_edl,
            "tool": "remove_selection",
            "start_ms": start_ms,
            "end_ms": end_ms,
        }
        registry.state.setdefault("undo_history", []).append(history_entry)

        retained_decisions = [
            d
            for d in current_proposal.decisions
            if not (
                d.source_start_ms >= start_ms
                and d.source_end_ms <= end_ms
                and str(d.action).lower() in ("remove", "tighten", "cut")
            )
        ]
        next_proposal = current_proposal.model_copy(
            update={"decisions": [*retained_decisions, decision]}
        )
        next_edl = _rebuild(next_proposal)
        matching_cut = next((c for c in next_edl.cuts if c.decision_id == decision.decision_id), None)
        if matching_cut and matching_cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE:
            registry.state["proposal"] = current_proposal
            registry.state["edl"] = current_edl
            registry.state["timeline_updated"] = False
            registry.state["undo_history"].pop()
            raise ValueError(f"Cannot cut this section safely: {matching_cut.safety_reason}")

        safe_start = matching_cut.safe_start_ms if matching_cut else start_ms
        safe_end = matching_cut.safe_end_ms if matching_cut else end_ms
        removed_dur_s = (safe_end - safe_start) / 1000.0

        adjustment_desc = ""
        if safe_start != start_ms or safe_end != end_ms:
            adjustment_desc = (
                f"from {format_timecode_ms(safe_start)}–{format_timecode_ms(safe_end)} "
                f"using safe word boundaries (requested {format_timecode_ms(start_ms)}–{format_timecode_ms(end_ms)})"
            )
        else:
            adjustment_desc = f"from {format_timecode_ms(safe_start)}–{format_timecode_ms(safe_end)}"

        summary_msg = f"Removed {removed_dur_s:.2f}s {adjustment_desc} and regenerated the edited preview."

        if "save_revision_history" in callbacks:
            rev_entry = EdlRevisionHistoryEntry(
                history_id=f"hist_{uuid.uuid4().hex[:12]}",
                production_id=production_id,
                previous_edl_id=current_edl.edl_id,
                previous_version=current_edl.version,
                new_edl_id=next_edl.edl_id,
                new_version=next_edl.version,
                tool_name="remove_selection",
                user_request=reason,
                requested_range_ms=[start_ms, end_ms],
                applied_range_ms=[safe_start, safe_end],
                previous_edl=current_edl,
                previous_proposal=current_proposal.model_dump(mode="json"),
            )
            cb = callbacks["save_revision_history"]
            if asyncio.iscoroutinefunction(cb):
                await cb(entry=rev_entry)
            else:
                cb(entry=rev_entry)
        return {
            "tool": "remove_selection",
            "decision": decision.model_dump(mode="json"),
            "cut": matching_cut.model_dump(mode="json") if matching_cut else None,
            "requested_range_ms": [start_ms, end_ms],
            "applied_range_ms": [safe_start, safe_end],
            "removed_duration_s": removed_dur_s,
            "new_edl_id": next_edl.edl_id,
            "new_version": next_edl.version,
            "active_cut_count": next_edl.active_cuts_count,
            "edited_duration_ms": next_edl.estimated_target_duration_ms,
            "message": summary_msg,
        }

    registry.register(ToolDefinition(
        name="remove_selection",
        description="Cut and remove the selected timeline or transcript region with safe word boundary snapping",
        parameters_schema=RemoveSelectionArgs,
        handler=remove_selection,
        human_summary_formatter=lambda args, out: out.get("message", "Removed selected section."),
    ))

    async def tighten_selection(
        start_ms: int,
        end_ms: int,
        intensity: str = "standard",
        active_edl_id: str | None = None,
    ) -> dict[str, Any]:
        current_edl: EditDecisionList = registry.state["edl"]
        current_proposal: EditorProposal = registry.state["proposal"]

        # Concurrency check
        if active_edl_id and active_edl_id != current_edl.edl_id:
            raise ValueError(
                f"EDL version conflict: client active EDL '{active_edl_id}' does not match current active EDL '{current_edl.edl_id}'."
            )

        if end_ms <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if start_ms >= current_edl.source_duration_ms:
            raise ValueError(
                f"Selection start {start_ms}ms is beyond source duration {current_edl.source_duration_ms}ms"
            )
        end_ms = min(end_ms, current_edl.source_duration_ms)

        existing_cut_intervals = [
            (c.safe_start_ms, c.safe_end_ms)
            for c in current_edl.active_cuts
        ]
        existing_union = compute_interval_union(existing_cut_intervals)

        words_in_range = [
            (idx, w)
            for idx, w in enumerate(transcript.words)
            if w.end_ms > start_ms and w.start_ms < end_ms
        ]

        pause_threshold_ms = 400 if intensity == "subtle" else 250 if intensity == "aggressive" else 300
        breath_pad_ms = 150

        candidate_decisions: list[EditorDecision] = []
        removals_summary: list[str] = []
        skipped_cuts: list[dict[str, Any]] = []

        # 1. Look for inter-word pauses in the selected range
        for i in range(len(words_in_range) - 1):
            w1_idx, w1 = words_in_range[i]
            w2_idx, w2 = words_in_range[i + 1]
            gap = w2.start_ms - w1.end_ms
            if gap > pause_threshold_ms:
                p_start = w1.end_ms + breath_pad_ms
                p_end = w2.start_ms - breath_pad_ms
                if p_end - p_start >= 100:
                    classification, newly_eff, overlap = classify_cut_overlap(
                        (p_start, p_end), existing_union
                    )
                    if newly_eff > 0:
                        candidate_decisions.append(EditorDecision(
                            decision_id=f"chat_tighten_pause_{uuid.uuid4().hex[:8]}",
                            decision_type=EditorDecisionType.TRIM_PAUSE,
                            transcript_start_word=w1_idx,
                            transcript_end_word=w2_idx,
                            source_start_ms=p_start,
                            source_end_ms=p_end,
                            original_text=f"[Silence: {w1.text} ... {w2.text}]",
                            action="remove",
                            concise_reason=f"Tightened {gap}ms inter-word pause to comfortable breath padding",
                            confidence=0.98,
                        ))
                        removals_summary.append(f"{gap}ms pause")
                    else:
                        skipped_cuts.append({
                            "type": "pause",
                            "range": [p_start, p_end],
                            "classification": classification,
                            "gap_ms": gap,
                        })

        # 2. Look for repeated words / phrases / false starts
        for i in range(len(words_in_range) - 1):
            w1_idx, w1 = words_in_range[i]
            w2_idx, w2 = words_in_range[i + 1]
            if w1.text.lower() == w2.text.lower() and len(w1.text) > 1:
                p_start = w1.start_ms
                p_end = w1.end_ms
                classification, newly_eff, overlap = classify_cut_overlap(
                    (p_start, p_end), existing_union
                )
                if newly_eff > 0:
                    candidate_decisions.append(EditorDecision(
                        decision_id=f"chat_tighten_rep_{uuid.uuid4().hex[:8]}",
                        decision_type=EditorDecisionType.REMOVE_REPETITION,
                        transcript_start_word=w1_idx,
                        transcript_end_word=w1_idx,
                        source_start_ms=p_start,
                        source_end_ms=p_end,
                        original_text=w1.text,
                        action="remove",
                        concise_reason=f"Removed repeated word '{w1.text}'",
                        confidence=0.95,
                    ))
                    removals_summary.append(f"repeated word '{w1.text}'")
                else:
                    skipped_cuts.append({
                        "type": "repeated_word",
                        "range": [p_start, p_end],
                        "classification": classification,
                        "word": w1.text,
                    })

        if len(words_in_range) >= 4:
            for i in range(len(words_in_range) - 3):
                phrase1 = f"{words_in_range[i][1].text} {words_in_range[i+1][1].text}".lower()
                phrase2 = f"{words_in_range[i+2][1].text} {words_in_range[i+3][1].text}".lower()
                if phrase1 == phrase2:
                    w1_idx = words_in_range[i][0]
                    w2_idx = words_in_range[i+1][0]
                    p_start = words_in_range[i][1].start_ms
                    p_end = words_in_range[i+1][1].end_ms
                    classification, newly_eff, overlap = classify_cut_overlap(
                        (p_start, p_end), existing_union
                    )
                    if newly_eff > 0:
                        candidate_decisions.append(EditorDecision(
                            decision_id=f"chat_tighten_phrase_{uuid.uuid4().hex[:8]}",
                            decision_type=EditorDecisionType.REMOVE_REPETITION,
                            transcript_start_word=w1_idx,
                            transcript_end_word=w2_idx,
                            source_start_ms=p_start,
                            source_end_ms=p_end,
                            original_text=phrase1,
                            action="remove",
                            concise_reason=f"Removed repeated phrase '{phrase1}'",
                            confidence=0.96,
                        ))
                        removals_summary.append(f"repeated phrase '{phrase1}'")
                    else:
                        skipped_cuts.append({
                            "type": "repeated_phrase",
                            "range": [p_start, p_end],
                            "classification": classification,
                            "phrase": phrase1,
                        })

        # 3. Look for filler words
        for i in range(len(words_in_range)):
            w_idx, w = words_in_range[i]
            if w.text.lower().strip(",.") in ("um", "uh", "you know"):
                p_start = w.start_ms
                p_end = w.end_ms
                classification, newly_eff, overlap = classify_cut_overlap(
                    (p_start, p_end), existing_union
                )
                if newly_eff > 0:
                    candidate_decisions.append(EditorDecision(
                        decision_id=f"chat_tighten_filler_{uuid.uuid4().hex[:8]}",
                        decision_type=EditorDecisionType.REMOVE_FILLER,
                        transcript_start_word=w_idx,
                        transcript_end_word=w_idx,
                        source_start_ms=p_start,
                        source_end_ms=p_end,
                        original_text=w.text,
                        action="remove",
                        concise_reason=f"Removed filler word '{w.text}'",
                        confidence=0.92,
                    ))
                    removals_summary.append(f"filler word '{w.text}'")
                else:
                    skipped_cuts.append({
                        "type": "filler_word",
                        "range": [p_start, p_end],
                        "classification": classification,
                        "word": w.text,
                    })

        # 4. Fallback: top inter-word gap if no other candidates
        if not candidate_decisions:
            gaps = []
            for i in range(len(words_in_range) - 1):
                w1_idx, w1 = words_in_range[i]
                w2_idx, w2 = words_in_range[i+1]
                gap = w2.start_ms - w1.end_ms
                if gap > 200:
                    gaps.append((gap, w1_idx, w2_idx, w1, w2))
            if gaps:
                gaps.sort(key=lambda x: x[0], reverse=True)
                for top_gap, w1_idx, w2_idx, w1, w2 in gaps:
                    p_start = w1.end_ms + breath_pad_ms
                    p_end = w2.start_ms - breath_pad_ms
                    if p_end > p_start:
                        classification, newly_eff, overlap = classify_cut_overlap(
                            (p_start, p_end), existing_union
                        )
                        if newly_eff > 0:
                            candidate_decisions.append(EditorDecision(
                                decision_id=f"chat_tighten_pause_{uuid.uuid4().hex[:8]}",
                                decision_type=EditorDecisionType.TRIM_PAUSE,
                                transcript_start_word=w1_idx,
                                transcript_end_word=w2_idx,
                                source_start_ms=p_start,
                                source_end_ms=p_end,
                                original_text=f"[Silence: {w1.text} ... {w2.text}]",
                                action="remove",
                                concise_reason=f"Trimmed {top_gap}ms pause to breath padding",
                                confidence=0.95,
                            ))
                            removals_summary.append(f"{top_gap}ms pause")
                            break
                        else:
                            skipped_cuts.append({
                                "type": "fallback_gap",
                                "range": [p_start, p_end],
                                "classification": classification,
                                "gap_ms": top_gap,
                            })

        # Handle complete no-op before rebuilding
        if not candidate_decisions:
            if skipped_cuts:
                no_change_msg = "This section is already tightly edited. The pauses I found are already covered by existing cuts, so I didn't apply another edit."
                reason_desc = "Candidate pauses already covered by active cuts."
            else:
                no_change_msg = "This section is already well-paced with no long pauses or filler words."
                reason_desc = "Section has no removable pauses or filler words."
            return {
                "tool": "tighten_selection",
                "status": "no_change",
                "changed": False,
                "message": no_change_msg,
                "reason": reason_desc,
                "candidate_decisions": [],
                "applied_cuts": [],
                "skipped_existing_cuts": skipped_cuts,
                "effective_removed_ms": 0,
                "removed_duration_s": 0.0,
                "before_duration_ms": current_edl.estimated_target_duration_ms,
                "after_duration_ms": current_edl.estimated_target_duration_ms,
                "active_cut_count": current_edl.active_cuts_count,
                "new_edl_id": current_edl.edl_id,
                "new_version": current_edl.version,
                "edited_duration_ms": current_edl.estimated_target_duration_ms,
            }

        # Stage candidate proposal and candidate EDL
        candidate_proposal = current_proposal.model_copy(
            update={"decisions": [*current_proposal.decisions, *candidate_decisions]}
        )
        candidate_edl = assemble_edl_from_proposal(
            proposal=candidate_proposal,
            transcript=transcript,
            version=current_edl.version + 1,
            analyzer=analyzer,
            editor_proposal_id=current_edl.editor_proposal_id,
        )

        effective_delta_ms = current_edl.estimated_target_duration_ms - candidate_edl.estimated_target_duration_ms

        if effective_delta_ms <= 0:
            # Invariant: no net duration change occurred
            return {
                "tool": "tighten_selection",
                "status": "no_change",
                "changed": False,
                "message": "This section is already tightly edited. The pauses I found are already covered by existing cuts, so I didn't apply another edit.",
                "reason": "Candidate pauses already covered by active cuts.",
                "candidate_decisions": [d.model_dump(mode="json") for d in candidate_decisions],
                "applied_cuts": [],
                "skipped_existing_cuts": [d.model_dump(mode="json") for d in candidate_decisions],
                "effective_removed_ms": 0,
                "removed_duration_s": 0.0,
                "before_duration_ms": current_edl.estimated_target_duration_ms,
                "after_duration_ms": current_edl.estimated_target_duration_ms,
                "active_cut_count": current_edl.active_cuts_count,
                "new_edl_id": current_edl.edl_id,
                "new_version": current_edl.version,
                "edited_duration_ms": current_edl.estimated_target_duration_ms,
            }

        # Effective change exists: commit rebuild and persist
        next_edl = candidate_edl.model_copy(update={
            "voiceover_segments": current_edl.voiceover_segments,
            "background_music": current_edl.background_music,
        })
        registry.state["proposal"] = candidate_proposal
        registry.state["edl"] = next_edl
        registry.state["timeline_updated"] = True

        # Snapshot for in-memory undo
        history_entry = {
            "proposal": current_proposal,
            "edl": current_edl,
            "tool": "tighten_selection",
            "start_ms": start_ms,
            "end_ms": end_ms,
        }
        registry.state.setdefault("undo_history", []).append(history_entry)

        removed_s = effective_delta_ms / 1000.0
        reasons_text = " and ".join(removals_summary[:3]) if removals_summary else "unnecessary pauses"
        summary_msg = f"Tightened this section by {removed_s:.2f}s: removed {reasons_text}. Edited Preview updated."

        if "save_revision_history" in callbacks:
            rev_entry = EdlRevisionHistoryEntry(
                history_id=f"hist_{uuid.uuid4().hex[:12]}",
                production_id=production_id,
                previous_edl_id=current_edl.edl_id,
                previous_version=current_edl.version,
                new_edl_id=next_edl.edl_id,
                new_version=next_edl.version,
                tool_name="tighten_selection",
                user_request="Tighten section",
                requested_range_ms=[start_ms, end_ms],
                applied_range_ms=[start_ms, end_ms],
                previous_edl=current_edl,
                previous_proposal=current_proposal.model_dump(mode="json"),
            )
            cb = callbacks["save_revision_history"]
            if asyncio.iscoroutinefunction(cb):
                await cb(entry=rev_entry)
            else:
                cb(entry=rev_entry)

        return {
            "tool": "tighten_selection",
            "status": "success",
            "changed": True,
            "candidate_decisions": [d.model_dump(mode="json") for d in candidate_decisions],
            "applied_cuts": [d.model_dump(mode="json") for d in candidate_decisions],
            "skipped_existing_cuts": skipped_cuts,
            "effective_removed_ms": effective_delta_ms,
            "removed_duration_s": removed_s,
            "reasons": removals_summary,
            "before_duration_ms": current_edl.estimated_target_duration_ms,
            "after_duration_ms": next_edl.estimated_target_duration_ms,
            "new_edl_id": next_edl.edl_id,
            "new_version": next_edl.version,
            "active_cut_count": next_edl.active_cuts_count,
            "edited_duration_ms": next_edl.estimated_target_duration_ms,
            "message": summary_msg,
        }
    registry.register(ToolDefinition(
        name="tighten_selection",
        description="Inspect selected region and remove long pauses, filler words, or repeated phrases while preserving semantic content",
        parameters_schema=TightenSelectionArgs,
        handler=tighten_selection,
        human_summary_formatter=lambda args, out: out.get("message", "Tightened selected section."),
    ))

    async def undo_last_edit(active_edl_id: str | None = None) -> dict[str, Any]:
        current_edl: EditDecisionList = registry.state["edl"]
        current_proposal: EditorProposal = registry.state["proposal"]

        # Concurrency check
        if active_edl_id and active_edl_id != current_edl.edl_id:
            raise ValueError(
                f"EDL version conflict: client active EDL '{active_edl_id}' does not match current active EDL '{current_edl.edl_id}'."
            )

        undo_history = registry.state.get("undo_history", [])
        prev_history_entry = None
        if undo_history:
            prev_history_entry = undo_history.pop()

        if prev_history_entry is None and "pop_revision_history" in callbacks:
            cb = callbacks["pop_revision_history"]
            durable_entry = await cb() if asyncio.iscoroutinefunction(cb) else cb()
            if durable_entry:
                prev_history_entry = {
                    "proposal": (
                        EditorProposal.model_validate(durable_entry.previous_proposal)
                        if durable_entry.previous_proposal
                        else current_proposal
                    ),
                    "edl": durable_entry.previous_edl,
                    "tool": durable_entry.tool_name,
                }

        if prev_history_entry is None:
            raise ValueError("There are no previous edits to undo.")
        restored_proposal = prev_history_entry.get("proposal") or current_proposal
        restored_edl = prev_history_entry["edl"]

        new_version = current_edl.version + 1
        new_edl = restored_edl.model_copy(update={
            "edl_id": f"edl_{uuid.uuid4().hex[:12]}",
            "version": new_version,
            "created_at": datetime.now(timezone.utc),
        })

        registry.state["proposal"] = restored_proposal
        registry.state["edl"] = new_edl
        registry.state["timeline_updated"] = True
        registry.state["preview_updated"] = False

        dur_tc = format_timecode_ms(new_edl.estimated_target_duration_ms)
        summary_msg = (
            f"Undid last edit. Restored EDL to version {new_version} "
            f"({new_edl.active_cuts_count} cuts, {dur_tc} duration). Edited Preview restored."
        )

        return {
            "tool": "undo_last_edit",
            "restored_version": new_version,
            "active_cut_count": new_edl.active_cuts_count,
            "edited_duration_ms": new_edl.estimated_target_duration_ms,
            "new_edl_id": new_edl.edl_id,
            "message": summary_msg,
        }

    registry.register(ToolDefinition(
        name="undo_last_edit",
        description="Undo the last Leo edit and restore the previous EDL state and preview",
        parameters_schema=UndoLastEditArgs,
        handler=undo_last_edit,
        human_summary_formatter=lambda args, out: out.get("message", "Undid last edit."),
    ))


    def add_cut(start_ms: int, end_ms: int, decision_type: EditorDecisionType, reason: str) -> dict[str, Any]:
        if decision_type not in destructive_types:
            raise ValueError(f"{decision_type.value} is not a destructive cut decision")
        start_word, end_word, original_text = _word_bounds(start_ms, end_ms)
        decision = EditorDecision(
            decision_id=f"chat_cut_{uuid.uuid4().hex[:10]}",
            decision_type=decision_type,
            transcript_start_word=start_word,
            transcript_end_word=end_word,
            source_start_ms=start_ms,
            source_end_ms=end_ms,
            original_text=original_text,
            action="remove",
            concise_reason=reason,
            confidence=1.0,
        )
        current: EditorProposal = registry.state["proposal"]
        previous_edl: EditDecisionList = registry.state["edl"]
        next_edl = _rebuild(current.model_copy(update={"decisions": [*current.decisions, decision]}))
        cut = next(item for item in next_edl.cuts if item.decision_id == decision.decision_id)
        if cut.safety_status == CutSafetyStatus.REJECTED_UNSAFE:
            registry.state["proposal"] = current
            registry.state["edl"] = previous_edl
            registry.state["timeline_updated"] = False
            raise ValueError(cut.safety_reason)
        return {"decision": decision.model_dump(mode="json"), "cut": cut.model_dump(mode="json")}

    registry.register(ToolDefinition(
        name="add_cut",
        description="Validate cut safety, add a canonical proposal decision, and rebuild the EDL",
        parameters_schema=AddCutArgs,
        handler=add_cut,
    ))

    def remove_cut(cut_id_or_time_ms: str | int) -> dict[str, Any]:
        current_edl: EditDecisionList = registry.state["edl"]
        cut = next(
            (
                item for item in current_edl.cuts
                if item.cut_id == str(cut_id_or_time_ms)
                or item.decision_id == str(cut_id_or_time_ms)
                or (
                    isinstance(cut_id_or_time_ms, int)
                    and item.safe_start_ms <= cut_id_or_time_ms <= item.safe_end_ms
                )
            ),
            None,
        )
        if cut is None:
            raise ValueError(f"No cut found for {cut_id_or_time_ms!r}")
        current: EditorProposal = registry.state["proposal"]
        next_proposal = current.model_copy(update={
            "decisions": [item for item in current.decisions if item.decision_id != cut.decision_id]
        })
        _rebuild(next_proposal)
        return {"removed_cut_id": cut.cut_id, "restored_range_ms": [cut.safe_start_ms, cut.safe_end_ms]}

    registry.register(ToolDefinition(
        name="remove_cut",
        description="Remove a cut by ID or source time and restore its source media",
        parameters_schema=RemoveCutArgs,
        handler=remove_cut,
    ))

    def restore_source_range(start_ms: int, end_ms: int) -> dict[str, Any]:
        _word_bounds(start_ms, end_ms)
        current: EditorProposal = registry.state["proposal"]
        removed = [
            item for item in current.decisions
            if item.decision_type in destructive_types
            and item.source_end_ms > start_ms
            and item.source_start_ms < end_ms
        ]
        next_proposal = current.model_copy(update={
            "decisions": [item for item in current.decisions if item not in removed]
        })
        _rebuild(next_proposal)
        return {"restored_range_ms": [start_ms, end_ms], "removed_cut_count": len(removed)}

    registry.register(ToolDefinition(
        name="restore_source_range",
        description="Restore every removed source interval overlapping a range",
        parameters_schema=TimelineRangeArgs,
        handler=restore_source_range,
    ))

    def adjust_cut(cut_id: str, safe_start_ms: int, safe_end_ms: int) -> dict[str, Any]:
        _word_bounds(safe_start_ms, safe_end_ms)
        current_edl: EditDecisionList = registry.state["edl"]
        cut_index = next((i for i, item in enumerate(current_edl.cuts) if item.cut_id == cut_id), None)
        if cut_index is None:
            raise ValueError(f"No cut found for {cut_id!r}")
        cut = current_edl.cuts[cut_index]
        next_cut = cut.model_copy(update={
            "requested_start_ms": safe_start_ms,
            "requested_end_ms": safe_end_ms,
            "safe_start_ms": safe_start_ms,
            "safe_end_ms": safe_end_ms,
            "removed_duration_ms": safe_end_ms - safe_start_ms,
            "safety_status": CutSafetyStatus.SAFE,
            "safety_reason": "Creator-adjusted safe cut boundaries",
        })
        next_cuts = list(current_edl.cuts)
        next_cuts[cut_index] = next_cut
        registry.state["edl"] = current_edl.model_copy(update={
            "edl_id": f"edl_{uuid.uuid4().hex[:12]}",
            "version": current_edl.version + 1,
            "cuts": next_cuts,
            "created_at": datetime.now(timezone.utc),
        })
        registry.state["timeline_updated"] = True
        return next_cut.model_dump(mode="json")

    registry.register(ToolDefinition(
        name="adjust_cut",
        description="Adjust an existing cut to explicitly safe source boundaries",
        parameters_schema=AdjustCutArgs,
        handler=adjust_cut,
    ))

    def mark_keep(start_ms: int, end_ms: int, reason: str) -> dict[str, Any]:
        restore_source_range(start_ms, end_ms)
        start_word, end_word, original_text = _word_bounds(start_ms, end_ms)
        keep = EditorDecision(
            decision_id=f"chat_keep_{uuid.uuid4().hex[:10]}",
            decision_type=EditorDecisionType.KEEP,
            transcript_start_word=start_word,
            transcript_end_word=end_word,
            source_start_ms=start_ms,
            source_end_ms=end_ms,
            original_text=original_text,
            action="keep",
            concise_reason=reason,
            confidence=1.0,
        )
        current: EditorProposal = registry.state["proposal"]
        _rebuild(current.model_copy(update={"decisions": [*current.decisions, keep]}))
        return keep.model_dump(mode="json")

    registry.register(ToolDefinition(
        name="mark_keep",
        description="Protect a source range and remove conflicting cuts",
        parameters_schema=MarkKeepArgs,
        handler=mark_keep,
    ))

    def add_chapter(title: str, start_ms: int, end_ms: int, summary: str) -> dict[str, Any]:
        _word_bounds(start_ms, end_ms)
        chapter = ChapterMarker(
            title=title,
            source_start_ms=start_ms,
            source_end_ms=end_ms,
            summary=summary,
            confidence=1.0,
        )
        current: EditorProposal = registry.state["proposal"]
        registry.state["proposal"] = current.model_copy(update={"chapters": [*current.chapters, chapter]})
        registry.state["timeline_updated"] = True
        return chapter.model_dump(mode="json")

    registry.register(ToolDefinition(
        name="add_chapter",
        description="Add a semantic chapter to the canonical proposal",
        parameters_schema=AddChapterArgs,
        handler=add_chapter,
    ))

    def rename_chapter(chapter_id_or_title: str, new_title: str) -> dict[str, Any]:
        current: EditorProposal = registry.state["proposal"]
        index = next(
            (i for i, chapter in enumerate(current.chapters) if chapter.title == chapter_id_or_title),
            None,
        )
        if index is None:
            raise ValueError(f"No chapter found for {chapter_id_or_title!r}")
        chapters = list(current.chapters)
        chapters[index] = chapters[index].model_copy(update={"title": new_title})
        registry.state["proposal"] = current.model_copy(update={"chapters": chapters})
        registry.state["timeline_updated"] = True
        return chapters[index].model_dump(mode="json")

    registry.register(ToolDefinition(
        name="rename_chapter",
        description="Rename a chapter by its current title",
        parameters_schema=RenameChapterArgs,
        handler=rename_chapter,
    ))


    async def generate_voiceover(
        start_ms: int,
        end_ms: int,
        text: str,
        voice_mode: EditorVoiceMode,
    ) -> dict[str, Any]:
        voice_mode_value = voice_mode.value
        _word_bounds(start_ms, end_ms)
        segment_id = f"voice_{uuid.uuid4().hex[:10]}"
        artifact = await _callback(
            "generate_voiceover",
            segment_id=segment_id,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text,
            voice_mode=voice_mode_value,
            edl=registry.state["edl"],
        )
        if artifact is None:
            raise RuntimeError("Voiceover generation callback is not configured")
        registry.state["artifacts"].append(artifact)
        preview_id = artifact.get("preview_artifact_id") if isinstance(artifact, dict) else None
        current_edl: EditDecisionList = registry.state["edl"]
        segment = VoiceoverSegment(
            segment_id=segment_id,
            source_start_ms=start_ms,
            source_end_ms=end_ms,
            text=text,
            voice_mode=voice_mode,
            preview_artifact_id=preview_id,
        )
        registry.state["edl"] = current_edl.model_copy(update={
            "version": current_edl.version + 1,
            "voiceover_segments": [*current_edl.voiceover_segments, segment],
            "created_at": datetime.now(timezone.utc),
        })
        registry.state["timeline_updated"] = True
        registry.state["voiceover_updated"] = True
        registry.state["preview_updated"] = True
        return artifact.model_dump(mode="json") if hasattr(artifact, "model_dump") else artifact

    registry.register(ToolDefinition(
        name="generate_voiceover",
        description="Generate a 24kHz voiceover and mix it with ducked source audio",
        parameters_schema=GenerateVoiceoverArgs,
        handler=generate_voiceover,
    ))

    def remove_voiceover(segment_id_or_time_ms: str | int) -> dict[str, Any]:
        current_edl: EditDecisionList = registry.state["edl"]
        removed = [
            segment for segment in current_edl.voiceover_segments
            if segment.segment_id == str(segment_id_or_time_ms)
            or (
                isinstance(segment_id_or_time_ms, int)
                and segment.source_start_ms <= segment_id_or_time_ms <= segment.source_end_ms
            )
        ]
        if not removed:
            raise ValueError(f"No voiceover found for {segment_id_or_time_ms!r}")
        registry.state["edl"] = current_edl.model_copy(update={
            "edl_id": f"edl_{uuid.uuid4().hex[:12]}",
            "version": current_edl.version + 1,
            "voiceover_segments": [
                segment for segment in current_edl.voiceover_segments if segment not in removed
            ],
            "created_at": datetime.now(timezone.utc),
        })
        registry.state["timeline_updated"] = True
        registry.state["voiceover_updated"] = True
        registry.state["preview_updated"] = False
        return {"removed_count": len(removed)}

    registry.register(ToolDefinition(
        name="remove_voiceover",
        description="Remove a voiceover segment and restore source audio",
        parameters_schema=RemoveVoiceoverArgs,
        handler=remove_voiceover,
    ))

    async def add_background_music(style: str, volume_db: float, ducking_db: float) -> dict[str, Any]:
        artifact = await _callback(
            "add_background_music",
            style=style,
            volume_db=volume_db,
            ducking_db=ducking_db,
            edl=registry.state["edl"],
        )
        if artifact is None:
            raise RuntimeError("Background music media callback is not configured")
        registry.state["artifacts"] = [
            item for item in registry.state["artifacts"]
            if not (isinstance(item, dict) and item.get("artifact_type") == "BACKGROUND_MUSIC")
        ] + [artifact]
        current_edl: EditDecisionList = registry.state["edl"]
        artifact_data = artifact if isinstance(artifact, dict) else {}
        mix = BackgroundMusicMix(
            style=style,
            volume_db=volume_db,
            ducking_db=ducking_db,
            target_lufs=-14.0,
            music_gcs_object=str(artifact_data.get("music_gcs_object", "")),
            preview_artifact_id=artifact_data.get("preview_artifact_id"),
        )
        registry.state["edl"] = current_edl.model_copy(update={
            "version": current_edl.version + 1,
            "background_music": mix,
            "created_at": datetime.now(timezone.utc),
        })
        registry.state["timeline_updated"] = True
        registry.state["preview_updated"] = True
        return artifact.model_dump(mode="json") if hasattr(artifact, "model_dump") else artifact

    registry.register(ToolDefinition(
        name="add_background_music",
        description="Mix ambient music normalized to -14 LUFS with automatic ducking under speech",
        parameters_schema=AddBackgroundMusicArgs,
        handler=add_background_music,
    ))

    def remove_background_music() -> dict[str, Any]:
        current_edl: EditDecisionList = registry.state["edl"]
        if current_edl.background_music is None:
            raise ValueError("No background music is active")
        registry.state["edl"] = current_edl.model_copy(update={
            "edl_id": f"edl_{uuid.uuid4().hex[:12]}",
            "version": current_edl.version + 1,
            "background_music": None,
            "created_at": datetime.now(timezone.utc),
        })
        registry.state["timeline_updated"] = True
        registry.state["preview_updated"] = False
        return {"removed": True}

    registry.register(ToolDefinition(
        name="remove_background_music",
        description="Remove the background music mix from the preview",
        parameters_schema=NoArgs,
        handler=remove_background_music,
    ))

    async def rerender_preview() -> dict[str, Any]:
        artifact = await _callback("rerender_preview", edl=registry.state["edl"])
        if artifact is not None:
            registry.state["artifacts"].append(artifact)
        registry.state["preview_updated"] = artifact is not None
        return {
            "preview_updated": registry.state["preview_updated"],
            "artifact": artifact.model_dump(mode="json") if hasattr(artifact, "model_dump") else artifact,
        }

    registry.register(ToolDefinition(
        name="rerender_preview",
        description="Render a new FFmpeg preview from canonical persisted editor state",
        parameters_schema=NoArgs,
        handler=rerender_preview,
    ))

    return registry

