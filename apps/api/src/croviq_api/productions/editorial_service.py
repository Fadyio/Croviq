"""Editorial application service orchestrating Leo's deterministic preview pipeline."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import tempfile
import uuid

from fastapi import HTTPException, status

from croviq_agents.client import GenAIClient
from croviq_agents.editor import LeoVideoEditor
from croviq_api.config import get_settings
from croviq_api.media.storage import MediaStorage
from croviq_api.memory.store import ChannelMemoryStore
from croviq_api.productions.edl_service import EDLService
from croviq_api.productions.editorial_repository import EditorialRepository
from croviq_api.productions.render_repository import RenderRepository
from croviq_api.productions.repository import ProductionRepository
from croviq_api.productions.transcript_repository import TranscriptRepository
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.edl import EditDecisionList
from croviq_domain.editorial import (
    AgentActivity,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
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
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript
from croviq_domain.user import User
from croviq_media.inspector import MediaInspector
from croviq_media.render import RenderService
from croviq_media.silence import SilenceCleanupPlanner
from croviq_observability import EventType, log_ai_event, log_render_event

logger = logging.getLogger(__name__)


class EditorialService:
    """Run Leo editing, deterministic cut safety, EDL assembly, and Preview rendering."""

    def __init__(
        self,
        production_repo: ProductionRepository,
        transcript_repo: TranscriptRepository,
        memory_store: ChannelMemoryStore,
        media_inspector: MediaInspector,
        editorial_repo: EditorialRepository,
        genai_client: GenAIClient,
        render_repo: RenderRepository,
        edl_service: EDLService,
        render_service: RenderService,
        media_storage: MediaStorage,
    ) -> None:
        self._production_repo = production_repo
        self._transcript_repo = transcript_repo
        self._memory_store = memory_store
        self._media_inspector = media_inspector
        self._editorial_repo = editorial_repo
        self._genai_client = genai_client
        self._render_repo = render_repo
        self._edl_service = edl_service
        self._render_service = render_service
        self._media_storage = media_storage

    async def run_editorial_analysis(
        self,
        production_id: str,
        current_user: User,
        request_id: str = "unknown",
        force: bool = False,
    ) -> tuple[
        EditorialRun,
        EditorProposal,
        EditDecisionList,
        RenderArtifact,
        list[AgentActivity],
    ]:
        """Execute the complete active editorial pipeline and return its Preview artifact."""
        production = await self._get_owned_uploaded_production(production_id, current_user)
        transcript = await self._transcript_repo.get_transcript_by_production_id(production_id)
        if transcript is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Production '{production_id}' must be transcribed before running editorial analysis",
            )

        existing_run = await self._editorial_repo.get_latest_editorial_run(production_id)
        if existing_run is not None and not force:
            if existing_run.status == EditorialRunStatus.COMPLETED:
                proposal = (
                    await self._editorial_repo.get_editor_proposal(
                        production_id, existing_run.editor_proposal_id
                    )
                    if existing_run.editor_proposal_id
                    else None
                )
                if proposal is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Completed editorial run '{existing_run.run_id}' is missing its editor proposal",
                    )
                edl = await self._edl_service.assemble_edl(
                    production_id, current_user, request_id=request_id
                )
                preview = await self._render_media(
                    production, edl, ArtifactType.PREVIEW, request_id=request_id
                )
                activities = await self._editorial_repo.list_activities(
                    production_id, run_id=existing_run.run_id
                )
                return existing_run, proposal, edl, preview, activities
            if existing_run.status in {
                EditorialRunStatus.ANALYZING,
                EditorialRunStatus.REVIEWING,
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Editorial run '{existing_run.run_id}' is already in progress",
                )

        run = EditorialRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            production_id=production_id,
            status=EditorialRunStatus.ANALYZING,
            started_at=datetime.now(timezone.utc),
        )
        await self._editorial_repo.save_editorial_run(run)

        try:
            channel_profile, lessons = await self._load_memory_context(production.channel_id)
            analysis_input = self._build_analysis_input(production, transcript)
            silence_decisions = SilenceCleanupPlanner().plan_silence_cleanup(
                transcript=transcript,
                media_metadata=analysis_input.media_metadata,
            )
            raw_proposal, _usage, leo_activities = await LeoVideoEditor(
                client=self._genai_client
            ).analyze(
                analysis_input=analysis_input,
                channel_profile=channel_profile,
                lessons=lessons,
                silence_decisions=silence_decisions,
                run_id=run.run_id,
                request_id=request_id,
            )
            decisions, system_activities = self._merge_silence_decisions(
                production_id, run.run_id, silence_decisions, raw_proposal.decisions
            )
            proposal = EditorProposal(
                production_id=raw_proposal.production_id,
                agent="leo",
                model=raw_proposal.model,
                summary=raw_proposal.summary,
                decisions=decisions,
                section_plan=raw_proposal.section_plan,
                chapters=raw_proposal.chapters,
                overall_confidence=raw_proposal.overall_confidence,
            )
            proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
            await self._editorial_repo.save_editor_proposal(proposal, proposal_id=proposal_id)
            activities = system_activities + leo_activities
            await self._editorial_repo.save_activities(activities)

            run.editor_proposal_id = proposal_id
            run.status = EditorialRunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            await self._editorial_repo.save_editorial_run(run)

            edl = await self._edl_service.assemble_edl(
                production_id, current_user, request_id=request_id
            )
            preview = await self._render_media(
                production, edl, ArtifactType.PREVIEW, request_id=request_id
            )
            log_ai_event(
                event_type=EventType.EDITORIAL_RUN_COMPLETED,
                agent="leo",
                model=proposal.model,
                status="success",
                production_id=production_id,
                run_id=run.run_id,
                request_id=request_id,
            )
            return run, proposal, edl, preview, activities
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

    async def _get_owned_uploaded_production(
        self, production_id: str, current_user: User
    ) -> Production:
        production = await self._production_repo.get_production(production_id)
        if production is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production '{production_id}' not found",
            )
        if production.owner_user_id != current_user.user_id and not getattr(
            current_user, "is_admin", False
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you do not own this production",
            )
        if (
            production.source_media is None
            or production.source_media.status != SourceMediaStatus.UPLOADED
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Production source media is not uploaded",
            )
        return production

    async def _load_memory_context(
        self, channel_id: str
    ) -> tuple[ChannelMemoryProfile, list[ChannelLesson]]:
        profile = None
        lessons = None
        try:
            profile = await self._memory_store.get_profile(channel_id)
            lessons = await self._memory_store.get_lessons(channel_id)
        except Exception:
            logger.debug("Channel memory unavailable; using sample profile", exc_info=True)
        if profile is None:
            channel = await SampleChannelDataProvider().get_channel()
            profile = ChannelProfileBuilder.build_profile(channel)
            lessons = ChannelProfileBuilder.build_lessons(channel)
        return profile, lessons or []

    def _build_analysis_input(
        self, production: Production, transcript: Transcript
    ) -> SourceVideoAnalysisInput:
        try:
            metadata = self._media_inspector.inspect_media(
                production.source_media.original_filename
            )
        except Exception:
            metadata = MediaMetadata(
                duration_ms=transcript.duration_ms,
                width=1920,
                height=1080,
                frame_rate=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                rotation=0,
                size_bytes=production.source_media.size_bytes,
            )
        if metadata.duration_ms <= 0:
            metadata = metadata.model_copy(update={"duration_ms": transcript.duration_ms})
        return SourceVideoAnalysisInput(
            production_id=production.production_id,
            source_media=production.source_media,
            media_metadata=metadata,
            transcript=transcript,
            channel_id=production.channel_id,
        )

    @staticmethod
    def _merge_silence_decisions(
        production_id: str,
        run_id: str,
        silence_decisions: list[EditorDecision],
        leo_decisions: list[EditorDecision],
    ) -> tuple[list[EditorDecision], list[AgentActivity]]:
        merged: list[EditorDecision] = []
        removed_ms = 0
        for silence in silence_decisions:
            overlap = next(
                (
                    decision
                    for decision in leo_decisions
                    if max(decision.source_start_ms, silence.source_start_ms)
                    < min(decision.source_end_ms, silence.source_end_ms)
                ),
                None,
            )
            if overlap is None or overlap.decision_type == EditorDecisionType.TRIM_PAUSE:
                merged.append(silence)
                removed_ms += silence.source_end_ms - silence.source_start_ms
        for decision in leo_decisions:
            if decision.decision_type == EditorDecisionType.TRIM_PAUSE and any(
                max(decision.source_start_ms, silence.source_start_ms)
                < min(decision.source_end_ms, silence.source_end_ms)
                for silence in merged
                if silence.decision_id.startswith("silence_cut_")
            ):
                continue
            merged.append(decision)
        merged.sort(key=lambda decision: decision.source_start_ms)
        activities: list[AgentActivity] = []
        if removed_ms:
            activities.append(
                AgentActivity(
                    activity_id=f"act_sys_silence_{uuid.uuid4().hex[:8]}",
                    production_id=production_id,
                    run_id=run_id,
                    agent="System",
                    role="Audio Processor",
                    activity_type="tool_execution",
                    message=f"I found and removed {removed_ms / 1000.0:.1f}s of dead air.",
                    related_decision_id=None,
                    created_at=datetime.now(timezone.utc),
                )
            )
        return merged, activities

    async def _render_media(
        self,
        production: Production,
        edl: EditDecisionList,
        artifact_type: ArtifactType,
        request_id: str,
    ) -> RenderArtifact:
        existing = await self._render_repo.get_render_artifact_by_type(
            production.production_id, edl.edl_id, artifact_type
        )
        if existing and existing.status == ArtifactStatus.completed:
            metadata = await self._media_storage.get_object_metadata(
                existing.gcs_bucket, existing.gcs_object
            )
            if metadata.exists:
                return existing

        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        bucket = production.source_media.gcs_bucket
        object_name = build_render_artifact_gcs_object_path(
            workspace_id=production.workspace_id,
            production_id=production.production_id,
            edl_id=edl.edl_id,
            artifact_type=artifact_type,
        )
        settings = get_settings()
        log_render_event(
            event_type=EventType.RENDER_STARTED,
            production_id=production.production_id,
            edl_id=edl.edl_id,
            artifact_id=artifact_id,
            artifact_type=artifact_type.value,
            status="rendering",
            source_duration_ms=edl.source_duration_ms,
            target_duration_ms=edl.estimated_target_duration_ms,
            request_id=request_id,
            git_sha=settings.git_sha,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            output_path = Path(temp_dir) / "preview.mp4"
            try:
                await self._media_storage.download_object_to_path(
                    bucket=bucket,
                    object_name=production.source_media.gcs_object,
                    target_path=source_path,
                )
                result = self._render_service.render_preview(
                    source_path=source_path, edl=edl, output_path=output_path
                )
                await self._media_storage.upload_object_from_path(
                    bucket=bucket,
                    object_name=object_name,
                    source_path=output_path,
                    content_type="video/mp4",
                )
                artifact = RenderArtifact(
                    artifact_id=artifact_id,
                    production_id=production.production_id,
                    edl_id=edl.edl_id,
                    artifact_type=artifact_type,
                    status=ArtifactStatus.completed,
                    gcs_bucket=bucket,
                    gcs_object=object_name,
                    content_type="video/mp4",
                    size_bytes=result.size_bytes,
                    duration_ms=result.duration_ms,
                    width=result.width,
                    height=result.height,
                    frame_rate=result.frame_rate,
                    video_codec=result.video_codec,
                    audio_codec=result.audio_codec,
                    created_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                await self._render_repo.save_render_artifact(artifact)
                log_render_event(
                    event_type=EventType.RENDER_COMPLETED,
                    production_id=production.production_id,
                    edl_id=edl.edl_id,
                    artifact_id=artifact_id,
                    artifact_type=artifact_type.value,
                    status="completed",
                    source_duration_ms=edl.source_duration_ms,
                    target_duration_ms=edl.estimated_target_duration_ms,
                    rendered_duration_ms=result.duration_ms,
                    render_time_ms=result.render_time_ms,
                    size_bytes=result.size_bytes,
                    request_id=request_id,
                    git_sha=settings.git_sha,
                )
                return artifact
            except Exception as exc:
                log_render_event(
                    event_type=EventType.RENDER_FAILED,
                    production_id=production.production_id,
                    edl_id=edl.edl_id,
                    artifact_id=artifact_id,
                    artifact_type=artifact_type.value,
                    status="failed",
                    source_duration_ms=edl.source_duration_ms,
                    target_duration_ms=edl.estimated_target_duration_ms,
                    request_id=request_id,
                    git_sha=settings.git_sha,
                    error_code=str(exc),
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Rendering {artifact_type.value} failed: {exc}",
                ) from exc
