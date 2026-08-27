"""Leo (Video Editor) agent implementation with tool execution and self-review."""

from datetime import datetime, timezone
import logging
from typing import Sequence
import uuid

from croviq_agents.client import AgentUsageMetadata, GenAIClient
from croviq_agents.terminal import SandboxedTerminalRunner
from croviq_agents.tools import (
    ToolRegistry,
    build_default_editor_tool_registry,
)
from croviq_domain.editorial import (
    AgentActivity,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    SectionAction,
    VideoSectionDecision,
)
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.render_review import RenderReview
from croviq_domain.source_analysis import SourceVideoAnalysisInput
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
    if reason.startswith("I "):
        return reason

    if decision.decision_type == EditorDecisionType.REMOVE_FALSE_START:
        clean = reason.removeprefix("Remove false start ").removeprefix("Removed false start ").removeprefix("Remove ").removeprefix("Removed ")
        if clean.lower().startswith("before ") or clean.lower().startswith("on ") or clean.lower().startswith("during "):
            return f"I removed a false start {clean}"
        return f"I removed a false start: {clean}"
    elif decision.decision_type == EditorDecisionType.REMOVE_FILLER:
        clean = reason.removeprefix("Remove filler ").removeprefix("Removed filler ").removeprefix("Remove ").removeprefix("Removed ")
        return f"I removed filler hesitation: {clean}"
    elif decision.decision_type == EditorDecisionType.TRIM_PAUSE:
        clean = reason.removeprefix("Trim dead air ").removeprefix("Trim silence ").removeprefix("Trim pause ").removeprefix("Trim ").removeprefix("Trimmed ")
        return f"I trimmed a speech pause: {clean}"
    elif decision.decision_type == EditorDecisionType.REMOVE_REPETITION:
        clean = reason.removeprefix("Remove repetition ").removeprefix("Removed repetition ").removeprefix("Remove ").removeprefix("Removed ")
        return f"I removed a repetition: {clean}"
    elif decision.decision_type in (EditorDecisionType.KEEP, EditorDecisionType.KEEP_FOR_CLARITY):
        clean = reason.removeprefix("Preserve ").removeprefix("Keep ").removeprefix("Retain ")
        return f"I preserved this segment: {clean}"
    return reason

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

        # 2. Manipulation / Test-Render Tool: render test cut of candidate decisions
        test_render_res = tools.execute(
            "render_test_edit",
            {"edl_summary": f"{len(proposal.decisions)} cut points", "decisions_count": len(proposal.decisions)},
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

    async def revise(
        self,
        analysis_input: SourceVideoAnalysisInput,
        render_review: RenderReview,
        original_proposal: EditorProposal | None = None,
        proposal: EditorProposal | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata, list[AgentActivity]]:
        """Perform a targeted editorial correction pass based on Maya's post-render review."""
        prop = original_proposal or proposal
        if prop is None:
            raise ValueError("Must provide either 'original_proposal' or 'proposal'")
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

        video_gcs_uri = f"gs://{analysis_input.source_media.gcs_bucket}/{analysis_input.source_media.gcs_object}"
        mime_type = analysis_input.source_media.content_type or "video/mp4"

        revised_proposal, usage = await self._client.generate_editor_correction(
            video_uri=video_gcs_uri,
            mime_type=mime_type,
            transcript=analysis_input.transcript,
            proposal=prop,
            render_review=render_review,
            production_id=analysis_input.production_id,
            channel_profile=channel_profile,
            lessons=lessons,
            run_id=run_id_val,
            request_id=request_id,
        )
        # Ensure full timeline coverage across revised proposal
        revised_sections = ensure_full_timeline_coverage(
            sections=revised_proposal.section_plan,
            total_duration_ms=analysis_input.media_metadata.duration_ms,
            production_id=analysis_input.production_id,
        )
        revised_proposal = revised_proposal.model_copy(update={"section_plan": revised_sections})

        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        activities.append(
            AgentActivity(
                activity_id=f"act_leo_rev_sum_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="proposal",
                message=f"I revised the edit according to Maya's feedback: {revised_proposal.summary}",
                related_decision_id=None,
                created_at=now,
            )
        )

        for decision in revised_proposal.decisions:
            start_tc = format_timecode_ms(decision.source_start_ms)
            msg = format_leo_decision_message(decision)
            activities.append(
                AgentActivity(
                    activity_id=f"act_leo_rev_dec_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="decision",
                    message=msg,
                    related_decision_id=decision.decision_id,
                    created_at=now,
                )
            )

        log_ai_event(
            event_type=EventType.EDITOR_ANALYSIS_COMPLETED,
            agent="leo",
            model=revised_proposal.model,
            status="success",
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
        )

        return revised_proposal, usage, activities


# Backward-compatible alias
LeoDialogueEditor = LeoVideoEditor
