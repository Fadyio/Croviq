"""API integration tests for video rendering endpoints (Preview and Master) and render listing."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pytest
from fastapi.testclient import TestClient

from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.productions.dependencies import (
    get_genai_client,
    get_render_repository,
    get_render_service,
    set_render_repository,
    set_render_service,
)
from croviq_api.productions.edl_repository import (
    InMemoryEDLRepository,
    get_edl_repository,
    set_edl_repository,
)
from croviq_api.productions.render_repository import (
    InMemoryRenderRepository,
)
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    get_production_repository,
    set_production_repository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    get_workspace_repository,
    set_workspace_repository,
)
from croviq_domain.editorial import EditorDecisionType
from croviq_domain.edl import (
    CoverageMarker,
    CoverageType,
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
)
from croviq_domain.production import Production, ProductionStatus, SourceMedia, SourceMediaStatus
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.user import User
from croviq_media.render import FakeRenderService, RenderExecutionResult, RenderService


class CountingFakeRenderService(FakeRenderService):
    def __init__(self) -> None:
        super().__init__()
        self.preview_call_count = 0
        self.master_call_count = 0
        self.short_call_count = 0
    def render_preview(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        self.preview_call_count += 1
        src = Path(source_path)
        out = Path(output_path) if output_path else Path("preview_out.mp4")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake preview mp4 bytes")
        return RenderExecutionResult(
            output_path=out,
            artifact_type=ArtifactType.PREVIEW,
            duration_ms=edl.estimated_target_duration_ms,
            size_bytes=len(b"fake preview mp4 bytes"),
            width=1280,
            height=720,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            render_time_ms=120.0,
        )

    def render_master(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        self.master_call_count += 1
        src = Path(source_path)
        out = Path(output_path) if output_path else Path("master_out.mp4")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake master mp4 bytes with higher quality")
        return RenderExecutionResult(
            output_path=out,
            artifact_type=ArtifactType.MASTER,
            duration_ms=edl.estimated_target_duration_ms,
            size_bytes=len(b"fake master mp4 bytes with higher quality"),
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            render_time_ms=350.0,
        )

    def render_short(
        self,
        source_path: Path | str,
        edl: EditDecisionList,
        short_candidate: Any,
        transcript: Any = None,
        output_path: Path | str | None = None,
    ) -> RenderExecutionResult:
        self.short_call_count += 1
        src = Path(source_path)
        out = Path(output_path) if output_path else Path("short_out.mp4")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake short mp4 bytes vertical")
        return RenderExecutionResult(
            output_path=out,
            artifact_type=ArtifactType.SHORT,
            duration_ms=4000,
            size_bytes=len(b"fake short mp4 bytes vertical"),
            width=1080,
            height=1920,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            render_time_ms=200.0,
        )


@pytest.fixture
def auth_user():
    now = datetime.now(timezone.utc)
    return User(
        user_id="user_test_render_owner",
        email="testowner@example.com",
        display_name="Test Owner",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def other_user():
    now = datetime.now(timezone.utc)
    return User(
        user_id="user_other_render",
        email="other@example.com",
        display_name="Other User",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def test_setup(auth_user):
    prod_repo = InMemoryProductionRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    ws_repo = InMemoryWorkspaceRepository()
    media_storage = FakeMediaStorage()
    fake_render_service = CountingFakeRenderService()
    fake_genai_client = FakeGenAIClient()

    set_production_repository(prod_repo)
    set_edl_repository(edl_repo)
    set_render_repository(render_repo)
    set_workspace_repository(ws_repo)
    set_render_service(fake_render_service)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    app.dependency_overrides[get_media_storage] = lambda: media_storage
    app.dependency_overrides[get_render_service] = lambda: fake_render_service
    app.dependency_overrides[get_genai_client] = lambda: fake_genai_client

    client = TestClient(app)

    return {
        "client": client,
        "app": app,
        "prod_repo": prod_repo,
        "edl_repo": edl_repo,
        "render_repo": render_repo,
        "ws_repo": ws_repo,
        "media_storage": media_storage,
        "render_service": fake_render_service,
        "genai_client": fake_genai_client,
        "auth_user": auth_user,
    }


@pytest.mark.asyncio
async def test_render_endpoints_auth_required():
    app = create_app()
    client = TestClient(app)

    r_preview = client.post("/api/productions/prod_any/renders/preview")
    assert r_preview.status_code == 401

    r_master = client.post("/api/productions/prod_any/renders/master")
    assert r_master.status_code == 401

    r_list = client.get("/api/productions/prod_any/renders")
    assert r_list.status_code == 401


@pytest.mark.asyncio
async def test_render_endpoints_404_production_not_found(test_setup):
    client = test_setup["client"]
    r = client.post("/api/productions/non_existent/renders/preview")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_render_endpoints_403_other_user(test_setup, other_user):
    prod_repo = test_setup["prod_repo"]
    client = test_setup["client"]
    now = datetime.now(timezone.utc)

    # Production belongs to other_user
    prod = Production(
        production_id="prod_other",
        workspace_id="ws_other",
        channel_id="ch_other",
        owner_user_id=other_user.user_id,
        status=ProductionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    r = client.post("/api/productions/prod_other/renders/preview")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_render_endpoints_400_no_source_media(test_setup, auth_user):
    prod_repo = test_setup["prod_repo"]
    client = test_setup["client"]
    now = datetime.now(timezone.utc)

    prod = Production(
        production_id="prod_no_media",
        workspace_id="ws_1",
        channel_id="ch_1",
        owner_user_id=auth_user.user_id,
        status=ProductionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    r = client.post("/api/productions/prod_no_media/renders/preview")
    assert r.status_code == 400
    assert "no uploaded source media" in r.json()["detail"]


@pytest.mark.asyncio
async def test_render_endpoints_400_no_edl(test_setup, auth_user):
    prod_repo = test_setup["prod_repo"]
    media_storage = test_setup["media_storage"]
    client = test_setup["client"]
    now = datetime.now(timezone.utc)

    source_obj = "workspaces/ws_1/productions/prod_1/source/up_1/video.mp4"
    media_storage.simulate_uploaded_object("croviq-506602-croviq-media-raw", source_obj, 1000, "video/mp4", b"fake video")

    prod = Production(
        production_id="prod_no_edl",
        workspace_id="ws_1",
        channel_id="ch_1",
        owner_user_id=auth_user.user_id,
        status=ProductionStatus.PENDING,
        source_media=SourceMedia(
            upload_id="up_1",
            original_filename="video.mp4",
            content_type="video/mp4",
            size_bytes=1000,
            gcs_bucket="croviq-506602-croviq-media-raw",
            gcs_object=source_obj,
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    r = client.post("/api/productions/prod_no_edl/renders/preview")
    assert r.status_code == 400
    assert "no assembled EDL" in r.json()["detail"]


@pytest.mark.asyncio
async def test_render_preview_success_and_idempotency(test_setup, auth_user):
    prod_repo = test_setup["prod_repo"]
    edl_repo = test_setup["edl_repo"]
    render_repo = test_setup["render_repo"]
    media_storage = test_setup["media_storage"]
    render_service = test_setup["render_service"]
    genai_client = test_setup["genai_client"]
    client = test_setup["client"]

    now = datetime.now(timezone.utc)
    source_obj = "workspaces/ws_1/productions/prod_render/source/up_1/video.mp4"
    media_storage.simulate_uploaded_object("croviq-506602-croviq-media-raw", source_obj, 1000, "video/mp4", b"fake video")

    prod = Production(
        production_id="prod_render",
        workspace_id="ws_1",
        channel_id="ch_1",
        owner_user_id=auth_user.user_id,
        status=ProductionStatus.PENDING,
        source_media=SourceMedia(
            upload_id="up_1",
            original_filename="video.mp4",
            content_type="video/mp4",
            size_bytes=1000,
            gcs_bucket="croviq-506602-croviq-media-raw",
            gcs_object=source_obj,
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    edl = EditDecisionList(
        edl_id="edl_render_01",
        production_id="prod_render",
        source_duration_ms=113824,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    # 1. First POST /preview -> triggers render
    r1 = client.post("/api/productions/prod_render/renders/preview")
    assert r1.status_code == 200
    data1 = r1.json()

    assert data1["production_id"] == "prod_render"
    assert data1["edl_id"] == "edl_render_01"
    assert data1["artifact_type"] == "PREVIEW"
    assert data1["status"] == "completed"
    assert data1["duration_ms"] == 113824
    assert data1["video_codec"] == "h264"
    assert data1["audio_codec"] == "aac"
    assert data1["playback_url"] is not None
    assert render_service.preview_call_count == 1

    # Verify GCS render object was uploaded
    expected_gcs_obj = "workspaces/ws_1/productions/prod_render/renders/edl_render_01/preview.mp4"
    meta = await media_storage.get_object_metadata("croviq-506602-croviq-media-raw", expected_gcs_obj)
    assert meta.exists is True

    # Verify Firestore persistence
    saved_art = await render_repo.get_render_artifact("prod_render", data1["artifact_id"])
    assert saved_art is not None
    assert saved_art.status == ArtifactStatus.completed

    # 2. Second POST /preview -> IDEMPOTENCY: returns cached artifact, render service not invoked again
    r2 = client.post("/api/productions/prod_render/renders/preview")
    assert r2.status_code == 200
    data2 = r2.json()

    assert data2["artifact_id"] == data1["artifact_id"]
    assert data2["status"] == "completed"
    assert render_service.preview_call_count == 1  # Still 1, NOT incremented!

    # 3. Model call assertions: Gemini models MUST have 0 calls
    assert getattr(genai_client, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_render_master_and_list_renders(test_setup, auth_user):
    prod_repo = test_setup["prod_repo"]
    edl_repo = test_setup["edl_repo"]
    media_storage = test_setup["media_storage"]
    render_service = test_setup["render_service"]
    client = test_setup["client"]

    now = datetime.now(timezone.utc)
    source_obj = "workspaces/ws_1/productions/prod_both/source/up_1/video.mp4"
    media_storage.simulate_uploaded_object("croviq-506602-croviq-media-raw", source_obj, 1000, "video/mp4", b"fake video")

    prod = Production(
        production_id="prod_both",
        workspace_id="ws_1",
        channel_id="ch_1",
        owner_user_id=auth_user.user_id,
        status=ProductionStatus.PENDING,
        source_media=SourceMedia(
            upload_id="up_1",
            original_filename="video.mp4",
            content_type="video/mp4",
            size_bytes=1000,
            gcs_bucket="croviq-506602-croviq-media-raw",
            gcs_object=source_obj,
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)
    edl = EditDecisionList(
        edl_id="edl_both_01",
        production_id="prod_both",
        source_duration_ms=60000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    # 1. Render Preview
    r_prev = client.post("/api/productions/prod_both/renders/preview")
    assert r_prev.status_code == 200

    # 2. Render Master
    r_mast = client.post("/api/productions/prod_both/renders/master")
    assert r_mast.status_code == 200
    data_mast = r_mast.json()
    assert data_mast["artifact_type"] == "MASTER"
    assert data_mast["status"] == "completed"
    assert data_mast["width"] == 1920
    assert data_mast["height"] == 1080
    assert render_service.master_call_count == 1

    # 3. GET /renders list
    r_list = client.get("/api/productions/prod_both/renders")
    assert r_list.status_code == 200
    list_data = r_list.json()
    assert list_data["production_id"] == "prod_both"
    assert len(list_data["renders"]) == 2
    types = {r["artifact_type"] for r in list_data["renders"]}
    assert types == {"PREVIEW", "MASTER"}
    for item in list_data["renders"]:
        assert item["status"] == "completed"
        assert item["playback_url"] is not None
@pytest.mark.asyncio
async def test_get_default_render_repository_production_mode(monkeypatch):
    """Factory must instantiate FirestoreRenderRepository in production without AttributeError."""
    from croviq_api.productions.render_repository import (
        FirestoreRenderRepository,
        get_default_render_repository,
        set_render_repository,
    )
    from croviq_api.config import get_settings

    set_render_repository(None)
    monkeypatch.setenv("CROVIQ_ENV", "production")
    monkeypatch.setenv("GCP_PROJECT_ID", "croviq-506602")
    get_settings.cache_clear()

    try:
        repo = get_default_render_repository()
        assert isinstance(repo, FirestoreRenderRepository)
        assert repo._project_id == "croviq-506602"
    finally:
        set_render_repository(None)
        get_settings.cache_clear()


def test_render_artifact_deserialization_backward_compatibility():
    """Deserialization must tolerate lowercase enum variants, string timestamps, and extra fields."""
    from croviq_api.productions.render_repository import FirestoreRenderRepository
    from croviq_domain.render import ArtifactStatus, ArtifactType

    repo = FirestoreRenderRepository(project_id="test-proj")
    raw_data = {
        "artifact_id": "art_prev_001",
        "production_id": "prod_123",
        "edl_id": "edl_123",
        "artifact_type": "preview",  # lowercase legacy variant
        "status": "COMPLETED",  # uppercase legacy variant
        "gcs_bucket": "croviq-media-raw",
        "gcs_object": "workspaces/ws1/productions/prod_123/renders/edl_123/preview.mp4",
        "content_type": "video/mp4",
        "created_at": "2026-08-26T22:00:00Z",
        "completed_at": "2026-08-26T22:01:00+00:00",
        "extra_legacy_field": "ignore_me",
        "frame_rate": 30.0,
    }

    artifact = repo._deserialize_render_artifact(raw_data)
    assert artifact.artifact_id == "art_prev_001"
    assert artifact.artifact_type == ArtifactType.PREVIEW
    assert artifact.status == ArtifactStatus.completed
    assert artifact.created_at == datetime(2026, 8, 26, 22, 0, 0, tzinfo=timezone.utc)
    assert artifact.completed_at == datetime(2026, 8, 26, 22, 1, 0, tzinfo=timezone.utc)
    assert artifact.frame_rate == 30.0
