"""API routes for Production lifecycle and direct GCS media upload."""

from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from croviq_api.auth.dependencies import get_current_user
from croviq_api.config import get_settings
from croviq_api.media.dependencies import (
    get_media_inspector,
    get_media_storage,
    get_transcription_service,
)
from croviq_api.media.logging import log_media_upload_event
from croviq_api.media.storage import MediaStorage
from croviq_api.productions.repository import (
    ProductionRepository,
    get_production_repository,
)
from croviq_api.productions.transcript_repository import (
    TranscriptRepository,
    get_transcript_repository,
)
from croviq_api.productions.schemas import (
    CreateUploadRequest,
    CreateUploadResponse,
    ProductionListResponse,
    TranscribeProductionResponse,
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
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript
from croviq_domain.user import User
from croviq_media.inspector import MediaInspector
from croviq_media.transcript import TranscriptionService
from croviq_observability import (
    log_media_inspect_event,
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
        current_user, default_name="Croviq Demo Workspace"
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
        current_user, default_name="Croviq Demo Workspace"
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


@router.post(
    "/productions/{production_id}/transcribe",
    response_model=TranscribeProductionResponse,
    summary="Transcribe Production Source Media",
    description="Trigger word-aligned speech recognition on uploaded source media via Speech-to-Text v2.",
)
async def transcribe_production(
    production_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    production_repo: Annotated[ProductionRepository, Depends(get_production_repository)],
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
    transcription_service: Annotated[TranscriptionService, Depends(get_transcription_service)],
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

    gcs_uri = f"gs://{source.gcs_bucket}/{source.gcs_object}"
    start_time = datetime.now(timezone.utc)
    import time
    perf_start = time.perf_counter()

    log_transcription_event(
        event_type="transcription.started",
        status="in_progress",
        request_id=request_id,
        production_id=production_id,
        message="Initiating word-aligned speech recognition",
    )

    try:
        transcript = await transcription_service.transcribe_gcs_uri(
            gcs_uri=gcs_uri,
            language_code="en-US",
            production_id=production_id,
        )
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
            message="Word-aligned speech recognition completed",
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
    except Exception as exc:
        latency_ms = (time.perf_counter() - perf_start) * 1000
        log_transcription_event(
            event_type="transcription.failed",
            status=500,
            request_id=request_id,
            production_id=production_id,
            latency_ms=latency_ms,
            error_code="transcription_failed",
            exception=exc,
            message=f"Transcription failed: {type(exc).__name__}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech transcription failed: {str(exc)}",
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
