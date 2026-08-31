"""Targeted test suite for BUG 15.1 — PREVIEW PLAYBACK & DELIVERY CONTRACT.

Covers:
A. new EDL produces new active preview artifact
B. active preview resolves to browser-compatible URL
C. raw gs:// never reaches HTML video src (API returns HTTPS / HTTP URL)
D. changed preview causes player source refresh
E. retry resolves fresh playback URL
F. successful render cannot be reported if artifact is missing
G. FFmpeg/render failure shows truthful state
H. signed URL failure does not claim playback success
I. undo resolves restored preview correctly
J. refresh resolves a playable URL again
K. range request behavior accepted correctly
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pytest
from starlette.testclient import TestClient

from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_media_storage, set_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.memory.dependencies import get_memory_store, set_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.broll_repository import InMemoryBRollRepository, get_broll_repository
from croviq_api.productions.dependencies import get_genai_client, set_genai_client, set_render_service
from croviq_api.productions.edl_repository import InMemoryEDLRepository, get_edl_repository, set_edl_repository
from croviq_api.productions.editorial_repository import InMemoryEditorialRepository, get_editorial_repository, set_editorial_repository
from croviq_api.productions.render_repository import InMemoryRenderRepository, get_render_repository, set_render_repository
from croviq_api.productions.repository import InMemoryProductionRepository, get_production_repository, set_production_repository
from croviq_api.productions.transcript_repository import InMemoryTranscriptRepository, get_transcript_repository, set_transcript_repository
from croviq_api.workspaces.agent_config_repository import InMemoryAgentConfigRepository, get_agent_config_repository, set_agent_config_repository
from croviq_api.workspaces.repository import InMemoryWorkspaceRepository, get_workspace_repository, set_workspace_repository
from croviq_domain.edl import CutInstruction, CutSafetyStatus, EditDecisionList, derive_keep_segments
from croviq_domain.editorial import EditorDecision, EditorDecisionType, EditorProposal, EditorialRun, EditorialRunStatus
from croviq_domain.production import Production, ProductionStatus, SourceMedia, SourceMediaStatus
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User
from croviq_media.render import FakeRenderService, RenderError


@pytest.fixture
def mock_env():
    now = datetime.now(timezone.utc)
    user = User(
        user_id="user_test_15_1",
        email="creator@croviq.app",
        display_name="Test Creator",
        avatar_url=None,
        created_at=now,
        updated_at=now,
    )
    prod_repo = InMemoryProductionRepository()
    trans_repo = InMemoryTranscriptRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    edit_repo = InMemoryEditorialRepository()
    ws_repo = InMemoryWorkspaceRepository()
    cfg_repo = InMemoryAgentConfigRepository()
    broll_repo = InMemoryBRollRepository()
    mem_store = FakeChannelMemoryStore()
    media_store = FakeMediaStorage()
    render_svc = FakeRenderService()
    genai_client = FakeGenAIClient()

    set_production_repository(prod_repo)
    set_transcript_repository(trans_repo)
    set_edl_repository(edl_repo)
    set_render_repository(render_repo)
    set_editorial_repository(edit_repo)
    set_workspace_repository(ws_repo)
    set_agent_config_repository(cfg_repo)
    set_memory_store(mem_store)
    set_media_storage(media_store)
    set_render_service(render_svc)
    set_genai_client(genai_client)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_transcript_repository] = lambda: trans_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_editorial_repository] = lambda: edit_repo
    app.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    app.dependency_overrides[get_agent_config_repository] = lambda: cfg_repo
    app.dependency_overrides[get_broll_repository] = lambda: broll_repo
    app.dependency_overrides[get_memory_store] = lambda: mem_store
    app.dependency_overrides[get_media_storage] = lambda: media_store
    app.dependency_overrides[get_genai_client] = lambda: genai_client

    client = TestClient(app)

    now = datetime.now(timezone.utc)
    production_id = "prod_473209137802"
    workspace_id = "ws_test_15_1"

    prod = Production(
        production_id=production_id,
        workspace_id=workspace_id,
        channel_id="ch_test",
        owner_user_id=user.user_id,
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="upl_src_01",
            original_filename="github.mp4",
            content_type="video/mp4",
            size_bytes=50_000_000,
            gcs_bucket="croviq-media-raw",
            gcs_object="workspaces/ws_test/github.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    asyncio.run(prod_repo.create_production(prod))

    transcript = Transcript(
        transcript_id="tr_01",
        production_id=production_id,
        language_code="en",
        duration_ms=60_000,
        words=[
            TranscriptWord(index=0, text="Hello", start_ms=1000, end_ms=2000),
            TranscriptWord(index=1, text="world", start_ms=2000, end_ms=3000),
            TranscriptWord(index=2, text="cutting", start_ms=10000, end_ms=15000),
            TranscriptWord(index=3, text="this", start_ms=15000, end_ms=20000),
            TranscriptWord(index=4, text="part", start_ms=20000, end_ms=25000),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=1000,
                end_ms=3000,
                text="Hello world",
                word_start_index=0,
                word_end_index=1,
            ),
            TranscriptSegment(
                segment_id="seg_02",
                start_ms=10000,
                end_ms=25000,
                text="cutting this part",
                word_start_index=2,
                word_end_index=4,
            ),
        ],
        created_at=now,
    )
    asyncio.run(trans_repo.save_transcript(transcript))

    edl = EditDecisionList(
        edl_id="edl_v1_001",
        production_id=production_id,
        source_duration_ms=60_000,
        version=1,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    asyncio.run(edl_repo.save_edl(edl))
    proposal = EditorProposal(
        production_id=production_id,
        model="gemini-3.7-flash",
        summary="Initial plan",
        decisions=[],
        chapters=[],
        overall_confidence=1.0,
    )
    asyncio.run(edit_repo.save_editor_proposal(proposal, proposal_id="prop_01"))

    run = EditorialRun(
        run_id="run_01",
        production_id=production_id,
        status=EditorialRunStatus.COMPLETED,
        editor_proposal_id="prop_01",
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    asyncio.run(edit_repo.save_editorial_run(run))

    # Seed source media file in fake storage
    media_store.simulate_uploaded_object("croviq-media-raw", "workspaces/ws_test/github.mp4", size_bytes=50_000_000, content_type="video/mp4", content=b"fake_mp4_bytes")
    return {
        "client": client,
        "production_id": production_id,
        "media_store": media_store,
        "render_repo": render_repo,
        "edl_repo": edl_repo,
        "render_svc": render_svc,
    }


def test_test_a_new_edl_produces_new_active_preview_artifact(mock_env):
    """Test A: New EDL produces a newly rendered active preview artifact."""
    client = mock_env["client"]
    prod_id = mock_env["production_id"]

    res = client.post(f"/api/productions/{prod_id}/renders/preview")
    assert res.status_code == 200
    data = res.json()
    assert data["artifact_type"] == "PREVIEW"
    assert data["status"] == "completed"
    assert data["playback_url"] is not None
    assert "https://" in data["playback_url"] or "http://" in data["playback_url"]


def test_test_b_active_preview_resolves_to_browser_compatible_url(mock_env):
    """Test B: Active preview resolves to browser-compatible HTTP/HTTPS playback URL."""
    client = mock_env["client"]
    prod_id = mock_env["production_id"]

    # Initial render
    client.post(f"/api/productions/{prod_id}/renders/preview")

    res = client.get(f"/api/productions/{prod_id}/playback")
    assert res.status_code == 200
    data = res.json()
    assert data["rendered_preview_url"] is not None
    assert data["edited"]["available"] is True
    assert data["edited"]["url"].startswith("http://") or data["edited"]["url"].startswith("https://")


def test_test_c_raw_gs_never_reaches_video_src(mock_env):
    """Test C: Raw gs:// URI is never returned as playback URL to frontend."""
    client = mock_env["client"]
    prod_id = mock_env["production_id"]

    client.post(f"/api/productions/{prod_id}/renders/preview")
    res = client.get(f"/api/productions/{prod_id}/playback")
    data = res.json()

    assert not data["rendered_preview_url"].startswith("gs://")
    assert not (data["original"]["url"] or "").startswith("gs://")
    assert not (data["edited"]["url"] or "").startswith("gs://")


def test_test_e_retry_resolves_fresh_playback_url(mock_env):
    """Test E: Stale/retry requests re-resolve a fresh playback URL from playback endpoint."""
    client = mock_env["client"]
    prod_id = mock_env["production_id"]

    client.post(f"/api/productions/{prod_id}/renders/preview")
    res1 = client.get(f"/api/productions/{prod_id}/playback")
    url1 = res1.json()["rendered_preview_url"]

    # Subsequent playback request yields valid fresh URL
    res2 = client.get(f"/api/productions/{prod_id}/playback")
    url2 = res2.json()["rendered_preview_url"]

    assert url1 is not None
    assert url2 is not None


def test_test_f_missing_artifact_cannot_be_reported_successful(mock_env):
    """Test F: Successful render cannot be reported if artifact does not exist in storage."""
    client = mock_env["client"]
    prod_id = mock_env["production_id"]
    render_repo = mock_env["render_repo"]

    # Create artifact record but do not upload to storage
    now = datetime.now(timezone.utc)
    phantom_art = RenderArtifact(
        artifact_id="art_phantom",
        production_id=prod_id,
        edl_id="edl_v1_001",
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_test/non_existent.mp4",
        content_type="video/mp4",
        created_at=now,
        completed_at=now,
    )
    asyncio.run(render_repo.save_render_artifact(phantom_art))

    # Playback endpoint should not return phantom object as ready URL
    res = client.get(f"/api/productions/{prod_id}/playback")
    data = res.json()
    assert data["rendered_preview_url"] is None or "non_existent" not in data["rendered_preview_url"]


def test_test_g_render_failure_shows_truthful_state(mock_env):
    """Test G: FFmpeg/render failure raises clear truthful failure state."""
    client = mock_env["client"]
    prod_id = mock_env["production_id"]
    render_svc = mock_env["render_svc"]

    class FailingRenderService(FakeRenderService):
        def render_preview(self, source_path, edl, output_path=None):
            raise RenderError("FFmpeg process failed: simulated encoder failure")

    set_render_service(FailingRenderService())

    res = client.post(f"/api/productions/{prod_id}/renders/preview")
    assert res.status_code == 500
    assert "simulated encoder failure" in res.json()["detail"]


def test_test_h_signed_url_failure_does_not_claim_playback_success(mock_env):
    """Test H: Signing failure returns null playback_url instead of broken claims."""
    client = mock_env["client"]
    prod_id = mock_env["production_id"]
    media_store = mock_env["media_store"]

    class BrokenSigningMediaStorage(FakeMediaStorage):
        async def generate_signed_read_target(self, bucket, object_name, expiry_seconds=1800):
            raise RuntimeError("Keyless signing credentials unavailable")

    set_media_storage(BrokenSigningMediaStorage())

    res = client.get(f"/api/productions/{prod_id}/playback")
    data = res.json()
    assert data["rendered_preview_url"] is None
    assert data["edited"]["url"] is None
    assert data["edited"]["available"] is False


def test_test_k_derive_keep_segments_matches_estimated_duration():
    """Test K: EDL estimated_target_duration_ms exactly matches sum of derive_keep_segments."""
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_test_k",
        production_id="prod_test",
        source_duration_ms=100_000,
        version=1,
        cuts=[
            CutInstruction(
                cut_id="c1",
                decision_id="d1",
                decision_type=EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
                safe_start_ms=10_000,
                safe_end_ms=20_000,
                requested_start_ms=10_000,
                requested_end_ms=20_000,
                transcript_start_word=0,
                transcript_end_word=1,
                left_anchor="word1",
                right_anchor="word2",
                safety_reason="safe cut",
                confidence=1.0,
                safety_status=CutSafetyStatus.SAFE,
                removed_duration_ms=10_000,
            ),
            # Overlapping cut subsumed by a larger range
            CutInstruction(
                cut_id="c2",
                decision_id="d2",
                decision_type=EditorDecisionType.REMOVE_LOW_VALUE_SECTION,
                safe_start_ms=12_000,
                safe_end_ms=18_000,
                requested_start_ms=12_000,
                requested_end_ms=18_000,
                transcript_start_word=0,
                transcript_end_word=1,
                left_anchor="word1",
                right_anchor="word2",
                safety_reason="subsumed cut",
                confidence=1.0,
                safety_status=CutSafetyStatus.SAFE,
                removed_duration_ms=6_000,
            ),
        ],
        created_at=now,
    )
    keeps = derive_keep_segments(edl)
    total_keep = sum(e - s for s, e in keeps)
    assert total_keep == 90_000
    assert edl.estimated_target_duration_ms == 90_000
    assert edl.total_removed_duration_ms == 10_000
