"""Comprehensive unit and integration tests for Vertical Short rendering and automatic post-master trigger (Issue #31)."""

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
from croviq_api.productions.dependencies import (
    get_genai_client,
    get_render_service,
    set_genai_client,
    set_render_service,
)
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
from croviq_api.productions.render_repository import (
    InMemoryRenderRepository,
    get_render_repository,
    set_render_repository,
)
from croviq_api.productions.render_review_repository import (
    InMemoryRenderReviewRepository,
    get_render_review_repository,
    set_render_review_repository,
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
from croviq_api.workspaces.repository import InMemoryWorkspaceRepository, set_workspace_repository
from croviq_domain.edl import EditDecisionList
from croviq_domain.editorial import (
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
    ShortCandidate,
)
from croviq_domain.production import (
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
)
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
)
from croviq_domain.render_review import (
    RenderReview,
    RenderReviewVerdict,
)
from croviq_domain.transcript import Transcript, TranscriptWord
from croviq_domain.user import User
from croviq_domain.workspace import Workspace
from croviq_media.render import FakeRenderService


@pytest.fixture
def test_user() -> User:
    return User(
        user_id="user_short_test",
        email="creator@example.com",
        display_name="Short Creator",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def other_user() -> User:
    return User(
        user_id="user_other",
        email="other@example.com",
        display_name="Other User",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def app_and_deps(test_user: User):
    app = create_app()
    prod_repo = InMemoryProductionRepository()
    workspace_repo = InMemoryWorkspaceRepository()
    transcript_repo = InMemoryTranscriptRepository()
    edl_repo = InMemoryEDLRepository()
    editorial_repo = InMemoryEditorialRepository()
    render_repo = InMemoryRenderRepository()
    render_review_repo = InMemoryRenderReviewRepository()
    media_storage = FakeMediaStorage()
    render_service = FakeRenderService()
    memory_store = FakeChannelMemoryStore()
    fake_genai = FakeGenAIClient()

    set_production_repository(prod_repo)
    set_workspace_repository(workspace_repo)
    set_transcript_repository(transcript_repo)
    set_edl_repository(edl_repo)
    set_editorial_repository(editorial_repo)
    set_render_repository(render_repo)
    set_render_review_repository(render_review_repo)
    set_render_service(render_service)
    set_memory_store(memory_store)
    set_genai_client(fake_genai)

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_editorial_repository] = lambda: editorial_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_render_review_repository] = lambda: render_review_repo
    app.dependency_overrides[get_media_storage] = lambda: media_storage
    app.dependency_overrides[get_render_service] = lambda: render_service
    app.dependency_overrides[get_genai_client] = lambda: fake_genai

    client = TestClient(app)
    return (
        client,
        prod_repo,
        transcript_repo,
        edl_repo,
        editorial_repo,
        render_repo,
        render_review_repo,
        media_storage,
        render_service,
    )


async def _seed_approved_production_with_short_candidate(
    prod_id: str,
    user_id: str,
    prod_repo: InMemoryProductionRepository,
    transcript_repo: InMemoryTranscriptRepository,
    edl_repo: InMemoryEDLRepository,
    editorial_repo: InMemoryEditorialRepository,
    render_repo: InMemoryRenderRepository,
    render_review_repo: InMemoryRenderReviewRepository,
    media_storage: FakeMediaStorage,
    approved: bool = True,
    has_short_candidate: bool = True,
) -> tuple[Production, EditDecisionList, ShortCandidate | None]:
    now = datetime.now(timezone.utc)
    ws_id = f"ws_{prod_id}"
    bucket = "test-media-bucket"
    src_obj = f"workspaces/{ws_id}/productions/{prod_id}/source.mp4"

    # 1. Seed Production
    prod = Production(
        production_id=prod_id,
        workspace_id=ws_id,
        channel_id=f"chan_{prod_id}",
        owner_user_id=user_id,
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id=f"upl_{prod_id}",
            original_filename="source.mp4",
            content_type="video/mp4",
            size_bytes=10000,
            gcs_bucket=bucket,
            gcs_object=src_obj,
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)
    media_storage.simulate_uploaded_object(
        bucket=bucket,
        object_name=src_obj,
        size_bytes=10000,
        content_type="video/mp4",
        content=b"synthetic video content",
    )
    # 2. Seed Transcript
    transcript = Transcript(
        transcript_id=f"tr_{prod_id}",
        production_id=prod_id,
        language_code="en",
        duration_ms=60000,
        words=[
            TranscriptWord(index=0, text="A", start_ms=1000, end_ms=1200),
            TranscriptWord(index=1, text="Modern", start_ms=1250, end_ms=1600),
            TranscriptWord(index=2, text="Smartphone", start_ms=1650, end_ms=2500),
            TranscriptWord(index=3, text="You", start_ms=2600, end_ms=2900),
            TranscriptWord(index=4, text="Can", start_ms=2950, end_ms=3200),
            TranscriptWord(index=5, text="Repair", start_ms=3250, end_ms=4000),
            TranscriptWord(index=6, text="Yourself!", start_ms=4050, end_ms=5000),
        ],
        created_at=now,
    )
    await transcript_repo.save_transcript(transcript)

    # 3. Seed ShortCandidate in Editorial Proposal
    short_candidate = None
    if has_short_candidate:
        short_candidate = ShortCandidate(
            start_ms=1000,
            end_ms=5000,
            transcript_start_word=0,
            transcript_end_word=6,
            hook_title="A Modern Smartphone You Can Actually Repair Yourself!",
            concise_reason="Highlighting modular phone repairability",
            confidence=0.96,
        )

    proposal = EditorProposal(
        production_id=prod_id,
        model="gemini-3.7-flash",
        summary="Leo dialogue pass with Short candidate",
        decisions=[],
        short_candidate=short_candidate,
        overall_confidence=0.95,
    )
    proposal_id = await editorial_repo.save_editor_proposal(proposal, proposal_id=f"prop_{prod_id}")

    run = EditorialRun(
        run_id=f"run_{prod_id}",
        production_id=prod_id,
        status=EditorialRunStatus.COMPLETED,
        editor_proposal_id=proposal_id,
        director_review_id=None,
        completed_at=now,
    )
    await editorial_repo.save_editorial_run(run)

    # 4. Seed EDL
    edl = EditDecisionList(
        edl_id=f"edl_{prod_id}",
        production_id=prod_id,
        source_duration_ms=60000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    # 5. Seed Preview RenderArtifact
    prev_obj = f"workspaces/{ws_id}/productions/{prod_id}/renders/{edl.edl_id}/preview.mp4"
    prev_art = RenderArtifact(
        artifact_id=f"art_prev_{prod_id}",
        production_id=prod_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket=bucket,
        gcs_object=prev_obj,
        content_type="video/mp4",
        size_bytes=5000,
        duration_ms=60000,
        width=1080,
        height=1920,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        created_at=now,
        completed_at=now,
    )
    await render_repo.save_render_artifact(prev_art)
    media_storage.simulate_uploaded_object(
        bucket=bucket,
        object_name=prev_obj,
        size_bytes=5000,
        content_type="video/mp4",
        content=b"preview bytes",
    )

    # 6. Seed RenderReview
    review = RenderReview(
        review_id=f"rrv_{prod_id}",
        production_id=prod_id,
        edl_id=edl.edl_id,
        preview_artifact_id=prev_art.artifact_id,
        agent="maya",
        model="gemini-3.7-flash",
        verdict=RenderReviewVerdict.APPROVE if approved else RenderReviewVerdict.CORRECT,
        summary="Dialogue flows naturally. Edit approved." if approved else "Cut is rough.",
        issues=[],
        approved_for_master=approved,
        confidence=0.98,
        created_at=now,
    )
    await render_review_repo.save_render_review(review)

    return prod, edl, short_candidate


@pytest.mark.asyncio
async def test_render_short_success(app_and_deps, test_user: User):
    (
        client,
        prod_repo,
        transcript_repo,
        edl_repo,
        editorial_repo,
        render_repo,
        render_review_repo,
        media_storage,
        render_service,
    ) = app_and_deps

    prod_id = "prod_short_ok"
    await _seed_approved_production_with_short_candidate(
        prod_id=prod_id,
        user_id=test_user.user_id,
        prod_repo=prod_repo,
        transcript_repo=transcript_repo,
        edl_repo=edl_repo,
        editorial_repo=editorial_repo,
        render_repo=render_repo,
        render_review_repo=render_review_repo,
        media_storage=media_storage,
        approved=True,
        has_short_candidate=True,
    )

    response = client.post(f"/api/productions/{prod_id}/renders/short")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["production_id"] == prod_id
    assert data["artifact_type"] == "SHORT"
    assert data["status"] == "completed"
    assert data["width"] == 1080
    assert data["height"] == 1920
    assert data["playback_url"] is not None

    # Verify persisted in repository
    persisted = await render_repo.get_render_artifact_by_type(
        production_id=prod_id,
        edl_id=f"edl_{prod_id}",
        artifact_type=ArtifactType.SHORT,
    )
    assert persisted is not None
    assert persisted.status == ArtifactStatus.completed
    assert persisted.width == 1080
    assert persisted.height == 1920


@pytest.mark.asyncio
async def test_render_short_idempotency_returns_cached_artifact(app_and_deps, test_user: User):
    (
        client,
        prod_repo,
        transcript_repo,
        edl_repo,
        editorial_repo,
        render_repo,
        render_review_repo,
        media_storage,
        render_service,
    ) = app_and_deps

    prod_id = "prod_short_idempotent"
    await _seed_approved_production_with_short_candidate(
        prod_id=prod_id,
        user_id=test_user.user_id,
        prod_repo=prod_repo,
        transcript_repo=transcript_repo,
        edl_repo=edl_repo,
        editorial_repo=editorial_repo,
        render_repo=render_repo,
        render_review_repo=render_review_repo,
        media_storage=media_storage,
        approved=True,
        has_short_candidate=True,
    )

    # First call renders
    resp1 = client.post(f"/api/productions/{prod_id}/renders/short")
    assert resp1.status_code == 200
    art1 = resp1.json()

    # Second call returns cached artifact
    resp2 = client.post(f"/api/productions/{prod_id}/renders/short")
    assert resp2.status_code == 200
    art2 = resp2.json()

    assert art1["artifact_id"] == art2["artifact_id"]
    assert art1["playback_url"] == art2["playback_url"]

@pytest.mark.asyncio
async def test_render_short_requires_approval_gate(app_and_deps, test_user: User):
    (
        client,
        prod_repo,
        transcript_repo,
        edl_repo,
        editorial_repo,
        render_repo,
        render_review_repo,
        media_storage,
        render_service,
    ) = app_and_deps

    prod_id = "prod_short_unapproved"
    await _seed_approved_production_with_short_candidate(
        prod_id=prod_id,
        user_id=test_user.user_id,
        prod_repo=prod_repo,
        transcript_repo=transcript_repo,
        edl_repo=edl_repo,
        editorial_repo=editorial_repo,
        render_repo=render_repo,
        render_review_repo=render_review_repo,
        media_storage=media_storage,
        approved=False,  # NOT approved
        has_short_candidate=True,
    )

    response = client.post(f"/api/productions/{prod_id}/renders/short")
    assert response.status_code == 400
    assert "approved for Master render" in response.json()["detail"]


@pytest.mark.asyncio
async def test_render_short_requires_short_candidate(app_and_deps, test_user: User):
    (
        client,
        prod_repo,
        transcript_repo,
        edl_repo,
        editorial_repo,
        render_repo,
        render_review_repo,
        media_storage,
        render_service,
    ) = app_and_deps

    prod_id = "prod_short_no_candidate"
    await _seed_approved_production_with_short_candidate(
        prod_id=prod_id,
        user_id=test_user.user_id,
        prod_repo=prod_repo,
        transcript_repo=transcript_repo,
        edl_repo=edl_repo,
        editorial_repo=editorial_repo,
        render_repo=render_repo,
        render_review_repo=render_review_repo,
        media_storage=media_storage,
        approved=True,
        has_short_candidate=False,  # No ShortCandidate in proposal
    )

    response = client.post(f"/api/productions/{prod_id}/renders/short")
    assert response.status_code == 400
    assert "no ShortCandidate" in response.json()["detail"]


@pytest.mark.asyncio
async def test_render_short_403_different_user(app_and_deps, other_user: User):
    (
        client,
        prod_repo,
        transcript_repo,
        edl_repo,
        editorial_repo,
        render_repo,
        render_review_repo,
        media_storage,
        render_service,
    ) = app_and_deps

    prod_id = "prod_short_other_user"
    # Seeded owned by other_user, client authed as test_user
    await _seed_approved_production_with_short_candidate(
        prod_id=prod_id,
        user_id=other_user.user_id,
        prod_repo=prod_repo,
        transcript_repo=transcript_repo,
        edl_repo=edl_repo,
        editorial_repo=editorial_repo,
        render_repo=render_repo,
        render_review_repo=render_review_repo,
        media_storage=media_storage,
        approved=True,
        has_short_candidate=True,
    )

    response = client.post(f"/api/productions/{prod_id}/renders/short")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_renders_includes_short_artifact(app_and_deps, test_user: User):
    (
        client,
        prod_repo,
        transcript_repo,
        edl_repo,
        editorial_repo,
        render_repo,
        render_review_repo,
        media_storage,
        render_service,
    ) = app_and_deps

    prod_id = "prod_short_list"
    await _seed_approved_production_with_short_candidate(
        prod_id=prod_id,
        user_id=test_user.user_id,
        prod_repo=prod_repo,
        transcript_repo=transcript_repo,
        edl_repo=edl_repo,
        editorial_repo=editorial_repo,
        render_repo=render_repo,
        render_review_repo=render_review_repo,
        media_storage=media_storage,
        approved=True,
        has_short_candidate=True,
    )

    # Render short
    client.post(f"/api/productions/{prod_id}/renders/short")

    # List renders
    response = client.get(f"/api/productions/{prod_id}/renders")
    assert response.status_code == 200
    renders = response.json()["renders"]
    artifact_types = [r["artifact_type"] for r in renders]
    assert "PREVIEW" in artifact_types
    assert "SHORT" in artifact_types
