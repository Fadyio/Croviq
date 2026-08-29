from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pytest
from starlette.testclient import TestClient

from croviq_api.config import get_settings
from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.main import create_app
from croviq_media.inspector import MediaInspector
from croviq_api.media.dependencies import get_media_inspector, get_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.memory.dependencies import get_memory_store, set_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.dependencies import get_genai_client, set_genai_client, set_render_service
from croviq_media.render import FakeRenderService
from croviq_api.productions.edl_repository import (
    EDLRepository,
    InMemoryEDLRepository,
    get_edl_repository,
    set_edl_repository,
)
from croviq_api.productions.editorial_repository import (
    EditorialRepository,
    InMemoryEditorialRepository,
    get_editorial_repository,
    set_editorial_repository,
)
from croviq_api.productions.render_repository import (
    InMemoryRenderRepository,
    RenderRepository,
    get_render_repository,
    set_render_repository,
)
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    ProductionRepository,
    get_production_repository,
    set_production_repository,
)
from croviq_api.productions.transcript_repository import (
    InMemoryTranscriptRepository,
    TranscriptRepository,
    get_transcript_repository,
    set_transcript_repository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    WorkspaceRepository,
    get_workspace_repository,
    set_workspace_repository,
)
from croviq_domain.editorial import (
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorialRunStatus,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.memory import ChannelMemoryProfile
from croviq_domain.production import (
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
)
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User


class FakeInspector(MediaInspector):
    def inspect_media(self, file_path: Path | str) -> MediaMetadata:
        return MediaMetadata(
            duration_ms=60000,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            size_bytes=10000000,
        )


@pytest.fixture
def test_user() -> User:
    return User(
        user_id="usr_test_123",
        email="creator@example.com",
        display_name="Test Creator",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_uploaded_production(prod_id: str, user_id: str, ws_id: str = "ws_test") -> Production:
    now = datetime.now(timezone.utc)
    return Production(
        production_id=prod_id,
        workspace_id=ws_id,
        owner_user_id=user_id,
        channel_id="ch_test",
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="up_01",
            gcs_bucket="test-bucket",
            gcs_object=f"workspaces/{ws_id}/productions/{prod_id}/source.mp4",
            original_filename="source.mp4",
            content_type="video/mp4",
            size_bytes=10000000,
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )


def _make_transcript(prod_id: str) -> Transcript:
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="Hello", start_ms=0, end_ms=400, confidence=0.99),
        TranscriptWord(index=1, text="um", start_ms=410, end_ms=700, confidence=0.95),
        TranscriptWord(index=2, text="world", start_ms=710, end_ms=1000, confidence=0.99),
        TranscriptWord(index=3, text="today", start_ms=1010, end_ms=1300, confidence=0.99),
    ]
    return Transcript(
        transcript_id=f"tr_{prod_id}",
        production_id=prod_id,
        language_code="en",
        duration_ms=60000,
        words=words,
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                text="Hello um world today",
                start_ms=0,
                end_ms=1300,
                word_start_index=0,
                word_end_index=3,
            )
        ],
        created_at=now,
    )


@pytest.fixture
def app_and_deps(test_user: User):
    prod_repo = InMemoryProductionRepository()
    ws_repo = InMemoryWorkspaceRepository()
    transcript_repo = InMemoryTranscriptRepository()
    editorial_repo = InMemoryEditorialRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    memory_store = FakeChannelMemoryStore()
    fake_genai = FakeGenAIClient()
    media_storage = FakeMediaStorage()
    fake_render_service = FakeRenderService()

    ws_repo.workspaces["ws_test"] = {
        "workspace_id": "ws_test",
        "owner_user_id": test_user.user_id,
        "name": "Test Workspace",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    ws_repo.users[test_user.user_id] = {
        "user_id": test_user.user_id,
        "email": str(test_user.email),
        "display_name": test_user.display_name,
        "created_at": test_user.created_at.isoformat(),
        "updated_at": test_user.updated_at.isoformat(),
    }

    set_production_repository(prod_repo)
    set_workspace_repository(ws_repo)
    set_transcript_repository(transcript_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)
    set_render_repository(render_repo)
    set_memory_store(memory_store)
    set_genai_client(fake_genai)
    set_render_service(fake_render_service)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_media_inspector] = lambda: FakeInspector()
    app.dependency_overrides[get_media_storage] = lambda: media_storage

    client = TestClient(app)
    return client, prod_repo, transcript_repo, editorial_repo, memory_store, fake_genai


@pytest.mark.asyncio
async def test_analyze_production_not_uploaded_state(app_and_deps, test_user: User):
    client, prod_repo, _, _, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id="prod_pending_upload",
        workspace_id="ws_test",
        owner_user_id=test_user.user_id,
        channel_id="ch_test",
        status=ProductionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    resp = client.post("/api/productions/prod_pending_upload/analyze")
    assert resp.status_code == 400
    assert "not uploaded" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_analyze_production_missing_transcript_prerequisite(app_and_deps, test_user: User):
    client, prod_repo, _, _, _, _ = app_and_deps
    prod = _make_uploaded_production("prod_no_transcript", test_user.user_id)
    await prod_repo.create_production(prod)

    resp = client.post("/api/productions/prod_no_transcript/analyze")
    assert resp.status_code == 400
    assert "must be transcribed before" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_analyze_production_success(app_and_deps, test_user: User):
    client, prod_repo, transcript_repo, editorial_repo, memory_store, fake_genai = app_and_deps
    prod_id = "prod_success_01"
    prod = _make_uploaded_production(prod_id, test_user.user_id)
    await prod_repo.create_production(prod)

    transcript = _make_transcript(prod_id)
    await transcript_repo.save_transcript(transcript)

    resp = client.post(f"/api/productions/{prod_id}/analyze")
    assert resp.status_code == 200
    data = resp.json()
    assert data["production_id"] == prod_id
    assert data["status"] == "completed"
    assert data["editor_proposal_id"] is not None

    # Inspect persisted state via GET endpoint
    detail_resp = client.get(f"/api/productions/{prod_id}/editorial-run")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()

    assert detail_data["run"]["status"] == "completed"
    assert detail_data["proposal"] is not None
    assert detail_data["proposal"]["agent"] == "leo"
    assert len(detail_data["proposal"]["decisions"]) > 0
    assert len(detail_data["activities"]) > 0


@pytest.mark.asyncio
async def test_analyze_completed_run_is_idempotent(app_and_deps, test_user: User):
    client, prod_repo, transcript_repo, _, _, fake_genai = app_and_deps
    prod_id = "prod_completed_idempotent"
    await prod_repo.create_production(_make_uploaded_production(prod_id, test_user.user_id))
    await transcript_repo.save_transcript(_make_transcript(prod_id))

    first_response = client.post(f"/api/productions/{prod_id}/analyze")
    assert first_response.status_code == 200
    first_run_id = first_response.json()["run_id"]
    fake_genai.call_history.clear()

    second_response = client.post(f"/api/productions/{prod_id}/analyze")

    assert second_response.status_code == 200
    assert second_response.json()["run_id"] == first_run_id
    assert fake_genai.call_history == []


@pytest.mark.asyncio
async def test_analyze_production_model_failure_maps_to_failed_run(app_and_deps, test_user: User):
    client, prod_repo, transcript_repo, editorial_repo, _, _ = app_and_deps
    prod_id = "prod_fail_01"
    prod = _make_uploaded_production(prod_id, test_user.user_id)
    await prod_repo.create_production(prod)

    transcript = _make_transcript(prod_id)
    await transcript_repo.save_transcript(transcript)

    failing_genai = FakeGenAIClient(fail_on_editor=True)
    set_genai_client(failing_genai)

    resp = client.post(f"/api/productions/{prod_id}/analyze")
    assert resp.status_code == 500

    run = await editorial_repo.get_latest_editorial_run(prod_id)
    assert run is not None
    assert run.status == EditorialRunStatus.FAILED
    assert run.failure_code == "SIMULATED_EDITOR_FAILURE"

def test_firestore_editorial_repository_init_with_project_id():
    from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
    repo = FirestoreEditorialRepository(project_id="croviq-506602")
    assert repo._project_id == "croviq-506602"
    assert repo._database == "(default)"
