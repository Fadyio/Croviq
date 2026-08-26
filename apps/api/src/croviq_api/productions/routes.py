"""API routes for Production lifecycle and direct GCS media upload."""

from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from croviq_api.auth.dependencies import get_current_user
from croviq_api.config import get_settings
from croviq_api.media.dependencies import get_media_storage
from croviq_api.media.logging import log_media_upload_event
from croviq_api.media.storage import MediaStorage
from croviq_api.productions.repository import (
    ProductionRepository,
    get_production_repository,
)
from croviq_api.productions.schemas import (
    CreateUploadRequest,
    CreateUploadResponse,
    ProductionListResponse,
)
from croviq_api.workspaces.repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from croviq_domain.production import (
    MAX_UPLOAD_SIZE_BYTES,
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
    build_source_media_gcs_object_path,
    validate_media_file,
)
from croviq_domain.user import User

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
