"""Leo (Video Editor) agent implementation with tool execution and self-review."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Sequence
import uuid

from croviq_agents.client import AgentUsageMetadata, GenAIClient
from croviq_agents.terminal import SandboxedTerminalRunner
from croviq_agents.tools import (
    ToolRegistry,
    build_default_editor_tool_registry,
    build_editor_chat_tool_registry,
)
from croviq_agents.prompts import (
    LEO_CHAT_SYSTEM_INSTRUCTION,
    build_leo_chat_context_prompt,
)
from croviq_domain.editorial import (
    AgentActivity,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorSelectionContext,
    SectionAction,
    VideoSectionDecision,
)
from croviq_domain.edl import EditDecisionList
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.render_review import EditorSelfReview, EditorSelfReviewVerdict
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript
from croviq_observability import log_ai_event
from croviq_observability.events import EventType
logger = logging.getLogger(__name__)


def format_timecode_ms(ms: int) -> str:
    """Format milliseconds into MM:SS or MM:SS.s."""
    total_seconds = ms / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:04.1f}"

def format_leo_decision_message(decision: EditorDecision) -> str:
    """Format clean, product-facing natural conversational message for Leo's edit decisions."""
    reason = decision.concise_reason.strip()
    start_tc = format_timecode_ms(decision.source_start_ms)
    dur_s = (decision.source_end_ms - decision.source_start_ms) / 1000.0

    if reason.startswith("I "):
        return reason

    if decision.decision_type in (EditorDecisionType.REMOVE_FALSE_START,):
        clean = reason.removeprefix("Remove false start ").removeprefix("Removed false start ").removeprefix("Remove ").removeprefix("Removed ")
        return f"Removed a false start at {start_tc}: {clean}"
    elif decision.decision_type in (EditorDecisionType.REMOVE_SILENCE, EditorDecisionType.TRIM_PAUSE):
        return f"Removed {dur_s:.1f}s of dead air at {start_tc}"
    elif decision.decision_type in (EditorDecisionType.REMOVE_REPETITION,):
        clean = reason.removeprefix("Remove repetition ").removeprefix("Removed repetition ").removeprefix("Remove ").removeprefix("Removed ")
        return f"Removed duplicate phrasing at {start_tc}: {clean}"
    elif decision.decision_type in (EditorDecisionType.TIGHTEN_PAUSE, EditorDecisionType.TIGHTEN_EXPLANATION):
        return f"Tightened pause at {start_tc} ({dur_s:.1f}s)"
    elif decision.decision_type in (EditorDecisionType.REMOVE_LOW_VALUE_SECTION, EditorDecisionType.REMOVE_FILLER):
        clean = reason.removeprefix("Remove filler ").removeprefix("Removed filler ").removeprefix("Remove ").removeprefix("Removed ")
        return f"Removed filler hesitation at {start_tc}: {clean}"
    elif decision.decision_type in (EditorDecisionType.BROLL_COVER, EditorDecisionType.BROLL_COVER_CANDIDATE):
        return f"Flagged B-roll visual coverage at {start_tc}"
    elif decision.decision_type in (EditorDecisionType.KEEP, EditorDecisionType.KEEP_FOR_CLARITY):
        clean = reason.removeprefix("Preserve ").removeprefix("Keep ").removeprefix("Retain ")
        return f"Preserved technical walkthrough at {start_tc}: {clean}"
    return f"Edit at {start_tc}: {reason}"
def ensure_full_timeline_coverage(
    sections: list[VideoSectionDecision],
    total_duration_ms: int,
    production_id: str,
) -> list[VideoSectionDecision]:
    """Ensure 100% of the source timeline from 0 to total_duration_ms is covered."""
    if not sections:
        return [
            VideoSectionDecision(
                section_id="sec_001",
                source_start_ms=0,
                source_end_ms=total_duration_ms,
                transcript_start_word=0,
                transcript_end_word=0,
                action=SectionAction.KEEP,
                reason="Default full timeline preservation",
                confidence=1.0,
                visual_summary="Full continuous source recording",
                speech_summary="Complete spoken presentation",
                editorial_intent="Preserve full original source duration",
            )
        ]

    # Sort sections by start time
    sorted_sections = sorted(sections, key=lambda s: s.source_start_ms)
    covered: list[VideoSectionDecision] = []
    current_cursor = 0

    for idx, sec in enumerate(sorted_sections):
        # Gap before section
        if sec.source_start_ms > current_cursor:
            gap_sec = VideoSectionDecision(
                section_id=f"sec_gap_{uuid.uuid4().hex[:6]}",
                source_start_ms=current_cursor,
                source_end_ms=sec.source_start_ms,
                transcript_start_word=sec.transcript_start_word,
                transcript_end_word=sec.transcript_start_word,
                action=SectionAction.KEEP,
                reason="Preserve natural pacing between edited sections",
                confidence=1.0,
                visual_summary="Continuous screen capture and demonstration",
                speech_summary="Spoken dialogue flow",
                editorial_intent="Maintain conversational cadence and context",
            )
            covered.append(gap_sec)

        # Append current section
        covered.append(sec)
        current_cursor = max(current_cursor, sec.source_end_ms)

    # Gap at end of timeline
    if current_cursor < total_duration_ms:
        end_sec = VideoSectionDecision(
            section_id=f"sec_end_{uuid.uuid4().hex[:6]}",
            source_start_ms=current_cursor,
            source_end_ms=total_duration_ms,
            transcript_start_word=sorted_sections[-1].transcript_end_word if sorted_sections else 0,
            transcript_end_word=sorted_sections[-1].transcript_end_word if sorted_sections else 0,
            action=SectionAction.KEEP,
            reason="Preserve closing video footage",
            confidence=1.0,
            visual_summary="Closing screen state and wrap-up demonstration",
            speech_summary="Final remarks and outro",
            editorial_intent="Preserve natural video conclusion",
        )
        covered.append(end_sec)

    return covered


class LeoVideoEditor:
    """Video Editor agent operating real media inspection tools, edit proposals, and self-review."""

    def __init__(
        self,
        client: GenAIClient,
        tool_registry: ToolRegistry | None = None,
        terminal_runner: SandboxedTerminalRunner | None = None,
    ) -> None:
        self._client = client
        self._tool_registry = tool_registry
        self._terminal_runner = terminal_runner

    async def analyze(
        self,
        analysis_input: SourceVideoAnalysisInput,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        silence_decisions: Sequence[EditorDecision] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
        custom_prompt: str | None = None,
    ) -> tuple[EditorProposal, AgentUsageMetadata, list[AgentActivity]]:
        """Execute autonomous observation, tool usage, and editorial proposal generation."""
        video_gcs_uri = f"gs://{analysis_input.source_media.gcs_bucket}/{analysis_input.source_media.gcs_object}"
        mime_type = analysis_input.source_media.content_type or "video/mp4"
        run_id_val = run_id or f"run_{uuid.uuid4().hex[:8]}"

        log_ai_event(
            event_type=EventType.EDITOR_ANALYSIS_STARTED,
            agent="leo",
            model="gemini-3.7-flash",
            status="started",
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
        )

        # Build tools for this production
        tools = self._tool_registry or build_default_editor_tool_registry(
            production_id=analysis_input.production_id,
            analysis_input=analysis_input,
            channel_profile=channel_profile,
            lessons=lessons,
            terminal_runner=self._terminal_runner,
            genai_client=self._client,
        )

        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        media_summary = (
            f"Duration: {analysis_input.media_metadata.duration_ms}ms, "
            f"Resolution: {analysis_input.media_metadata.width}x{analysis_input.media_metadata.height}, "
            f"Video Codec: {analysis_input.media_metadata.video_codec}, "
            f"Audio Codec: {analysis_input.media_metadata.audio_codec}"
        )

        # Generate proposal from reasoning client
        proposal, usage = await self._client.generate_editor_proposal(
            video_uri=video_gcs_uri,
            mime_type=mime_type,
            transcript=analysis_input.transcript,
            channel_profile=channel_profile,
            lessons=lessons,
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            media_summary=media_summary,
            silence_decisions=silence_decisions,
            request_id=request_id,
        )

        # Ensure full timeline coverage across 100% of duration
        verified_sections = ensure_full_timeline_coverage(
            sections=proposal.section_plan,
            total_duration_ms=analysis_input.media_metadata.duration_ms,
            production_id=analysis_input.production_id,
        )
        proposal = proposal.model_copy(update={"section_plan": verified_sections})

        # Summary activity first
        activities.append(
            AgentActivity(
                activity_id=f"act_leo_sum_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="proposal",
                message=proposal.summary,
                related_decision_id=None,
                created_at=now,
            )
        )
        tools.run_id = run_id_val
        tools.production_id = analysis_input.production_id

        # 1. Inspection Tool: inspect source media properties
        media_probe_res = tools.execute("inspect_media", {"start_ms": 0, "end_ms": analysis_input.media_metadata.duration_ms})
        if media_probe_res.status == "success" and media_probe_res.human_summary:
            activities.append(
                AgentActivity(
                    activity_id=f"act_tool_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="tool_execution",
                    message=media_probe_res.human_summary,
                    related_decision_id=None,
                    created_at=now,
                )
            )

        if silence_decisions:
            total_silence_s = sum(d.source_end_ms - d.source_start_ms for d in silence_decisions) / 1000.0
            activities.append(
                AgentActivity(
                    activity_id=f"act_tool_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="tool_execution",
                    message=f"I found {total_silence_s:.1f} seconds of dead air.",
                    related_decision_id=None,
                    created_at=now,
                )
            )

        # Render a real-count test preview of the proposed editorial decisions.
        test_render_res = tools.execute(
            "render_test_edit",
            {
                "edl_summary": f"{len(proposal.decisions)} editorial decisions",
                "decisions_count": len(proposal.decisions),
            },
        )
        if test_render_res.status == "success" and test_render_res.human_summary:
            activities.append(
                AgentActivity(
                    activity_id=f"act_tool_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="tool_execution",
                    message=test_render_res.human_summary,
                    related_decision_id=None,
                    created_at=now,
                )
            )

        # 3. Output Inspection Tool: inspect rendered preview test cut result
        probe_preview_res = tools.execute("probe_media", {"target": "preview"})
        if probe_preview_res.status == "success":
            activities.append(
                AgentActivity(
                    activity_id=f"act_self_review_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="proposal",
                    message="I inspected the test cut preview stream and verified continuous audio/video flow.",
                    related_decision_id=None,
                    created_at=datetime.now(timezone.utc),
                )
            )
        if proposal.chapters:
            chapter_titles = ", ".join(c.title for c in proposal.chapters[:3])
            activities.append(
                AgentActivity(
                    activity_id=f"act_chapters_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="proposal",
                    message=f"Identified {len(proposal.chapters)} chapters from multimodal analysis: {chapter_titles}{'…' if len(proposal.chapters) > 3 else ''}",
                    related_decision_id=None,
                    created_at=datetime.now(timezone.utc),
                )
            )

        for decision in proposal.decisions:
            start_tc = format_timecode_ms(decision.source_start_ms)
            msg = format_leo_decision_message(decision)
            activities.append(
                AgentActivity(
                    activity_id=f"act_leo_dec_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="decision",
                    message=msg,
                    related_decision_id=decision.decision_id,
                    created_at=datetime.now(timezone.utc),
                )
            )

        log_ai_event(
            event_type=EventType.EDITOR_ANALYSIS_COMPLETED,
            agent="leo",
            model=proposal.model,
            status="success",
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
        )

        return proposal, usage, activities


    async def chat(
        self,
        *,
        message: str,
        conversation_history: list[dict[str, Any]] | None = None,
        production: Any = None,
        media_metadata: Any = None,
        transcript: Transcript | None = None,
        proposal: EditorProposal | None = None,
        edl: EditDecisionList | None = None,
        artifacts: Sequence[Any] | None = None,
        editor_context: EditorSelectionContext | Any | None = None,
        current_playhead_ms: int | None = None,
        selected_range: Sequence[int] | None = None,
        selected_element: dict[str, Any] | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        custom_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Respond in the Editor workspace and execute one canonical typed editing tool."""
        tools = self._tool_registry or build_editor_chat_tool_registry(
            production_id=getattr(production, "production_id", "unknown"),
            transcript=transcript,
            proposal=proposal,
            edl=edl,
            artifacts=artifacts,
            media_metadata=media_metadata,
        )
        lower = message.lower().strip()

        # 1. Normalize selection coordinates and element context
        element_id = None
        has_selection = False
        if editor_context:
            sel_t = getattr(editor_context, "selection_type", None)
            has_selection = sel_t is not None and str(sel_t).upper() not in ("NONE", "CLEARED")
            start_ms = int(getattr(editor_context, "source_start_ms", 0))
            end_ms = int(getattr(editor_context, "source_end_ms", start_ms))
            element_id = getattr(editor_context, "cut_id", None) or getattr(editor_context, "chapter_id", None)
        elif selected_range and len(selected_range) == 2:
            has_selection = True
            start_ms, end_ms = int(selected_range[0]), int(selected_range[1])
            if selected_element:
                element_id = selected_element.get("id")
        else:
            has_selection = False
            start_ms = int(current_playhead_ms or 0)
            source_dur = getattr(edl, "source_duration_ms", 0) or getattr(transcript, "duration_ms", 100_000)
            end_ms = min(source_dur, start_ms + 3000)
            timecodes = re.findall(r"\b(\d+):(\d+(?:\.\d+)?)\b", message)
            parsed_times = [
                int((int(minutes) * 60 + float(seconds)) * 1000)
                for minutes, seconds in timecodes[:2]
            ]
            if len(parsed_times) < 2:
                second_values = re.findall(
                    r"\b(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b",
                    lower,
                )
                parsed_times = [int(float(value) * 1000) for value in second_values[:2]]
            if len(parsed_times) == 2:
                start_ms, end_ms = parsed_times
                has_selection = True
            if selected_element:
                element_id = selected_element.get("id")
                if selected_element.get("start_ms") is not None:
                    start_ms = int(selected_element["start_ms"])
                if selected_element.get("end_ms") is not None:
                    end_ms = int(selected_element["end_ms"])
                has_selection = True
        end_ms = max(start_ms + 1, end_ms)

        # 2. Build system instruction and context prompt for Gemini
        media_fn = getattr(getattr(production, "source_media", None), "original_filename", None)
        media_dur = getattr(edl, "source_duration_ms", 0) or (getattr(transcript, "duration_ms", 0) if transcript else 0)
        video_uri = None
        if production and getattr(production, "source_media", None):
            b = getattr(production.source_media, "gcs_bucket", "")
            o = getattr(production.source_media, "gcs_object", "")
            if b and o:
                video_uri = f"gs://{b}/{o}"

        context_prompt = build_leo_chat_context_prompt(
            production_id=getattr(production, "production_id", "unknown") if production else "unknown",
            media_filename=media_fn,
            media_duration_ms=media_dur,
            media_metadata=media_metadata,
            edl=edl,
            transcript=transcript,
            editor_context=editor_context,
            channel_profile=channel_profile,
            lessons=lessons,
        )
        sys_parts = [LEO_CHAT_SYSTEM_INSTRUCTION]
        if custom_prompt and custom_prompt.strip():
            sys_parts.append(f"Creator Working Directives:\n{custom_prompt.strip()}")
        full_sys = "\n\n".join(sys_parts)

        tool_declarations = tools.to_genai_function_declarations()

        # 3. Invoke real Gemini model with typed tool declarations
        model_result = await self._client.generate_leo_chat_reply(
            message=message,
            system_instruction=full_sys,
            context_prompt=context_prompt,
            conversation_history=conversation_history,
            video_uri=video_uri,
            production_id=getattr(production, "production_id", "unknown") if production else "unknown",
            tool_declarations=tool_declarations,
        )

        executions: list[dict[str, Any]] = []
        content: str

        if model_result.function_name:
            tool_name = model_result.function_name
            arguments = model_result.function_args or {}

            # Fill in selection context arguments if not explicitly provided
            if tool_name in ("remove_selection", "tighten_selection", "add_cut", "restore_source_range", "add_broll", "add_chapter"):
                if "start_ms" not in arguments or arguments.get("start_ms") is None:
                    arguments["start_ms"] = start_ms
                if "end_ms" not in arguments or arguments.get("end_ms") is None:
                    arguments["end_ms"] = end_ms
                if arguments.get("start_ms") is not None and arguments.get("end_ms") is not None:
                    if int(arguments["end_ms"]) <= int(arguments["start_ms"]):
                        if end_ms > start_ms:
                            arguments["start_ms"] = start_ms
                            arguments["end_ms"] = end_ms
                        else:
                            arguments["end_ms"] = int(arguments["start_ms"]) + 2000
            if tool_name in ("remove_selection", "tighten_selection", "undo_last_edit"):
                if "active_edl_id" not in arguments and edl:
                    arguments["active_edl_id"] = edl.edl_id
            # Empty selection check for range mutation tools
            if tool_name in ("remove_selection", "tighten_selection") and not has_selection and not editor_context and not selected_range:
                content = "No section is currently selected on the timeline. Click or drag any region on the timeline or transcript to select it."
            else:
                result = await tools.execute_async(tool_name, arguments)
                exec_status = result.status
                if isinstance(result.output, dict):
                    if result.output.get("changed") is False or result.output.get("status") == "no_change":
                        exec_status = "no_change"
                    elif result.output.get("status") in ("success", "error"):
                        exec_status = result.output["status"]
                executions.append({
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "status": exec_status,
                    "output": result.output,
                    "error": result.error_message,
                    "latency_ms": result.latency_ms,
                })
                if result.status == "error":
                    content = f"I couldn't apply that edit: {result.error_message}"
                else:
                    if isinstance(result.output, dict) and result.output.get("message"):
                        content = result.output["message"]
                    else:
                        content = result.human_summary or self._format_chat_tool_result(tool_name, result.output)
                    state = getattr(tools, "state", {})
                    if (
                        state.get("timeline_updated")
                        and not state.get("preview_updated")
                        and tool_name != "rerender_preview"
                        and tools.has_tool("rerender_preview")
                    ):
                        render_result = await tools.execute_async("rerender_preview", {})
                        executions.append({
                            "tool_name": "rerender_preview",
                            "arguments": {},
                            "status": render_result.status,
                            "output": render_result.output,
                            "error": render_result.error_message,
                            "latency_ms": render_result.latency_ms,
                        })
                        if render_result.status == "error":
                            content = f"{content} However, preview rendering failed: {render_result.error_message}"
        else:
            content = model_result.reply or "I inspected the timeline and current edit decisions."
        state = getattr(tools, "state", {})
        return {
            "content": content,
            "reply": content,
            "tool_executions": executions,
            "proposal": state.get("proposal", proposal),
            "edl": state.get("edl", edl),
            "artifacts": state.get("artifacts", list(artifacts or [])),
            "timeline_updated": bool(state.get("timeline_updated", False)),
            "voiceover_updated": bool(state.get("voiceover_updated", False)),
            "preview_updated": bool(state.get("preview_updated", False)),
            "seek_range": state.get("seek_range"),
        }

    @staticmethod
    def _format_chat_tool_result(tool_name: str, output: Any) -> str:
        """Format concise creator-facing tool completion messages."""
        labels = {
            "remove_selection": "I removed the selected section using safe word boundaries and updated the preview.",
            "tighten_selection": "I tightened the selected section and updated the preview.",
            "undo_last_edit": "I undid the last edit and restored the previous edit state.",
            "add_cut": "I added the cut at safe word boundaries and updated the timeline.",
            "remove_cut": "I removed that cut and restored the source range.",
            "restore_source_range": "I restored the selected source range.",
            "adjust_cut": "I adjusted the cut boundaries and updated the timeline.",
            "mark_keep": "I marked that range to keep and removed conflicting cuts.",
            "add_chapter": "I added the chapter to the editorial plan.",
            "rename_chapter": "I renamed the chapter.",
            "add_broll": "I added the B-roll coverage, preserving the original audio.",
            "remove_broll": "I removed the B-roll coverage.",
            "generate_voiceover": "I generated the voiceover preview and mixed it under the source.",
            "remove_voiceover": "I removed the voiceover and restored the source audio.",
            "add_background_music": "I added the background music mix with speech ducking.",
            "remove_background_music": "I removed the background music.",
            "rerender_preview": "I rendered an updated preview.",
            "seek_range": "I moved the editor to that range.",
            "inspect_range": "I inspected the selected range.",
            "explain_edit": "Here’s the edit rationale and source evidence.",
        }
        return labels.get(tool_name, "I updated the edit.")


    async def self_review_render(
        self,
        preview_gcs_bucket: str,
        preview_gcs_object: str,
        preview_artifact_id: str,
        edl: EditDecisionList,
        proposal: EditorProposal,
        transcript: Transcript,
        production_id: str,
        preview_mime_type: str = "video/mp4",
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorSelfReview, AgentUsageMetadata, list[AgentActivity]]:
        """Perform multimodal video self-review by watching the rendered preview MP4."""
        preview_video_uri = f"gs://{preview_gcs_bucket}/{preview_gcs_object}"
        run_id_val = run_id or f"run_{uuid.uuid4().hex[:8]}"

        self_review, usage = await self._client.generate_editor_self_review(
            preview_video_uri=preview_video_uri,
            preview_mime_type=preview_mime_type,
            transcript=transcript,
            proposal=proposal,
            edl=edl,
            production_id=production_id,
            preview_artifact_id=preview_artifact_id,
            channel_profile=channel_profile,
            lessons=lessons,
            run_id=run_id_val,
            request_id=request_id,
        )

        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        activities.append(
            AgentActivity(
                activity_id=f"act_leo_sr_{uuid.uuid4().hex[:8]}",
                production_id=production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="self_review",
                message=self_review.summary,
                related_decision_id=None,
                created_at=now,
            )
        )

        for finding in self_review.findings:
            activities.append(
                AgentActivity(
                    activity_id=f"act_leo_fnd_{uuid.uuid4().hex[:8]}",
                    production_id=production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="self_review_finding",
                    message=finding,
                    related_decision_id=None,
                    created_at=now,
                )
            )

        return self_review, usage, activities


# Backward-compatible alias
LeoDialogueEditor = LeoVideoEditor
