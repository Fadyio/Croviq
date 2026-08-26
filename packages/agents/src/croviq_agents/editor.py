"""Leo (Dialogue Editor) agent implementation."""

from datetime import datetime, timezone
import uuid

from croviq_agents.client import AgentUsageMetadata, GenAIClient
from croviq_domain.editorial import (
    AgentActivity,
    EditorProposal,
)
from croviq_domain.render_review import RenderReview
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_observability import log_ai_event
from croviq_observability.events import EventType


def format_timecode_ms(ms: int) -> str:
    """Format milliseconds into MM:SS or MM:SS.s."""
    total_seconds = ms / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:04.1f}"


class LeoDialogueEditor:
    """Dialogue Editor agent responsible for video/audio analysis and editorial proposals."""

    def __init__(self, client: GenAIClient) -> None:
        self._client = client

    async def analyze(
        self,
        analysis_input: SourceVideoAnalysisInput,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata, list[AgentActivity]]:
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

        media_summary = (
            f"Duration: {analysis_input.media_metadata.duration_ms}ms, "
            f"Resolution: {analysis_input.media_metadata.width}x{analysis_input.media_metadata.height}, "
            f"Video Codec: {analysis_input.media_metadata.video_codec}, "
            f"Audio Codec: {analysis_input.media_metadata.audio_codec}"
        )

        proposal, usage = await self._client.generate_editor_proposal(
            video_uri=video_gcs_uri,
            mime_type=mime_type,
            transcript=analysis_input.transcript,
            channel_profile=channel_profile,
            lessons=lessons,
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            media_summary=media_summary,
            request_id=request_id,
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

        # Generate truthful, non-hallucinated AgentActivity events from model output
        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        # High-level summary activity
        activities.append(
            AgentActivity(
                activity_id=f"act_leo_sum_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Dialogue Editor",
                activity_type="proposal",
                message=proposal.summary,
                related_decision_id=None,
                created_at=now,
            )
        )

        # Individual decision activities
        for decision in proposal.decisions:
            start_tc = format_timecode_ms(decision.source_start_ms)
            msg = f"[{decision.decision_type.value}] At {start_tc}: {decision.concise_reason}"
            activities.append(
                AgentActivity(
                    activity_id=f"act_leo_dec_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Dialogue Editor",
                    activity_type="decision",
                    message=msg,
                    related_decision_id=decision.decision_id,
                    created_at=now,
                )
            )

        if proposal.short_candidate:
            sc = proposal.short_candidate
            start_tc = format_timecode_ms(sc.start_ms)
            end_tc = format_timecode_ms(sc.end_ms)
            activities.append(
                AgentActivity(
                    activity_id=f"act_leo_short_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Dialogue Editor",
                    activity_type="proposal",
                    message=f"Short candidate ({start_tc} - {end_tc}) \"{sc.hook_title}\": {sc.concise_reason}",
                    related_decision_id=None,
                    created_at=now,
                )
            )

        return proposal, usage, activities

    async def revise(
        self,
        analysis_input: SourceVideoAnalysisInput,
        proposal: EditorProposal,
        render_review: RenderReview,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata, list[AgentActivity]]:
        """Perform a targeted editorial correction pass based on Maya's post-render review."""
        video_gcs_uri = f"gs://{analysis_input.source_media.gcs_bucket}/{analysis_input.source_media.gcs_object}"
        mime_type = analysis_input.source_media.content_type or "video/mp4"
        run_id_val = run_id or f"run_{uuid.uuid4().hex[:8]}"

        log_ai_event(
            event_type=EventType.EDITOR_CORRECTION_STARTED,
            agent="leo",
            model="gemini-3.7-flash",
            status="started",
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
        )

        revised_proposal, usage = await self._client.generate_editor_correction(
            video_uri=video_gcs_uri,
            mime_type=mime_type,
            transcript=analysis_input.transcript,
            proposal=proposal,
            render_review=render_review,
            production_id=analysis_input.production_id,
            channel_profile=channel_profile,
            lessons=lessons,
            run_id=run_id_val,
            request_id=request_id,
        )

        log_ai_event(
            event_type=EventType.EDITOR_CORRECTION_COMPLETED,
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

        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        activities.append(
            AgentActivity(
                activity_id=f"act_leo_rev_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Dialogue Editor",
                activity_type="correction",
                message="Adjusted the affected section.",
                related_decision_id=None,
                created_at=now,
            )
        )

        for decision in revised_proposal.decisions:
            start_tc = format_timecode_ms(decision.source_start_ms)
            msg = f"At {start_tc}: {decision.concise_reason}"
            activities.append(
                AgentActivity(
                    activity_id=f"act_leo_dec_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Dialogue Editor",
                    activity_type="decision",
                    message=msg,
                    related_decision_id=decision.decision_id,
                    created_at=now,
                )
            )

        return revised_proposal, usage, activities
