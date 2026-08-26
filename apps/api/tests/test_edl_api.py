"""API integration tests for EDL assembly and retrieval endpoints."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_media_inspector
from croviq_api.memory.dependencies import get_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.dependencies import get_genai_client
from croviq_api.productions.edl_repository import (
    InMemoryEDLRepository,
    get_edl_repository,
    set_edl_repository,
)
from croviq_api.productions.editorial_repository import (
    InMemoryEditorialRepository,
    get_editorial_repository,
    set_editorial_repository,
)
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    get_production_repository,
    set_production_repository,
)
from croviq_api.productions.transcript_repository import (
    InMemoryTranscriptRepository,
    get_transcript_repository,
    set_transcript_repository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
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
    EditorialRun,
    EditorialRunStatus,
)
from croviq_domain.edl import CoverageType, CutSafetyStatus
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import Production, ProductionStatus, SourceMedia, SourceMediaStatus
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User
from croviq_media.inspector import MediaInspector


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
            size_bytes=15_000_000,
        )


@pytest.fixture
def test_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="usr_test_edl_01",
        email="creator@croviq.app",
        display_name="Test Creator",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def other_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="usr_other_edl_02",
        email="intruder@other.app",
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
    edl_repo = InMemoryEDLRepository()
    memory_store = FakeChannelMemoryStore()
    fake_genai = FakeGenAIClient()
    fake_inspector = FakeInspector()

    set_workspace_repository(ws_repo)
    set_production_repository(prod_repo)
    set_transcript_repository(transcript_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)

    app = create_app()
    app.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_editorial_repository] = lambda: editorial_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    app.dependency_overrides[get_genai_client] = lambda: fake_genai
    app.dependency_overrides[get_media_inspector] = lambda: fake_inspector
    app.dependency_overrides[get_current_user] = lambda: test_user

    client = TestClient(app)
    return client, prod_repo, transcript_repo, editorial_repo, edl_repo, fake_genai


def _make_uploaded_production(
    production_id: str = "prod_edl_test_01",
    owner_user_id: str = "usr_test_edl_01",
    workspace_id: str = "ws_test_01",
    channel_id: str = "croviq_syn_ai_eng_01",
) -> Production:
    now = datetime.now(timezone.utc)
    source_media = SourceMedia(
        upload_id=f"up_{production_id}",
        original_filename="tutorial_recording.mp4",
        content_type="video/mp4",
        size_bytes=15_000_000,
        gcs_bucket="croviq-media-raw",
        gcs_object=f"workspaces/{workspace_id}/productions/{production_id}/source/up_{production_id}/tutorial_recording.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=now,
        uploaded_at=now,
    )
    return Production(
        production_id=production_id,
        workspace_id=workspace_id,
        channel_id=channel_id,
        owner_user_id=owner_user_id,
        status=ProductionStatus.PENDING,
        source_media=source_media,
        created_at=now,
        updated_at=now,
    )

def _make_transcript(production_id: str) -> Transcript:
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=100, end_ms=500),
        TranscriptWord(index=1, text="to", start_ms=520, end_ms=700),
        TranscriptWord(index=2, text="um", start_ms=900, end_ms=1200),  # Filler
        TranscriptWord(index=3, text="this", start_ms=1400, end_ms=1600),
        TranscriptWord(index=4, text="tutorial", start_ms=1620, end_ms=2200),
    ]
    return Transcript(
        transcript_id=f"tr_{production_id}",
        production_id=production_id,
        language_code="en",
        duration_ms=60000,
        words=words,
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                text="Welcome to um this tutorial",
                start_ms=100,
                end_ms=2200,
                word_start_index=0,
                word_end_index=4,
            )
        ],
        created_at=now,
    )


@pytest.mark.asyncio
async def test_assemble_edl_unauthenticated():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/productions/prod_edl_test_01/edl")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_assemble_edl_production_not_found(app_and_deps):
    client, _, _, _, _, _ = app_and_deps
    resp = client.post("/api/productions/prod_nonexistent/edl")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assemble_edl_forbidden_wrong_workspace(app_and_deps, other_user: User):
    client, prod_repo, _, _, _, _ = app_and_deps
    prod = _make_uploaded_production(owner_user_id=other_user.user_id)
    await prod_repo.create_production(prod)

    resp = client.post(f"/api/productions/{prod.production_id}/edl")
    assert resp.status_code == 403
    assert "forbidden" in resp.json()["detail"].lower() or "do not own" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assemble_edl_missing_transcript_prerequisite(app_and_deps):
    client, prod_repo, _, _, _, _ = app_and_deps
    prod = _make_uploaded_production()
    await prod_repo.create_production(prod)

    resp = client.post(f"/api/productions/{prod.production_id}/edl")
    assert resp.status_code == 400
    assert "must be transcribed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assemble_edl_missing_editorial_run_prerequisite(app_and_deps):
    client, prod_repo, transcript_repo, _, _, _ = app_and_deps
    prod = _make_uploaded_production()
    await prod_repo.create_production(prod)

    transcript = _make_transcript(prod.production_id)
    await transcript_repo.save_transcript(transcript)

    resp = client.post(f"/api/productions/{prod.production_id}/edl")
    assert resp.status_code == 400
    assert "editorial analysis must be run" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assemble_edl_editorial_run_not_approved_for_edl(app_and_deps):
    client, prod_repo, transcript_repo, editorial_repo, _, _ = app_and_deps
    now = datetime.now(timezone.utc)
    prod = _make_uploaded_production()
    await prod_repo.create_production(prod)

    transcript = _make_transcript(prod.production_id)
    await transcript_repo.save_transcript(transcript)

    proposal = EditorProposal(
        production_id=prod.production_id,
        model="gemini-3.7-flash",
        summary="Leo proposal",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=2,
                transcript_end_word=2,
                source_start_ms=900,
                source_end_ms=1200,
                original_text="um",
                action="remove",
                concise_reason="Remove filler",
                confidence=0.9,
            )
        ],
        overall_confidence=0.9,
    )
    # Maya rejects approved_for_edl
    review = DirectorReview(
        production_id=prod.production_id,
        model="director-maya-v2",
        overall_assessment="Needs more human review",
        decisions=[
            DirectorDecision(
                editor_decision_id="dec_01",
                verdict=DirectorVerdict.REJECT,
                concise_reason="Reject cut",
            )
        ],
        editor_feedback="Do not proceed to EDL",
        approved_for_edl=False,
        confidence=0.9,
    )

    pid = await editorial_repo.save_editor_proposal(proposal)
    rid = await editorial_repo.save_director_review(review)

    run = EditorialRun(
        run_id="run_01",
        production_id=prod.production_id,
        status=EditorialRunStatus.COMPLETED,
        editor_proposal_id=pid,
        director_review_id=rid,
        started_at=now,
        completed_at=now,
    )
    await editorial_repo.save_editorial_run(run)

    resp = client.post(f"/api/productions/{prod.production_id}/edl")
    assert resp.status_code == 400
    assert "not been approved for edl" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assemble_edl_success_and_idempotency(app_and_deps):
    client, prod_repo, transcript_repo, editorial_repo, edl_repo, _ = app_and_deps
    now = datetime.now(timezone.utc)
    prod = _make_uploaded_production()
    await prod_repo.create_production(prod)

    transcript = _make_transcript(prod.production_id)
    await transcript_repo.save_transcript(transcript)

    proposal = EditorProposal(
        production_id=prod.production_id,
        model="gemini-3.7-flash",
        summary="Leo proposal with 1 filler cut and 1 b-roll marker",
        decisions=[
            EditorDecision(
                decision_id="dec_filler_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=2,
                transcript_end_word=2,
                source_start_ms=900,
                source_end_ms=1200,
                original_text="um",
                action="remove",
                concise_reason="Remove filler um",
                confidence=0.95,
                visual_context="screen recording demo",
            ),
            EditorDecision(
                decision_id="dec_broll_01",
                decision_type=EditorDecisionType.BROLL_COVER_CANDIDATE,
                transcript_start_word=3,
                transcript_end_word=4,
                source_start_ms=1400,
                source_end_ms=2200,
                original_text="this tutorial",
                action="cover",
                concise_reason="B-roll insert candidate",
                confidence=0.92,
            ),
        ],
        overall_confidence=0.94,
    )
    review = DirectorReview(
        production_id=prod.production_id,
        model="director-maya-v2",
        overall_assessment="Approved for EDL assembly",
        decisions=[
            DirectorDecision(
                editor_decision_id="dec_filler_01",
                verdict=DirectorVerdict.APPROVE,
                concise_reason="Approved filler removal",
            ),
            DirectorDecision(
                editor_decision_id="dec_broll_01",
                verdict=DirectorVerdict.APPROVE,
                concise_reason="Approved B-roll marker",
            ),
        ],
        editor_feedback="Proceed to render EDL",
        approved_for_edl=True,
        confidence=0.95,
    )

    pid = await editorial_repo.save_editor_proposal(proposal)
    rid = await editorial_repo.save_director_review(review)

    run = EditorialRun(
        run_id="run_edl_01",
        production_id=prod.production_id,
        status=EditorialRunStatus.COMPLETED,
        editor_proposal_id=pid,
        director_review_id=rid,
        started_at=now,
        completed_at=now,
    )
    await editorial_repo.save_editorial_run(run)

    # 1. First Assembly Call
    resp1 = client.post(f"/api/productions/{prod.production_id}/edl")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["production_id"] == prod.production_id
    assert data1["cut_count"] == 1
    assert data1["coverage_marker_count"] == 1
    assert data1["source_duration_ms"] == 60000
    assert data1["total_removed_duration_ms"] > 0
    assert data1["status"] == "READY"
    edl_id = data1["edl_id"]

    # 2. Repeated Assembly Call (Idempotent)
    resp2 = client.post(f"/api/productions/{prod.production_id}/edl")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["edl_id"] == edl_id  # Returns the exact same active EDL entity

    # 3. GET /api/productions/{production_id}/edl
    resp_get = client.get(f"/api/productions/{prod.production_id}/edl")
    assert resp_get.status_code == 200
    detail = resp_get.json()
    assert detail["edl"]["edl_id"] == edl_id
    assert len(detail["keep_segments"]) == 2  # (0 -> cut_start), (cut_end -> duration)
    assert detail["keep_segments"][0][0] == 0
    assert detail["keep_segments"][-1][1] == 60000
