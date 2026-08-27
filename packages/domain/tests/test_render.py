"""Unit tests for RenderArtifact, ArtifactType, ArtifactStatus, and GCS path builder."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
    build_render_artifact_gcs_object_path,
)


def test_artifact_type_values():
    assert ArtifactType.PREVIEW == "PREVIEW"
    assert ArtifactType.MASTER == "MASTER"
    assert ArtifactType.SHORT == "SHORT"
    assert set(ArtifactType) == {ArtifactType.PREVIEW, ArtifactType.MASTER, ArtifactType.SHORT}

def test_artifact_status_values():
    assert ArtifactStatus.pending == "pending"
    assert ArtifactStatus.rendering == "rendering"
    assert ArtifactStatus.completed == "completed"
    assert ArtifactStatus.failed == "failed"
    assert set(ArtifactStatus) == {
        ArtifactStatus.pending,
        ArtifactStatus.rendering,
        ArtifactStatus.completed,
        ArtifactStatus.failed,
    }


def test_build_render_artifact_gcs_object_path():
    preview_path = build_render_artifact_gcs_object_path(
        workspace_id="ws_123",
        production_id="prod_abc",
        edl_id="edl_xyz",
        artifact_type=ArtifactType.PREVIEW,
    )
    assert preview_path == "workspaces/ws_123/productions/prod_abc/renders/edl_xyz/preview.mp4"

    master_path = build_render_artifact_gcs_object_path(
        workspace_id="ws_123",
        production_id="prod_abc",
        edl_id="edl_xyz",
        artifact_type=ArtifactType.MASTER,
    )
    assert master_path == "workspaces/ws_123/productions/prod_abc/renders/edl_xyz/master.mp4"

    # String input support
    str_preview_path = build_render_artifact_gcs_object_path(
        workspace_id="ws_123",
        production_id="prod_abc",
        edl_id="edl_xyz",
        artifact_type="PREVIEW",
    )
    assert str_preview_path == "workspaces/ws_123/productions/prod_abc/renders/edl_xyz/preview.mp4"
    short_path = build_render_artifact_gcs_object_path(
        "ws_123", "prod_abc", "edl_xyz", ArtifactType.SHORT
    )
    assert short_path == "workspaces/ws_123/productions/prod_abc/renders/edl_xyz/short.mp4"



def test_build_render_artifact_gcs_object_path_invalid_inputs():
    with pytest.raises(ValueError, match="workspace_id must be non-empty"):
        build_render_artifact_gcs_object_path("", "prod_abc", "edl_xyz", ArtifactType.PREVIEW)

    with pytest.raises(ValueError, match="production_id must be non-empty"):
        build_render_artifact_gcs_object_path("ws_123", "", "edl_xyz", ArtifactType.PREVIEW)

    with pytest.raises(ValueError, match="edl_id must be non-empty"):
        build_render_artifact_gcs_object_path("ws_123", "prod_abc", "", ArtifactType.PREVIEW)


def test_render_artifact_minimal_valid():
    now = datetime.now(timezone.utc)
    artifact = RenderArtifact(
        artifact_id="art_001",
        production_id="prod_001",
        edl_id="edl_001",
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.pending,
        gcs_bucket="croviq-506602-croviq-media-raw",
        gcs_object="workspaces/ws_1/productions/prod_001/renders/edl_001/preview.mp4",
        created_at=now,
    )
    assert artifact.artifact_id == "art_001"
    assert artifact.artifact_type == ArtifactType.PREVIEW
    assert artifact.status == ArtifactStatus.pending
    assert artifact.content_type == "video/mp4"
    assert artifact.size_bytes is None
    assert artifact.duration_ms is None
    assert artifact.created_at == now
    assert artifact.completed_at is None
    assert artifact.failure_code is None


def test_render_artifact_completed_full():
    now = datetime.now(timezone.utc)
    artifact = RenderArtifact(
        artifact_id="art_master_001",
        production_id="prod_001",
        edl_id="edl_001",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-506602-croviq-media-raw",
        gcs_object="workspaces/ws_1/productions/prod_001/renders/edl_001/master.mp4",
        content_type="video/mp4",
        size_bytes=15_420_000,
        duration_ms=113824,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        created_at=now,
        completed_at=now,
        failure_code=None,
    )
    assert artifact.status == ArtifactStatus.completed
    assert artifact.size_bytes == 15_420_000
    assert artifact.duration_ms == 113824
    assert artifact.width == 1920
    assert artifact.height == 1080
    assert artifact.frame_rate == 30.0
    assert artifact.video_codec == "h264"
    assert artifact.audio_codec == "aac"


def test_render_artifact_extra_forbid():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        RenderArtifact(
            artifact_id="art_001",
            production_id="prod_001",
            edl_id="edl_001",
            artifact_type=ArtifactType.PREVIEW,
            status=ArtifactStatus.pending,
            gcs_bucket="croviq-506602-croviq-media-raw",
            gcs_object="workspaces/ws_1/productions/prod_001/renders/edl_001/preview.mp4",
            created_at=now,
            extra_field="disallowed",
        )


def test_render_artifact_timezone_validation():
    naive = datetime(2026, 8, 27, 12, 0, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        RenderArtifact(
            artifact_id="art_001",
            production_id="prod_001",
            edl_id="edl_001",
            artifact_type=ArtifactType.PREVIEW,
            status=ArtifactStatus.pending,
            gcs_bucket="croviq-506602-croviq-media-raw",
            gcs_object="workspaces/ws_1/productions/prod_001/renders/edl_001/preview.mp4",
            created_at=naive,
        )
