"""Integration tests for Agent Settings, Prompt Versioning, Voice Audition, and Studio Voice API endpoints."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from croviq_api.main import app
from croviq_api.auth.dependencies import get_current_user
from croviq_api.media.dependencies import get_media_storage, get_transcription_service
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.productions.dependencies import get_render_service
from croviq_api.productions.edl_repository import (
    InMemoryEDLRepository,
    get_edl_repository,
)
from croviq_api.productions.render_repository import (
    InMemoryRenderRepository,
    get_render_repository,
)
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    get_production_repository,
)
from croviq_api.productions.studio_voice_repository import (
    InMemoryStudioVoiceRepository,
    get_studio_voice_repository,
)
from croviq_api.productions.transcript_repository import (
    InMemoryTranscriptRepository,
    get_transcript_repository,
)
from croviq_api.workspaces.agent_config_repository import (
    InMemoryAgentConfigRepository,
    get_agent_config_repository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    get_workspace_repository,
)
from croviq_domain.agent_config import AgentId, NarrationMode
from croviq_domain.edl import EditDecisionList
from croviq_domain.narration import NarrationSegmentStatus
from croviq_domain.production import Production, ProductionStatus, SourceMedia, SourceMediaStatus
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User
from croviq_media.render import FakeRenderService
from croviq_domain.render import ArtifactType


@pytest.fixture
def api_test_context():
    test_user = User(
        user_id="user_sv_test",
        email="creator@croviq.app",
        display_name="Creator Test",
        avatar_url=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    ws_repo = InMemoryWorkspaceRepository()
    agent_config_repo = InMemoryAgentConfigRepository()
    prod_repo = InMemoryProductionRepository()
    transcript_repo = InMemoryTranscriptRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    sv_repo = InMemoryStudioVoiceRepository()
    fake_storage = FakeMediaStorage()
    fake_render = FakeRenderService()

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    app.dependency_overrides[get_agent_config_repository] = lambda: agent_config_repo
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_studio_voice_repository] = lambda: sv_repo
    app.dependency_overrides[get_media_storage] = lambda: fake_storage
    app.dependency_overrides[get_render_service] = lambda: fake_render

    client = TestClient(app)

    yield {
        "client": client,
        "user": test_user,
        "prod_repo": prod_repo,
        "transcript_repo": transcript_repo,
        "edl_repo": edl_repo,
        "sv_repo": sv_repo,
        "render_repo": render_repo,
    }

    app.dependency_overrides.clear()


def test_get_and_update_agent_settings(api_test_context):
    client = api_test_context["client"]

    # 1. Get initial agent settings
    resp = client.get("/api/workspace/agent-settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "leo_prompt" in data
    assert "maya_prompt" in data
    assert "voice_settings" in data
    assert "voices" in data
    assert len(data["voices"]) >= 4

    # 2. Update Leo prompt
    custom_prompt = "You are Leo. Keep cuts ultra tight."
    put_resp = client.put(
        "/api/workspace/agent-settings/prompts/leo",
        json={"prompt_text": custom_prompt},
    )
    assert put_resp.status_code == 200
    leo_data = put_resp.json()
    assert leo_data["prompt_text"] == custom_prompt
    assert leo_data["is_custom"] is True
    assert leo_data["version"] >= 1

    # 3. Reset Leo prompt
    reset_resp = client.post("/api/workspace/agent-settings/prompts/leo/reset")
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data["is_custom"] is False
    assert "Editorial Principles:" in reset_data["prompt_text"]


def test_agent_memory_read_only_endpoint(api_test_context):
    client = api_test_context["client"]
    resp = client.get("/api/workspace/agent-settings/memory")
    assert resp.status_code == 200
    data = resp.json()
    assert "channel_title" in data
    assert "style_guide" in data
    assert "creator_preferences" in data
    assert "lessons" in data


def test_voice_settings_and_sample_endpoint(api_test_context):
    client = api_test_context["client"]

    # Update voice settings
    put_resp = client.put(
        "/api/workspace/agent-settings/voice",
        json={
            "narration_mode": "studio_voice",
            "selected_voice": "en-US-Journey-D",
            "language": "en-US",
        },
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["selected_voice"] == "en-US-Journey-D"

    # Audition voice sample
    sample_resp = client.post(
        "/api/workspace/agent-settings/voice/sample",
        json={
            "voice_id": "en-US-Journey-D",
            "sample_text": "Welcome to Croviq. I'll make your video clear, concise, and easy to follow.",
        },
    )
    assert sample_resp.status_code == 200
    sample_data = sample_resp.json()
    assert sample_data["voice_id"] == "en-US-Journey-D"
    assert "audio_base64" in sample_data
    assert len(sample_data["audio_base64"]) > 0


@pytest.mark.asyncio
async def test_studio_voice_generation_endpoint(api_test_context):
    client = api_test_context["client"]
    prod_repo = api_test_context["prod_repo"]
    transcript_repo = api_test_context["transcript_repo"]
    edl_repo = api_test_context["edl_repo"]
    user = api_test_context["user"]

    prod_id = "prod_sv_demo_1"
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id=prod_id,
        owner_user_id=user.user_id,
        workspace_id="ws_user_sv_test",
        channel_id="croviq_syn_ai_eng_01",
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="up_sv_01",
            original_filename="demo.mp4",
            content_type="video/mp4",
            size_bytes=5000000,
            gcs_bucket="test-bucket",
            gcs_object="workspaces/ws_user_sv_test/productions/prod_sv_demo_1/source/demo.mp4",
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # Save transcript with 2 segments
    transcript = Transcript(
        transcript_id="tr_sv_01",
        production_id=prod_id,
        language_code="en",
        duration_ms=8000,
        words=[
            TranscriptWord(index=0, text="Hello", start_ms=0, end_ms=800, confidence=0.99),
            TranscriptWord(index=1, text="world", start_ms=900, end_ms=1800, confidence=0.99),
            TranscriptWord(index=2, text="here", start_ms=3000, end_ms=4500, confidence=0.99),
            TranscriptWord(index=3, text="we", start_ms=4600, end_ms=5500, confidence=0.99),
            TranscriptWord(index=4, text="go", start_ms=5600, end_ms=7500, confidence=0.99),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=0,
                end_ms=2000,
                text="Hello world",
                word_start_index=0,
                word_end_index=1,
            ),
            TranscriptSegment(
                segment_id="seg_02",
                start_ms=3000,
                end_ms=8000,
                text="Here we go install everything.",
                word_start_index=2,
                word_end_index=4,
            ),
        ],
        created_at=now,
    )
    await transcript_repo.save_transcript(transcript)

    edl = EditDecisionList(
        edl_id="edl_sv_demo",
        production_id=prod_id,
        source_duration_ms=8000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    # Trigger Studio Voice generation
    gen_resp = client.post(f"/api/productions/{prod_id}/studio-voice")
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["production_id"] == prod_id
    assert "result" in gen_data
    result = gen_data["result"]
    assert result["total_segments"] == 2
    assert result["accepted_segments"] == 2
    assert result["all_within_budget"] is True

    assert gen_data["studio_voice_preview_url"] is not None

    # Verify distinct RenderArtifact persistence
    render_repo = api_test_context["render_repo"]
    artifacts = await render_repo.list_render_artifacts(prod_id)
    sv_artifacts = [a for a in artifacts if a.artifact_type == ArtifactType.STUDIO_VOICE_PREVIEW]
    assert len(sv_artifacts) == 1
    assert "studio_voice_preview.mp4" in sv_artifacts[0].gcs_object

    # Retrieve Studio Voice result
    get_resp = client.get(f"/api/productions/{prod_id}/studio-voice")
    assert get_resp.status_code == 200
    assert get_resp.json()["total_segments"] == 2

    # Get playback URLs
    playback_resp = client.get(f"/api/productions/{prod_id}/playback")
    assert playback_resp.status_code == 200
    playback_data = playback_resp.json()
    assert playback_data["production_id"] == prod_id
    assert playback_data["playback_url"] is not None
    assert playback_data["studio_voice_preview_url"] is not None
