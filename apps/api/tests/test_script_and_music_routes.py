"""Integration tests for Corrected Script, Voiceover Preview, Final Mix, and Music API routes."""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.memory.dependencies import set_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.dependencies import set_genai_client, set_render_service
from croviq_api.productions.edl_repository import (
    InMemoryEDLRepository,
    set_edl_repository,
)
from croviq_api.productions.editorial_repository import (
    InMemoryEditorialRepository,
    set_editorial_repository,
)
from croviq_api.productions.render_repository import (
    InMemoryRenderRepository,
    set_render_repository,
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
from croviq_domain.edl import CutInstruction, CutSafetyStatus, EditDecisionList, VoiceoverSegment
from croviq_domain.editorial import EditorDecisionType
from croviq_domain.production import (
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
)
from croviq_domain.render import ArtifactType
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User
from croviq_media.render import FakeRenderService


@pytest.fixture
def test_user() -> User:
    return User(
        user_id="usr_test_123",
        email="creator@example.com",
        display_name="Test Creator",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
    app.dependency_overrides[get_media_storage] = lambda: media_storage

    client = TestClient(app)
    return client, prod_repo, transcript_repo, edl_repo, render_repo, fake_genai, media_storage


@pytest.mark.asyncio
async def test_get_corrected_script_route(app_and_deps, test_user: User):
    client, prod_repo, trans_repo, edl_repo, _, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id="prod_script_01",
        workspace_id="ws_test",
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=test_user.user_id,
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="up_01",
            original_filename="tutorial.mp4",
            content_type="video/mp4",
            size_bytes=1000000,
            gcs_bucket="test-bucket",
            gcs_object="workspaces/ws_test/productions/prod_script_01/source.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    t = Transcript(
        transcript_id="tr_01",
        production_id="prod_script_01",
        language_code="en-US",
        duration_ms=8000,
        words=[
            TranscriptWord(index=0, text="So", start_ms=0, end_ms=500),
            TranscriptWord(index=1, text="uh", start_ms=500, end_ms=1000),
            TranscriptWord(index=2, text="we", start_ms=1000, end_ms=1500),
            TranscriptWord(index=3, text="is", start_ms=1500, end_ms=2000),
            TranscriptWord(index=4, text="going", start_ms=2000, end_ms=2500),
            TranscriptWord(index=5, text="to", start_ms=2500, end_ms=3000),
            TranscriptWord(index=6, text="deploy.", start_ms=3000, end_ms=3500),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=0,
                end_ms=3500,
                text="So uh we is going to deploy.",
                word_start_index=0,
                word_end_index=6,
            )
        ],
        created_at=now,
    )
    await trans_repo.save_transcript(t)

    edl = EditDecisionList(
        edl_id="edl_01",
        production_id="prod_script_01",
        source_duration_ms=8000,
        version=1,
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    response = client.get("/api/productions/prod_script_01/corrected-script")
    assert response.status_code == 200
    data = response.json()
    assert data["production_id"] == "prod_script_01"
    assert "corrected_transcript" in data
    assert len(data["corrected_transcript"]["segments"]) >= 1
    assert data["meaning_preserved"] is True


@pytest.mark.asyncio
async def test_generate_and_update_music_routes(app_and_deps, test_user: User):
    client, prod_repo, _, edl_repo, _, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id="prod_music_01",
        workspace_id="ws_test",
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=test_user.user_id,
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="up_01",
            original_filename="tutorial.mp4",
            content_type="video/mp4",
            size_bytes=1000000,
            gcs_bucket="test-bucket",
            gcs_object="workspaces/ws_test/productions/prod_music_01/source.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    edl = EditDecisionList(
        edl_id="edl_01",
        production_id="prod_music_01",
        source_duration_ms=10000,
        version=1,
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    # 1. Generate music
    gen_resp = client.post(
        "/api/productions/prod_music_01/music/generate",
        json={"model_id": "lyria-3-pro-preview", "volume_db": -24.0, "ducking_db": -14.0},
    )
    assert gen_resp.status_code == 200
    edl_data = gen_resp.json()
    assert edl_data["edl"]["background_music"] is not None
    assert edl_data["edl"]["background_music"]["model_id"] == "lyria-3-pro-preview"

    # 2. Update music (lower by 4 dB)
    patch_resp = client.patch(
        "/api/productions/prod_music_01/music",
        json={"volume_db": -28.0},
    )
    assert patch_resp.status_code == 200
    patched_edl = patch_resp.json()
    assert patched_edl["edl"]["background_music"]["volume_db"] == -28.0


@pytest.mark.asyncio
async def test_render_final_mix_and_voiceover_preview_uses_active_edl_cuts_and_timeline_mapping(
    app_and_deps, test_user: User
):
    client, prod_repo, trans_repo, edl_repo, render_repo, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id="prod_render_cut_01",
        workspace_id="ws_test",
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=test_user.user_id,
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="up_01",
            original_filename="tutorial.mp4",
            content_type="video/mp4",
            size_bytes=1000000,
            gcs_bucket="test-bucket",
            gcs_object="workspaces/ws_test/productions/prod_render_cut_01/source.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # Create EDL with a 4-second cut: 10000ms source -> 6000ms target
    cut = CutInstruction(
        cut_id="cut_01",
        decision_id="dec_01",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=1,
        transcript_end_word=2,
        requested_start_ms=2000,
        requested_end_ms=6000,
        safe_start_ms=2000,
        safe_end_ms=6000,
        removed_duration_ms=4000,
        left_anchor="left",
        right_anchor="right",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="clean cut",
        confidence=0.99,
    )
    vo = VoiceoverSegment(
        segment_id="vo_01",
        source_start_ms=7000,
        source_end_ms=9000,
        text="Corrected voiceover replacement",
        original_text="Original voiceover",
    )
    edl = EditDecisionList(
        edl_id="edl_cuts_01",
        production_id="prod_render_cut_01",
        source_duration_ms=10000,
        cuts=[cut],
        voiceover_segments=[vo],
        version=1,
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    # 1. Render Voiceover Preview - must have duration = 6000ms (preserving EDL cuts)
    vo_resp = client.post("/api/productions/prod_render_cut_01/renders/voiceover-preview")
    assert vo_resp.status_code == 200
    vo_data = vo_resp.json()
    assert vo_data["artifact_type"] == "VOICEOVER_PREVIEW"
    assert vo_data["duration_ms"] == 6000

    # 2. Render Final Mix - must have duration = 6000ms (preserving EDL cuts)
    fm_resp = client.post("/api/productions/prod_render_cut_01/renders/final-mix")
    assert fm_resp.status_code == 200
    fm_data = fm_resp.json()
    assert fm_data["artifact_type"] == "FINAL_MIX"
    assert fm_data["duration_ms"] == 6000
