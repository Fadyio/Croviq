"""API routes for Production lifecycle and direct GCS media upload."""

import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal
import tempfile
import time
import uuid
import wave

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from croviq_api.auth.dependencies import get_current_user
from croviq_api.config import get_settings
from croviq_api.media.dependencies import (
    get_audio_extractor,
    get_media_inspector,
    get_media_storage,
    get_transcription_service,
)
from croviq_api.media.logging import log_media_upload_event
from croviq_api.media.storage import MediaStorage, MediaStorageError
from croviq_api.productions.repository import (
    ProductionRepository,
    get_production_repository,
)
from croviq_media.transcript import GeminiTranscriptionService
from croviq_api.productions.transcript_repository import (
    TranscriptRepository,
    get_transcript_repository,
)
from croviq_api.productions.render_repository import (
    RenderRepository,
    get_render_repository,
)
from croviq_api.productions.edl_repository import (
    EDLRepository,
    get_edl_repository,
)
from croviq_api.productions.dependencies import (
    get_render_service,
    get_genai_client,
)
from croviq_media.render import RenderError, RenderService
from croviq_api.productions.dependencies import (
    get_editorial_service,
    get_edl_service,
)
from croviq_api.productions.edl_service import EDLService
from croviq_api.productions.editorial_repository import (
    EditorialRepository,
    get_editorial_repository,
)
from croviq_api.productions.editorial_service import EditorialService
from croviq_api.productions.schemas import (
    AssembleEDLResponse,
    EDLDetailResponse,
    AnalyzeProductionResponse,
    CorrectedScriptResponse,
    CreateUploadRequest,
    CreateUploadResponse,
    DeleteProductionResponse,
    EditorialRunDetailResponse,
    GenerateBackgroundMusicRequest,
    ProductionListResponse,
    TranscribeProductionResponse,
    MediaOutputState,
    ProductionPlaybackResponse,
    RenderArtifactResponse,
    RenderListResponse,
    StudioVoiceGenerationResponse,
    BRollListResponse,
    PackagingDetailResponse,
    UpdateBackgroundMusicRequest,
    UpdatePackagingOverridesRequest,
    GenerateReleaseReviewRequest,
    ReleaseReviewDetailResponse,
    PublishPreparationResponse,
    PublishRequest,
    PublishJobDetailResponse,
)
from croviq_domain.transcript import (
    CorrectedTranscript,
    CorrectedTranscriptSegment,
    EntailmentVerdict,
    ScriptCorrectionChangeType,
)
from croviq_domain.edl import BackgroundMusicMix, VoiceoverSegment, map_source_time_to_edited
from croviq_domain.editorial import EditorSelectionContext, EditorVoiceMode
from croviq_api.productions.release_review_repository import (
    ReleaseReviewRepository,
    get_release_review_repository,
)
from croviq_agents.iris import IrisQAAgent
from croviq_domain.release_review import (
    ClaimSupportStatus,
    ClaimVerification,
    ReleaseChecklist,
    ReleaseIssue,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseReview,
    ReleaseStatus,
    ReleaseVerdict,
    ThumbnailEvaluation,
    build_release_fingerprint,
    get_creator_facing_release_status,
    verify_release_fingerprint,
)
from croviq_api.productions.packaging_repository import (
    PackagingRepository,
    get_packaging_repository,
)
from croviq_api.channels.research_repository import (
    ResearchRepository,
    get_research_repository,
)
from croviq_api.memory.dependencies import get_memory_store
from croviq_api.memory.store import ChannelMemoryStore
from croviq_domain.agent_config import AgentId
from croviq_domain.packaging import (
    CreatorPackageOverrides,
    PackagingChapter,
    PackagingProposal,
    ThumbnailConcept,
    TitleAngle,
    TitleCandidate,
)
from croviq_domain.publish import (
    PublishJobStatus,
    ThumbnailArtifact,
    ThumbnailUploadStatus,
    YouTubePublishJob,
)
from croviq_api.productions.dependencies import (
    get_publish_service,
    get_publish_job_repository,
)
from croviq_api.productions.publish_service import YouTubePublishService
from croviq_api.productions.publish_job_repository import PublishJobRepository
from croviq_api.channels.youtube_repository import (
    YouTubeConnectionRepository,
    get_youtube_connection_repository,
)
from croviq_api.channels.youtube_provider import SCOPE_YOUTUBE_UPLOAD
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.memory import ChannelProfileBuilder
from croviq_api.productions.studio_voice_repository import (
    StudioVoiceRepository,
    get_studio_voice_repository,
)
from croviq_api.productions.broll_repository import (
    BRollRepository,
    get_broll_repository,
)
from croviq_api.workspaces.agent_config_repository import (
    AgentConfigRepository,
    get_agent_config_repository,
)
from croviq_agents.client import GenAIClient
from croviq_agents.voice import StudioVoiceSynthesizer
from croviq_api.workspaces.chat_service import (
    AgentChatService,
    clear_production_chat_history,
    get_production_chat_history,
)
from croviq_domain.narration import (
    BRollArtifact,
    BRollArtifactStatus,
    NarrationSegment,
    NarrationSegmentStatus,
    StudioVoiceResult,
)
from croviq_api.workspaces.repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import (
    ALLOWED_MEDIA_TYPES,
    MAX_UPLOAD_SIZE_BYTES,
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
    build_source_media_gcs_object_path,
    validate_media_file,
)
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
    build_render_artifact_gcs_object_path,
)
from croviq_domain.edl import EditDecisionList
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript
from croviq_domain.user import User
from croviq_media.audio import AudioExtractionError, AudioExtractor
from croviq_media.inspector import MediaInspector, MediaInspectionError
from croviq_media.transcript import TranscriptionError, TranscriptionService
from croviq_observability import (
    log_event,
    EventType,
    log_media_inspect_event,
    log_render_event,
    log_transcription_event,
)

router = APIRouter(tags=["Productions & Uploads"])

class ProductionChatSelectedElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., min_length=1)
    id: str = Field(..., min_length=1)
    label: str = Field(default="")
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)


class ProductionChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=10_000)
    editor_context: EditorSelectionContext | None = None
    selected_range_ms: tuple[int, int] | None = None
    selected_element: ProductionChatSelectedElement | None = None
    current_playhead_ms: int | None = Field(default=None, ge=0)

class ProductionChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: Literal["assistant"] = "assistant"
    content: str
    tool_executions: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    edl: EditDecisionList | None = None
    timeline_updated: bool = False
    voiceover_updated: bool = False
    preview_updated: bool = False
    seek_range: list[int] | None = None


class ProductionChatHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    production_id: str
    messages: list[dict[str, Any]] = Field(default_factory=list)


@router.post(
    "/uploads",
    response_model=CreateUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate Direct GCS Media Upload",
    description="Registers an upload session, creates a pending Production record, and returns a short-lived V4 signed PUT URL for direct browser-to-GCS upload.",
)
async def create_upload(
    payload: CreateUploadRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> CreateUploadResponse:
    request_id = getattr(request.state, "request_id", "unknown")

    # Resolve active workspace
    workspace, _ = await workspace_repo.get_or_create_default_workspace(
        current_user, default_name="Croviq"
    )

    # Validate file type, extension coherence, and size limit
    try:
        norm_content_type, _ = validate_media_file(
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except ValueError as val_err:
        log_media_upload_event(
            event_type="upload.failed",
            status=status.HTTP_400_BAD_REQUEST,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=workspace.workspace_id,
            channel_id=payload.channel_id,
            production_id="unknown",
            upload_id="unknown",
            filename=payload.filename,
            size_bytes=payload.size_bytes,
            content_type=payload.content_type,
            error_code="invalid_media_file",
            message=str(val_err),
            exception=val_err,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )

    # Generate server-controlled IDs and object path
    production_id = f"prod_{uuid.uuid4().hex[:12]}"
    upload_id = f"upl_{uuid.uuid4().hex[:12]}"
    settings = get_settings()
    bucket_name = settings.media_bucket_name

    gcs_object = build_source_media_gcs_object_path(
        workspace_id=workspace.workspace_id,
        production_id=production_id,
        upload_id=upload_id,
        filename=payload.filename,
    )

    # Generate short-lived signed upload target
    try:
        signed_target = await media_storage.generate_signed_upload_target(
            bucket=bucket_name,
            object_name=gcs_object,
            content_type=norm_content_type,
            expiry_seconds=settings.signed_url_expiry_seconds,
        )
    except Exception as exc:
        log_media_upload_event(
            event_type="upload.failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=workspace.workspace_id,
            channel_id=payload.channel_id,
            production_id=production_id,
            upload_id=upload_id,
            filename=payload.filename,
            size_bytes=payload.size_bytes,
            content_type=norm_content_type,
            error_code="signed_url_generation_failed",
            message=f"Failed to generate pre-signed upload URL: {type(exc).__name__}",
            exception=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate secure upload target",
        )

    # Persist pending Production and SourceMedia record
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id=upload_id,
        original_filename=payload.filename,
        content_type=norm_content_type,
        size_bytes=payload.size_bytes,
        gcs_bucket=bucket_name,
        gcs_object=gcs_object,
        status=SourceMediaStatus.PENDING,
        created_at=now,
    )
    production = Production(
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        channel_id=payload.channel_id,
        owner_user_id=current_user.user_id,
        source_media=source_media,
        status=ProductionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    await production_repo.create_production(production)

    log_media_upload_event(
        event_type="upload.created",
        status=status.HTTP_201_CREATED,
        request_id=request_id,
        user_id=current_user.user_id,
        workspace_id=workspace.workspace_id,
        channel_id=payload.channel_id,
        production_id=production_id,
        upload_id=upload_id,
        filename=payload.filename,
        size_bytes=payload.size_bytes,
        content_type=norm_content_type,
        message=f"Registered upload {upload_id} for production {production_id}",
    )

    return CreateUploadResponse(
        production_id=production_id,
        upload_id=upload_id,
        upload_url=signed_target.upload_url,
        method=signed_target.method,
        required_headers=signed_target.required_headers,
        expires_at=signed_target.expires_at,
    )


@router.post(
    "/uploads/{upload_id}/complete",
    response_model=Production,
    status_code=status.HTTP_200_OK,
    summary="Verify and Complete Media Upload",
    description="Verifies the uploaded object in GCS (existence, size, content type) and transitions the Production to uploaded.",
)
async def complete_upload(
    upload_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> Production:
    request_id = getattr(request.state, "request_id", "unknown")

    # Locate production by upload_id
    production = await production_repo.get_production_by_upload_id(upload_id)
    if not production or not production.source_media:
        log_media_upload_event(
            event_type="upload.failed",
            status=status.HTTP_404_NOT_FOUND,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id="unknown",
            channel_id="unknown",
            production_id="unknown",
            upload_id=upload_id,
            error_code="upload_not_found",
            message=f"Upload {upload_id} not found",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload session '{upload_id}' not found",
        )

    # Verify authorization
    if production.owner_user_id != current_user.user_id:
        log_media_upload_event(
            event_type="upload.failed",
            status=status.HTTP_403_FORBIDDEN,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=production.workspace_id,
            channel_id=production.channel_id,
            production_id=production.production_id,
            upload_id=upload_id,
            error_code="upload_forbidden",
            message=f"User {current_user.user_id} not authorized to complete upload {upload_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own this production",
        )

    # Idempotent return if already verified and completed
    if (
        production.status == ProductionStatus.UPLOADED
        and production.source_media.status == SourceMediaStatus.UPLOADED
    ):
        log_media_upload_event(
            event_type="upload.completed",
            status=status.HTTP_200_OK,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=production.workspace_id,
            channel_id=production.channel_id,
            production_id=production.production_id,
            upload_id=upload_id,
            filename=production.source_media.original_filename,
            size_bytes=production.source_media.size_bytes,
            content_type=production.source_media.content_type,
            message=f"Upload {upload_id} already completed (idempotent)",
        )
        return production

    # Inspect object in GCS
    try:
        metadata = await media_storage.get_object_metadata(
            bucket=production.source_media.gcs_bucket,
            object_name=production.source_media.gcs_object,
        )
    except Exception as exc:
        log_media_upload_event(
            event_type="upload.failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=production.workspace_id,
            channel_id=production.channel_id,
            production_id=production.production_id,
            upload_id=upload_id,
            error_code="storage_inspection_failed",
            message=f"Failed to inspect storage object: {type(exc).__name__}",
            exception=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage inspection failed",
        )

    # Validate object existence and size
    if not metadata.exists:
        log_media_upload_event(
            event_type="upload.failed",
            status=status.HTTP_400_BAD_REQUEST,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=production.workspace_id,
            channel_id=production.channel_id,
            production_id=production.production_id,
            upload_id=upload_id,
            filename=production.source_media.original_filename,
            error_code="object_not_found",
            message=f"GCS object '{production.source_media.gcs_object}' does not exist in bucket '{production.source_media.gcs_bucket}'",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media file was not found in storage. Upload may still be in progress or failed.",
        )

    if metadata.size_bytes <= 0:
        log_media_upload_event(
            event_type="upload.failed",
            status=status.HTTP_400_BAD_REQUEST,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=production.workspace_id,
            channel_id=production.channel_id,
            production_id=production.production_id,
            upload_id=upload_id,
            filename=production.source_media.original_filename,
            error_code="empty_object",
            message="GCS object size is 0 bytes",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded media file is empty (0 bytes)",
        )

    if metadata.size_bytes > MAX_UPLOAD_SIZE_BYTES:
        log_media_upload_event(
            event_type="upload.failed",
            status=status.HTTP_400_BAD_REQUEST,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=production.workspace_id,
            channel_id=production.channel_id,
            production_id=production.production_id,
            upload_id=upload_id,
            filename=production.source_media.original_filename,
            size_bytes=metadata.size_bytes,
            error_code="size_exceeded",
            message=f"Uploaded object size {metadata.size_bytes} exceeds {MAX_UPLOAD_SIZE_BYTES} bytes",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file exceeds maximum limit of {MAX_UPLOAD_SIZE_BYTES} bytes",
        )

    # Mark uploaded
    now = datetime.now(timezone.utc)
    updated_source_media = production.source_media.model_copy(
        update={
            "status": SourceMediaStatus.UPLOADED,
            "size_bytes": metadata.size_bytes,
            "uploaded_at": now,
        }
    )
    updated_production = production.model_copy(
        update={
            "status": ProductionStatus.UPLOADED,
            "source_media": updated_source_media,
            "updated_at": now,
        }
    )

    saved_production = await production_repo.update_production(updated_production)

    log_media_upload_event(
        event_type="upload.completed",
        status=status.HTTP_200_OK,
        request_id=request_id,
        user_id=current_user.user_id,
        workspace_id=production.workspace_id,
        channel_id=production.channel_id,
        production_id=production.production_id,
        upload_id=upload_id,
        filename=production.source_media.original_filename,
        size_bytes=metadata.size_bytes,
        content_type=production.source_media.content_type,
        message=f"Successfully verified and completed upload {upload_id} for production {production.production_id}",
    )

    return saved_production


@router.get(
    "/productions",
    response_model=ProductionListResponse,
    summary="List Recent Productions",
    description="Retrieve a list of recent content productions belonging to the creator's workspace.",
)
async def list_productions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    limit: int = 20,
) -> ProductionListResponse:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(
        current_user, default_name="Croviq"
    )
    prods = await production_repo.list_productions(
        workspace_id=workspace.workspace_id, limit=limit
    )
    return ProductionListResponse(
        productions=prods,
        total=len(prods),
    )


async def _get_owned_production(
    production_id: str,
    current_user: User,
    production_repo: ProductionRepository,
) -> Production:
    """Retrieve a production and verify ownership, raising 404 or 403 as appropriate."""
    prod = await production_repo.get_production(production_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )
    if prod.owner_user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own this production",
        )
    return prod


@router.get(
    "/productions/{production_id}",
    response_model=Production,
    summary="Get Production by ID",
    description="Retrieve a single Production record by its identifier.",
)
async def get_production(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
) -> Production:
    return await _get_owned_production(production_id, current_user, production_repo)


@router.delete(
    "/productions/{production_id}",
    response_model=DeleteProductionResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Production",
    description="Idempotent coordinated deletion of a production: sets status to deleting, removes GCS production prefix, purges external transcript records and subcollections, and deletes root production document last.",
)
async def delete_production(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    editorial_repo: Annotated[EditorialRepository, Depends(get_editorial_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    studio_voice_repo: Annotated[StudioVoiceRepository, Depends(get_studio_voice_repository)],
    broll_repo: Annotated[BRollRepository, Depends(get_broll_repository)],
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)],
    release_review_repo: Annotated[ReleaseReviewRepository, Depends(get_release_review_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> DeleteProductionResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)

    prod = await production_repo.get_production(production_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )
    if prod.workspace_id != workspace.workspace_id or prod.owner_user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to delete this production",
        )

    settings = get_settings()
    bucket_name = (
        prod.source_media.gcs_bucket
        if prod.source_media and prod.source_media.gcs_bucket
        else settings.media_bucket_name
    )

    # 0. Set status to deleting
    prod.status = ProductionStatus.DELETING
    prod.updated_at = datetime.now(timezone.utc)
    try:
        await production_repo.update_production(prod)
    except Exception as exc:
        logger.warning("Could not set production %s to deleting status: %s", production_id, exc)

    deleted_storage_count = 0
    # 1. Delete production prefix objects in GCS
    prefix = f"workspaces/{prod.workspace_id}/productions/{production_id}/"
    try:
        deleted_storage_count += await media_storage.delete_prefix(bucket_name, prefix)
    except Exception as exc:
        logger.warning("Error deleting storage prefix %s: %s", prefix, exc)
    # 2. Delete source media object if located outside prefix
    if prod.source_media and prod.source_media.gcs_object:
        if not prod.source_media.gcs_object.startswith(prefix):
            try:
                if await media_storage.delete_object(
                    prod.source_media.gcs_bucket or bucket_name,
                    prod.source_media.gcs_object,
                ):
                    deleted_storage_count += 1
            except Exception as exc:
                logger.warning("Error deleting source media object %s: %s", prod.source_media.gcs_object, exc)

    # 3. Clean up Firestore records and subcollections
    try:
        await transcript_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting transcripts for %s: %s", production_id, exc)

    try:
        await editorial_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting editorial records for %s: %s", production_id, exc)

    try:
        await edl_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting EDL records for %s: %s", production_id, exc)

    try:
        await render_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting renders for %s: %s", production_id, exc)

    try:
        await studio_voice_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting studio voice for %s: %s", production_id, exc)

    try:
        await broll_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting broll for %s: %s", production_id, exc)


    try:
        await packaging_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting packaging records for %s: %s", production_id, exc)

    try:
        await release_review_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting release reviews for %s: %s", production_id, exc)
    # 4. Delete root production record
    await production_repo.delete_production(production_id)

    deleted_at = datetime.now(timezone.utc)
    log_event(
        event_type="production.deleted",
        status=status.HTTP_200_OK,
        request_id=request_id,
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        user_id=current_user.user_id,
        deleted_storage_objects_count=deleted_storage_count,
        message=f"Production '{production_id}' and all associated storage artifacts were deleted successfully",
    )

    return DeleteProductionResponse(
        status="deleted",
        production_id=production_id,
        deleted_storage_objects_count=deleted_storage_count,
        deleted_at=deleted_at,
    )


@router.post(
    "/productions/{production_id}/transcribe",
    response_model=TranscribeProductionResponse,
    summary="Transcribe Production Source Media",
    description="Extract 16 kHz mono WAV audio from uploaded source media and transcribe it with Gemini 3.5 Transcribe.",
)
async def transcribe_production(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    transcription_service: Annotated[TranscriptionService, Depends(get_transcription_service)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
    audio_extractor: Annotated[AudioExtractor, Depends(get_audio_extractor)],
    media_inspector: Annotated[MediaInspector, Depends(get_media_inspector)],
) -> TranscribeProductionResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    prod = await _get_owned_production(production_id, current_user, production_repo)

    # 1. Idempotency check: if transcript already exists for this production, return it immediately
    existing = await transcript_repo.get_transcript_by_production_id(production_id)
    if existing:
        log_transcription_event(
            event_type="transcription.completed",
            status=200,
            request_id=request_id,
            production_id=production_id,
            transcript_id=existing.transcript_id,
            duration_ms=existing.duration_ms,
            word_count=existing.word_count,
            segment_count=existing.segment_count,
            language_code=existing.language_code,
            message="Retrieved existing transcript (idempotent)",
        )
        return TranscribeProductionResponse(
            status="already_transcribed",
            transcript_id=existing.transcript_id,
            production_id=production_id,
            duration_ms=existing.duration_ms,
            word_count=existing.word_count,
            segment_count=existing.segment_count,
            language_code=existing.language_code,
            transcript=existing,
        )

    # 2. Validate production source media state for fresh transcription
    if (
        prod.status in {ProductionStatus.DELETING, ProductionStatus.FAILED}
        or prod.source_media is None
        or prod.source_media.status != SourceMediaStatus.UPLOADED
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Production source media is not uploaded or invalid",
        )

    source = prod.source_media
    if source.content_type.strip().lower() not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported media content type: {source.content_type}",
        )

    perf_start = time.perf_counter()
    settings = get_settings()
    provider = "google" if isinstance(transcription_service, GeminiTranscriptionService) else getattr(transcription_service, "provider", "google")
    model = getattr(transcription_service, "model", settings.gemini_transcription_model)

    log_transcription_event(
        event_type="transcription.started",
        status="in_progress",
        request_id=request_id,
        production_id=production_id,
        provider=provider,
        model=model,
        message="Initiating speech transcription",
    )
    try:
        suffix = Path(source.original_filename).suffix or Path(source.gcs_object).suffix or ".video"
        with tempfile.TemporaryDirectory(prefix="croviq_transcribe_") as temp_dir:
            source_path = Path(temp_dir) / f"source{suffix}"
            await media_storage.download_object_to_path(
                bucket=source.gcs_bucket,
                object_name=source.gcs_object,
                target_path=source_path,
            )
            media_metadata = media_inspector.inspect_media(source_path)

            extraction_started = time.perf_counter()
            with audio_extractor.temporary_speech_audio(source_path, sample_rate=16000) as audio_path:
                extraction_latency_ms = (time.perf_counter() - extraction_started) * 1000
                stt_started = time.perf_counter()
                transcript = await transcription_service.transcribe_audio_file(
                    audio_path=audio_path,
                    language_code="en-US",
                    production_id=production_id,
                    source_duration_ms=media_metadata.duration_ms,
                )
                stt_latency_ms = (time.perf_counter() - stt_started) * 1000
        saved_transcript = await transcript_repo.save_transcript(transcript)
        latency_ms = (time.perf_counter() - perf_start) * 1000

        log_transcription_event(
            event_type="transcription.completed",
            status=200,
            request_id=request_id,
            production_id=production_id,
            transcript_id=saved_transcript.transcript_id,
            duration_ms=saved_transcript.duration_ms,
            word_count=saved_transcript.word_count,
            segment_count=saved_transcript.segment_count,
            language_code=saved_transcript.language_code,
            latency_ms=latency_ms,
            provider=provider,
            model=model,
            extraction_latency_ms=extraction_latency_ms,
            transcription_latency_ms=stt_latency_ms,
            request_provider_id=getattr(transcription_service, "last_request_id", None),
            message="Speech transcription completed",
        )

        return TranscribeProductionResponse(
            status="completed",
            transcript_id=saved_transcript.transcript_id,
            production_id=production_id,
            duration_ms=saved_transcript.duration_ms,
            word_count=saved_transcript.word_count,
            segment_count=saved_transcript.segment_count,
            language_code=saved_transcript.language_code,
            transcript=saved_transcript,
        )
    except (MediaStorageError, AudioExtractionError, MediaInspectionError) as exc:
        latency_ms = (time.perf_counter() - perf_start) * 1000
        log_transcription_event(
            event_type="transcription.failed",
            status=400,
            request_id=request_id,
            production_id=production_id,
            latency_ms=latency_ms,
            provider=provider,
            model=model,
            error_code="transcription_invalid_media",
            message=f"Transcription media preparation failed: {type(exc).__name__}",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="transcription_invalid_media",
        )
    except TranscriptionError as exc:
        latency_ms = (time.perf_counter() - perf_start) * 1000
        log_transcription_event(
            event_type="transcription.failed",
            status=502,
            request_id=request_id,
            production_id=production_id,
            latency_ms=latency_ms,
            provider=provider,
            model=model,
            error_code="transcription_provider_error",
            message=f"Transcription provider failed: {type(exc).__name__}",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="transcription_provider_error",
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - perf_start) * 1000
        log_transcription_event(
            event_type="transcription.failed",
            status=500,
            request_id=request_id,
            production_id=production_id,
            latency_ms=latency_ms,
            provider=provider,
            model=model,
            error_code="transcription_failed",
            message=f"Transcription failed: {type(exc).__name__}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="transcription_failed",
        )


@router.get(
    "/productions/{production_id}/transcript",
    response_model=Transcript,
    summary="Get Production Transcript",
    description="Retrieve the word-aligned transcript for a production.",
)
async def get_production_transcript(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
) -> Transcript:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    transcript = await transcript_repo.get_transcript_by_production_id(production_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript for production '{production_id}' not found",
        )
    return transcript



@router.get(
    "/productions/{production_id}/corrected-script",
    response_model=CorrectedScriptResponse,
    summary="Get Source-Grounded Corrected Script",
    description="Retrieve the source-grounded corrected script with verification metrics, change types, and visual evidence.",
)
async def get_production_corrected_script(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    genai_client: Annotated[Any, Depends(get_genai_client)],
) -> CorrectedScriptResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    transcript = await transcript_repo.get_transcript_by_production_id(production_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript for production '{production_id}' not found",
        )
    edl = await edl_repo.get_latest_edl(production_id)
    video_uri = f"gs://{prod.source_media.gcs_bucket}/{prod.source_media.gcs_object}" if prod.source_media else "gs://mock/video.mp4"
    corrected, _ = await genai_client.correct_transcript_with_video_grounding(
        video_uri=video_uri,
        mime_type="video/mp4",
        transcript=transcript,
        edl=edl,
        production_id=production_id,
    )
    return CorrectedScriptResponse(
        production_id=production_id,
        corrected_transcript=corrected,
        corrections_count=corrected.corrections_count,
        transcription_corrections_count=corrected.transcription_corrections_count,
        grammar_corrections_count=corrected.grammar_corrections_count,
        meaning_preserved=corrected.meaning_preserved,
        supported_corrections_count=corrected.supported_corrections_count,
    )

@router.get(
    "/productions/{production_id}/source-analysis-input",
    response_model=SourceVideoAnalysisInput,
    summary="Get Source Video Analysis Input Contract",
    description="Retrieve the complete source video analysis contract ready for Gemini reasoning (Issue #26).",
)
async def get_source_analysis_input(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    media_inspector: Annotated[MediaInspector, Depends(get_media_inspector)],
) -> SourceVideoAnalysisInput:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    if prod.source_media is None or prod.source_media.status != SourceMediaStatus.UPLOADED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Production source media is not uploaded",
        )

    transcript = await transcript_repo.get_transcript_by_production_id(production_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' must be transcribed before generating source analysis input",
        )

    # Derive MediaMetadata using MediaInspector or fallback to deterministic metadata
    try:
        media_metadata = media_inspector.inspect_media(
            prod.source_media.original_filename
        )
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
        production_id=production_id,
        source_media=prod.source_media,
        media_metadata=media_metadata,
        transcript=transcript,
        channel_id=prod.channel_id,
    )


@router.post(
    "/productions/{production_id}/analyze",
    response_model=AnalyzeProductionResponse,
    summary="Run Leo Editorial Analysis and Render Preview",
    description="Run Leo's dialogue edit, deterministic cut safety, EDL assembly, and Preview rendering.",
)
async def analyze_production(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    editorial_service: Annotated[EditorialService, Depends(get_editorial_service)],
    force: bool = False,
) -> AnalyzeProductionResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    run, proposal, edl, preview, activities = await editorial_service.run_editorial_analysis(
        production_id=production_id,
        current_user=current_user,
        request_id=request_id,
        force=force,
    )
    return AnalyzeProductionResponse(
        run_id=run.run_id,
        production_id=run.production_id,
        status=run.status,
        editor_proposal_id=run.editor_proposal_id,
        edl_id=edl.edl_id,
        preview_artifact_id=preview.artifact_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get(
    "/productions/{production_id}/editorial-run",
    response_model=EditorialRunDetailResponse,
    summary="Get Latest Editorial Run Details",
    description="Retrieve the latest editorial run, Leo proposal, and agent activities.",
)
async def get_editorial_run(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    editorial_repo: Annotated[EditorialRepository, Depends(get_editorial_repository)],
) -> EditorialRunDetailResponse:
    await _get_owned_production(production_id, current_user, production_repo)

    run = await editorial_repo.get_latest_editorial_run(production_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No editorial run found for production '{production_id}'",
        )

    proposal = None
    if run.editor_proposal_id:
        proposal = await editorial_repo.get_editor_proposal(production_id, run.editor_proposal_id)


    activities = await editorial_repo.list_activities(production_id, run_id=run.run_id)

    return EditorialRunDetailResponse(
        run=run,
        proposal=proposal,
        activities=activities,
    )


@router.post(
    "/productions/{production_id}/chat",
    response_model=ProductionChatResponse,
    summary="Chat with Leo in the production editor",
)
async def chat_with_leo(
    production_id: str,
    payload: ProductionChatRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    editorial_service: Annotated[EditorialService, Depends(get_editorial_service)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    broll_repo: Annotated[BRollRepository, Depends(get_broll_repository)],
) -> ProductionChatResponse:
    production = await _get_owned_production(production_id, current_user, production_repo)
    chat_service = AgentChatService(
        workspace_id=production.workspace_id,
        agent_config_repo=agent_config_repo,
        memory_store=memory_store,
    )
    voice_settings = await agent_config_repo.get_voice_settings(production.workspace_id)
    result = await editorial_service.handle_chat_message(
        production_id=production_id,
        current_user=current_user,
        chat_service=chat_service,
        message=payload.message,
        editor_context=payload.editor_context,
        current_playhead_ms=payload.current_playhead_ms,
        selected_range=list(payload.selected_range_ms) if payload.selected_range_ms else None,
        selected_element=(
            payload.selected_element.model_dump(mode="json")
            if payload.selected_element else None
        ),
        request_id=getattr(request.state, "request_id", "unknown"),
        broll_repo=broll_repo,
        voice_settings=voice_settings,
    )
    return ProductionChatResponse.model_validate(result)


@router.get(
    "/productions/{production_id}/chat/history",
    response_model=ProductionChatHistoryResponse,
    summary="Get Leo production chat history",
)
async def get_leo_chat_history(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
) -> ProductionChatHistoryResponse:
    await _get_owned_production(production_id, current_user, production_repo)
    messages = await get_production_chat_history(production_id, current_user.user_id)
    return ProductionChatHistoryResponse(
        production_id=production_id,
        messages=messages,
    )


@router.delete(
    "/productions/{production_id}/chat/history",
    response_model=ProductionChatHistoryResponse,
    summary="Clear Leo production chat history",
)
async def delete_leo_chat_history(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
) -> ProductionChatHistoryResponse:
    await _get_owned_production(production_id, current_user, production_repo)
    await clear_production_chat_history(production_id, current_user.user_id)
    return ProductionChatHistoryResponse(production_id=production_id, messages=[])


@router.post(
    "/productions/{production_id}/edl",
    response_model=AssembleEDLResponse,
    summary="Assemble Canonical Edit Decision List (EDL)",
    description="Deterministically derives audio-safe cut instructions and visual coverage markers from Leo's proposal.",
)
async def assemble_edl(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    edl_service: Annotated[EDLService, Depends(get_edl_service)],
) -> AssembleEDLResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    edl = await edl_service.assemble_edl(
        production_id=production_id,
        current_user=current_user,
        request_id=request_id,
    )
    return AssembleEDLResponse(
        edl_id=edl.edl_id,
        production_id=edl.production_id,
        version=edl.version,
        cut_count=edl.active_cuts_count,
        coverage_marker_count=len(edl.coverage_markers),
        source_duration_ms=edl.source_duration_ms,
        total_removed_duration_ms=edl.total_removed_duration_ms,
        estimated_target_duration_ms=edl.estimated_target_duration_ms,
        status="READY",
        created_at=edl.created_at,
    )


@router.get(
    "/productions/{production_id}/edl",
    response_model=EDLDetailResponse,
    summary="Get Production Edit Decision List",
    description="Retrieve the active canonical Edit Decision List and derived renderable keep segments.",
)
async def get_production_edl(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    edl_service: Annotated[EDLService, Depends(get_edl_service)],
) -> EDLDetailResponse:
    edl, keep_segments = await edl_service.get_edl(
        production_id=production_id,
        current_user=current_user,
    )
    return EDLDetailResponse(
        edl=edl,
        keep_segments=keep_segments,
    )



async def _execute_render_for_production(
    production_id: str,
    artifact_type: ArtifactType,
    request: Request,
    current_user: User,
    production_repo: ProductionRepository,
    edl_repo: EDLRepository,
    render_repo: RenderRepository,
    render_service: RenderService,
    media_storage: MediaStorage,
    genai_client: Any | None = None,
) -> RenderArtifactResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    settings = get_settings()
    prod = await _get_owned_production(production_id, current_user, production_repo)
    if not prod.source_media or not prod.source_media.gcs_bucket or not prod.source_media.gcs_object:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' has no uploaded source media to render",
        )

    edl = await edl_repo.get_latest_edl(production_id)
    if not edl:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' has no assembled EDL. Assemble an EDL before rendering.",
        )

    # 1. Idempotency check: return cached completed artifact if object exists in storage
    existing_artifact = await render_repo.get_render_artifact_by_type(
        production_id=production_id,
        edl_id=edl.edl_id,
        artifact_type=artifact_type,
    )
    if existing_artifact and existing_artifact.status == ArtifactStatus.completed:
        meta = await media_storage.get_object_metadata(
            existing_artifact.gcs_bucket,
            existing_artifact.gcs_object,
        )
        if meta.exists:
            signed_target = await media_storage.generate_signed_read_target(
                bucket=existing_artifact.gcs_bucket,
                object_name=existing_artifact.gcs_object,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )
            return RenderArtifactResponse.from_domain(
                artifact=existing_artifact,
                playback_url=signed_target.read_url,
                playback_expires_at=signed_target.expires_at,
            )

    # 2. Execute deterministic render
    artifact_id = f"art_{uuid.uuid4().hex[:12]}"
    gcs_bucket = prod.source_media.gcs_bucket
    gcs_object = build_render_artifact_gcs_object_path(
        workspace_id=prod.workspace_id,
        production_id=prod.production_id,
        edl_id=edl.edl_id,
        artifact_type=artifact_type,
    )
    now = datetime.now(timezone.utc)
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
            await media_storage.download_object_to_path(
                bucket=gcs_bucket,
                object_name=prod.source_media.gcs_object,
                target_path=local_src,
            )

            if artifact_type == ArtifactType.PREVIEW:
                render_res = await asyncio.to_thread(
                    render_service.render_preview,
                    source_path=local_src,
                    edl=edl,
                    output_path=local_out,
                )
            elif artifact_type in (ArtifactType.VOICEOVER_PREVIEW, ArtifactType.STUDIO_VOICE_PREVIEW):
                local_narr = tmp_path / "voiceover.wav"
                target_dur_ms = edl.estimated_target_duration_ms
                total_samples = int(24_000 * target_dur_ms / 1000)
                track = bytearray(total_samples * 2)
                speech_intervals: list[tuple[int, int]] = []
                if edl.voiceover_segments:
                    for seg in edl.voiceover_segments:
                        ed_start = map_source_time_to_edited(seg.source_start_ms, edl)
                        ed_end = map_source_time_to_edited(seg.source_end_ms, edl)
                        speech_intervals.append((ed_start, ed_end))
                        dur_ms, pcm = await genai_client.synthesize_studio_voice(
                            text=seg.text,
                            voice_id=seg.voice_id or "Puck",
                            production_id=prod.production_id,
                        )
                        start_byte = int(24_000 * ed_start / 1000) * 2
                        copy_len = min(len(pcm), len(track) - start_byte)
                        if copy_len > 0 and start_byte < len(track):
                            track[start_byte:start_byte + copy_len] = pcm[:copy_len]
                else:
                    # Default sample voiceover segment
                    speech_intervals.append((0, min(5000, target_dur_ms)))
                with wave.open(str(local_narr), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24_000)
                    wf.writeframes(track)
                render_res = await asyncio.to_thread(
                    render_service.render_voiceover_preview,
                    source_path=local_src,
                    edl=edl,
                    narration_audio_path=local_narr,
                    speech_intervals_ms=speech_intervals,
                    output_path=local_out,
                )
            elif artifact_type == ArtifactType.FINAL_MIX:
                local_music = tmp_path / "music.wav"
                target_dur_ms = edl.estimated_target_duration_ms
                music_bytes, _, _ = await genai_client.generate_background_music(
                    prompt="Minimal modern technology documentary underscore. Warm subtle synthesizer pads, restrained soft electronic pulse, very sparse percussion, calm focused mood, clean professional mix, instrumental only, consistent low intensity throughout. Designed to sit quietly underneath spoken tutorial narration.",
                    duration_s=int(target_dur_ms / 1000) + 1,
                    model_id=edl.background_music.model_id if edl.background_music else "lyria-3-pro-preview",
                    production_id=prod.production_id,
                )
                local_music.write_bytes(music_bytes)
                local_narr = None
                speech_intervals = []
                if edl.voiceover_segments:
                    local_narr = tmp_path / "voiceover.wav"
                    total_samples = int(24_000 * target_dur_ms / 1000)
                    track = bytearray(total_samples * 2)
                    for seg in edl.voiceover_segments:
                        ed_start = map_source_time_to_edited(seg.source_start_ms, edl)
                        ed_end = map_source_time_to_edited(seg.source_end_ms, edl)
                        speech_intervals.append((ed_start, ed_end))
                        dur_ms, pcm = await genai_client.synthesize_studio_voice(
                            text=seg.text,
                            voice_id=seg.voice_id or "Puck",
                            production_id=prod.production_id,
                        )
                        start_byte = int(24_000 * ed_start / 1000) * 2
                        copy_len = min(len(pcm), len(track) - start_byte)
                        if copy_len > 0 and start_byte < len(track):
                            track[start_byte:start_byte + copy_len] = pcm[:copy_len]
                    with wave.open(str(local_narr), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24_000)
                        wf.writeframes(track)
                render_res = await asyncio.to_thread(
                    render_service.render_final_mix,
                    source_path=local_src,
                    edl=edl,
                    music_audio_path=local_music,
                    narration_audio_path=local_narr,
                    speech_intervals_ms=speech_intervals if speech_intervals else None,
                    output_path=local_out,
                    music_volume_db=edl.background_music.volume_db if edl.background_music else -24.0,
                    music_ducking_db=edl.background_music.ducking_db if edl.background_music else -14.0,
                )
            else:
                render_res = await asyncio.to_thread(
                    render_service.render_master,
                    source_path=local_src,
                    edl=edl,
                    output_path=local_out,
                )
            await media_storage.upload_object_from_path(
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
            await render_repo.save_render_artifact(artifact)

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

            signed_target = await media_storage.generate_signed_read_target(
                bucket=gcs_bucket,
                object_name=gcs_object,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )

            return RenderArtifactResponse.from_domain(
                artifact=artifact,
                playback_url=signed_target.read_url,
                playback_expires_at=signed_target.expires_at,
            )
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
            )


@router.post(
    "/productions/{production_id}/renders/preview",
    response_model=RenderArtifactResponse,
    summary="Render Fast Preview Video",
    description="Deterministically render a fast preview MP4 from the canonical Edit Decision List.",
)
async def render_preview_video(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    render_service: Annotated[RenderService, Depends(get_render_service)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
    genai_client: Annotated[Any, Depends(get_genai_client)],
) -> RenderArtifactResponse:
    return await _execute_render_for_production(
        production_id=production_id,
        artifact_type=ArtifactType.PREVIEW,
        request=request,
        current_user=current_user,
        production_repo=production_repo,
        edl_repo=edl_repo,
        render_repo=render_repo,
        render_service=render_service,
        media_storage=media_storage,
        genai_client=genai_client,
    )


@router.post(
    "/productions/{production_id}/renders/master",
    response_model=RenderArtifactResponse,
    summary="Render High Quality Master Video",
    description="Deterministically render a high quality YouTube master MP4 from the canonical Edit Decision List.",
)
async def render_master_video(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    render_service: Annotated[RenderService, Depends(get_render_service)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
    genai_client: Annotated[Any, Depends(get_genai_client)],
) -> RenderArtifactResponse:
    return await _execute_render_for_production(
        production_id=production_id,
        artifact_type=ArtifactType.MASTER,
        request=request,
        current_user=current_user,
        production_repo=production_repo,
        edl_repo=edl_repo,
        render_repo=render_repo,
        render_service=render_service,
        media_storage=media_storage,
        genai_client=genai_client,
    )


@router.post(
    "/productions/{production_id}/renders/voiceover-preview",
    response_model=RenderArtifactResponse,
    summary="Render Voiceover Preview Video",
    description="Render a preview MP4 combining EDL cuts with active voiceover replacements.",
)
async def render_voiceover_preview_video(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    render_service: Annotated[RenderService, Depends(get_render_service)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
    genai_client: Annotated[Any, Depends(get_genai_client)],
) -> RenderArtifactResponse:
    return await _execute_render_for_production(
        production_id=production_id,
        artifact_type=ArtifactType.VOICEOVER_PREVIEW,
        request=request,
        current_user=current_user,
        production_repo=production_repo,
        edl_repo=edl_repo,
        render_repo=render_repo,
        render_service=render_service,
        media_storage=media_storage,
        genai_client=genai_client,
    )


@router.post(
    "/productions/{production_id}/renders/final-mix",
    response_model=RenderArtifactResponse,
    summary="Render Final Mix Video",
    description="Render Final Mix combining EDL cuts, B-roll overlays, voiceover corrections, and background music.",
)
async def render_final_mix_video(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    render_service: Annotated[RenderService, Depends(get_render_service)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
    genai_client: Annotated[Any, Depends(get_genai_client)],
) -> RenderArtifactResponse:
    return await _execute_render_for_production(
        production_id=production_id,
        artifact_type=ArtifactType.FINAL_MIX,
        request=request,
        current_user=current_user,
        production_repo=production_repo,
        edl_repo=edl_repo,
        render_repo=render_repo,
        render_service=render_service,
        media_storage=media_storage,
        genai_client=genai_client,
    )

@router.post(
    "/productions/{production_id}/music/generate",
    response_model=EDLDetailResponse,
    summary="Generate Google Lyria Background Music",
    description="Generate subtle instrumental background music with Google Lyria and attach to EDL.",
)
async def generate_production_music(
    production_id: str,
    body: GenerateBackgroundMusicRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    genai_client: Annotated[Any, Depends(get_genai_client)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> EDLDetailResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    edl = await edl_repo.get_latest_edl(production_id)
    if not edl:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' has no assembled EDL",
        )
    prompt_text = body.prompt or (
        "Minimal modern technology documentary underscore. "
        "Warm subtle synthesizer pads, restrained soft electronic pulse, very sparse percussion, "
        "calm focused mood, clean professional mix, instrumental only, consistent low intensity throughout. "
        "Designed to sit quietly underneath spoken tutorial narration."
    )
    duration_s = max(5, int(edl.source_duration_ms / 1000))
    wav_bytes, _, dur_ms = await genai_client.generate_background_music(
        prompt=prompt_text,
        duration_s=duration_s,
        model_id=body.model_id,
        production_id=production_id,
    )
    object_name = f"workspaces/{prod.workspace_id}/productions/{production_id}/music/lyria_underscore.wav"
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_f:
        tmp_f.write(wav_bytes)
        tmp_wav_path = Path(tmp_f.name)
    try:
        await media_storage.upload_object_from_path(
            bucket=prod.source_media.gcs_bucket,
            object_name=object_name,
            source_path=tmp_wav_path,
            content_type="audio/wav",
        )
    finally:
        tmp_wav_path.unlink(missing_ok=True)
    mix = BackgroundMusicMix(
        style="Minimal modern technology documentary underscore",
        model_id=body.model_id,
        prompt=prompt_text,
        duration_ms=dur_ms,
        volume_db=body.volume_db,
        ducking_db=body.ducking_db,
        target_lufs=-32.0,
        music_gcs_object=object_name,
        is_muted=False,
    )
    updated_edl = edl.model_copy(update={
        "version": edl.version + 1,
        "background_music": mix,
        "created_at": datetime.now(timezone.utc),
    })
    await edl_repo.save_edl(updated_edl)
    from croviq_domain.edl import derive_keep_segments
    return EDLDetailResponse(
        edl=updated_edl,
        keep_segments=derive_keep_segments(updated_edl),
    )


@router.patch(
    "/productions/{production_id}/music",
    response_model=EDLDetailResponse,
    summary="Update Background Music Mix Settings",
    description="Modify volume, ducking, or mute state of background music.",
)
async def update_production_music(
    production_id: str,
    body: UpdateBackgroundMusicRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
) -> EDLDetailResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    edl = await edl_repo.get_latest_edl(production_id)
    if not edl or not edl.background_music:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No background music mix is configured on the EDL",
        )
    current_mix = edl.background_music
    updates: dict[str, Any] = {}
    if body.volume_db is not None:
        updates["volume_db"] = body.volume_db
    if body.ducking_db is not None:
        updates["ducking_db"] = body.ducking_db
    if body.is_muted is not None:
        updates["is_muted"] = body.is_muted
    if body.style is not None:
        updates["style"] = body.style
    new_mix = current_mix.model_copy(update=updates)
    updated_edl = edl.model_copy(update={
        "version": edl.version + 1,
        "background_music": new_mix,
        "created_at": datetime.now(timezone.utc),
    })
    await edl_repo.save_edl(updated_edl)
    from croviq_domain.edl import derive_keep_segments
    return EDLDetailResponse(
        edl=updated_edl,
        keep_segments=derive_keep_segments(updated_edl),
    )



@router.get(
    "/productions/{production_id}/renders",
    response_model=RenderListResponse,
    summary="List Production Render Artifacts",
    description="Retrieve all rendered artifacts (preview and master) for a production.",
)
async def list_production_renders(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> RenderListResponse:
    settings = get_settings()
    prod = await _get_owned_production(production_id, current_user, production_repo)
    artifacts = await render_repo.list_render_artifacts(production_id)

    async def _sign_artifact(art) -> RenderArtifactResponse:
        playback_url = None
        playback_expires_at = None
        if art.status == ArtifactStatus.completed:
            try:
                target = await media_storage.generate_signed_read_target(
                    bucket=art.gcs_bucket,
                    object_name=art.gcs_object,
                    expiry_seconds=settings.signed_url_expiry_seconds,
                )
                playback_url = target.read_url
                playback_expires_at = target.expires_at
            except Exception:
                pass
        return RenderArtifactResponse.from_domain(
            artifact=art,
            playback_url=playback_url,
            playback_expires_at=playback_expires_at,
        )

    responses = await asyncio.gather(*[_sign_artifact(art) for art in artifacts]) if artifacts else []
    return RenderListResponse(
        production_id=prod.production_id,
        renders=list(responses),
    )

@router.get(
    "/productions/{production_id}/playback",
    response_model=ProductionPlaybackResponse,
    summary="Get Production Media Playback URLs",
    description="Retrieve distinct signed URLs and canonical media states for Original, Edited Preview, Master, and Studio Voice media.",
)
async def get_production_playback_urls(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> ProductionPlaybackResponse:
    settings = get_settings()
    prod = await _get_owned_production(production_id, current_user, production_repo)
    latest_edl = await edl_repo.get_latest_edl(prod.production_id)
    transcript = await transcript_repo.get_transcript_by_production_id(prod.production_id)

    active_edl_id = latest_edl.edl_id if latest_edl else None
    renders = await render_repo.list_render_artifacts(prod.production_id)
    active_renders = [r for r in renders if (active_edl_id is None or r.edl_id == active_edl_id)]

    # Find target artifacts for active lineage
    preview_art = next((r for r in active_renders if (r.artifact_type.value if hasattr(r.artifact_type, "value") else str(r.artifact_type)) == ArtifactType.PREVIEW.value), None)
    master_art = next((r for r in active_renders if (r.artifact_type.value if hasattr(r.artifact_type, "value") else str(r.artifact_type)) == ArtifactType.MASTER.value), None)
    sv_art = next((r for r in active_renders if (r.artifact_type.value if hasattr(r.artifact_type, "value") else str(r.artifact_type)) in (ArtifactType.STUDIO_VOICE_PREVIEW.value, ArtifactType.VOICEOVER_PREVIEW.value)), None)
    fm_art = next((r for r in active_renders if (r.artifact_type.value if hasattr(r.artifact_type, "value") else str(r.artifact_type)) == ArtifactType.FINAL_MIX.value), None)

    async def _sign_target(bucket: str, obj: str) -> str | None:
        try:
            target = await media_storage.generate_signed_read_target(
                bucket=bucket,
                object_name=obj,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )
            return target.read_url
        except Exception as exc:
            logger.warning("Failed to generate signed target for %s/%s: %s", bucket, obj, exc)
            return None

    # Parallel signing of active artifacts
    tasks = []
    source_eligible = prod.source_media and (prod.source_media.status.value if hasattr(prod.source_media.status, "value") else str(prod.source_media.status)).lower() == "uploaded"
    tasks.append(_sign_target(prod.source_media.gcs_bucket, prod.source_media.gcs_object) if source_eligible else asyncio.sleep(0, result=None))

    preview_eligible = preview_art and (preview_art.status.value if hasattr(preview_art.status, "value") else str(preview_art.status)).lower() == "completed"
    tasks.append(_sign_target(preview_art.gcs_bucket, preview_art.gcs_object) if preview_eligible else asyncio.sleep(0, result=None))

    master_eligible = master_art and (master_art.status.value if hasattr(master_art.status, "value") else str(master_art.status)).lower() == "completed"
    tasks.append(_sign_target(master_art.gcs_bucket, master_art.gcs_object) if master_eligible else asyncio.sleep(0, result=None))

    sv_eligible = sv_art and (sv_art.status.value if hasattr(sv_art.status, "value") else str(sv_art.status)).lower() == "completed"
    tasks.append(_sign_target(sv_art.gcs_bucket, sv_art.gcs_object) if sv_eligible else asyncio.sleep(0, result=None))

    fm_eligible = fm_art and (fm_art.status.value if hasattr(fm_art.status, "value") else str(fm_art.status)).lower() == "completed"
    tasks.append(_sign_target(fm_art.gcs_bucket, fm_art.gcs_object) if fm_eligible else asyncio.sleep(0, result=None))

    signed_results = await asyncio.gather(*tasks)
    source_url = signed_results[0]
    preview_url = signed_results[1]
    master_url = signed_results[2]
    sv_url = signed_results[3]
    final_mix_url = signed_results[4]

    source_dur = transcript.duration_ms if transcript else (latest_edl.source_duration_ms if latest_edl else 0)
    original_state = MediaOutputState(
        available=bool(source_url),
        artifact_id=prod.source_media.upload_id if prod.source_media else None,
        url=source_url,
        duration_ms=source_dur,
        status="ready" if source_url else "unavailable",
    )

    def _build_state(art, url: str | None) -> MediaOutputState:
        if not art:
            return MediaOutputState(available=False, edl_id=active_edl_id, status="unavailable")
        s_val = (art.status.value if hasattr(art.status, "value") else str(art.status)).lower()
        if s_val == "completed" and url:
            return MediaOutputState(
                available=True,
                artifact_id=art.artifact_id,
                edl_id=art.edl_id,
                url=url,
                duration_ms=art.duration_ms or 0,
                status="ready",
            )
        if s_val in ("rendering", "pending"):
            return MediaOutputState(
                available=False,
                artifact_id=art.artifact_id,
                edl_id=art.edl_id,
                status="generating",
            )
        if s_val == "failed":
            return MediaOutputState(
                available=False,
                artifact_id=art.artifact_id,
                edl_id=art.edl_id,
                status="failed",
            )
        return MediaOutputState(available=False, artifact_id=art.artifact_id, edl_id=art.edl_id, status="unavailable")

    edited_state = _build_state(preview_art, preview_url)
    voiceover_state = _build_state(sv_art, sv_url)
    final_mix_state = _build_state(fm_art, final_mix_url)

    return ProductionPlaybackResponse(
        production_id=prod.production_id,
        playback_url=source_url,
        rendered_preview_url=preview_url,
        master_url=master_url,
        studio_voice_preview_url=sv_url,
        final_mix_url=final_mix_url,
        original=original_state,
        edited=edited_state,
        voiceover=voiceover_state,
        final_mix=final_mix_state,
    )

@router.post(
    "/productions/{production_id}/studio-voice",
    response_model=StudioVoiceGenerationResponse,
    summary="Generate Studio Voice Narration",
    description="Synthesize section-by-section Studio Voice narration adhering to strict hard duration budgets.",
)
async def generate_studio_voice(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    studio_voice_repo: Annotated[StudioVoiceRepository, Depends(get_studio_voice_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
    render_service: Annotated[RenderService, Depends(get_render_service)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    genai_client: Annotated[GenAIClient, Depends(get_genai_client)],
) -> StudioVoiceGenerationResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    transcript = await transcript_repo.get_transcript_by_production_id(prod.production_id)
    if not transcript or not transcript.segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Production must be transcribed before generating Studio Voice.",
        )
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    voice_cfg = await agent_config_repo.get_voice_settings(workspace.workspace_id)
    selected_voice = voice_cfg.selected_voice

    synthesizer = StudioVoiceSynthesizer()

    # Define TTS generator and Leo narration rewrite function for fit loop
    async def tts_fn(text: str, voice_id: str) -> tuple[int, bytes]:
        return await genai_client.synthesize_studio_voice(
            text=text,
            voice_id=voice_id,
            production_id=prod.production_id,
        )

    async def leo_rewrite_fn(orig_text: str, max_dur_s: float, attempt: int) -> str:
        return await genai_client.generate_narration_rewrite(
            original_text=orig_text,
            available_duration_s=max_dur_s,
            attempt=attempt,
            production_id=prod.production_id,
        )

    tasks = [
        synthesizer.fit_narration_segment_with_audio(
            segment_id=f"seg_{idx+1:03d}",
            production_id=prod.production_id,
            source_start_ms=seg.start_ms,
            source_end_ms=seg.end_ms,
            available_duration_ms=max(500, seg.end_ms - seg.start_ms),
            original_text=seg.text,
            voice_id=selected_voice,
            tts_fn=tts_fn,
            rewrite_fn=leo_rewrite_fn,
        )
        for idx, seg in enumerate(transcript.segments)
    ]
    results: list[tuple[NarrationSegment, bytes]] = list(await asyncio.gather(*tasks))
    segments: list[NarrationSegment] = [r[0] for r in results]
    now = datetime.now(timezone.utc)
    all_within = all(
        s.generated_duration_ms <= s.available_duration_ms
        for s in segments
        if s.status == NarrationSegmentStatus.ACCEPTED
    )

    # Render distinct Studio Voice Preview artifact
    edl = await edl_repo.get_latest_edl(prod.production_id)
    sv_playback_url = None
    narration_gcs_obj: str | None = None

    if edl is not None and prod.source_media and prod.source_media.status == SourceMediaStatus.UPLOADED:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                local_src = tmp_path / "source.mp4"
                local_narr = tmp_path / "narration.wav"
                local_out = tmp_path / "studio_voice_preview.mp4"

                await media_storage.download_object_to_path(
                    bucket=prod.source_media.gcs_bucket,
                    object_name=prod.source_media.gcs_object,
                    target_path=local_src,
                )

                # Create composite narration audio track at 24000 Hz, 16-bit mono (matching Gemini TTS output)
                sample_rate = 24000
                total_dur_ms = edl.estimated_target_duration_ms or (transcript.duration_ms if transcript else 10000)
                num_samples = int(sample_rate * total_dur_ms / 1000)
                audio_buffer = bytearray(num_samples * 2)

                speech_intervals: list[tuple[int, int]] = []
                for seg, pcm_bytes in results:
                    if seg.status == NarrationSegmentStatus.ACCEPTED and pcm_bytes:
                        ed_start = map_source_time_to_edited(seg.source_start_ms, edl)
                        ed_end = map_source_time_to_edited(seg.source_end_ms, edl)
                        speech_intervals.append((ed_start, ed_end))
                        start_sample = int(sample_rate * ed_start / 1000)
                        start_byte = start_sample * 2
                        end_byte = min(len(audio_buffer), start_byte + len(pcm_bytes))
                        copy_len = end_byte - start_byte
                        if copy_len > 0 and start_byte < len(audio_buffer):
                            audio_buffer[start_byte : start_byte + copy_len] = pcm_bytes[:copy_len]
                with wave.open(str(local_narr), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(bytes(audio_buffer))

                narration_gcs_obj = f"workspaces/{workspace.workspace_id}/productions/{prod.production_id}/narration/studio_voice_narration.wav"
                await media_storage.upload_object_from_path(
                    bucket=prod.source_media.gcs_bucket,
                    object_name=narration_gcs_obj,
                    source_path=local_narr,
                    content_type="audio/wav",
                )

                # Run deterministic studio voice preview render in worker thread
                render_res = await asyncio.to_thread(
                    render_service.render_studio_voice_preview,
                    source_path=local_src,
                    edl=edl,
                    narration_audio_path=local_narr,
                    speech_intervals_ms=speech_intervals,
                    output_path=local_out,
                )

                gcs_obj = build_render_artifact_gcs_object_path(
                    workspace_id=workspace.workspace_id,
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_type=ArtifactType.STUDIO_VOICE_PREVIEW,
                )

                await media_storage.upload_object_from_path(
                    bucket=prod.source_media.gcs_bucket,
                    object_name=gcs_obj,
                    source_path=local_out,
                    content_type="video/mp4",
                )

                art = RenderArtifact(
                    artifact_id=f"art_sv_{uuid.uuid4().hex[:8]}",
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_type=ArtifactType.STUDIO_VOICE_PREVIEW,
                    status=ArtifactStatus.completed,
                    gcs_bucket=prod.source_media.gcs_bucket,
                    gcs_object=gcs_obj,
                    content_type="video/mp4",
                    size_bytes=render_res.size_bytes,
                    duration_ms=render_res.duration_ms,
                    width=render_res.width,
                    height=render_res.height,
                    frame_rate=render_res.frame_rate,
                    video_codec=render_res.video_codec,
                    audio_codec=render_res.audio_codec,
                    created_at=now,
                    completed_at=now,
                )
                await render_repo.save_render_artifact(art)
                settings = get_settings()
                target = await media_storage.generate_signed_read_target(
                    bucket=art.gcs_bucket,
                    object_name=art.gcs_object,
                    expiry_seconds=settings.signed_url_expiry_seconds,
                )
                sv_playback_url = target.read_url
        except Exception as exc:
            logger.warning("Studio Voice render preview failed: %s", exc)

    accepted_count = sum(1 for s in segments if s.status == NarrationSegmentStatus.ACCEPTED)
    if narration_gcs_obj:
        for s in segments:
            if s.status == NarrationSegmentStatus.ACCEPTED:
                s.audio_artifact_reference = narration_gcs_obj

    sv_status = "completed" if (accepted_count > 0 and sv_playback_url is not None) else "failed"
    sv_result = StudioVoiceResult(
        production_id=prod.production_id,
        voice_id=selected_voice,
        narration_mode="studio_voice",
        segments=segments,
        total_segments=len(segments),
        accepted_segments=accepted_count,
        all_within_budget=all_within,
        gcs_bucket=prod.source_media.gcs_bucket if (accepted_count > 0 and narration_gcs_obj) else None,
        gcs_object=narration_gcs_obj if accepted_count > 0 else None,
        status=sv_status,
        created_at=now,
        updated_at=now,
    )
    await studio_voice_repo.save(sv_result)

    return StudioVoiceGenerationResponse(
        production_id=prod.production_id,
        result=sv_result,
        studio_voice_preview_url=sv_playback_url,
    )

@router.get(
    "/productions/{production_id}/studio-voice",
    response_model=StudioVoiceResult,
    summary="Get Studio Voice Result",
    description="Retrieve the latest generated Studio Voice segments and timing data for a production.",
)
async def get_studio_voice(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    studio_voice_repo: Annotated[StudioVoiceRepository, Depends(get_studio_voice_repository)],
) -> StudioVoiceResult:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    res = await studio_voice_repo.get_by_production_id(prod.production_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Studio Voice has not been generated for production {production_id}.",
        )
    return res


@router.get(
    "/productions/{production_id}/broll",
    response_model=BRollListResponse,
    summary="List Generated B-Roll Artifacts",
    description="Retrieve all B-roll video clips generated by Leo for this production.",
)
async def list_production_broll(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    broll_repo: Annotated[BRollRepository, Depends(get_broll_repository)],
) -> BRollListResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    artifacts = await broll_repo.list_by_production_id(prod.production_id)
    return BRollListResponse(
        production_id=prod.production_id,
        artifacts=artifacts,
    )


async def _build_packaging_detail_response(
    production_id: str,
    proposal: PackagingProposal | None,
    overrides: CreatorPackageOverrides | None,
    master_artifact: RenderArtifact | None,
    media_storage: MediaStorage,
) -> PackagingDetailResponse:
    settings = get_settings()
    master_url: str | None = None
    if master_artifact and master_artifact.status == ArtifactStatus.completed:
        try:
            target = await media_storage.generate_signed_read_target(
                bucket=master_artifact.gcs_bucket,
                object_name=master_artifact.gcs_object,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )
            master_url = target.read_url
        except Exception as exc:
            logger.warning("Could not generate signed master url for packaging: %s", exc)

    master_response = (
        RenderArtifactResponse.from_domain(master_artifact, playback_url=master_url)
        if master_artifact
        else None
    )
    effective_title = (
        overrides.custom_title
        if overrides and overrides.custom_title
        else overrides.selected_title
        if overrides and overrides.selected_title
        else proposal.primary_title
        if proposal
        else ""
    )
    effective_description = (
        overrides.custom_description
        if overrides and overrides.custom_description
        else proposal.description
        if proposal
        else ""
    )
    effective_chapters = (
        overrides.custom_chapters
        if overrides and overrides.custom_chapters is not None
        else proposal.chapters
        if proposal
        else []
    )
    effective_thumbnail_id = (
        overrides.selected_thumbnail_concept_id
        if overrides and overrides.selected_thumbnail_concept_id
        else proposal.thumbnail_concepts[0].concept_id
        if proposal and proposal.thumbnail_concepts
        else None
    )
    has_master = bool(
        master_artifact and master_artifact.status == ArtifactStatus.completed
    )
    return PackagingDetailResponse(
        production_id=production_id,
        proposal=proposal,
        overrides=overrides,
        effective_title=effective_title,
        effective_description=effective_description,
        effective_chapters=effective_chapters,
        effective_thumbnail_concept_id=effective_thumbnail_id,
        master_artifact=master_response,
        master_url=master_url,
        has_master=has_master,
        status="completed" if proposal else ("needs_master" if not has_master else "ready"),
        generated_at=proposal.created_at if proposal else None,
    )



@router.get(
    "/productions/{production_id}/packaging",
    response_model=PackagingDetailResponse,
    summary="Get Production Packaging Details",
    description="Retrieve the latest packaging proposal, creator overrides, and publishing state for a production.",
)
async def get_packaging_details(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> PackagingDetailResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    latest_edl = await edl_repo.get_latest_edl(prod.production_id)
    master_artifact = None
    if latest_edl:
        master_artifact = await render_repo.get_render_artifact_by_type(
            prod.production_id, latest_edl.edl_id, ArtifactType.MASTER
        )
        if not master_artifact:
            master_artifact = await render_repo.get_render_artifact_by_type(
                prod.production_id, latest_edl.edl_id, ArtifactType.STUDIO_VOICE_MASTER
            )

    proposal = await packaging_repo.get_latest_packaging_proposal(prod.production_id)
    overrides = await packaging_repo.get_package_overrides(prod.production_id)

    return await _build_packaging_detail_response(
        production_id=prod.production_id,
        proposal=proposal,
        overrides=overrides,
        master_artifact=master_artifact,
        media_storage=media_storage,
    )


@router.patch(
    "/productions/{production_id}/packaging",
    response_model=PackagingDetailResponse,
    summary="Update Creator Package Overrides",
    description="Update creator overrides for title, description, chapters, or thumbnail selection.",
)
async def update_packaging_overrides(
    production_id: str,
    payload: UpdatePackagingOverridesRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> PackagingDetailResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    existing_overrides = await packaging_repo.get_package_overrides(prod.production_id)
    now = datetime.now(timezone.utc)

    selected_title = payload.selected_title if payload.selected_title is not None else (existing_overrides.selected_title if existing_overrides else None)
    custom_title = payload.custom_title if payload.custom_title is not None else (existing_overrides.custom_title if existing_overrides else None)
    custom_description = payload.custom_description if payload.custom_description is not None else (existing_overrides.custom_description if existing_overrides else None)
    custom_chapters = payload.custom_chapters if payload.custom_chapters is not None else (existing_overrides.custom_chapters if existing_overrides else None)
    selected_thumb_id = payload.selected_thumbnail_concept_id if payload.selected_thumbnail_concept_id is not None else (existing_overrides.selected_thumbnail_concept_id if existing_overrides else None)

    updated_overrides = CreatorPackageOverrides(
        selected_title=selected_title,
        custom_title=custom_title,
        custom_description=custom_description,
        custom_chapters=custom_chapters,
        selected_thumbnail_concept_id=selected_thumb_id,
        updated_at=now,
    )
    await packaging_repo.save_package_overrides(prod.production_id, updated_overrides)

    latest_edl = await edl_repo.get_latest_edl(prod.production_id)
    master_artifact = None
    if latest_edl:
        master_artifact = await render_repo.get_render_artifact_by_type(
            prod.production_id, latest_edl.edl_id, ArtifactType.MASTER
        )
        if not master_artifact:
            master_artifact = await render_repo.get_render_artifact_by_type(
                prod.production_id, latest_edl.edl_id, ArtifactType.STUDIO_VOICE_MASTER
            )
    proposal = await packaging_repo.get_latest_packaging_proposal(prod.production_id)

    return await _build_packaging_detail_response(
        production_id=prod.production_id,
        proposal=proposal,
        overrides=updated_overrides,
        master_artifact=master_artifact,
        media_storage=media_storage,
    )


async def _build_release_review_response(
    production_id: str,
    review: ReleaseReview | None,
    master_artifact: RenderArtifact | None,
    proposal: PackagingProposal | None,
    media_storage: MediaStorage,
) -> ReleaseReviewDetailResponse:
    settings = get_settings()
    master_url: str | None = None
    if master_artifact and master_artifact.status == ArtifactStatus.completed:
        try:
            target = await media_storage.generate_signed_read_target(
                bucket=master_artifact.gcs_bucket,
                object_name=master_artifact.gcs_object,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )
            master_url = target.read_url
        except Exception as exc:
            logger.warning("Could not generate signed master url for release review: %s", exc)

    master_response = (
        RenderArtifactResponse.from_domain(master_artifact, playback_url=master_url)
        if master_artifact
        else None
    )
    calculated_fingerprint = None
    if master_artifact:
        calculated_fingerprint = build_release_fingerprint(
            production_id=production_id,
            edl_id=master_artifact.edl_id,
            master_artifact_id=master_artifact.artifact_id,
            master_hash=master_artifact.sha256 or "unhashed",
            packaging_proposal_id=proposal.proposal_id if proposal else "none",
            package_version=proposal.version if proposal else 1,
            release_review_id=review.review_id if review else None,
        )
    has_master = bool(
        master_artifact and master_artifact.status == ArtifactStatus.completed
    )
    release_ready = bool(
        review
        and has_master
        and review.verdict == ReleaseVerdict.PASS
        and review.approved_for_release
        and review.master_artifact_id == master_artifact.artifact_id
        and (
            review.release_fingerprint is None
            or calculated_fingerprint is None
            or review.release_fingerprint == calculated_fingerprint
        )
    )
    if release_ready:
        release_status = "Ready to publish"
    elif review and review.verdict == ReleaseVerdict.FIX_REQUIRED:
        release_status = "Fix required"
    elif review and review.verdict == ReleaseVerdict.MANUAL_REVIEW:
        release_status = "Manual review"
    elif review:
        release_status = "Checking final output"
    else:
        release_status = "Pending review"
    return ReleaseReviewDetailResponse(
        production_id=production_id,
        review=review,
        release_status=release_status,
        release_ready=release_ready,
        checklist=review.checklist if review else None,
        master_artifact=master_response,
        master_url=master_url,
        has_master=has_master,
        has_packaging=proposal is not None,
        release_fingerprint=review.release_fingerprint if review else calculated_fingerprint,
        generated_at=review.created_at if review else None,
    )

@router.post(
    "/productions/{production_id}/release-review",
    response_model=ReleaseReviewDetailResponse,
    summary="Generate Iris QA Release Review",
    description="Invoke Iris (QA Agent) to evaluate the Master video, transcript, captions, chapters, and packaging truth before release.",
)
async def generate_release_review(
    production_id: str,
    request: Request,
    payload: GenerateReleaseReviewRequest | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)] = None,
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)] = None,
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)] = None,
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)] = None,
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)] = None,
    release_review_repo: Annotated[ReleaseReviewRepository, Depends(get_release_review_repository)] = None,
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)] = None,
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)] = None,
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)] = None,
    genai_client: Annotated[GenAIClient, Depends(get_genai_client)] = None,
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)] = None,
) -> ReleaseReviewDetailResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    force_regenerate = payload.force_regenerate if payload else False

    prod = await _get_owned_production(production_id, current_user, production_repo)

    latest_edl = await edl_repo.get_latest_edl(prod.production_id)
    master_artifact = None
    if latest_edl:
        master_artifact = await render_repo.get_render_artifact_by_type(
            prod.production_id, latest_edl.edl_id, ArtifactType.MASTER
        )
        if not master_artifact:
            master_artifact = await render_repo.get_render_artifact_by_type(
                prod.production_id, latest_edl.edl_id, ArtifactType.STUDIO_VOICE_MASTER
            )
    else:
        renders = await render_repo.list_render_artifacts(prod.production_id)
        master_artifact = next(
            (r for r in renders if (r.artifact_type == ArtifactType.MASTER or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.MASTER.value)) and r.status == ArtifactStatus.completed),
            None,
        )
        if master_artifact and master_artifact.edl_id:
            latest_edl = await edl_repo.get_edl(prod.production_id, master_artifact.edl_id)

    if not master_artifact or master_artifact.status != ArtifactStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Master video must be rendered and completed before executing Iris QA review.",
        )
    proposal = await packaging_repo.get_latest_packaging_proposal(prod.production_id)
    overrides = await packaging_repo.get_package_overrides(prod.production_id)

    # Idempotency check for the same Master and packaging proposal.
    if not force_regenerate:
        latest_review = await release_review_repo.get_latest_release_review(prod.production_id)
        if (
            latest_review
            and latest_review.master_artifact_id == master_artifact.artifact_id
            and latest_review.packaging_proposal_id == (proposal.proposal_id if proposal else "none")
        ):
            return await _build_release_review_response(
                production_id=prod.production_id,
                review=latest_review,
                master_artifact=master_artifact,
                proposal=proposal,
                media_storage=media_storage,
            )

    # Load Transcript
    transcript = await transcript_repo.get_transcript_by_production_id(prod.production_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript must exist before executing Iris QA review.",
        )

    # Load Channel Memory & Research Findings
    channel_profile = None
    lessons = []
    if prod.channel_id:
        try:
            channel_profile = await memory_store.get_profile(prod.channel_id)
            if not channel_profile:
                sample_provider = SampleChannelDataProvider()
                c_data = await sample_provider.get_channel(prod.channel_id)
                if c_data:
                    channel_profile, lessons = ChannelProfileBuilder.build(c_data)
                    await memory_store.save_profile(channel_profile)
                    if lessons:
                        await memory_store.save_lessons(prod.channel_id, lessons)
            else:
                lessons = await memory_store.get_lessons(prod.channel_id)
        except Exception as exc:
            logger.warning("Could not load channel memory for release review: %s", exc)

    research_findings = []
    if prod.channel_id:
        try:
            research_findings = await research_repo.list_findings(
                workspace_id=prod.workspace_id,
                channel_id=prod.channel_id,
                limit=5,
            )
        except Exception as exc:
            logger.warning("Could not load research findings for release review: %s", exc)

    # Load Iris prompt config
    iris_prompt_config = await agent_config_repo.get_agent_prompt(
        workspace_id=prod.workspace_id,
        agent_id=AgentId.IRIS,
    )

    # Execute Iris QA Review
    iris_agent = IrisQAAgent(genai_client=genai_client, model_id="gemini-3.7-flash")
    review, _ = await iris_agent.review_production(
        production_id=prod.production_id,
        master_artifact=master_artifact,
        transcript=transcript,
        proposal=proposal,
        overrides=overrides,
        channel_profile=channel_profile,
        lessons=lessons,
        research_findings=research_findings,
        custom_prompt=iris_prompt_config.prompt_text if iris_prompt_config.is_custom else None,
        prompt_version=iris_prompt_config.version,
        request_id=request_id,
    )

    package_ver = (proposal.version if hasattr(proposal, "version") else 1) if proposal else 1
    pkg_id = proposal.proposal_id if proposal else "none"
    effective_edl_id = latest_edl.edl_id if latest_edl else master_artifact.edl_id
    fp = build_release_fingerprint(
        production_id=prod.production_id,
        edl_id=effective_edl_id,
        master_artifact_id=master_artifact.artifact_id,
        master_hash=master_artifact.sha256 or "unhashed",
        packaging_proposal_id=pkg_id,
        package_version=package_ver,
        release_review_id=review.review_id,
    )
    review = review.model_copy(
        update={
            "edl_id": effective_edl_id,
            "master_hash": master_artifact.sha256,
            "package_version": package_ver,
            "release_fingerprint": fp,
        }
    )
    await release_review_repo.save_release_review(review)
    if review.approved_for_release or review.verdict == ReleaseVerdict.PASS:
        try:
            from croviq_observability import log_master_approved_event
            request_id = getattr(request.state, "request_id", "unknown")
            log_master_approved_event(
                production_id=prod.production_id,
                edl_id=effective_edl_id,
                preview_artifact_id=master_artifact.artifact_id,
                review_id=review.review_id,
                request_id=request_id,
            )
        except Exception:
            pass
    return await _build_release_review_response(
        production_id=prod.production_id,
        review=review,
        master_artifact=master_artifact,
        proposal=proposal,
        media_storage=media_storage,
    )


@router.get(
    "/productions/{production_id}/release-review",
    response_model=ReleaseReviewDetailResponse,
    summary="Get Production Release Review Details",
    description="Retrieve the latest Iris QA evaluation, checklist, and release readiness for a production.",
)
async def get_release_review_details(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)],
    release_review_repo: Annotated[ReleaseReviewRepository, Depends(get_release_review_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> ReleaseReviewDetailResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)

    latest_edl = await edl_repo.get_latest_edl(prod.production_id)
    master_artifact = None
    if latest_edl:
        master_artifact = await render_repo.get_render_artifact_by_type(
            prod.production_id, latest_edl.edl_id, ArtifactType.MASTER
        )
        if not master_artifact:
            master_artifact = await render_repo.get_render_artifact_by_type(
                prod.production_id, latest_edl.edl_id, ArtifactType.STUDIO_VOICE_MASTER
            )
    else:
        renders = await render_repo.list_render_artifacts(prod.production_id)
        master_artifact = next(
            (r for r in renders if (r.artifact_type == ArtifactType.MASTER or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.MASTER.value)) and r.status == ArtifactStatus.completed),
            None,
        )
    proposal = await packaging_repo.get_latest_packaging_proposal(prod.production_id)
    review = await release_review_repo.get_latest_release_review(prod.production_id)

    return await _build_release_review_response(
        production_id=prod.production_id,
        review=review,
        master_artifact=master_artifact,
        proposal=proposal,
        media_storage=media_storage,
    )



# -----------------------------------------------------------------------------
# 12. YouTube Publishing Endpoints (Milestone: YouTube Publishing)
# -----------------------------------------------------------------------------


@router.get(
    "/productions/{production_id}/publish/prep",
    response_model=PublishPreparationResponse,
    summary="Get YouTube Publishing Preparation Data",
    description="Retrieve channel connection info, suggested title/description/chapters, and synthetic media suggestions before publishing.",
)
async def get_publish_preparation(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    publish_service: Annotated[YouTubePublishService, Depends(get_publish_service)],
) -> PublishPreparationResponse:
    try:
        data = await publish_service.get_publish_preparation(production_id, current_user)
        return PublishPreparationResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post(
    "/productions/{production_id}/publish",
    response_model=PublishJobDetailResponse,
    summary="Initiate Creator-Approved YouTube Publication",
    description="Trigger creator-approved, idempotent publishing of Master video to YouTube with release gate validation.",
)
async def publish_to_youtube(
    production_id: str,
    payload: PublishRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    publish_service: Annotated[YouTubePublishService, Depends(get_publish_service)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
) -> PublishJobDetailResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        job = await publish_service.initiate_publish_job(
            production_id=production_id,
            current_user=current_user,
            requested_privacy=payload.requested_privacy,
            made_for_kids=payload.made_for_kids,
            contains_synthetic_media=payload.contains_synthetic_media,
            selected_title=payload.selected_title,
            selected_description=payload.selected_description,
            selected_tags=payload.selected_tags,
            category_id=payload.category_id,
            thumbnail_frame_ms=payload.thumbnail_frame_ms,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    prod = await production_repo.get_production(production_id)
    workspace = await workspace_repo.get_workspace_by_id(prod.workspace_id) if prod else None
    conn = await youtube_repo.get_connection(workspace.workspace_id) if workspace else None
    is_sample = bool(prod and (prod.channel_id.startswith("sample_") or prod.channel_id == "sample_tech_channel"))
    has_upload = bool(conn and SCOPE_YOUTUBE_UPLOAD in conn.scopes)

    status_msg = "Publishing initiated."
    if job.audit_restriction_detected:
        status_msg = (
            "Uploaded successfully, but YouTube restricted this API project to private uploads. "
            "YouTube API compliance verification is required before public publishing."
        )
    elif job.status == PublishJobStatus.COMPLETED:
        if job.actual_privacy == "private":
            status_msg = "Uploaded privately"
        elif job.actual_privacy == "unlisted":
            status_msg = "Published unlisted"
        else:
            status_msg = "Published"
    elif job.status == PublishJobStatus.AUTH_REQUIRED:
        status_msg = "YouTube upload access required. Please grant publishing permission."

    return PublishJobDetailResponse(
        job=job,
        can_publish=not is_sample and conn is not None,
        has_upload_access=has_upload,
        status_message=status_msg,
        is_sample_channel=is_sample,
    )


@router.get(
    "/productions/{production_id}/publish",
    response_model=PublishJobDetailResponse,
    summary="Get Production YouTube Publish Status",
    description="Poll current or latest YouTube publish job status, upload progress, and remote video metadata.",
)
async def get_publish_status(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
    publish_job_repo: Annotated[PublishJobRepository, Depends(get_publish_job_repository)],
) -> PublishJobDetailResponse:
    prod = await production_repo.get_production(production_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production not found.")
    if prod.owner_user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    workspace = await workspace_repo.get_workspace_by_id(prod.workspace_id) if prod else None
    conn = await youtube_repo.get_connection(workspace.workspace_id) if workspace else None
    is_sample = bool(prod.channel_id.startswith("sample_") or prod.channel_id == "sample_tech_channel")
    has_upload = bool(conn and SCOPE_YOUTUBE_UPLOAD in conn.scopes)

    latest_job = await publish_job_repo.get_latest_by_production_id(production_id)

    status_msg = ""
    if latest_job:
        if latest_job.audit_restriction_detected:
            status_msg = (
                "Uploaded successfully, but YouTube restricted this API project to private uploads. "
                "YouTube API compliance verification is required before public publishing."
            )
        elif latest_job.status == PublishJobStatus.COMPLETED:
            if latest_job.actual_privacy == "private":
                status_msg = "Uploaded privately"
            elif latest_job.actual_privacy == "unlisted":
                status_msg = "Published unlisted"
            else:
                status_msg = "Published"
        elif latest_job.status == PublishJobStatus.UPLOADING:
            status_msg = f"Uploading to YouTube {latest_job.progress_percent:.0f}%"
        elif latest_job.status == PublishJobStatus.PROCESSING:
            status_msg = "YouTube is processing the video"
        elif latest_job.status == PublishJobStatus.AUTH_REQUIRED:
            status_msg = "YouTube upload access required. Please grant publishing permission."
        elif latest_job.status == PublishJobStatus.FAILED:
            status_msg = latest_job.error_message or "Publication failed"

    return PublishJobDetailResponse(
        job=latest_job,
        can_publish=not is_sample and conn is not None,
        has_upload_access=has_upload,
        status_message=status_msg,
        is_sample_channel=is_sample,
    )


@router.post(
    "/productions/{production_id}/publish/cancel",
    response_model=PublishJobDetailResponse,
    summary="Cancel Pending YouTube Publish Job",
    description="Cancel a queued or pending publish job before bytes start uploading.",
)
async def cancel_publish_job(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    publish_service: Annotated[YouTubePublishService, Depends(get_publish_service)],
    publish_job_repo: Annotated[PublishJobRepository, Depends(get_publish_job_repository)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
) -> PublishJobDetailResponse:
    latest_job = await publish_job_repo.get_latest_by_production_id(production_id)
    if not latest_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No publish job found to cancel.")

    try:
        cancelled_job = await publish_service.cancel_publish_job(latest_job.publish_job_id, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    prod = await production_repo.get_production(production_id)
    workspace = await workspace_repo.get_workspace_by_id(prod.workspace_id) if prod else None
    conn = await youtube_repo.get_connection(workspace.workspace_id) if workspace else None
    is_sample = bool(prod and (prod.channel_id.startswith("sample_") or prod.channel_id == "sample_tech_channel"))
    has_upload = bool(conn and SCOPE_YOUTUBE_UPLOAD in conn.scopes)

    return PublishJobDetailResponse(
        job=cancelled_job,
        can_publish=not is_sample and conn is not None,
        has_upload_access=has_upload,
        status_message="Publication cancelled.",
        is_sample_channel=is_sample,
    )
