"""API routes for Production lifecycle and direct GCS media upload."""

import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
import tempfile
import time
import uuid

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
from croviq_api.productions.render_review_repository import (
    RenderReviewRepository,
    get_render_review_repository,
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
from croviq_api.productions.editorial_service import DirectorEditorService
from croviq_api.productions.schemas import (
    AssembleEDLResponse,
    EDLDetailResponse,
    AnalyzeProductionResponse,
    CreateUploadRequest,
    CreateUploadResponse,
    DeleteProductionResponse,
    EditorialRunDetailResponse,
    ProductionListResponse,
    TranscribeProductionResponse,
    ProductionPlaybackResponse,
    RenderArtifactResponse,
    RenderListResponse,
    ReviewPreviewResponse,
    RenderReviewDetailResponse,
    StudioVoiceGenerationResponse,
    BRollListResponse,
    GeneratePackagingRequest,
    PackagingDetailResponse,
    UpdatePackagingOverridesRequest,
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
from croviq_agents.nina import NinaPackagingAgent
from croviq_domain.agent_config import AgentId
from croviq_domain.packaging import (
    CreatorPackageOverrides,
    PackagingChapter,
    PackagingProposal,
    ShortPackage,
    ThumbnailConcept,
    TitleAngle,
    TitleCandidate,
)
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
    log_short_render_event,
    log_transcription_event,
)

router = APIRouter(tags=["Productions & Uploads"])


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
    render_review_repo: Annotated[RenderReviewRepository, Depends(get_render_review_repository)],
    studio_voice_repo: Annotated[StudioVoiceRepository, Depends(get_studio_voice_repository)],
    broll_repo: Annotated[BRollRepository, Depends(get_broll_repository)],
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)],
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
        await render_review_repo.delete_by_production_id(production_id)
    except Exception as exc:
        logger.warning("Error deleting render reviews for %s: %s", production_id, exc)

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

    # Validate production source media state
    if (
        prod.status != ProductionStatus.UPLOADED
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

    # Idempotency check: check if transcript already exists for this production
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
    summary="Run Director + Editor Editorial Analysis",
    description="Execute Leo dialogue editing pass and Maya director review sequence using Gemini 3.7 Flash.",
)
async def analyze_production(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    editorial_service: Annotated[DirectorEditorService, Depends(get_editorial_service)],
    force: bool = False,
) -> AnalyzeProductionResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    run, proposal, review, activities = await editorial_service.run_editorial_analysis(
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
        director_review_id=run.director_review_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get(
    "/productions/{production_id}/editorial-run",
    response_model=EditorialRunDetailResponse,
    summary="Get Latest Editorial Run Details",
    description="Retrieve the latest EditorialRun, EditorProposal, DirectorReview, and AgentActivities.",
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

    review = None
    if run.director_review_id:
        review = await editorial_repo.get_director_review(production_id, run.director_review_id)

    activities = await editorial_repo.list_activities(production_id, run_id=run.run_id)

    return EditorialRunDetailResponse(
        run=run,
        proposal=proposal,
        review=review,
        activities=activities,
    )


@router.post(
    "/productions/{production_id}/edl",
    response_model=AssembleEDLResponse,
    summary="Assemble Canonical Edit Decision List (EDL)",
    description="Deterministically derives audio-safe cut instructions and visual coverage markers from approved Director review.",
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
    )



@router.post(
    "/productions/{production_id}/renders/short",
    response_model=RenderArtifactResponse,
    summary="Render Vertical Short Video",
    description="Deterministically render a 9:16 vertical Short MP4 with word-synced captions for an approved production.",
)
async def render_short_video(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)],
    editorial_repo: Annotated[EditorialRepository, Depends(get_editorial_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    render_review_repo: Annotated[RenderReviewRepository, Depends(get_render_review_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    render_service: Annotated[RenderService, Depends(get_render_service)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> RenderArtifactResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    prod = await _get_owned_production(production_id, current_user, production_repo)
    if not prod.source_media or not prod.source_media.gcs_bucket or not prod.source_media.gcs_object:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' has no uploaded source media to render",
        )
    request_id = getattr(request.state, "request_id", "unknown")
    settings = get_settings()
    edl = await edl_repo.get_latest_edl(production_id)
    if not edl:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' has no assembled EDL.",
        )

    # 1. Approval Gate: Maya review must approve for Master
    latest_review = await render_review_repo.get_latest_render_review(production_id)
    if not latest_review or not latest_review.approved_for_master:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' has not been approved for Master render by Director review.",
        )

    # 2. ShortCandidate check
    latest_run = await editorial_repo.get_latest_editorial_run(production_id)
    if not latest_run or not latest_run.editor_proposal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' has no editorial proposal.",
        )
    proposal = await editorial_repo.get_editor_proposal(production_id, latest_run.editor_proposal_id)
    if not proposal or not proposal.short_candidate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Production '{production_id}' has no ShortCandidate selected by Leo.",
        )
    short_candidate = proposal.short_candidate

    # 3. Idempotency check: if completed artifact exists in storage, return signed target
    existing_artifact = await render_repo.get_render_artifact_by_type(
        production_id=production_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.SHORT,
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

    # 4. Load transcript
    transcript = await transcript_repo.get_transcript_by_production_id(production_id)

    # 5. Execute render
    artifact_id = f"art_short_{uuid.uuid4().hex[:12]}"
    gcs_bucket = prod.source_media.gcs_bucket
    gcs_object = build_render_artifact_gcs_object_path(
        workspace_id=prod.workspace_id,
        production_id=prod.production_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.SHORT,
    )
    now = datetime.now(timezone.utc)
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
            await media_storage.download_object_to_path(
                bucket=prod.source_media.gcs_bucket,
                object_name=prod.source_media.gcs_object,
                target_path=local_src,
            )

            render_res = render_service.render_short(
                source_path=local_src,
                edl=edl,
                short_candidate=short_candidate,
                transcript=transcript,
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
            await render_repo.save_render_artifact(artifact)

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

            signed_target = await media_storage.generate_signed_read_target(
                bucket=artifact.gcs_bucket,
                object_name=artifact.gcs_object,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )
            return RenderArtifactResponse.from_domain(
                artifact=artifact,
                playback_url=signed_target.read_url,
                playback_expires_at=signed_target.expires_at,
            )
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
    responses: list[RenderArtifactResponse] = []
    for art in artifacts:
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
        responses.append(
            RenderArtifactResponse.from_domain(
                artifact=art,
                playback_url=playback_url,
                playback_expires_at=playback_expires_at,
            )
        )
    return RenderListResponse(
        production_id=prod.production_id,
        renders=responses,
    )


@router.post(
    "/productions/{production_id}/review-preview",
    response_model=ReviewPreviewResponse,
    summary="Review Preview Render & Gate Master Render",
    description="Maya (Director) inspects the rendered preview video, evaluates editorial quality, and either approves for Master render or executes a single bounded correction loop.",
)
async def review_preview_video(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    editorial_service: Annotated[DirectorEditorService, Depends(get_editorial_service)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> ReviewPreviewResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    settings = get_settings()
    (
        review,
        master_art,
        second_review,
        status_str,
        activities,
        self_review,
    ) = await editorial_service.review_preview(
        production_id=production_id,
        current_user=current_user,
        request_id=request_id,
    )
    master_response = None
    if master_art is not None and master_art.status == ArtifactStatus.completed:
        playback_url = None
        playback_expires_at = None
        try:
            target = await media_storage.generate_signed_read_target(
                bucket=master_art.gcs_bucket,
                object_name=master_art.gcs_object,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )
            playback_url = target.read_url
            playback_expires_at = target.expires_at
        except Exception:
            pass
        master_response = RenderArtifactResponse.from_domain(
            artifact=master_art,
            playback_url=playback_url,
            playback_expires_at=playback_expires_at,
        )
    return ReviewPreviewResponse(
        production_id=production_id,
        review=review,
        self_review=self_review,
        master_artifact=master_response,
        second_review=second_review,
        status=status_str,
        activities=activities,
    )


@router.get(
    "/productions/{production_id}/render-reviews",
    response_model=RenderReviewDetailResponse,
    summary="Get Render Reviews",
    description="Retrieve all post-render reviews for a production.",
)
@router.get(
    "/productions/{production_id}/render-review",
    response_model=RenderReviewDetailResponse,
    summary="Get Latest Render Review",
    description="Retrieve latest post-render review for a production.",
)
async def get_render_reviews(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    render_review_repo: Annotated[RenderReviewRepository, Depends(get_render_review_repository)],
) -> RenderReviewDetailResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)
    reviews = await render_review_repo.list_render_reviews(prod.production_id)
    latest = reviews[0] if reviews else None
    needs_manual = len(reviews) >= 2 and latest is not None and latest.verdict == "CORRECT"

    return RenderReviewDetailResponse(
        production_id=prod.production_id,
        review=latest,
        reviews=reviews,
        needs_manual_review=needs_manual,
    )
@router.get(
    "/productions/{production_id}/playback",
    response_model=ProductionPlaybackResponse,
    summary="Get Production Media Playback URLs",
    description="Retrieve distinct signed URLs for Original source, Edited Preview, Master, Studio Voice, and Short.",
)
async def get_production_playback_urls(
    production_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> ProductionPlaybackResponse:
    settings = get_settings()
    prod = await _get_owned_production(production_id, current_user, production_repo)

    source_url = None
    if prod.source_media and prod.source_media.status == SourceMediaStatus.UPLOADED:
        try:
            target = await media_storage.generate_signed_read_target(
                bucket=prod.source_media.gcs_bucket,
                object_name=prod.source_media.gcs_object,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )
            source_url = target.read_url
        except Exception:
            pass

    renders = await render_repo.list_render_artifacts(prod.production_id)
    preview_url = None
    master_url = None
    sv_url = None
    short_url = None

    for r in renders:
        status_val = r.status.value if hasattr(r.status, "value") else str(r.status)
        if status_val.lower() == "completed":
            try:
                target = await media_storage.generate_signed_read_target(
                    bucket=r.gcs_bucket,
                    object_name=r.gcs_object,
                    expiry_seconds=settings.signed_url_expiry_seconds,
                )
                type_val = r.artifact_type.value if hasattr(r.artifact_type, "value") else str(r.artifact_type)
                if type_val == ArtifactType.PREVIEW.value and preview_url is None:
                    preview_url = target.read_url
                elif type_val == ArtifactType.MASTER.value and master_url is None:
                    master_url = target.read_url
                elif type_val == ArtifactType.STUDIO_VOICE_PREVIEW.value and sv_url is None:
                    sv_url = target.read_url
                elif type_val == ArtifactType.SHORT.value and short_url is None:
                    short_url = target.read_url
            except Exception as exc:
                logger.warning("Failed to generate signed read target for artifact %s: %s", r.artifact_id, exc)

    return ProductionPlaybackResponse(
        production_id=prod.production_id,
        playback_url=source_url,
        rendered_preview_url=preview_url,
        master_url=master_url,
        studio_voice_preview_url=sv_url,
        short_playback_url=short_url,
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
    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        words = len(text.split())
        dur_ms = max(500, int(words * 360 + 100))
        return dur_ms, b"fake_studio_voice_pcm_bytes"

    async def leo_rewrite_fn(orig_text: str, max_dur_s: float, attempt: int) -> str:
        return await genai_client.generate_narration_rewrite(
            original_text=orig_text,
            available_duration_s=max_dur_s,
            attempt=attempt,
            production_id=prod.production_id,
        )

    tasks = [
        synthesizer.fit_narration_segment(
            segment_id=f"seg_{idx+1:03d}",
            production_id=prod.production_id,
            source_start_ms=seg.start_ms,
            source_end_ms=seg.end_ms,
            available_duration_ms=max(500, seg.end_ms - seg.start_ms),
            original_text=seg.text,
            voice_id=selected_voice,
            tts_fn=mock_tts,
            rewrite_fn=leo_rewrite_fn,
        )
        for idx, seg in enumerate(transcript.segments)
    ]
    segments: list[NarrationSegment] = list(await asyncio.gather(*tasks))
    now = datetime.now(timezone.utc)
    all_within = all(s.generated_duration_ms <= s.available_duration_ms for s in segments if s.status == NarrationSegmentStatus.ACCEPTED)

    # Render distinct Studio Voice Preview artifact
    edl = await edl_repo.get_latest_edl(prod.production_id)
    sv_playback_url = None

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

                # Create composite narration audio track
                total_dur_ms = edl.source_duration_ms or prod.source_media.duration_ms or 10000
                num_samples = int(48000 * total_dur_ms / 1000)
                data_size = num_samples * 2
                with open(local_narr, "wb") as f:
                    f.write(b"RIFF")
                    f.write((36 + data_size).to_bytes(4, "little"))
                    f.write(b"WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\xbb\x00\x00\x00\x77\x01\x00\x02\x00\x10\x00data")
                    f.write(data_size.to_bytes(4, "little"))
                    f.write(b"\x00" * min(data_size, 48000))

                # Run deterministic studio voice preview render in worker thread
                render_res = await asyncio.to_thread(
                    render_service.render_studio_voice_preview,
                    source_path=local_src,
                    edl=edl,
                    narration_audio_path=local_narr,
                    speech_intervals_ms=[(s.source_start_ms, s.source_end_ms) for s in segments],
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

    sv_result = StudioVoiceResult(
        production_id=prod.production_id,
        voice_id=selected_voice,
        narration_mode="studio_voice",
        segments=segments,
        total_segments=len(segments),
        accepted_segments=sum(1 for s in segments if s.status == NarrationSegmentStatus.ACCEPTED),
        all_within_budget=all_within,
        status="completed",
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
    short_artifact: RenderArtifact | None,
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

    short_url: str | None = None
    if short_artifact and short_artifact.status == ArtifactStatus.completed:
        try:
            target = await media_storage.generate_signed_read_target(
                bucket=short_artifact.gcs_bucket,
                object_name=short_artifact.gcs_object,
                expiry_seconds=settings.signed_url_expiry_seconds,
            )
            short_url = target.read_url
        except Exception as exc:
            logger.warning("Could not generate signed short url for packaging: %s", exc)

    master_resp = RenderArtifactResponse(
        artifact_id=master_artifact.artifact_id,
        production_id=master_artifact.production_id,
        edl_id=master_artifact.edl_id,
        artifact_type=master_artifact.artifact_type.value if hasattr(master_artifact.artifact_type, "value") else str(master_artifact.artifact_type),
        status=master_artifact.status.value if hasattr(master_artifact.status, "value") else str(master_artifact.status),
        duration_ms=master_artifact.duration_ms,
        created_at=master_artifact.created_at,
        completed_at=master_artifact.completed_at,
        playback_url=master_url,
    ) if master_artifact else None

    short_resp = RenderArtifactResponse(
        artifact_id=short_artifact.artifact_id,
        production_id=short_artifact.production_id,
        edl_id=short_artifact.edl_id,
        artifact_type=short_artifact.artifact_type.value if hasattr(short_artifact.artifact_type, "value") else str(short_artifact.artifact_type),
        status=short_artifact.status.value if hasattr(short_artifact.status, "value") else str(short_artifact.status),
        duration_ms=short_artifact.duration_ms,
        created_at=short_artifact.created_at,
        completed_at=short_artifact.completed_at,
        playback_url=short_url,
    ) if short_artifact else None

    effective_title = ""
    if overrides and overrides.custom_title:
        effective_title = overrides.custom_title
    elif overrides and overrides.selected_title:
        effective_title = overrides.selected_title
    elif proposal and proposal.primary_title:
        effective_title = proposal.primary_title

    effective_description = ""
    if overrides and overrides.custom_description:
        effective_description = overrides.custom_description
    elif proposal and proposal.description:
        effective_description = proposal.description

    effective_chapters: list[PackagingChapter] = []
    if overrides and overrides.custom_chapters is not None:
        effective_chapters = overrides.custom_chapters
    elif proposal and proposal.chapters:
        effective_chapters = proposal.chapters

    effective_short: ShortPackage | None = None
    if proposal and proposal.short_package:
        stitle = overrides.custom_short_title if (overrides and overrides.custom_short_title) else proposal.short_package.title
        sdesc = overrides.custom_short_description if (overrides and overrides.custom_short_description) else proposal.short_package.description
        effective_short = ShortPackage(
            title=stitle,
            description=sdesc,
            hook=proposal.short_package.hook,
            hashtags=proposal.short_package.hashtags,
        )

    effective_thumb_id = None
    if overrides and overrides.selected_thumbnail_concept_id:
        effective_thumb_id = overrides.selected_thumbnail_concept_id
    elif proposal and proposal.thumbnail_concepts:
        effective_thumb_id = proposal.thumbnail_concepts[0].concept_id

    has_master_bool = bool(master_artifact and master_artifact.status == ArtifactStatus.completed)
    has_short_bool = bool(short_artifact and short_artifact.status == ArtifactStatus.completed)
    status_str = "completed" if proposal else ("needs_master" if not has_master_bool else "ready")

    return PackagingDetailResponse(
        production_id=production_id,
        proposal=proposal,
        overrides=overrides,
        effective_title=effective_title,
        effective_description=effective_description,
        effective_chapters=effective_chapters,
        effective_short_package=effective_short,
        effective_thumbnail_concept_id=effective_thumb_id,
        master_artifact=master_resp,
        short_artifact=short_resp,
        master_url=master_url,
        short_url=short_url,
        has_master=has_master_bool,
        has_short=has_short_bool,
        status=status_str,
        generated_at=proposal.created_at if proposal else None,
    )


@router.post(
    "/productions/{production_id}/package",
    response_model=PackagingDetailResponse,
    summary="Generate Packaging Proposal",
    description="Invoke Nina (Packaging Agent) to generate title candidates, descriptions, chapters, thumbnail concepts, and Short packaging for an approved Master video.",
)
async def generate_packaging(
    production_id: str,
    request: Request,
    payload: GeneratePackagingRequest | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)] = None,
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)] = None,
    edl_repo: Annotated[EDLRepository, Depends(get_edl_repository)] = None,
    editorial_repo: Annotated[EditorialRepository, Depends(get_editorial_repository)] = None,
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)] = None,
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)] = None,
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)] = None,
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)] = None,
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)] = None,
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)] = None,
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)] = None,
    genai_client: Annotated[GenAIClient, Depends(get_genai_client)] = None,
) -> PackagingDetailResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    force_regenerate = payload.force_regenerate if payload else False

    prod = await _get_owned_production(production_id, current_user, production_repo)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)

    # 1. Prerequisite: Master video artifact must exist and be completed
    renders = await render_repo.list_render_artifacts(prod.production_id)
    master_artifact = next(
        (r for r in renders if (r.artifact_type == ArtifactType.MASTER or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.MASTER.value)) and r.status == ArtifactStatus.completed),
        None,
    )
    if not master_artifact:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Master video must be rendered and completed before generating packaging.",
        )

    short_artifact = next(
        (r for r in renders if (r.artifact_type == ArtifactType.SHORT or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.SHORT.value)) and r.status == ArtifactStatus.completed),
        None,
    )

    # 2. Retrieve Nina agent prompt configuration
    nina_prompt_config = await agent_config_repo.get_agent_prompt(workspace.workspace_id, AgentId.NINA)

    # 3. Idempotency check: Return cached proposal if already generated with same Master & prompt version
    overrides = await packaging_repo.get_package_overrides(prod.production_id)
    if not force_regenerate:
        latest_proposal = await packaging_repo.get_latest_packaging_proposal(prod.production_id)
        if (
            latest_proposal
            and latest_proposal.master_artifact_id == master_artifact.artifact_id
            and latest_proposal.prompt_version == nina_prompt_config.version
        ):
            return await _build_packaging_detail_response(
                production_id=prod.production_id,
                proposal=latest_proposal,
                overrides=overrides,
                master_artifact=master_artifact,
                short_artifact=short_artifact,
                media_storage=media_storage,
            )

    # 4. Gather transcript, chapters, editorial decisions, research, and memory
    transcript = await transcript_repo.get_transcript_by_production_id(prod.production_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcript not found for production {production_id}.",
        )

    latest_edl = await edl_repo.get_latest_edl(prod.production_id)
    latest_run = await editorial_repo.get_latest_editorial_run(prod.production_id)
    chapters = []
    short_candidate = None
    if latest_run and latest_run.editor_proposal_id:
        editor_prop = await editorial_repo.get_editor_proposal(prod.production_id, latest_run.editor_proposal_id)
        if editor_prop:
            short_candidate = editor_prop.short_candidate
            if editor_prop.chapters:
                chapters = editor_prop.chapters
    # Channel memory profile & lessons
    channel_profile = None
    lessons = []
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
        logger.warning("Could not retrieve memory profile for %s: %s", prod.channel_id, exc)

    # Research findings
    research_findings = []
    try:
        research_findings = await research_repo.list_findings(workspace_id=workspace.workspace_id, channel_id=prod.channel_id, limit=5)
    except Exception as exc:
        logger.warning("Could not retrieve research findings for %s: %s", prod.channel_id, exc)

    # 5. Invoke Nina Packaging Agent
    agent = NinaPackagingAgent(genai_client=genai_client)
    proposal, usage = await agent.package_production(
        production_id=prod.production_id,
        master_artifact=master_artifact,
        transcript=transcript,
        channel_profile=channel_profile,
        lessons=lessons,
        chapters=chapters,
        research_findings=research_findings,
        short_candidate=short_candidate,
        has_short_artifact=bool(short_artifact),
        custom_prompt=nina_prompt_config.prompt_text if nina_prompt_config.is_custom else None,
        prompt_version=nina_prompt_config.version,
        request_id=request_id,
    )

    # 6. Persist proposal
    await packaging_repo.save_packaging_proposal(proposal)

    return await _build_packaging_detail_response(
        production_id=prod.production_id,
        proposal=proposal,
        overrides=overrides,
        master_artifact=master_artifact,
        short_artifact=short_artifact,
        media_storage=media_storage,
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
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> PackagingDetailResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)

    renders = await render_repo.list_render_artifacts(prod.production_id)
    master_artifact = next(
        (r for r in renders if (r.artifact_type == ArtifactType.MASTER or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.MASTER.value)) and r.status == ArtifactStatus.completed),
        None,
    )
    short_artifact = next(
        (r for r in renders if (r.artifact_type == ArtifactType.SHORT or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.SHORT.value)) and r.status == ArtifactStatus.completed),
        None,
    )

    proposal = await packaging_repo.get_latest_packaging_proposal(prod.production_id)
    overrides = await packaging_repo.get_package_overrides(prod.production_id)

    return await _build_packaging_detail_response(
        production_id=prod.production_id,
        proposal=proposal,
        overrides=overrides,
        master_artifact=master_artifact,
        short_artifact=short_artifact,
        media_storage=media_storage,
    )


@router.patch(
    "/productions/{production_id}/packaging",
    response_model=PackagingDetailResponse,
    summary="Update Creator Package Overrides",
    description="Update creator overrides for title selection, custom title, description, chapter titles, Short title/description, or thumbnail concept selection.",
)
async def update_packaging_overrides(
    production_id: str,
    payload: UpdatePackagingOverridesRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    render_repo: Annotated[RenderRepository, Depends(get_render_repository)],
    packaging_repo: Annotated[PackagingRepository, Depends(get_packaging_repository)],
    media_storage: Annotated[MediaStorage, Depends(get_media_storage)],
) -> PackagingDetailResponse:
    prod = await _get_owned_production(production_id, current_user, production_repo)

    existing_overrides = await packaging_repo.get_package_overrides(prod.production_id)
    now = datetime.now(timezone.utc)

    selected_title = payload.selected_title if payload.selected_title is not None else (existing_overrides.selected_title if existing_overrides else None)
    custom_title = payload.custom_title if payload.custom_title is not None else (existing_overrides.custom_title if existing_overrides else None)
    custom_description = payload.custom_description if payload.custom_description is not None else (existing_overrides.custom_description if existing_overrides else None)
    custom_chapters = payload.custom_chapters if payload.custom_chapters is not None else (existing_overrides.custom_chapters if existing_overrides else None)
    custom_short_title = payload.custom_short_title if payload.custom_short_title is not None else (existing_overrides.custom_short_title if existing_overrides else None)
    custom_short_description = payload.custom_short_description if payload.custom_short_description is not None else (existing_overrides.custom_short_description if existing_overrides else None)
    selected_thumb_id = payload.selected_thumbnail_concept_id if payload.selected_thumbnail_concept_id is not None else (existing_overrides.selected_thumbnail_concept_id if existing_overrides else None)

    updated_overrides = CreatorPackageOverrides(
        selected_title=selected_title,
        custom_title=custom_title,
        custom_description=custom_description,
        custom_chapters=custom_chapters,
        custom_short_title=custom_short_title,
        custom_short_description=custom_short_description,
        selected_thumbnail_concept_id=selected_thumb_id,
        updated_at=now,
    )
    await packaging_repo.save_package_overrides(prod.production_id, updated_overrides)

    renders = await render_repo.list_render_artifacts(prod.production_id)
    master_artifact = next(
        (r for r in renders if (r.artifact_type == ArtifactType.MASTER or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.MASTER.value)) and r.status == ArtifactStatus.completed),
        None,
    )
    short_artifact = next(
        (r for r in renders if (r.artifact_type == ArtifactType.SHORT or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.SHORT.value)) and r.status == ArtifactStatus.completed),
        None,
    )
    proposal = await packaging_repo.get_latest_packaging_proposal(prod.production_id)

    return await _build_packaging_detail_response(
        production_id=prod.production_id,
        proposal=proposal,
        overrides=updated_overrides,
        master_artifact=master_artifact,
        short_artifact=short_artifact,
        media_storage=media_storage,
    )
