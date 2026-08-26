from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

from croviq_api.auth.dependencies import get_current_user
from croviq_api.auth.principal import AuthenticatedPrincipal
from croviq_api.config import Settings
from croviq_api.main import create_app
from croviq_api.media.dependencies import (
    get_fake_media_storage,
    set_media_inspector,
    set_transcription_service,
)
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    set_production_repository,
)
from croviq_api.productions.transcript_repository import (
    InMemoryTranscriptRepository,
    set_transcript_repository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    set_workspace_repository,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import (
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
)
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User
from croviq_media.inspector import FakeMediaInspector
from croviq_media.transcript import FakeTranscriptionService, TranscriptionError


@pytest.fixture
def test_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="test_user_001",
        email="demo@croviq.app",
        display_name="Demo Creator",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def other_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="other_user_999",
        email="other@croviq.app",
        display_name="Other User",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def app_and_deps(test_user: User):
    ws_repo = InMemoryWorkspaceRepository()
    prod_repo = InMemoryProductionRepository()
    transcript_repo = InMemoryTranscriptRepository()
    fake_storage = get_fake_media_storage()
    fake_storage.clear()
    fake_stt = FakeTranscriptionService()
    fake_inspector = FakeMediaInspector()

    set_workspace_repository(ws_repo)
    set_production_repository(prod_repo)
    set_transcript_repository(transcript_repo)
    set_transcription_service(fake_stt)
    set_media_inspector(fake_inspector)

    app = create_app()

    # Override auth dependency
    app.dependency_overrides[get_current_user] = lambda: test_user

    client = TestClient(app)
    return client, ws_repo, prod_repo, transcript_repo, fake_stt, fake_inspector


@pytest.mark.asyncio
async def test_transcribe_unauthenticated():
    app = create_app()
    client = TestClient(app)
    # No auth header / dependency override
    resp = client.post("/api/productions/prod_1/transcribe")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_transcribe_production_not_found(app_and_deps):
    client, _, _, _, _, _ = app_and_deps
    resp = client.post("/api/productions/prod_nonexistent/transcribe")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_transcribe_production_forbidden_wrong_owner(app_and_deps, other_user: User):
    client, _, prod_repo, _, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    # Production owned by other_user
    prod = Production(
        production_id="prod_other",
        workspace_id="ws_other",
        channel_id="channel_other",
        owner_user_id=other_user.user_id,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    resp = client.post(f"/api/productions/{prod.production_id}/transcribe")
    assert resp.status_code == 403
    assert "forbidden" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_transcribe_production_not_uploaded_state(app_and_deps, test_user: User):
    client, _, prod_repo, _, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id="prod_pending",
        workspace_id="ws_01",
        channel_id="channel_01",
        owner_user_id=test_user.user_id,
        status=ProductionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    resp = client.post(f"/api/productions/{prod.production_id}/transcribe")
    assert resp.status_code == 400
    assert "not uploaded" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_transcribe_production_success(app_and_deps, test_user: User):
    client, _, prod_repo, transcript_repo, fake_stt, _ = app_and_deps
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id="upl_01",
        original_filename="github_actions.mp4",
        content_type="video/mp4",
        size_bytes=52428800,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_01/source/upl_01/github_actions.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=now,
        uploaded_at=now,
    )
    prod = Production(
        production_id="prod_01",
        workspace_id="ws_01",
        channel_id="channel_01",
        owner_user_id=test_user.user_id,
        source_media=source_media,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    resp = client.post(f"/api/productions/{prod.production_id}/transcribe")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["production_id"] == "prod_01"
    assert data["word_count"] > 0
    assert data["duration_ms"] > 0
    assert "transcript" in data
    assert len(data["transcript"]["words"]) == data["word_count"]

    # Verify transcript is stored in repository
    saved = await transcript_repo.get_transcript_by_production_id("prod_01")
    assert saved is not None
    assert saved.transcript_id == data["transcript_id"]


@pytest.mark.asyncio
async def test_transcribe_production_idempotent(app_and_deps, test_user: User):
    client, _, prod_repo, transcript_repo, fake_stt, _ = app_and_deps
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id="upl_02",
        original_filename="demo.mp4",
        content_type="video/mp4",
        size_bytes=10485760,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_02/source/upl_02/demo.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=now,
        uploaded_at=now,
    )
    prod = Production(
        production_id="prod_02",
        workspace_id="ws_01",
        channel_id="channel_01",
        owner_user_id=test_user.user_id,
        source_media=source_media,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # First call
    resp1 = client.post(f"/api/productions/{prod.production_id}/transcribe")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "completed"
    t_id1 = data1["transcript_id"]

    # Second call (must be idempotent: no new transcript generated)
    resp2 = client.post(f"/api/productions/{prod.production_id}/transcribe")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "already_transcribed"
    assert data2["transcript_id"] == t_id1


@pytest.mark.asyncio
async def test_get_transcript_endpoints(app_and_deps, test_user: User):
    client, _, prod_repo, transcript_repo, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id="upl_03",
        original_filename="demo.mp4",
        content_type="video/mp4",
        size_bytes=10485760,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_03/source/upl_03/demo.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=now,
        uploaded_at=now,
    )
    prod = Production(
        production_id="prod_03",
        workspace_id="ws_01",
        channel_id="channel_01",
        owner_user_id=test_user.user_id,
        source_media=source_media,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # GET transcript before transcribe -> 404
    resp_get_before = client.get(f"/api/productions/{prod.production_id}/transcript")
    assert resp_get_before.status_code == 404

    # Transcribe
    resp_transcribe = client.post(f"/api/productions/{prod.production_id}/transcribe")
    assert resp_transcribe.status_code == 200

    # GET transcript after transcribe -> 200
    resp_get_after = client.get(f"/api/productions/{prod.production_id}/transcript")
    assert resp_get_after.status_code == 200
    t_data = resp_get_after.json()
    assert t_data["production_id"] == "prod_03"
    assert len(t_data["words"]) > 0


@pytest.mark.asyncio
async def test_get_source_analysis_input_endpoint(app_and_deps, test_user: User):
    client, _, prod_repo, transcript_repo, _, fake_inspector = app_and_deps
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id="upl_04",
        original_filename="github_actions_screen.mp4",
        content_type="video/mp4",
        size_bytes=20485760,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_04/source/upl_04/github_actions_screen.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=now,
        uploaded_at=now,
    )
    prod = Production(
        production_id="prod_04",
        workspace_id="ws_01",
        channel_id="channel_01",
        owner_user_id=test_user.user_id,
        source_media=source_media,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # GET before transcribe -> 400
    resp_before = client.get(f"/api/productions/{prod.production_id}/source-analysis-input")
    assert resp_before.status_code == 400

    # Transcribe
    client.post(f"/api/productions/{prod.production_id}/transcribe")

    # GET after transcribe -> 200
    resp_after = client.get(f"/api/productions/{prod.production_id}/source-analysis-input")
    assert resp_after.status_code == 200
    data = resp_after.json()
    assert data["production_id"] == "prod_04"
    assert data["channel_id"] == "channel_01"
    assert data["media_metadata"]["duration_ms"] > 0
    assert len(data["transcript"]["words"]) > 0
