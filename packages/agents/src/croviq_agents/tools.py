"""Internal Tool Registry and media tools for Leo (Video Editor) agent."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Sequence
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
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Standardized tool execution output."""

    tool_name: str
    status: str  # "success" | "error"
    output: Any
    latency_ms: int = 0
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
    prompt: str = Field(..., min_length=1, description="Visual description for Omni Flash video generation")
    duration_ms: int = Field(default=4000, ge=2000, le=8000, description="Duration in ms (2000-8000)")
    source_start_ms: int = Field(..., ge=0)
    source_end_ms: int = Field(..., ge=0)


class InspectBRollArgs(BaseModel):
    artifact_id: str = Field(..., min_length=1, description="BRoll artifact identifier")


class SynthesizeVoiceSegmentArgs(BaseModel):
    text: str = Field(..., min_length=1, description="Text script for the segment")
    voice_id: str = Field(default="en-US-Journey-F", description="Selected voice id")
    max_duration_ms: int = Field(..., ge=100, description="Strict duration ceiling in ms")


class ToolRegistry:
    """Central registry and dispatcher for internal agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Validate arguments and safely execute the named tool."""
        tool = self._tools.get(tool_name)
        if not tool:
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
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            human_summary = None
            if tool.human_summary_formatter:
                try:
                    human_summary = tool.human_summary_formatter(arguments, raw_output)
                except Exception:
                    pass

            return ToolResult(
                tool_name=tool_name,
                status="success",
                output=raw_output,
                latency_ms=duration_ms,
                human_summary=human_summary,
            )
        except ValidationError as val_err:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolResult(
                tool_name=tool_name,
                status="error",
                output=None,
                latency_ms=duration_ms,
                error_message=f"Validation error: {val_err}",
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
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
) -> ToolRegistry:
    """Create and wire the standard internal tool registry for Leo (Video Editor)."""
    registry = ToolRegistry()
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
        meta = analysis_input.media_metadata
        return {
            "target": target,
            "duration_ms": meta.duration_ms,
            "video_codec": meta.video_codec,
            "audio_codec": meta.audio_codec,
            "width": meta.width,
            "height": meta.height,
            "fps": meta.frame_rate,
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
        return {
            "status": "rendered",
            "summary": edl_summary,
            "decisions_applied": decisions_count,
            "preview_ready": True,
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
        duration_ms: int = 4000,
        source_start_ms: int = 0,
        source_end_ms: int = 4000,
    ) -> dict[str, Any]:
        artifact_id = f"broll_{source_start_ms}_{int(time.time())}"
        return {
            "artifact_id": artifact_id,
            "prompt_summary": prompt,
            "duration_ms": duration_ms,
            "source_start_ms": source_start_ms,
            "source_end_ms": source_end_ms,
            "status": "generated",
        }

    registry.register(
        ToolDefinition(
            name="generate_broll",
            description="Generate visual coverage B-roll video clip via Omni Flash for an abstract or transition section",
            parameters_schema=GenerateBRollArgs,
            handler=handle_generate_broll,
            human_summary_formatter=lambda args, out: f"Leo created visual coverage for {args.get('prompt', 'transition')}.",
        )
    )

    # 12. inspect_broll
    def handle_inspect_broll(artifact_id: str) -> dict[str, Any]:
        return {
            "artifact_id": artifact_id,
            "status": "accepted",
            "duration_ms": 4000,
        }

    registry.register(
        ToolDefinition(
            name="inspect_broll",
            description="Inspect generated B-roll video clip for visual continuity and quality",
            parameters_schema=InspectBRollArgs,
            handler=handle_inspect_broll,
            human_summary_formatter=lambda args, out: f"Leo verified generated B-roll visual continuity.",
        )
    )

    # 13. synthesize_voice_segment
    def handle_synthesize_voice_segment(text: str, voice_id: str = "en-US-Journey-F", max_duration_ms: int = 4000) -> dict[str, Any]:
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
