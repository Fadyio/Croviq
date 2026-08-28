"""Deterministic YouTube Publishing orchestration service and background worker.

Enforces release gate verification, least-privilege YouTube OAuth usage, idempotent execution,
resumable video upload, thumbnail extraction, and truthful audit reporting.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import logging
from pathlib import Path
import tempfile
from typing import Any
import uuid

import httpx

from croviq_api.channels.token_encryption import get_oauth_token_encryptor
from croviq_api.channels.youtube_provider import SCOPE_YOUTUBE_UPLOAD, YOUTUBE_OAUTH_TOKEN_URL
from croviq_api.channels.youtube_publisher import (
    GoogleYouTubePublishClient,
    YouTubeAuthExpiredError,
    YouTubePermissionError,
    YouTubePublishClient,
    YouTubePublishError,
    YouTubeQuotaExceededError,
    YouTubeThumbnailError,
    YouTubeVideoMetadata,
    YouTubeVideoResource,
    get_youtube_publish_client,
    validate_youtube_metadata,
)
from croviq_api.channels.youtube_repository import (
    YouTubeConnection,
    YouTubeConnectionRepository,
    get_youtube_connection_repository,
)
from croviq_api.config import get_settings
from croviq_api.media.storage import MediaStorage
from croviq_api.productions.broll_repository import (
    BRollRepository,
    get_broll_repository,
)
from croviq_api.productions.edl_repository import (
    EDLRepository,
    get_edl_repository,
)
from croviq_api.productions.packaging_repository import (
    PackagingRepository,
    get_packaging_repository,
)
from croviq_api.productions.publish_job_repository import (
    PublishJobRepository,
    get_publish_job_repository,
)
from croviq_api.productions.release_review_repository import (
    ReleaseReviewRepository,
    get_release_review_repository,
)
from croviq_api.productions.render_repository import (
    RenderRepository,
    get_render_repository,
)
from croviq_api.productions.repository import (
    ProductionRepository,
    get_production_repository,
)
from croviq_api.productions.studio_voice_repository import (
    StudioVoiceRepository,
    get_studio_voice_repository,
)
from croviq_api.productions.thumbnail_repository import (
    ThumbnailRepository,
    get_thumbnail_repository,
)
from croviq_api.workspaces.repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from croviq_domain.packaging import PackagingChapter, format_ms_as_timestamp
from croviq_domain.production import Production
from croviq_domain.publish import (
    PublishJobStatus,
    ThumbnailArtifact,
    ThumbnailUploadStatus,
    YouTubePublishJob,
    build_publish_idempotency_key,
    build_thumbnail_artifact_gcs_path,
    derive_synthetic_media_status,
)
from croviq_domain.release_review import (
    ReleaseVerdict,
    build_release_fingerprint,
    verify_release_fingerprint,
)
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.user import User
from croviq_media.thumbnail import (
    FFmpegThumbnailExtractor,
    FakeThumbnailExtractor,
    ThumbnailExtractor,
)
from croviq_observability import log_event

logger = logging.getLogger(__name__)


class YouTubePublishService:
    """Orchestrates YouTube publication lifecycle, pre-publish validation, and background execution."""

    def __init__(
        self,
        production_repo: ProductionRepository,
        workspace_repo: WorkspaceRepository,
        youtube_repo: YouTubeConnectionRepository,
        edl_repo: EDLRepository,
        release_review_repo: ReleaseReviewRepository,
        packaging_repo: PackagingRepository,
        render_repo: RenderRepository,
        studio_voice_repo: StudioVoiceRepository,
        broll_repo: BRollRepository,
        thumbnail_repo: ThumbnailRepository,
        publish_job_repo: PublishJobRepository,
        media_storage: MediaStorage,
        publish_client: YouTubePublishClient | None = None,
        thumbnail_extractor: ThumbnailExtractor | None = None,
    ) -> None:
        self.production_repo = production_repo
        self.workspace_repo = workspace_repo
        self.youtube_repo = youtube_repo
        self.edl_repo = edl_repo
        self.release_review_repo = release_review_repo
        self.packaging_repo = packaging_repo
        self.render_repo = render_repo
        self.studio_voice_repo = studio_voice_repo
        self.broll_repo = broll_repo
        self.thumbnail_repo = thumbnail_repo
        self.publish_job_repo = publish_job_repo
        self.media_storage = media_storage
        self.publish_client = publish_client or get_youtube_publish_client()
        self.thumbnail_extractor = thumbnail_extractor or (
            FFmpegThumbnailExtractor() if get_settings().is_production else FakeThumbnailExtractor()
        )
    async def get_publish_preparation(
        self,
        production_id: str,
        current_user: User,
    ) -> dict[str, Any]:
        """Inspect and return pre-publish metadata, channel information, and suggested disclosures."""
        production = await self.production_repo.get_production(production_id)
        if not production:
            raise ValueError(f"Production '{production_id}' not found.")
        if production.owner_user_id != current_user.user_id:
            raise PermissionError("Access denied to production.")

        workspace = await self.workspace_repo.get_workspace_by_id(production.workspace_id)
        if not workspace:
            raise ValueError(f"Workspace '{production.workspace_id}' not found.")

        # Check channel connection
        is_sample = production.channel_id.startswith("sample_") or production.channel_id == "sample_tech_channel"
        connection = await self.youtube_repo.get_connection(workspace.workspace_id)

        channel_title = "Croviq Sample Channel" if is_sample else (connection.channel_title if connection else "Not Connected")
        channel_avatar_url = "" if is_sample else (connection.avatar_url if connection else "")
        has_upload_access = False if is_sample else (
            SCOPE_YOUTUBE_UPLOAD in connection.scopes if connection else False
        )
        can_publish = (not is_sample) and (connection is not None)

        # Load active EDL & verified Master/Short artifacts for this production
        edl = await self.edl_repo.get_latest_edl(production_id)
        master_artifact: RenderArtifact | None = None
        short_artifact: RenderArtifact | None = None
        if edl:
            master_artifact = await self.render_repo.get_render_artifact_by_type(
                production_id, edl.edl_id, ArtifactType.MASTER
            )
            if not master_artifact:
                master_artifact = await self.render_repo.get_render_artifact_by_type(
                    production_id, edl.edl_id, ArtifactType.STUDIO_VOICE_MASTER
                )
            short_artifact = await self.render_repo.get_render_artifact_by_type(
                production_id, edl.edl_id, ArtifactType.SHORT
            )
        else:
            renders = await self.render_repo.list_render_artifacts(production_id)
            master_artifact = next((r for r in renders if r.artifact_type in (ArtifactType.MASTER, ArtifactType.STUDIO_VOICE_MASTER) and r.status == ArtifactStatus.completed), None)
            if master_artifact:
                edl = await self.edl_repo.get_edl(production_id, master_artifact.edl_id)
                short_artifact = await self.render_repo.get_render_artifact_by_type(
                    production_id, master_artifact.edl_id, ArtifactType.SHORT
                )
        # Release Review & Gate Check
        release_review = await self.release_review_repo.get_latest_release_review(production_id)

        # Packaging
        proposal = await self.packaging_repo.get_latest_packaging_proposal(production_id)
        overrides = await self.packaging_repo.get_package_overrides(production_id)

        # Fingerprint calculation & lineage verification
        package_ver = proposal.version if (proposal and hasattr(proposal, "version")) else 1
        effective_edl_id = edl.edl_id if edl else (master_artifact.edl_id if master_artifact else "unknown_edl")
        calculated_fp = (
            build_release_fingerprint(
                production_id=production_id,
                edl_id=effective_edl_id,
                master_artifact_id=master_artifact.artifact_id,
                master_hash=master_artifact.sha256 or "unhashed",
                packaging_proposal_id=proposal.proposal_id,
                package_version=package_ver,
                release_review_id=release_review.review_id if release_review else None,
                short_artifact_id=short_artifact.artifact_id if short_artifact else None,
                short_hash=short_artifact.sha256 if short_artifact else None,
            )
            if (master_artifact and proposal)
            else None
        )

        has_master = bool(master_artifact and master_artifact.status == ArtifactStatus.completed)
        has_short = bool(short_artifact and short_artifact.status == ArtifactStatus.completed)
        has_packaging = bool(proposal is not None)

        release_ready = False
        if release_review and release_review.verdict == ReleaseVerdict.PASS and release_review.approved_for_release:
            matching_master = bool(master_artifact and release_review.master_artifact_id == master_artifact.artifact_id)
            matching_pkg = bool(proposal and release_review.packaging_proposal_id == proposal.proposal_id)
            package_ver_valid = bool(proposal and release_review.package_version >= package_ver)
            matching_short = bool(
                (not has_short and not release_review.short_artifact_id)
                or (has_short and short_artifact and release_review.short_artifact_id == short_artifact.artifact_id)
            )
            fingerprint_valid = bool(
                release_review.release_fingerprint is None or release_review.release_fingerprint == calculated_fp
            )
            release_ready = bool(
                has_master
                and has_packaging
                and matching_master
                and matching_pkg
                and package_ver_valid
                and matching_short
                and fingerprint_valid
            )
            if has_short and release_review.checklist and not release_review.checklist.short:
                release_ready = False

        suggested_title = ""
        suggested_description = ""
        suggested_chapters: list[dict[str, Any]] = []
        suggested_tags: list[str] = []
        verified_thumbnail_frames: list[dict[str, Any]] = []

        if proposal:
            suggested_title = overrides.selected_title if (overrides and overrides.selected_title) else proposal.primary_title
            suggested_description = overrides.description_template if (overrides and overrides.description_template) else proposal.description
            chapters = overrides.chapters if (overrides and overrides.chapters) else proposal.chapters
            suggested_chapters = [c.model_dump(mode="json") for c in chapters]
            suggested_tags = overrides.tags if (overrides and overrides.tags) else proposal.keywords
            verified_thumbnail_frames = [
                {
                    "concept_index": i,
                    "concept_id": c.concept_id,
                    "headline": c.headline,
                    "frame_timestamp_ms": c.supporting_frame_ms,
                    "formatted_time": format_ms_as_timestamp(c.supporting_frame_ms),
                    "visual_description": c.visual_subject,
                }
                for i, c in enumerate(proposal.thumbnail_concepts)
            ]

        master_duration_ms = master_artifact.duration_ms if master_artifact else None
        master_title = suggested_title or "Master Video"

        short_title = proposal.short_package.title if (proposal and proposal.short_package) else "Short"
        short_description = proposal.short_package.description if (proposal and proposal.short_package) else ""

        # Synthetic Media Detection deterministically derived strictly from Master artifact lineage
        contains_synthetic_media_suggested = derive_synthetic_media_status(
            master_artifact=master_artifact,
            edl=edl,
        )
        return {
            "production_id": production_id,
            "channel_title": channel_title,
            "channel_avatar_url": channel_avatar_url,
            "is_sample_channel": is_sample,
            "can_publish": can_publish,
            "has_upload_access": has_upload_access,
            "master_duration_ms": master_duration_ms,
            "master_title": master_title,
            "suggested_title": suggested_title,
            "suggested_description": suggested_description,
            "suggested_chapters": suggested_chapters,
            "suggested_tags": suggested_tags,
            "suggested_category_id": "28",
            "suggested_synthetic_media": contains_synthetic_media_suggested,
            "verified_thumbnail_frames": verified_thumbnail_frames,
            "has_short": has_short,
            "short_title": short_title,
            "short_description": short_description,
            "release_ready": release_ready,
        }

    async def initiate_publish_job(
        self,
        production_id: str,
        current_user: User,
        requested_privacy: str = "private",
        made_for_kids: bool = False,
        contains_synthetic_media: bool = False,
        selected_title: str | None = None,
        selected_description: str | None = None,
        selected_tags: list[str] | None = None,
        category_id: str = "28",
        thumbnail_frame_ms: int | None = None,
        upload_short: bool = False,
    ) -> YouTubePublishJob:
        """Create and queue a YouTubePublishJob, enforcing idempotency and strict release gates."""
        production = await self.production_repo.get_production(production_id)
        if not production:
            raise ValueError(f"Production '{production_id}' not found.")
        if production.owner_user_id != current_user.user_id:
            raise PermissionError("Access denied to production.")

        workspace = await self.workspace_repo.get_workspace_by_id(production.workspace_id)
        if not workspace:
            raise ValueError(f"Workspace '{production.workspace_id}' not found.")

        # 1. Sample Channel Restriction
        if production.channel_id.startswith("sample_") or production.channel_id == "sample_tech_channel":
            raise ValueError("The synthetic Croviq Sample Channel cannot publish to YouTube. Please connect a YouTube channel.")

        # 2. Connection and Scope Validation
        connection = await self.youtube_repo.get_connection(workspace.workspace_id)
        if not connection:
            raise ValueError("No connected YouTube channel found for this workspace.")

        # 3. Release Gate Validation (Requirement 1: release_ready = true)
        release_review = await self.release_review_repo.get_latest_release_review(production_id)
        if not release_review or release_review.verdict != ReleaseVerdict.PASS or not release_review.approved_for_release:
            raise ValueError("Release Gate check failed: Iris approval (PASS) is strictly required before publishing.")

        # 4. Active EDL and Master Render Artifact Validation (Strict Lineage)
        edl = await self.edl_repo.get_latest_edl(production_id)
        master_artifact: RenderArtifact | None = None
        short_art: RenderArtifact | None = None
        if edl:
            master_artifact = await self.render_repo.get_render_artifact_by_type(
                production_id, edl.edl_id, ArtifactType.MASTER
            )
            if not master_artifact:
                master_artifact = await self.render_repo.get_render_artifact_by_type(
                    production_id, edl.edl_id, ArtifactType.STUDIO_VOICE_MASTER
                )
            short_art = await self.render_repo.get_render_artifact_by_type(
                production_id, edl.edl_id, ArtifactType.SHORT
            )
        else:
            renders = await self.render_repo.list_render_artifacts(production_id)
            master_artifact = next((r for r in renders if r.artifact_type in (ArtifactType.MASTER, ArtifactType.STUDIO_VOICE_MASTER) and r.status == ArtifactStatus.completed), None)
            if master_artifact:
                edl = await self.edl_repo.get_edl(production_id, master_artifact.edl_id)
                short_art = await self.render_repo.get_render_artifact_by_type(
                    production_id, master_artifact.edl_id, ArtifactType.SHORT
                )

        if not master_artifact or master_artifact.status != ArtifactStatus.completed:
            raise ValueError("Approved Master render artifact not found or rendering incomplete.")

        if master_artifact.production_id != production_id:
            raise ValueError(f"Master artifact '{master_artifact.artifact_id}' belongs to a different production.")
        if edl and master_artifact.edl_id != edl.edl_id:
            raise ValueError(f"Master artifact '{master_artifact.artifact_id}' belongs to EDL '{master_artifact.edl_id}', but active release EDL is '{edl.edl_id}'.")

        if release_review.master_artifact_id != master_artifact.artifact_id:
            raise ValueError(
                f"Release review '{release_review.review_id}' was conducted on Master '{release_review.master_artifact_id}', "
                f"which does not match active Master '{master_artifact.artifact_id}'."
            )

        if edl and release_review.edl_id and release_review.edl_id != edl.edl_id:
            raise ValueError(
                f"Release review '{release_review.review_id}' was conducted on EDL '{release_review.edl_id}', "
                f"which does not match active EDL '{edl.edl_id}'."
            )
        proposal = await self.packaging_repo.get_latest_packaging_proposal(production_id)
        overrides = await self.packaging_repo.get_package_overrides(production_id)
        if not proposal:
            raise ValueError("Packaging proposal not found. Packaging is required before publishing.")
        final_title = selected_title or (overrides.selected_title if overrides and overrides.selected_title else proposal.primary_title)
        final_description = selected_description or (overrides.description_template if overrides and overrides.description_template else proposal.description)
        final_tags = selected_tags or (overrides.tags if overrides and overrides.tags else proposal.keywords)

        # Validate title and description length
        meta_to_validate = YouTubeVideoMetadata(
            title=final_title,
            description=final_description,
            tags=final_tags,
            category_id=category_id,
            privacy_status=requested_privacy,
            made_for_kids=made_for_kids,
            contains_synthetic_media=contains_synthetic_media,
        )
        validate_youtube_metadata(meta_to_validate)

        # 6. Release Fingerprint & Idempotency Check (Requirements 8, 19, 21)
        short_art = None
        if upload_short:
            short_art = await self.render_repo.get_render_artifact_by_type(
                production_id, edl.edl_id, ArtifactType.SHORT
            )
            if not short_art or short_art.status != ArtifactStatus.completed:
                raise ValueError(f"Approved Short render artifact for active EDL '{edl.edl_id}' not found.")

        package_ver = proposal.version if hasattr(proposal, "version") else 1
        if proposal.version > release_review.package_version:
            raise ValueError(
                f"Packaging proposal (v{proposal.version}) is newer than Iris review (v{release_review.package_version}). "
                "A fresh Iris review is required before publishing."
            )

        if release_review.packaging_proposal_id != proposal.proposal_id:
            raise ValueError(
                f"Release review packaging proposal '{release_review.packaging_proposal_id}' does not match active proposal '{proposal.proposal_id}'."
            )

        effective_edl_id = edl.edl_id if edl else (master_artifact.edl_id if master_artifact else "unknown_edl")
        calculated_fp = build_release_fingerprint(
            production_id=production_id,
            edl_id=effective_edl_id,
            master_artifact_id=master_artifact.artifact_id,
            master_hash=master_artifact.sha256 or "unhashed",
            packaging_proposal_id=proposal.proposal_id,
            package_version=package_ver,
            release_review_id=release_review.review_id,
            short_artifact_id=short_art.artifact_id if short_art else None,
            short_hash=short_art.sha256 if short_art else None,
        )
        if release_review.release_fingerprint and release_review.release_fingerprint != calculated_fp:
            raise ValueError(
                "Release gate check failed: release fingerprint mismatch against active pipeline artifacts. "
                "A new Iris QA review is required."
            )

        idempotency_key = build_publish_idempotency_key(
            production_id=production_id,
            release_review_id=release_review.review_id,
            master_artifact_id=master_artifact.artifact_id,
            package_version=package_ver,
        )
        existing_job = await self.publish_job_repo.get_by_idempotency_key(idempotency_key)
        if existing_job:
            if existing_job.status in (
                PublishJobStatus.PENDING,
                PublishJobStatus.UPLOADING,
                PublishJobStatus.PROCESSING,
                PublishJobStatus.COMPLETED,
            ):
                logger.info("Publish job already exists for idempotency key '%s'; returning existing job.", idempotency_key)
                return existing_job

        has_upload_scope = bool(connection and SCOPE_YOUTUBE_UPLOAD in connection.scopes)
        initial_status = PublishJobStatus.PENDING if has_upload_scope else PublishJobStatus.AUTH_REQUIRED

        publish_job_id = f"pub_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        job = YouTubePublishJob(
            publish_job_id=publish_job_id,
            production_id=production_id,
            workspace_id=workspace.workspace_id,
            user_id=current_user.user_id,
            connection_id=f"workspace:{workspace.workspace_id}:channel:{connection.channel_id}",
            channel_id=connection.channel_id,
            release_review_id=release_review.review_id,
            package_version=package_ver,
            artifact_id=master_artifact.artifact_id,
            artifact_type="MASTER",
            status=initial_status,
            requested_privacy=requested_privacy,
            selected_title=final_title,
            description=final_description,
            tags=final_tags,
            category_id=category_id,
            made_for_kids=made_for_kids,
            is_synthetic_media=contains_synthetic_media,
            short_requested=upload_short,
            short_artifact_id=short_art.artifact_id if short_art else None,
            master_hash=master_artifact.sha256,
            master_duration_ms=master_artifact.duration_ms,
            master_size_bytes=master_artifact.size_bytes,
            release_fingerprint=calculated_fp,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )

        saved_job = await self.publish_job_repo.save(job)

        log_event(
            "youtube.publish.started",
            production_id=production_id,
            publish_job_id=publish_job_id,
            artifact_id=master_artifact.artifact_id,
            requested_privacy=requested_privacy,
            is_synthetic_media=contains_synthetic_media,
            made_for_kids=made_for_kids,
        )

        # Kick off background execution if authorization is granted
        if has_upload_scope:
            asyncio.create_task(
                self.execute_publish_job(
                    publish_job_id=publish_job_id,
                    thumbnail_frame_ms=thumbnail_frame_ms,
                )
            )

        return saved_job

    async def _refresh_access_token_if_needed(self, connection: YouTubeConnection) -> str:
        """Verify and refresh YouTube access token if expired, updating secure storage."""
        now = datetime.now(timezone.utc)
        if connection.token_expiry and (connection.token_expiry - now).total_seconds() > 300:
            return connection.access_token

        if not connection.refresh_token:
            return connection.access_token

        client_id = get_settings().google_oauth_client_id
        client_secret = get_settings().google_oauth_client_secret
        if not client_id or not client_secret or connection.refresh_token.startswith("yt_refresh_mock"):
            return connection.access_token

        try:
            async with httpx.AsyncClient(timeout=20) as http_client:
                token_resp = await http_client.post(
                    YOUTUBE_OAUTH_TOKEN_URL,
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": connection.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    new_access = token_data.get("access_token", connection.access_token)
                    new_refresh = token_data.get("refresh_token") or connection.refresh_token
                    expires_in = token_data.get("expires_in", 3600)
                    updated_conn = connection.model_copy(
                        update={
                            "access_token": new_access,
                            "refresh_token": new_refresh,
                            "token_expiry": now + timedelta(seconds=expires_in),
                            "last_sync_at": now,
                        }
                    )
                    await self.youtube_repo.save_connection(updated_conn)
                    return new_access
        except Exception as exc:
            logger.warning("Token refresh call failed, attempting with current access token: %s", exc)

        return connection.access_token

    async def execute_publish_job(
        self,
        publish_job_id: str,
        thumbnail_frame_ms: int | None = None,
    ) -> None:
        """Durable background worker executing resumable video upload, thumbnail set, and Short upload."""
        job = await self.publish_job_repo.get_by_id(publish_job_id)
        if not job or job.status in (PublishJobStatus.COMPLETED, PublishJobStatus.FAILED, PublishJobStatus.CANCELLED):
            return

        workspace = await self.workspace_repo.get_workspace_by_id(job.workspace_id)
        if not workspace:
            await self.publish_job_repo.save(job.mark_failed("WORKSPACE_NOT_FOUND", "Workspace tenant not found."))
            return
        connection = await self.youtube_repo.get_connection(workspace.workspace_id)
        if not connection or SCOPE_YOUTUBE_UPLOAD not in connection.scopes:
            await self.publish_job_repo.save(
                job.mark_failed("AUTH_REQUIRED", "YouTube publishing permission not granted. Please grant upload access.")
            )
            return

        master_art = await self.render_repo.get_render_artifact(job.production_id, job.artifact_id)
        if not master_art:
            await self.publish_job_repo.save(
                job.mark_failed("MASTER_ARTIFACT_NOT_FOUND", "Master media artifact not found.")
            )
            return
        access_token = await self._refresh_access_token_if_needed(connection)

        temp_dir = tempfile.TemporaryDirectory()
        local_master_path = Path(temp_dir.name) / "master.mp4"
        local_thumbnail_path = Path(temp_dir.name) / "thumbnail.jpg"

        try:
            # 1. Download Master media from GCS
            logger.info("Downloading Master artifact '%s' from GCS for publication", master_art.artifact_id)
            await self.media_storage.download_object_to_path(
                bucket=master_art.gcs_bucket,
                object_name=master_art.gcs_object,
                target_path=local_master_path,
            )

            file_size = local_master_path.stat().st_size
            local_sha = hashlib.sha256(local_master_path.read_bytes()).hexdigest()
            if master_art.sha256 and local_sha != master_art.sha256:
                logger.error("Master artifact sha256 mismatch before upload: expected %s, got %s", master_art.sha256, local_sha)
                await self.publish_job_repo.save(job.mark_failed("INTEGRITY_ERROR", f"Master video SHA-256 integrity check failed (expected {master_art.sha256}, got {local_sha})."))
                return

            job = job.mark_uploading(total_bytes=file_size)
            if not job.master_hash:
                job = job.model_copy(update={"master_hash": local_sha, "master_size_bytes": file_size, "master_duration_ms": master_art.duration_ms})
            await self.publish_job_repo.save(job)
            # 2. Extract Thumbnail Frame if requested or available from Nina's proposal
            thumbnail_artifact: ThumbnailArtifact | None = None
            if thumbnail_frame_ms is not None or thumbnail_frame_ms == 0:
                target_frame_ms = thumbnail_frame_ms
            else:
                proposal = await self.packaging_repo.get_latest_packaging_proposal(job.production_id)
                target_frame_ms = proposal.thumbnail_concepts[0].supporting_frame_ms if (proposal and proposal.thumbnail_concepts) else 1000

            try:
                thumb_result = self.thumbnail_extractor.extract_thumbnail_frame(
                    source_media_path=local_master_path,
                    frame_ms=target_frame_ms,
                    output_path=local_thumbnail_path,
                )

                thumb_art_id = f"thumb_{uuid.uuid4().hex[:12]}"
                thumb_gcs_obj = build_thumbnail_artifact_gcs_path(
                    workspace_id=job.workspace_id,
                    production_id=job.production_id,
                    artifact_id=thumb_art_id,
                    ext="jpg",
                )
                gcs_bucket = master_art.gcs_bucket

                await self.media_storage.upload_object_from_path(
                    bucket=gcs_bucket,
                    object_name=thumb_gcs_obj,
                    source_path=thumb_result.output_path,
                    content_type=thumb_result.content_type,
                )

                thumbnail_artifact = ThumbnailArtifact(
                    artifact_id=thumb_art_id,
                    production_id=job.production_id,
                    source_frame_ms=target_frame_ms,
                    gcs_bucket=gcs_bucket,
                    gcs_object=thumb_gcs_obj,
                    width=thumb_result.width,
                    height=thumb_result.height,
                    size_bytes=thumb_result.size_bytes,
                    content_type=thumb_result.content_type,
                    created_at=datetime.now(timezone.utc),
                )
                await self.thumbnail_repo.save(thumbnail_artifact)
                job = job.model_copy(update={"thumbnail_artifact_id": thumb_art_id})
                await self.publish_job_repo.save(job)
            except Exception as thumb_exc:
                logger.warning("Thumbnail extraction failed; continuing video upload: %s", thumb_exc)

            # 3. Progress callback closure
            async def on_progress(uploaded: int, total: int) -> None:
                nonlocal job
                job = job.update_progress(uploaded)
                await self.publish_job_repo.save(job)
                log_event(
                    "youtube.publish.progress",
                    production_id=job.production_id,
                    publish_job_id=job.publish_job_id,
                    bytes_uploaded=uploaded,
                    total_bytes=total,
                    progress_percent=job.progress_percent,
                )

            # 4. Perform videos.insert (Resumable Upload)
            meta = YouTubeVideoMetadata(
                title=job.selected_title,
                description=job.description,
                tags=job.tags,
                category_id=job.category_id,
                privacy_status=job.requested_privacy,
                made_for_kids=job.made_for_kids,
                contains_synthetic_media=job.is_synthetic_media,
            )

            video_resource = await self.publish_client.upload_video(
                access_token=access_token,
                media_path=local_master_path,
                metadata=meta,
                progress_callback=on_progress,
            )

            job = job.mark_video_created(
                youtube_video_id=video_resource.video_id,
                actual_privacy=video_resource.privacy_status,
                audit_restriction_detected=video_resource.audit_restriction_detected,
            )
            await self.publish_job_repo.save(job)

            log_event(
                "youtube.publish.video_created",
                production_id=job.production_id,
                publish_job_id=job.publish_job_id,
                youtube_video_id=video_resource.video_id,
                requested_privacy=job.requested_privacy,
                actual_privacy=video_resource.privacy_status,
                audit_restriction_detected=video_resource.audit_restriction_detected,
            )

            # 5. Upload Custom Thumbnail via thumbnails.set
            thumb_status = ThumbnailUploadStatus.SKIPPED
            if thumbnail_artifact and local_thumbnail_path.exists():
                try:
                    job = job.model_copy(update={"thumbnail_status": ThumbnailUploadStatus.UPLOADING})
                    await self.publish_job_repo.save(job)

                    image_bytes = local_thumbnail_path.read_bytes()
                    await self.publish_client.set_thumbnail(
                        access_token=access_token,
                        video_id=video_resource.video_id,
                        image_bytes=image_bytes,
                        content_type=thumbnail_artifact.content_type,
                    )
                    thumb_status = ThumbnailUploadStatus.COMPLETED
                    log_event(
                        "youtube.publish.thumbnail_completed",
                        production_id=job.production_id,
                        publish_job_id=job.publish_job_id,
                        youtube_video_id=video_resource.video_id,
                        thumbnail_artifact_id=thumbnail_artifact.artifact_id,
                    )
                except Exception as thumb_err:
                    logger.warning("Thumbnail upload to YouTube failed: %s", thumb_err)
                    thumb_status = ThumbnailUploadStatus.FAILED

            # 6. Upload Short if requested
            short_video_id = None
            if job.short_requested and job.short_artifact_id:
                short_art = await self.render_repo.get_render_artifact(job.production_id, job.short_artifact_id)
                if short_art and short_art.status == ArtifactStatus.completed:
                    try:
                        local_short_path = Path(temp_dir.name) / "short.mp4"
                        await self.media_storage.download_object_to_path(
                            bucket=short_art.gcs_bucket,
                            object_name=short_art.gcs_object,
                            target_path=local_short_path,
                        )

                        proposal = await self.packaging_repo.get_latest_packaging_proposal(job.production_id)
                        short_title = proposal.short_package.title if (proposal and proposal.short_package) else f"{job.selected_title} #Shorts"
                        short_desc = proposal.short_package.description if (proposal and proposal.short_package) else "#Shorts"

                        short_meta = YouTubeVideoMetadata(
                            title=short_title[:100],
                            description=short_desc,
                            tags=job.tags + ["Shorts"],
                            category_id=job.category_id,
                            privacy_status=job.requested_privacy,
                            made_for_kids=job.made_for_kids,
                            contains_synthetic_media=job.is_synthetic_media,
                        )

                        short_resource = await self.publish_client.upload_video(
                            access_token=access_token,
                            media_path=local_short_path,
                            metadata=short_meta,
                        )
                        short_video_id = short_resource.video_id
                    except Exception as short_err:
                        logger.warning("Short upload failed: %s", short_err)

            # 7. Complete Publish Job
            job = job.mark_completed(
                thumbnail_status=thumb_status,
                short_youtube_video_id=short_video_id,
            )
            await self.publish_job_repo.save(job)

            log_event(
                "youtube.publish.completed",
                production_id=job.production_id,
                publish_job_id=job.publish_job_id,
                youtube_video_id=video_resource.video_id,
                requested_privacy=job.requested_privacy,
                actual_privacy=video_resource.privacy_status,
                audit_restriction_detected=video_resource.audit_restriction_detected,
                thumbnail_status=thumb_status.value,
                short_uploaded=bool(short_video_id),
            )

        except YouTubeAuthExpiredError as auth_err:
            logger.error("Publishing auth expired: %s", auth_err)
            job = job.mark_failed("AUTH_EXPIRED", "Reconnect YouTube: authorization has expired.")
            await self.publish_job_repo.save(job)
            log_event("youtube.publish.failed", production_id=job.production_id, error_code="AUTH_EXPIRED")
        except YouTubePermissionError as perm_err:
            logger.error("Publishing permission denied: %s", perm_err)
            job = job.mark_failed("PERMISSION_DENIED", "Publishing permission not granted. Please grant upload access.")
            await self.publish_job_repo.save(job)
            log_event("youtube.publish.failed", production_id=job.production_id, error_code="PERMISSION_DENIED")
        except YouTubeQuotaExceededError as quota_err:
            logger.error("Publishing quota exceeded: %s", quota_err)
            job = job.mark_failed("QUOTA_EXCEEDED", "YouTube upload quota reached. Please retry tomorrow.")
            await self.publish_job_repo.save(job)
            log_event("youtube.publish.failed", production_id=job.production_id, error_code="QUOTA_EXCEEDED")
        except Exception as exc:
            logger.error("YouTube publication encountered an error: %s", exc, exc_info=True)
            job = job.mark_failed("UPLOAD_ERROR", f"YouTube publication failed: {str(exc)}")
            await self.publish_job_repo.save(job)
            log_event("youtube.publish.failed", production_id=job.production_id, error_code="UPLOAD_ERROR", error=str(exc))
        finally:
            temp_dir.cleanup()

    async def cancel_publish_job(self, publish_job_id: str, current_user: User) -> YouTubePublishJob:
        """Cancel a pending publish job before remote upload starts."""
        job = await self.publish_job_repo.get_by_id(publish_job_id)
        if not job:
            raise ValueError(f"Publish job '{publish_job_id}' not found.")
        if job.user_id != current_user.user_id:
            raise PermissionError("Access denied to publish job.")

        if job.status == PublishJobStatus.PENDING or job.status == PublishJobStatus.AUTH_REQUIRED:
            job = job.mark_cancelled()
            return await self.publish_job_repo.save(job)
        return job
