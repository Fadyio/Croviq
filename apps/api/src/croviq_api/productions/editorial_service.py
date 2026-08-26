"""Director + Editor application service orchestrating Leo and Maya GenAI SDK agents."""

from datetime import datetime, timezone
import logging
import uuid

from fastapi import HTTPException, status

from croviq_agents.client import GenAIClient
from croviq_agents.director import MayaDirector
from croviq_agents.editor import LeoDialogueEditor
from croviq_media.inspector import MediaInspector
from croviq_api.memory.store import ChannelMemoryStore
from croviq_api.productions.editorial_repository import EditorialRepository
from croviq_api.productions.repository import ProductionRepository
from croviq_api.productions.transcript_repository import TranscriptRepository
from croviq_domain.editorial import (
    AgentActivity,
    DirectorReview,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import SourceMediaStatus
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.user import User
from croviq_observability import log_ai_event
from croviq_observability.events import EventType

logger = logging.getLogger(__name__)


class DirectorEditorService:
    """Orchestrates the sequential dialogue editing (Leo) and director review (Maya) workflow."""

    def __init__(
        self,
        production_repo: ProductionRepository,
        transcript_repo: TranscriptRepository,
        memory_store: ChannelMemoryStore,
        media_inspector: MediaInspector,
        editorial_repo: EditorialRepository,
        genai_client: GenAIClient,
    ) -> None:
        self._production_repo = production_repo
        self._transcript_repo = transcript_repo
        self._memory_store = memory_store
        self._media_inspector = media_inspector
        self._editorial_repo = editorial_repo
        self._genai_client = genai_client

    async def run_editorial_analysis(
        self,
        production_id: str,
        current_user: User,
        request_id: str = "unknown",
    ) -> tuple[EditorialRun, EditorProposal, DirectorReview, list[AgentActivity]]:
        """Execute the complete Leo dialogue pass and Maya director review sequence."""
        # 1. Load production and verify ownership
        prod = await self._production_repo.get_production(production_id)
        if prod is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production '{production_id}' not found",
            )
        if prod.owner_user_id != current_user.user_id and not getattr(current_user, "is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you do not own this production",
            )

        # 2. Check source media upload prerequisite
        if prod.source_media is None or prod.source_media.status != SourceMediaStatus.UPLOADED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Production source media is not uploaded",
            )

        # 3. Check transcript prerequisite
        transcript = await self._transcript_repo.get_transcript_by_production_id(production_id)
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Production '{production_id}' must be transcribed before running editorial analysis",
            )

        # 4. Load Channel Memory (profile and lessons)
        channel_profile = await self._memory_store.get_profile(prod.channel_id)
        lessons = await self._memory_store.get_lessons(prod.channel_id)

        # 5. Build MediaMetadata and SourceVideoAnalysisInput
        try:
            media_metadata = self._media_inspector.inspect_media(prod.source_media.original_filename)
        except Exception:
            media_metadata = MediaMetadata(
                duration_ms=transcript.duration_ms,
                width=1920,
                height=1080,
                frame_rate=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                rotation=0,
                size_bytes=prod.source_media.size_bytes,
            )
        else:
            if media_metadata.duration_ms <= 0:
                media_metadata = MediaMetadata(
                    duration_ms=transcript.duration_ms,
                    width=media_metadata.width or 1920,
                    height=media_metadata.height or 1080,
                    frame_rate=media_metadata.frame_rate or 30.0,
                    video_codec=media_metadata.video_codec if media_metadata.video_codec != "none" else "h264",
                    audio_codec=media_metadata.audio_codec or "aac",
                    audio_sample_rate=media_metadata.audio_sample_rate or 48000,
                    audio_channels=media_metadata.audio_channels or 2,
                    rotation=media_metadata.rotation,
                    size_bytes=prod.source_media.size_bytes,
                )

        analysis_input = SourceVideoAnalysisInput(
            production_id=production_id,
            source_media=prod.source_media,
            media_metadata=media_metadata,
            transcript=transcript,
            channel_id=prod.channel_id,
        )

        # 6. Initialize EditorialRun
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run = EditorialRun(
            run_id=run_id,
            production_id=production_id,
            status=EditorialRunStatus.ANALYZING,
            started_at=datetime.now(timezone.utc),
        )
        await self._editorial_repo.save_editorial_run(run)

        all_activities: list[AgentActivity] = []

        try:
            # 7. Leo (Dialogue Editor) analysis pass
            editor = LeoDialogueEditor(client=self._genai_client)
            proposal, leo_usage, leo_activities = await editor.analyze(
                analysis_input=analysis_input,
                channel_profile=channel_profile,
                lessons=lessons,
                run_id=run_id,
                request_id=request_id,
            )

            # Persist proposal and Leo activities
            proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
            await self._editorial_repo.save_editor_proposal(proposal, proposal_id=proposal_id)
            await self._editorial_repo.save_activities(leo_activities)
            all_activities.extend(leo_activities)

            # 8. Update run to REVIEWING
            run.status = EditorialRunStatus.REVIEWING
            run.editor_proposal_id = proposal_id
            await self._editorial_repo.save_editorial_run(run)

            # 9. Maya (Director) review pass
            director = MayaDirector(client=self._genai_client)
            review, maya_usage, maya_activities = await director.review(
                analysis_input=analysis_input,
                proposal=proposal,
                channel_profile=channel_profile,
                lessons=lessons,
                run_id=run_id,
                request_id=request_id,
            )

            # Persist review and Maya activities
            review_id = f"rev_{uuid.uuid4().hex[:12]}"
            await self._editorial_repo.save_director_review(review, review_id=review_id)
            await self._editorial_repo.save_activities(maya_activities)
            all_activities.extend(maya_activities)

            # 10. Complete run
            run.status = EditorialRunStatus.COMPLETED
            run.director_review_id = review_id
            run.completed_at = datetime.now(timezone.utc)
            await self._editorial_repo.save_editorial_run(run)

            log_ai_event(
                event_type=EventType.EDITORIAL_RUN_COMPLETED,
                agent="maya",
                model=review.model,
                status="success",
                production_id=production_id,
                run_id=run_id,
                request_id=request_id,
            )

            return run, proposal, review, all_activities

        except Exception as exc:
            run.status = EditorialRunStatus.FAILED
            run.failure_code = getattr(exc, "error_code", "EDITORIAL_RUN_FAILED")
            run.completed_at = datetime.now(timezone.utc)
            await self._editorial_repo.save_editorial_run(run)

            log_ai_event(
                event_type=EventType.EDITORIAL_RUN_FAILED,
                agent="leo",
                model="gemini-3.7-flash",
                status="failed",
                production_id=production_id,
                run_id=run_id,
                request_id=request_id,
                error_code=run.failure_code,
                message=str(exc),
            )
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Editorial analysis failed: {exc}",
            ) from exc
