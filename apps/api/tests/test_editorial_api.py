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
from croviq_api.media.dependencies import get_media_inspector
from croviq_api.memory.dependencies import get_memory_store, set_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.dependencies import get_genai_client, set_genai_client
from croviq_api.productions.editorial_repository import (
    EditorialRepository,
    InMemoryEditorialRepository,
    get_editorial_repository,
    set_editorial_repository,
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
    DirectorDecision,
    DirectorReview,
    DirectorVerdict,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorialRunStatus,
    ShortCandidate,
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
            duration_ms=4500,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            size_bytes=1048576,
        )


@pytest.fixture
def test_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="usr_test_owner",
        email="owner@croviq.app",
        display_name="Test Owner",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def other_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="usr_other_user",
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
    editorial_repo = InMemoryEditorialRepository()
    memory_store = FakeChannelMemoryStore()
    fake_inspector = FakeInspector()
    fake_genai = FakeGenAIClient()

    set_workspace_repository(ws_repo)
    set_production_repository(prod_repo)
    set_transcript_repository(transcript_repo)
    set_editorial_repository(editorial_repo)
    set_memory_store(memory_store)
    set_genai_client(fake_genai)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_editorial_repository] = lambda: editorial_repo
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    app.dependency_overrides[get_genai_client] = lambda: get_genai_client(get_settings())

    client = TestClient(app)
    return client, prod_repo, transcript_repo, editorial_repo, memory_store, fake_genai


def _make_uploaded_production(
    production_id: str,
    user_id: str,
    channel_id: str = "croviq_syn_ai_eng_01",
) -> Production:
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id=f"up_{production_id}",
        original_filename="sample_demo.mp4",
        content_type="video/mp4",
        size_bytes=2048000,
        gcs_bucket="croviq-media-raw",
        gcs_object=f"workspaces/ws_01/productions/{production_id}/source/up_{production_id}/sample_demo.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=now,
        uploaded_at=now,
    )
    return Production(
        production_id=production_id,
        workspace_id="ws_01",
        channel_id=channel_id,
        owner_user_id=user_id,
        status=ProductionStatus.PENDING,
        source_media=source_media,
        created_at=now,
        updated_at=now,
    )


def _make_transcript(production_id: str) -> Transcript:
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=0, end_ms=400),
        TranscriptWord(index=1, text="um", start_ms=410, end_ms=700),
        TranscriptWord(index=2, text="to", start_ms=710, end_ms=900),
        TranscriptWord(index=3, text="Croviq.", start_ms=910, end_ms=1300),
        TranscriptWord(index=4, text="GitHub", start_ms=1400, end_ms=1800),
        TranscriptWord(index=5, text="Actions", start_ms=1810, end_ms=2200),
        TranscriptWord(index=6, text="runs", start_ms=2210, end_ms=2500),
        TranscriptWord(index=7, text="the", start_ms=2510, end_ms=2700),
        TranscriptWord(index=8, text="workflow.", start_ms=2710, end_ms=3100),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_001",
            start_ms=0,
            end_ms=1300,
            text="Welcome um to Croviq.",
            word_start_index=0,
            word_end_index=3,
        ),
        TranscriptSegment(
            segment_id="seg_002",
            start_ms=1400,
            end_ms=3100,
            text="GitHub Actions runs the workflow.",
            word_start_index=4,
            word_end_index=8,
        ),
    ]
    return Transcript(
        transcript_id=f"tr_{production_id}",
        production_id=production_id,
        language_code="en-US",
        duration_ms=3100,
        words=words,
        segments=segments,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_analyze_unauthenticated():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/productions/prod_123/analyze")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analyze_production_not_found(app_and_deps):
    client, _, _, _, _, _ = app_and_deps
    resp = client.post("/api/productions/prod_nonexistent/analyze")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_analyze_production_forbidden_wrong_owner(app_and_deps, other_user: User):
    client, prod_repo, _, _, _, _ = app_and_deps
    prod = _make_uploaded_production("prod_other_owner", other_user.user_id)
    await prod_repo.create_production(prod)

    resp = client.post("/api/productions/prod_other_owner/analyze")
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_analyze_production_not_uploaded_state(app_and_deps, test_user: User):
    client, prod_repo, _, _, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    prod = Production(
        production_id="prod_pending_upload",
        workspace_id="ws_01",
        channel_id="chan_01",
        owner_user_id=test_user.user_id,
        status=ProductionStatus.PENDING,
        source_media=None,
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
    assert data["director_review_id"] is not None

    # Inspect persisted state via GET endpoint
    detail_resp = client.get(f"/api/productions/{prod_id}/editorial-run")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()

    assert detail_data["run"]["status"] == "completed"
    assert detail_data["proposal"] is not None
    assert detail_data["proposal"]["agent"] == "leo"
    assert len(detail_data["proposal"]["decisions"]) > 0
    assert detail_data["review"] is not None
    assert detail_data["review"]["agent"] == "maya"
    assert detail_data["review"]["approved_for_edl"] is True
    assert len(detail_data["activities"]) > 0


@pytest.mark.asyncio
async def test_analyze_production_with_director_rejections_and_modifications(
    app_and_deps, test_user: User
):
    client, prod_repo, transcript_repo, editorial_repo, _, _ = app_and_deps
    prod_id = "prod_modified_01"
    prod = _make_uploaded_production(prod_id, test_user.user_id)
    await prod_repo.create_production(prod)

    transcript = _make_transcript(prod_id)
    await transcript_repo.save_transcript(transcript)

    custom_proposal = EditorProposal(
        production_id=prod_id,
        agent="leo",
        model="fake-gemini-3.7-flash",
        summary="Leo proposed 2 cuts",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=1,
                transcript_end_word=1,
                source_start_ms=410,
                source_end_ms=700,
                original_text="um",
                action="remove",
                concise_reason="Remove filler",
                confidence=0.95,
            ),
            EditorDecision(
                decision_id="dec_02",
                decision_type=EditorDecisionType.TIGHTEN_EXPLANATION,
                transcript_start_word=4,
                transcript_end_word=8,
                source_start_ms=1400,
                source_end_ms=3100,
                original_text="GitHub Actions runs the workflow.",
                action="remove",
                concise_reason="Remove explanation",
                confidence=0.85,
            ),
        ],
        overall_confidence=0.9,
    )

    custom_review = DirectorReview(
        production_id=prod_id,
        agent="maya",
        model="fake-gemini-3.7-flash",
        overall_assessment="Approved filler cut, rejected command removal",
        decisions=[
            DirectorDecision(
                editor_decision_id="dec_01",
                verdict=DirectorVerdict.APPROVE,
                concise_reason="Clean filler cut",
            ),
            DirectorDecision(
                editor_decision_id="dec_02",
                verdict=DirectorVerdict.REJECT,
                concise_reason="Keep this sentence because it explains the command execution",
            ),
        ],
        editor_feedback="Do not remove key command explanations",
        approved_for_edl=True,
        confidence=0.95,
    )

    custom_genai = FakeGenAIClient(
        canned_proposal=custom_proposal,
        canned_review=custom_review,
    )
    set_genai_client(custom_genai)

    resp = client.post(f"/api/productions/{prod_id}/analyze")
    assert resp.status_code == 200

    detail_resp = client.get(f"/api/productions/{prod_id}/editorial-run")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()

    review_decisions = detail_data["review"]["decisions"]
    assert len(review_decisions) == 2
    assert review_decisions[0]["verdict"] == "APPROVE"
    assert review_decisions[1]["verdict"] == "REJECT"
    # Verify activities contain Maya's rejection message
    activities = detail_data["activities"]
    maya_reject_acts = [a for a in activities if a["related_decision_id"] == "dec_02" and a["agent"] == "Maya"]
    assert len(maya_reject_acts) == 1
    assert "REJECT" in maya_reject_acts[0]["message"]
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
