"""Director + Editor application service orchestrating Leo and Maya GenAI SDK agents."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import tempfile
import time
import uuid

from fastapi import HTTPException, status

from croviq_agents.client import GenAIClient
from croviq_agents.director import MayaDirector
from croviq_agents.editor import LeoDialogueEditor
from croviq_api.config import get_settings
from croviq_api.media.storage import MediaStorage
from croviq_api.memory.store import ChannelMemoryStore
from croviq_api.productions.edl_repository import EDLRepository
from croviq_api.productions.edl_service import EDLService
from croviq_api.productions.editorial_repository import EditorialRepository
from croviq_api.productions.render_repository import RenderRepository
from croviq_api.productions.render_review_repository import RenderReviewRepository
from croviq_api.productions.repository import ProductionRepository
from croviq_api.productions.transcript_repository import TranscriptRepository
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.edl import EditDecisionList
from croviq_domain.editorial import (
    AgentActivity,
    DirectorReview,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
    ShortCandidate,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, ChannelProfileBuilder
from croviq_domain.production import Production, SourceMediaStatus
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
    build_render_artifact_gcs_object_path,
)
from croviq_domain.render_review import RenderReview, RenderReviewVerdict
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript
from croviq_domain.user import User
from croviq_media.inspector import MediaInspector
from croviq_media.render import RenderService
from croviq_observability import (
    EventType,
    log_ai_event,
    log_master_approved_event,
    log_render_event,
    log_short_render_event,
)
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
        render_review_repo: RenderReviewRepository | None = None,
        edl_repo: EDLRepository | None = None,
        render_repo: RenderRepository | None = None,
        edl_service: EDLService | None = None,
        render_service: RenderService | None = None,
        media_storage: MediaStorage | None = None,
    ) -> None:
        self._production_repo = production_repo
        self._transcript_repo = transcript_repo
        self._memory_store = memory_store
        self._media_inspector = media_inspector
        self._editorial_repo = editorial_repo
        self._genai_client = genai_client
        self._render_review_repo = render_review_repo
        self._edl_repo = edl_repo
        self._render_repo = render_repo
        self._edl_service = edl_service
        self._render_service = render_service
        self._media_storage = media_storage
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
        # Reuse canonical persisted work before loading memory or invoking either model.
        existing_run = await self._editorial_repo.get_latest_editorial_run(production_id)
        resume_proposal: EditorProposal | None = None
        existing_activities: list[AgentActivity] = []
        if existing_run is not None:
            if existing_run.status == EditorialRunStatus.COMPLETED:
                proposal = (
                    await self._editorial_repo.get_editor_proposal(
                        production_id, existing_run.editor_proposal_id
                    )
                    if existing_run.editor_proposal_id
                    else None
                )
                review = (
                    await self._editorial_repo.get_director_review(
                        production_id, existing_run.director_review_id
                    )
                    if existing_run.director_review_id
                    else None
                )
                if proposal is None or review is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Completed editorial run '{existing_run.run_id}' is missing persisted output",
                    )
                activities = await self._editorial_repo.list_activities(
                    production_id, run_id=existing_run.run_id
                )
                return existing_run, proposal, review, activities

            if existing_run.status in {
                EditorialRunStatus.ANALYZING,
                EditorialRunStatus.REVIEWING,
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Editorial run '{existing_run.run_id}' is already in progress",
                )

            if existing_run.editor_proposal_id:
                resume_proposal = await self._editorial_repo.get_editor_proposal(
                    production_id, existing_run.editor_proposal_id
                )
                if resume_proposal is not None:
                    existing_activities = await self._editorial_repo.list_activities(
                        production_id, run_id=existing_run.run_id
                    )


        # 4. Load Channel Memory (profile and lessons with sample fallback)
        channel_profile = None
        lessons = None
        try:
            channel_profile = await self._memory_store.get_profile(prod.channel_id)
            lessons = await self._memory_store.get_lessons(prod.channel_id)
        except Exception:
            pass
        if not channel_profile:
            from croviq_domain.channel_provider import SampleChannelDataProvider
            from croviq_domain.memory import ChannelProfileBuilder

            provider = SampleChannelDataProvider()
            channel = await provider.get_channel()
            channel_profile = ChannelProfileBuilder.build_profile(channel)
            lessons = ChannelProfileBuilder.build_lessons(channel)
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

        # 6. Initialize a new run, or resume Maya from Leo's persisted proposal.
        if resume_proposal is not None and existing_run is not None:
            run = existing_run
            run.status = EditorialRunStatus.REVIEWING
            run.failure_code = None
            await self._editorial_repo.save_editorial_run(run)
            all_activities = existing_activities
        else:
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
            if resume_proposal is not None:
                proposal = resume_proposal
            else:
                # 7. Leo (Dialogue Editor) analysis pass
                editor = LeoDialogueEditor(client=self._genai_client)
                proposal, leo_usage, leo_activities = await editor.analyze(
                    analysis_input=analysis_input,
                    channel_profile=channel_profile,
                    lessons=lessons,
                    run_id=run.run_id,
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
                run_id=run.run_id,
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
                run_id=run.run_id,
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
                agent="maya" if run.editor_proposal_id else "leo",
                model="gemini-3.7-flash",
                status="failed",
                production_id=production_id,
                run_id=run.run_id,
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

    async def _load_memory_context(
        self, channel_id: str
    ) -> tuple[ChannelMemoryProfile, list[ChannelLesson]]:
        """Load ChannelProfile and ChannelLessons from memory store or sample fallback."""
        channel_profile = None
        lessons = None
        try:
            channel_profile = await self._memory_store.get_profile(channel_id)
            lessons = await self._memory_store.get_lessons(channel_id)
        except Exception:
            pass
        if not channel_profile:
            provider = SampleChannelDataProvider()
            channel = await provider.get_channel()
            channel_profile = ChannelProfileBuilder.build_profile(channel)
            lessons = ChannelProfileBuilder.build_lessons(channel)
        return channel_profile, lessons or []

    def _build_analysis_input(
        self, prod: Production, transcript: Transcript
    ) -> SourceVideoAnalysisInput:
        """Build SourceVideoAnalysisInput from production and transcript."""
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

        return SourceVideoAnalysisInput(
            production_id=prod.production_id,
            source_media=prod.source_media,
            media_metadata=media_metadata,
            transcript=transcript,
            channel_id=prod.channel_id,
        )

    async def _render_media(
        self,
        prod: Production,
        edl: EditDecisionList,
        artifact_type: ArtifactType,
        request_id: str = "unknown",
    ) -> RenderArtifact:
        """Execute deterministic video render for Preview or Master."""
        if not self._render_repo or not self._render_service or not self._media_storage:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Render services not initialized",
            )

        # Idempotency check: return cached completed artifact if exists
        existing = await self._render_repo.get_render_artifact_by_type(
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_type=artifact_type,
        )
        if existing and existing.status == ArtifactStatus.completed:
            meta = await self._media_storage.get_object_metadata(
                existing.gcs_bucket, existing.gcs_object
            )
            if meta.exists:
                return existing

        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        gcs_bucket = prod.source_media.gcs_bucket
        gcs_object = build_render_artifact_gcs_object_path(
            workspace_id=prod.workspace_id,
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_type=artifact_type,
        )
        now = datetime.now(timezone.utc)
        settings = get_settings()

        log_render_event(
            event_type=EventType.RENDER_STARTED,
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_id=artifact_id,
            artifact_type=artifact_type.value,
            status="rendering",
            source_duration_ms=edl.source_duration_ms,
            target_duration_ms=edl.estimated_target_duration_ms,
            request_id=request_id,
            git_sha=settings.git_sha,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            local_src = tmp_path / "source.mp4"
            local_out = tmp_path / f"{artifact_type.value.lower()}.mp4"

            try:
                await self._media_storage.download_object_to_path(
                    bucket=gcs_bucket,
                    object_name=prod.source_media.gcs_object,
                    target_path=local_src,
                )

                if artifact_type == ArtifactType.PREVIEW:
                    render_res = self._render_service.render_preview(
                        source_path=local_src,
                        edl=edl,
                        output_path=local_out,
                    )
                else:
                    render_res = self._render_service.render_master(
                        source_path=local_src,
                        edl=edl,
                        output_path=local_out,
                    )

                await self._media_storage.upload_object_from_path(
                    bucket=gcs_bucket,
                    object_name=gcs_object,
                    source_path=local_out,
                    content_type="video/mp4",
                )

                completed_at = datetime.now(timezone.utc)
                artifact = RenderArtifact(
                    artifact_id=artifact_id,
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_type=artifact_type,
                    status=ArtifactStatus.completed,
                    gcs_bucket=gcs_bucket,
                    gcs_object=gcs_object,
                    content_type="video/mp4",
                    size_bytes=render_res.size_bytes,
                    duration_ms=render_res.duration_ms,
                    width=render_res.width,
                    height=render_res.height,
                    frame_rate=render_res.frame_rate,
                    video_codec=render_res.video_codec,
                    audio_codec=render_res.audio_codec,
                    created_at=now,
                    completed_at=completed_at,
                    failure_code=None,
                )
                await self._render_repo.save_render_artifact(artifact)

                log_render_event(
                    event_type=EventType.RENDER_COMPLETED,
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_id=artifact_id,
                    artifact_type=artifact_type.value,
                    status="completed",
                    source_duration_ms=edl.source_duration_ms,
                    target_duration_ms=edl.estimated_target_duration_ms,
                    rendered_duration_ms=render_res.duration_ms,
                    render_time_ms=render_res.render_time_ms,
                    size_bytes=render_res.size_bytes,
                    request_id=request_id,
                    git_sha=settings.git_sha,
                )
                return artifact
            except Exception as exc:
                sanitized_err = str(exc)
                log_render_event(
                    event_type=EventType.RENDER_FAILED,
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_id=artifact_id,
                    artifact_type=artifact_type.value,
                    status="failed",
                    source_duration_ms=edl.source_duration_ms,
                    target_duration_ms=edl.estimated_target_duration_ms,
                    request_id=request_id,
                    git_sha=settings.git_sha,
                    error_code=sanitized_err,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Rendering {artifact_type.value} failed: {sanitized_err}",
                ) from exc


    async def _execute_short_render(
        self,
        prod: Production,
        edl: EditDecisionList,
        short_candidate: ShortCandidate,
        transcript: Transcript | None,
        request_id: str = "unknown",
    ) -> RenderArtifact:
        """Execute deterministic vertical Short render with word-synced captions."""
        if self._render_repo:
            existing_short = await self._render_repo.get_render_artifact_by_type(
                production_id=prod.production_id,
                edl_id=edl.edl_id,
                artifact_type=ArtifactType.SHORT,
            )
            if existing_short and existing_short.status == ArtifactStatus.completed:
                return existing_short

        if not self._render_service or not self._media_storage or not self._render_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Rendering infrastructure not initialized",
            )

        now = datetime.now(timezone.utc)
        artifact_id = f"art_short_{uuid.uuid4().hex[:12]}"
        gcs_bucket = prod.source_media.gcs_bucket
        gcs_object = build_render_artifact_gcs_object_path(
            workspace_id=prod.workspace_id,
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_type=ArtifactType.SHORT,
        )

        settings = get_settings()
        log_short_render_event(
            event_type=EventType.SHORT_RENDER_STARTED,
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_id=artifact_id,
            short_start_ms=short_candidate.start_ms,
            short_end_ms=short_candidate.end_ms,
            status="started",
            request_id=request_id,
            git_sha=settings.git_sha,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            local_src = tmp_path / "source.mp4"
            local_out = tmp_path / "short.mp4"

            try:
                await self._media_storage.download_object_to_path(
                    bucket=prod.source_media.gcs_bucket,
                    object_name=prod.source_media.gcs_object,
                    target_path=local_src,
                )

                render_res = self._render_service.render_short(
                    source_path=local_src,
                    edl=edl,
                    short_candidate=short_candidate,
                    transcript=transcript,
                    output_path=local_out,
                )

                await self._media_storage.upload_object_from_path(
                    bucket=gcs_bucket,
                    object_name=gcs_object,
                    source_path=local_out,
                    content_type="video/mp4",
                )

                completed_at = datetime.now(timezone.utc)
                artifact = RenderArtifact(
                    artifact_id=artifact_id,
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_type=ArtifactType.SHORT,
                    status=ArtifactStatus.completed,
                    gcs_bucket=gcs_bucket,
                    gcs_object=gcs_object,
                    content_type="video/mp4",
                    size_bytes=render_res.size_bytes,
                    duration_ms=render_res.duration_ms,
                    width=render_res.width,
                    height=render_res.height,
                    frame_rate=render_res.frame_rate,
                    video_codec=render_res.video_codec,
                    audio_codec=render_res.audio_codec,
                    created_at=now,
                    completed_at=completed_at,
                    failure_code=None,
                )
                await self._render_repo.save_render_artifact(artifact)

                log_short_render_event(
                    event_type=EventType.SHORT_RENDER_COMPLETED,
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_id=artifact_id,
                    short_start_ms=short_candidate.start_ms,
                    short_end_ms=short_candidate.end_ms,
                    duration_ms=render_res.duration_ms,
                    render_time_ms=render_res.render_time_ms,
                    size_bytes=render_res.size_bytes,
                    status="completed",
                    request_id=request_id,
                    git_sha=settings.git_sha,
                )
                return artifact
            except Exception as exc:
                sanitized_err = str(exc)
                log_short_render_event(
                    event_type=EventType.SHORT_RENDER_FAILED,
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_id=artifact_id,
                    status="failed",
                    request_id=request_id,
                    git_sha=settings.git_sha,
                    error_code=sanitized_err,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Rendering SHORT failed: {sanitized_err}",
                ) from exc

    async def review_preview(
        self,
        production_id: str,
        current_user: User,
        request_id: str = "unknown",
    ) -> tuple[RenderReview, RenderArtifact | None, RenderReview | None, str, list[AgentActivity]]:
        """Execute Maya's post-render review on rendered Preview video output and gate Master render."""
        if not self._render_review_repo or not self._edl_repo or not self._render_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Render review repositories not initialized",
            )

        # 1. Load production & verify ownership
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

        # 2. Check EDL and Preview artifact prerequisites
        edl = await self._edl_repo.get_latest_edl(production_id)
        if not edl:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Production '{production_id}' has no assembled EDL. Assemble an EDL before review.",
            )

        preview_artifact = await self._render_repo.get_render_artifact_by_type(
            production_id=production_id,
            edl_id=edl.edl_id,
            artifact_type=ArtifactType.PREVIEW,
        )
        if not preview_artifact or preview_artifact.status != ArtifactStatus.completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Production '{production_id}' has no completed PREVIEW render to review.",
            )

        # 3. IDEMPOTENCY CHECK: if a RenderReview already exists for this exact EDL + preview, return it!
        existing_review = await self._render_review_repo.get_render_review_by_preview(
            production_id=production_id,
            edl_id=edl.edl_id,
            preview_artifact_id=preview_artifact.artifact_id,
        )
        if existing_review is not None:
            master_art = await self._render_repo.get_render_artifact_by_type(
                production_id=production_id,
                edl_id=edl.edl_id,
                artifact_type=ArtifactType.MASTER,
            )
            status_str = "complete" if (master_art and master_art.status == ArtifactStatus.completed) else ("approved" if existing_review.approved_for_master else "needs_manual_review")
            activities = await self._editorial_repo.list_activities(production_id)
            return existing_review, master_art, None, status_str, activities

        # 4. Check prior review history for bounded correction limit
        prior_reviews = await self._render_review_repo.list_render_reviews(production_id)
        if len(prior_reviews) >= 2:
            latest_prior = prior_reviews[0]
            activities = await self._editorial_repo.list_activities(production_id)
            return latest_prior, None, None, "needs_manual_review", activities

        # 5. Load inputs for Maya review
        transcript = await self._transcript_repo.get_transcript_by_production_id(production_id)
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Production '{production_id}' has no transcript",
            )

        latest_run = await self._editorial_repo.get_latest_editorial_run(production_id)
        proposal = None
        director_review = None
        if latest_run and latest_run.editor_proposal_id:
            proposal = await self._editorial_repo.get_editor_proposal(
                production_id, latest_run.editor_proposal_id
            )
        if latest_run and latest_run.director_review_id:
            director_review = await self._editorial_repo.get_director_review(
                production_id, latest_run.director_review_id
            )

        if not proposal:
            proposal = EditorProposal(
                production_id=production_id,
                model="gemini-3.7-flash",
                summary="Dialogue edit pass",
                decisions=[],
                short_candidate=None,
                overall_confidence=0.9,
            )

        channel_profile, lessons = await self._load_memory_context(prod.channel_id)

        # 6. Maya (Director) watches rendered preview video
        maya = MayaDirector(client=self._genai_client)
        render_review, maya_usage, maya_activities = await maya.review_render(
            preview_gcs_bucket=preview_artifact.gcs_bucket,
            preview_gcs_object=preview_artifact.gcs_object,
            preview_artifact_id=preview_artifact.artifact_id,
            edl=edl,
            proposal=proposal,
            director_review=director_review,
            transcript=transcript,
            production_id=production_id,
            preview_mime_type=preview_artifact.content_type or "video/mp4",
            channel_profile=channel_profile,
            lessons=lessons,
            run_id=latest_run.run_id if latest_run else None,
            request_id=request_id,
        )

        # Save review and activities
        await self._render_review_repo.save_render_review(render_review)
        await self._editorial_repo.save_activities(maya_activities)
        all_activities = list(maya_activities)

        settings = get_settings()

        # 7. Branch on verdict
        if render_review.verdict == RenderReviewVerdict.APPROVE:
            log_master_approved_event(
                production_id=production_id,
                edl_id=edl.edl_id,
                preview_artifact_id=preview_artifact.artifact_id,
                review_id=render_review.review_id,
                run_id=latest_run.run_id if latest_run else None,
                request_id=request_id,
                git_sha=settings.git_sha,
            )
            # Automatically trigger Master render using the SAME approved EDL
            master_art = await self._render_media(
                prod=prod,
                edl=edl,
                artifact_type=ArtifactType.MASTER,
                request_id=request_id,
            )
            # If ShortCandidate exists, automatically render Short
            if proposal and proposal.short_candidate:
                try:
                    await self._execute_short_render(
                        prod=prod,
                        edl=edl,
                        short_candidate=proposal.short_candidate,
                        transcript=transcript,
                        request_id=request_id,
                    )
                except Exception as short_exc:
                    logger.warning("Automatic Short render failed after Master approval: %s", short_exc)
            return render_review, master_art, None, "complete", all_activities

        # 8. CORRECT: Execute ONE bounded correction loop
        if len(prior_reviews) == 0:
            # Step A: Leo correction pass
            leo = LeoDialogueEditor(client=self._genai_client)
            analysis_input = self._build_analysis_input(prod, transcript)
            revised_proposal, leo_usage, leo_activities = await leo.revise(
                analysis_input=analysis_input,
                proposal=proposal,
                render_review=render_review,
                channel_profile=channel_profile,
                lessons=lessons,
                run_id=latest_run.run_id if latest_run else None,
                request_id=request_id,
            )
            revised_proposal_id = f"prop_corr_{uuid.uuid4().hex[:8]}"
            await self._editorial_repo.save_editor_proposal(
                revised_proposal, proposal_id=revised_proposal_id
            )
            await self._editorial_repo.save_activities(leo_activities)
            all_activities.extend(leo_activities)

            # Step B: Maya plan review on revised proposal
            new_director_review, plan_usage, plan_activities = await maya.review(
                analysis_input=analysis_input,
                proposal=revised_proposal,
                channel_profile=channel_profile,
                lessons=lessons,
                run_id=latest_run.run_id if latest_run else None,
                request_id=request_id,
            )
            revised_review_id = f"rev_corr_{uuid.uuid4().hex[:8]}"
            await self._editorial_repo.save_director_review(
                new_director_review, review_id=revised_review_id
            )
            await self._editorial_repo.save_activities(plan_activities)
            all_activities.extend(plan_activities)

            # Save updated editorial run pointing to revised proposal and review
            corr_run_id = latest_run.run_id if latest_run else f"run_{uuid.uuid4().hex[:12]}"
            corr_run = EditorialRun(
                run_id=corr_run_id,
                production_id=production_id,
                status=EditorialRunStatus.COMPLETED,
                editor_proposal_id=revised_proposal_id,
                director_review_id=revised_review_id,
                started_at=latest_run.started_at if latest_run else datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            await self._editorial_repo.save_editorial_run(corr_run)

            # Step C: Assemble new EDL version
            if self._edl_service:
                new_edl = await self._edl_service.assemble_edl(
                    production_id=production_id,
                    current_user=current_user,
                    request_id=request_id,
                )
            else:
                new_edl = edl

            # Step D: Render new PREVIEW artifact
            new_preview = await self._render_media(
                prod=prod,
                edl=new_edl,
                artifact_type=ArtifactType.PREVIEW,
                request_id=request_id,
            )

            # Step E: Maya watches corrected Preview (FINAL 2nd review)
            second_render_review, second_usage, final_activities = await maya.review_render(
                preview_gcs_bucket=new_preview.gcs_bucket,
                preview_gcs_object=new_preview.gcs_object,
                preview_artifact_id=new_preview.artifact_id,
                edl=new_edl,
                proposal=revised_proposal,
                director_review=new_director_review,
                transcript=transcript,
                production_id=production_id,
                preview_mime_type=new_preview.content_type or "video/mp4",
                channel_profile=channel_profile,
                lessons=lessons,
                run_id=latest_run.run_id if latest_run else None,
                request_id=request_id,
            )
            await self._render_review_repo.save_render_review(second_render_review)
            await self._editorial_repo.save_activities(final_activities)
            all_activities.extend(final_activities)

            if second_render_review.verdict == RenderReviewVerdict.APPROVE:
                log_master_approved_event(
                    production_id=production_id,
                    edl_id=new_edl.edl_id,
                    preview_artifact_id=new_preview.artifact_id,
                    review_id=second_render_review.review_id,
                    run_id=latest_run.run_id if latest_run else None,
                    request_id=request_id,
                    git_sha=settings.git_sha,
                )
                master_art = await self._render_media(
                    prod=prod,
                    edl=new_edl,
                    artifact_type=ArtifactType.MASTER,
                    request_id=request_id,
                )
                if revised_proposal and revised_proposal.short_candidate:
                    try:
                        await self._execute_short_render(
                            prod=prod,
                            edl=new_edl,
                            short_candidate=revised_proposal.short_candidate,
                            transcript=transcript,
                            request_id=request_id,
                        )
                    except Exception as short_exc:
                        logger.warning("Automatic Short render failed after Master approval: %s", short_exc)
                return render_review, master_art, second_render_review, "complete", all_activities
            else:
                # Second post-render review is FINAL -> needs_manual_review
                return render_review, None, second_render_review, "needs_manual_review", all_activities

        # Prior reviews already exist and returned CORRECT again -> needs_manual_review
        return render_review, None, None, "needs_manual_review", all_activities
