"""Maya (Director) agent implementation."""

from datetime import datetime, timezone
import uuid

from croviq_agents.client import AgentUsageMetadata, GenAIClient
from croviq_agents.editor import format_timecode_ms
from croviq_domain.edl import EditDecisionList
from croviq_domain.editorial import (
    AgentActivity,
    DirectorDecision,
    DirectorReview,
    DirectorVerdict,
    EditorProposal,
)
from croviq_domain.render_review import (
    RenderReview,
    RenderReviewIssue,
    RenderReviewIssueType,
    RenderReviewSeverity,
    RenderReviewVerdict,
)
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.transcript import Transcript
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_observability import log_ai_event
from croviq_observability.events import EventType

def format_maya_verdict_message(dec_verdict: DirectorDecision) -> str:
    """Format clean, product-facing natural conversational message for Maya's director reviews."""
    reason = dec_verdict.concise_reason.strip()
    clean_reason = reason
    for prefix in ("Approved: ", "Approved ", "Approved. ", "Modified: ", "Modified ", "Modified. ", "Rejected: ", "Rejected ", "Rejected. "):
        if clean_reason.startswith(prefix):
            clean_reason = clean_reason[len(prefix):].strip()
            break

    if dec_verdict.verdict == DirectorVerdict.APPROVE:
        if clean_reason:
            if not clean_reason.endswith("."):
                clean_reason += "."
            return f"Approved. {clean_reason}"
        return "Approved. The technical context is preserved."
    elif dec_verdict.verdict == DirectorVerdict.MODIFY:
        return f"Modified. {clean_reason}"
    elif dec_verdict.verdict == DirectorVerdict.REJECT:
        return f"Rejected. {clean_reason}"
    return reason


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
            msg = format_maya_verdict_message(dec_verdict)
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

        # Clean product-facing feedback activity
        if review.approved_for_edl:
            feed_msg = "Edit plan approved."
        else:
            feed_msg = f"Feedback: {review.editor_feedback}"
        activities.append(
            AgentActivity(
                activity_id=f"act_maya_feed_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Maya",
                role="Director",
                activity_type="review",
                message=feed_msg,
                related_decision_id=None,
                created_at=now,
            )
        )

        return review, usage, activities

    async def review_render(
        self,
        preview_gcs_bucket: str,
        preview_gcs_object: str,
        preview_artifact_id: str,
        edl: EditDecisionList,
        proposal: EditorProposal,
        director_review: DirectorReview | None,
        transcript: Transcript,
        production_id: str,
        preview_mime_type: str = "video/mp4",
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[RenderReview, AgentUsageMetadata, list[AgentActivity]]:
        """Review rendered preview video output and generate structured RenderReview and activity events."""
        preview_video_uri = f"gs://{preview_gcs_bucket}/{preview_gcs_object}"
        run_id_val = run_id or f"run_{uuid.uuid4().hex[:8]}"

        log_ai_event(
            event_type=EventType.DIRECTOR_RENDER_REVIEW_STARTED,
            agent="maya",
            model="gemini-3.7-flash",
            status="started",
            production_id=production_id,
            run_id=run_id_val,
            request_id=request_id,
        )

        render_review, usage = await self._client.generate_render_review(
            preview_video_uri=preview_video_uri,
            preview_mime_type=preview_mime_type,
            transcript=transcript,
            proposal=proposal,
            director_review=director_review,
            edl=edl,
            production_id=production_id,
            preview_artifact_id=preview_artifact_id,
            channel_profile=channel_profile,
            lessons=lessons,
            run_id=run_id_val,
            request_id=request_id,
        )

        log_ai_event(
            event_type=EventType.DIRECTOR_RENDER_REVIEW_COMPLETED,
            agent="maya",
            model=render_review.model,
            status="success",
            production_id=production_id,
            run_id=run_id_val,
            request_id=request_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
        )

        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        if render_review.verdict == RenderReviewVerdict.APPROVE:
            activities.append(
                AgentActivity(
                    activity_id=f"act_maya_rrv_{uuid.uuid4().hex[:8]}",
                    production_id=production_id,
                    run_id=run_id_val,
                    agent="Maya",
                    role="Director",
                    activity_type="render_review",
                    message="The dialogue flows naturally. Edit approved.",
                    related_decision_id=None,
                    created_at=now,
                )
            )
        else:
            activities.append(
                AgentActivity(
                    activity_id=f"act_maya_rrv_{uuid.uuid4().hex[:8]}",
                    production_id=production_id,
                    run_id=run_id_val,
                    agent="Maya",
                    role="Director",
                    activity_type="render_review",
                    message=render_review.summary,
                    related_decision_id=None,
                    created_at=now,
                )
            )
            for issue in render_review.issues:
                activities.append(
                    AgentActivity(
                        activity_id=f"act_maya_iss_{uuid.uuid4().hex[:8]}",
                        production_id=production_id,
                        run_id=run_id_val,
                        agent="Maya",
                        role="Director",
                        activity_type="review_issue",
                        message=issue.message,
                        related_decision_id=issue.related_decision_id,
                        created_at=now,
                    )
                )

        return render_review, usage, activities
