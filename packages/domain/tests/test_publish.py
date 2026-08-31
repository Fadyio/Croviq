"""Unit tests for YouTube Publishing domain models and idempotency contracts."""

from datetime import datetime, timezone
import pytest

from croviq_domain.agent_config import NarrationMode
from croviq_domain.edl import EditDecisionList
from croviq_domain.publish import (
    PublishJobStatus,
    ThumbnailArtifact,
    ThumbnailUploadStatus,
    YouTubePublishJob,
    build_publish_idempotency_key,
    build_thumbnail_artifact_gcs_path,
    derive_synthetic_media_status,
)
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact


def test_build_publish_idempotency_key() -> None:
    key1 = build_publish_idempotency_key(
        production_id="prod_01",
        release_review_id="rev_01",
        master_artifact_id="art_master_01",
        package_version=1,
    )
    assert key1 == "prod_01:rev_01:art_master_01:1:attempt_1"

    key2 = build_publish_idempotency_key(
        production_id="prod_01",
        release_review_id="rev_01",
        master_artifact_id="art_master_01",
        package_version=1,
        attempt=2,
    )
    assert key2 == "prod_01:rev_01:art_master_01:1:attempt_2"


def test_build_thumbnail_artifact_gcs_path() -> None:
    path = build_thumbnail_artifact_gcs_path(
        workspace_id="ws_01",
        production_id="prod_01",
        artifact_id="thumb_01",
    )
    assert path == "workspaces/ws_01/productions/prod_01/thumbnails/thumb_01.jpg"


def test_thumbnail_artifact_validation() -> None:
    now = datetime.now(timezone.utc)
    artifact = ThumbnailArtifact(
        artifact_id="thumb_01",
        production_id="prod_01",
        source_frame_ms=12500,
        gcs_bucket="croviq-media-thumbnails",
        gcs_object="workspaces/ws_01/productions/prod_01/thumbnails/thumb_01.jpg",
        width=1920,
        height=1080,
        size_bytes=1024000,
        content_type="image/jpeg",
        created_at=now,
    )
    assert artifact.artifact_id == "thumb_01"
    assert artifact.source_frame_ms == 12500
    assert artifact.size_bytes == 1024000
    assert artifact.size_bytes <= 2 * 1024 * 1024


def test_youtube_publish_job_initial_state() -> None:
    now = datetime.now(timezone.utc)
    job = YouTubePublishJob(
        publish_job_id="pub_01",
        production_id="prod_01",
        workspace_id="ws_01",
        user_id="usr_01",
        connection_id="conn_01",
        channel_id="UC_01",
        release_review_id="rev_01",
        package_version=1,
        artifact_id="art_master_01",
        selected_title="Building Autonomous AI Systems",
        description="Full video tutorial.\n\n0:00 Introduction\n1:00 Demo",
        tags=["AI", "Engineering"],
        idempotency_key="prod_01:rev_01:art_master_01:1:attempt_1",
        created_at=now,
        updated_at=now,
    )

    assert job.status == PublishJobStatus.PENDING
    assert job.requested_privacy == "private"
    assert job.actual_privacy is None
    assert job.youtube_video_id is None
    assert job.thumbnail_status == ThumbnailUploadStatus.PENDING
    assert job.progress_percent == 0.0
    assert job.audit_restriction_detected is False


def test_youtube_publish_job_state_transitions() -> None:
    now = datetime.now(timezone.utc)
    job = YouTubePublishJob(
        publish_job_id="pub_01",
        production_id="prod_01",
        workspace_id="ws_01",
        user_id="usr_01",
        connection_id="conn_01",
        channel_id="UC_01",
        release_review_id="rev_01",
        package_version=1,
        artifact_id="art_master_01",
        selected_title="Building Autonomous AI Systems",
        description="Full video tutorial.",
        idempotency_key="prod_01:rev_01:art_master_01:1:attempt_1",
        created_at=now,
        updated_at=now,
    )

    # Transition to UPLOADING
    uploading_job = job.mark_uploading(total_bytes=50000000)
    assert uploading_job.status == PublishJobStatus.UPLOADING
    assert uploading_job.total_bytes == 50000000
    assert uploading_job.started_at is not None

    # Update progress
    progress_job = uploading_job.update_progress(bytes_uploaded=25000000)
    assert progress_job.bytes_uploaded == 25000000
    assert progress_job.progress_percent == 50.0

    # Video created
    video_created_job = progress_job.mark_video_created(
        youtube_video_id="yt_vid_123",
        actual_privacy="private",
        audit_restriction_detected=False,
    )
    assert video_created_job.youtube_video_id == "yt_vid_123"
    assert video_created_job.youtube_url == "https://youtu.be/yt_vid_123"
    assert video_created_job.actual_privacy == "private"

    # Completed
    completed_job = video_created_job.mark_completed(thumbnail_status=ThumbnailUploadStatus.COMPLETED)
    assert completed_job.status == PublishJobStatus.COMPLETED
    assert completed_job.thumbnail_status == ThumbnailUploadStatus.COMPLETED
    assert completed_job.completed_at is not None


def test_derive_synthetic_media_status_original_footage_and_voice() -> None:
    now = datetime.now(timezone.utc)
    master_art = RenderArtifact(
        artifact_id="art_mast_01",
        production_id="prod_01",
        edl_id="edl_01",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="test-bucket",
        gcs_object="test.mp4",
        size_bytes=1000,
        duration_ms=10000,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        sha256="abc",
        created_at=now,
    )
    # Unaltered original footage + original voice -> False
    assert derive_synthetic_media_status(master_artifact=master_art) is False
    # Unaltered original footage + enhanced original voice -> False
    assert (
        derive_synthetic_media_status(
            master_artifact=master_art,
            narration_mode=NarrationMode.ENHANCED_ORIGINAL,
        )
        is False
    )


def test_derive_synthetic_media_status_studio_voice() -> None:
    now = datetime.now(timezone.utc)
    sv_master_art = RenderArtifact(
        artifact_id="art_mast_sv_01",
        production_id="prod_01",
        edl_id="edl_01",
        artifact_type=ArtifactType.STUDIO_VOICE_MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="test-bucket",
        gcs_object="test_sv.mp4",
        size_bytes=1000,
        duration_ms=10000,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        sha256="def",
        created_at=now,
    )
    # Studio Voice Master artifact -> True
    assert derive_synthetic_media_status(master_artifact=sv_master_art) is True
    # Standard Master artifact but studio voice explicitly used in master render -> True
    assert (
        derive_synthetic_media_status(
            master_artifact_type=ArtifactType.MASTER,
            studio_voice_used=True,
        )
        is True
    )


def test_derive_synthetic_media_status_my_voice() -> None:
    # My Voice replication used in master -> True
    assert (
        derive_synthetic_media_status(
            master_artifact_type=ArtifactType.MASTER,
            my_voice_used=True,
        )
        is True
    )
    assert (
        derive_synthetic_media_status(
            narration_mode=NarrationMode.MY_VOICE,
        )
        is True
    )



def test_derive_synthetic_media_status_from_release_object() -> None:
    now = datetime.now(timezone.utc)
    job_clean = YouTubePublishJob(
        publish_job_id="pub_clean",
        production_id="prod_01",
        workspace_id="ws_01",
        user_id="u_01",
        connection_id="c_01",
        channel_id="ch_01",
        release_review_id="rev_01",
        package_version=1,
        artifact_id="art_mast_01",
        artifact_type="MASTER",
        status=PublishJobStatus.COMPLETED,
        selected_title="Clean Title",
        description="Clean Description",
        is_synthetic_media=False,
        idempotency_key="idemp_clean",
        created_at=now,
    )
    assert derive_synthetic_media_status(release=job_clean) is False

    job_synthetic = YouTubePublishJob(
        publish_job_id="pub_syn",
        production_id="prod_01",
        workspace_id="ws_01",
        user_id="u_01",
        connection_id="c_01",
        channel_id="ch_01",
        release_review_id="rev_01",
        package_version=1,
        artifact_id="art_mast_sv_01",
        artifact_type="STUDIO_VOICE_MASTER",
        status=PublishJobStatus.COMPLETED,
        selected_title="Synthetic Title",
        description="Synthetic Description",
        is_synthetic_media=True,
        idempotency_key="idemp_syn",
        created_at=now,
    )
    assert derive_synthetic_media_status(release=job_synthetic) is True
