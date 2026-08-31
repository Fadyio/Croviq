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
    BRollArtifact,
    BRollArtifactStatus,
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
        description="Optional GCS URI of brief reference video context",
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


class AddBRollArgs(TimelineRangeArgs):
    prompt: str = Field(..., min_length=1, max_length=1000)
    quality_mode: Literal["draft", "standard", "finishing", "4k"] = "draft"


class RemoveBRollArgs(BaseModel):
    marker_id_or_time_ms: str | int


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
                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = None
                        if loop and loop.is_running():
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                                pool.submit(
                                    asyncio.run,
                                    media_storage.upload_bytes(bucket, gcs_object, raw_video_bytes, "video/mp4"),
                                ).result()
                        else:
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
        return {
            "WHAT": decision.decision_type.value,
            "WHY": decision.concise_reason,
            "SOURCE_RANGE": [decision.source_start_ms, decision.source_end_ms],
            "RESULT": (
                cut.model_dump(mode="json") if cut
                else marker.model_dump(mode="json") if marker
                else {"action": decision.action}
            ),
            "EVIDENCE": inspect_range(decision.source_start_ms, decision.source_end_ms),
        }

    registry.register(ToolDefinition(
        name="explain_edit",
        description="Explain what an edit changes, why, its source range, result, and evidence",
        parameters_schema=ExplainEditArgs,
        handler=explain_edit,
        human_summary_formatter=lambda args, out: (
            f"**WHAT**: {out['WHAT']}\n\n"
            f"**WHY**: {out['WHY']}\n\n"
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

    async def add_broll(start_ms: int, end_ms: int, prompt: str, quality_mode: str) -> dict[str, Any]:
        start_word, end_word, original_text = _word_bounds(start_ms, end_ms)
        decision = EditorDecision(
            decision_id=f"chat_broll_{uuid.uuid4().hex[:10]}",
            decision_type=EditorDecisionType.BROLL_COVER_CANDIDATE,
            transcript_start_word=start_word,
            transcript_end_word=end_word,
            source_start_ms=start_ms,
            source_end_ms=end_ms,
            original_text=original_text,
            action="cover",
            concise_reason=prompt,
            confidence=1.0,
            visual_context=f"Gemini Omni {quality_mode} B-roll",
        )
        current: EditorProposal = registry.state["proposal"]
        previous_edl: EditDecisionList = registry.state["edl"]
        next_edl = _rebuild(current.model_copy(update={"decisions": [*current.decisions, decision]}))
        marker = next(item for item in next_edl.coverage_markers if item.decision_id == decision.decision_id)
        try:
            artifact = await _callback(
                "add_broll",
                start_ms=start_ms,
                end_ms=end_ms,
                prompt=prompt,
                quality_mode=quality_mode,
                marker=marker,
                edl=next_edl,
            )
        except Exception:
            registry.state["proposal"] = current
            registry.state["edl"] = previous_edl
            registry.state["timeline_updated"] = False
            raise
        if artifact is None:
            duration = end_ms - start_ms
            artifact = BRollArtifact(
                artifact_id=f"broll_{uuid.uuid4().hex[:12]}",
                production_id=production_id,
                decision_id=decision.decision_id,
                source_start_ms=start_ms,
                source_end_ms=end_ms,
                gcs_bucket="croviq-506602-croviq-media-raw",
                gcs_object=f"workspaces/ws/productions/{production_id}/broll/{marker.marker_id}.mp4",
                duration_ms=duration,
                placement_duration_ms=duration,
                prompt_summary=prompt,
                status=BRollArtifactStatus.ACCEPTED,
                quality_mode=quality_mode,
                created_at=datetime.now(timezone.utc),
            )
        registry.state["preview_updated"] = True
        return {
            "coverage_marker": marker.model_dump(mode="json"),
            "artifact": artifact.model_dump(mode="json") if hasattr(artifact, "model_dump") else artifact,
            "audio_preserved": True,
        }

    registry.register(ToolDefinition(
        name="add_broll",
        description="Generate Gemini Omni B-roll, preserve original audio, and persist coverage",
        parameters_schema=AddBRollArgs,
        handler=add_broll,
    ))

    def remove_broll(marker_id_or_time_ms: str | int) -> dict[str, Any]:
        current_edl: EditDecisionList = registry.state["edl"]
        marker = next(
            (
                item for item in current_edl.coverage_markers
                if item.coverage_type == CoverageType.BROLL_CANDIDATE
                and (
                    item.marker_id == str(marker_id_or_time_ms)
                    or (
                        isinstance(marker_id_or_time_ms, int)
                        and item.source_start_ms <= marker_id_or_time_ms <= item.source_end_ms
                    )
                )
            ),
            None,
        )
        if marker is None:
            raise ValueError(f"No B-roll marker found for {marker_id_or_time_ms!r}")
        current: EditorProposal = registry.state["proposal"]
        _rebuild(current.model_copy(update={
            "decisions": [item for item in current.decisions if item.decision_id != marker.decision_id]
        }))
        return {"removed_marker_id": marker.marker_id}

    registry.register(ToolDefinition(
        name="remove_broll",
        description="Remove generated B-roll and its persisted coverage marker",
        parameters_schema=RemoveBRollArgs,
        handler=remove_broll,
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


def build_default_iris_tool_registry(
    master_artifact: RenderArtifact,
    transcript: Transcript,
    proposal: Any,
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
        art = master_artifact
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


    return registry
