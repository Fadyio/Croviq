"""Maya (Director) agent implementation."""

from datetime import datetime, timezone
import uuid

from croviq_agents.client import AgentUsageMetadata, GenAIClient
from croviq_agents.editor import format_timecode_ms
from croviq_domain.editorial import (
    AgentActivity,
    DirectorDecision,
    DirectorReview,
    DirectorVerdict,
    EditorProposal,
)
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_observability import log_ai_event
from croviq_observability.events import EventType


class MayaDirector:
    """Director agent responsible for reviewing Leo's proposals and orchestrating EDL readiness."""

    def __init__(self, client: GenAIClient) -> None:
        self._client = client

    async def review(
        self,
        analysis_input: SourceVideoAnalysisInput,
        proposal: EditorProposal,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[DirectorReview, AgentUsageMetadata, list[AgentActivity]]:
        """Review Leo's proposed batch of edits and generate review and activity events."""
        video_gcs_uri = f"gs://{analysis_input.source_media.gcs_bucket}/{analysis_input.source_media.gcs_object}"
        mime_type = analysis_input.source_media.content_type or "video/mp4"
        run_id_val = run_id or f"run_{uuid.uuid4().hex[:8]}"

        log_ai_event(
            event_type=EventType.DIRECTOR_REVIEW_STARTED,
            agent="maya",
            model="gemini-3.7-flash",
            status="started",
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
        )

        review, usage = await self._client.generate_director_review(
            video_uri=video_gcs_uri,
            mime_type=mime_type,
            transcript=analysis_input.transcript,
            channel_profile=channel_profile,
            lessons=lessons,
            proposal=proposal,
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
        )

        log_ai_event(
            event_type=EventType.DIRECTOR_REVIEW_COMPLETED,
            agent="maya",
            model=review.model,
            status="success",
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
        )

        # Generate truthful, non-hallucinated AgentActivity events from model review
        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        # High-level assessment activity
        activities.append(
            AgentActivity(
                activity_id=f"act_maya_rev_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Maya",
                role="Director",
                activity_type="review",
                message=review.overall_assessment,
                related_decision_id=None,
                created_at=now,
            )
        )

        # Per-decision review verdict activities
        for dec_verdict in review.decisions:
            verdict_str = dec_verdict.verdict.value
            msg = f"[{verdict_str}] Decision {dec_verdict.editor_decision_id}: {dec_verdict.concise_reason}"
            activities.append(
                AgentActivity(
                    activity_id=f"act_maya_dec_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Maya",
                    role="Director",
                    activity_type="decision",
                    message=msg,
                    related_decision_id=dec_verdict.editor_decision_id,
                    created_at=now,
                )
            )

        # Feedback activity
        activities.append(
            AgentActivity(
                activity_id=f"act_maya_feed_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Maya",
                role="Director",
                activity_type="review",
                message=f"Feedback to Leo: {review.editor_feedback} (Approved for EDL: {review.approved_for_edl})",
                related_decision_id=None,
                created_at=now,
            )
        )

        return review, usage, activities
