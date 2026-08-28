"""Comprehensive unit and integration tests for Nina Packaging API and repository (Issue #32)."""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.channels.research_repository import InMemoryResearchRepository, set_research_repository
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.memory.dependencies import set_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.productions.dependencies import (
    get_genai_client,
    set_genai_client,
)
from croviq_api.productions.edl_repository import (
    InMemoryEDLRepository,
    set_edl_repository,
)
from croviq_api.productions.editorial_repository import (
    InMemoryEditorialRepository,
    set_editorial_repository,
)
from croviq_api.productions.packaging_repository import (
    InMemoryPackagingRepository,
    set_packaging_repository,
)
from croviq_api.productions.render_repository import (
    InMemoryRenderRepository,
    set_render_repository,
)
from croviq_api.productions.render_review_repository import (
    InMemoryRenderReviewRepository,
    set_render_review_repository,
)
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    set_production_repository,
)
from croviq_api.productions.transcript_repository import (
    InMemoryTranscriptRepository,
    set_transcript_repository,
)
from croviq_api.workspaces.agent_config_repository import (
    InMemoryAgentConfigRepository,
    set_agent_config_repository,
)
from croviq_api.workspaces.repository import InMemoryWorkspaceRepository, set_workspace_repository
from croviq_domain.agent_config import AgentId, AgentPromptConfig
from croviq_domain.channel_intelligence import ResearchConfig, ResearchFinding, SourceCitation
from croviq_domain.edl import EditDecisionList
from croviq_domain.editorial import (
    ChapterMarker,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
    ShortCandidate,
)
from croviq_domain.packaging import (
    CreatorPackageOverrides,
    PackagingChapter,
    PackagingProposal,
    ShortPackage,
    ThumbnailConcept,
    TitleAngle,
    TitleCandidate,
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


@pytest.fixture
def test_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="user_pkg_test",
        email="creator@example.com",
        display_name="Test Creator",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def other_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="user_other_intruder",
        email="intruder@example.com",
        display_name="Other User",
        created_at=now,
        updated_at=now,
    )
@pytest.fixture
def test_workspace(test_user: User) -> Workspace:
    now = datetime.now(timezone.utc)
    return Workspace(
        workspace_id="ws_pkg_test",
        name="Personal Workspace",
        owner_user_id=test_user.user_id,
        created_at=now,
        updated_at=now,
    )

@pytest.fixture
def test_production(test_user: User, test_workspace: Workspace) -> Production:
    now = datetime.now(timezone.utc)
    return Production(
        production_id="prod_pkg_100",
        workspace_id=test_workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=test_user.user_id,
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="upl_pkg_01",
            original_filename="Fairphone 6 Plus teardown.mp4",
            content_type="video/mp4",
            size_bytes=45_000_000,
            gcs_bucket="croviq-media-raw",
            gcs_object="workspaces/ws_pkg_test/productions/prod_pkg_100/source/upl_pkg_01/Fairphone 6 Plus teardown.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def test_transcript(test_production: Production) -> Transcript:
    words = [
        TranscriptWord(index=0, start_ms=0, end_ms=500, text="The", confidence=0.99),
        TranscriptWord(index=1, start_ms=500, end_ms=1200, text="Fairphone", confidence=0.99),
        TranscriptWord(index=2, start_ms=1200, end_ms=1800, text="6", confidence=0.99),
        TranscriptWord(index=3, start_ms=1800, end_ms=2500, text="Plus", confidence=0.99),
        TranscriptWord(index=4, start_ms=2500, end_ms=3000, text="is", confidence=0.99),
        TranscriptWord(index=5, start_ms=3000, end_ms=3500, text="a", confidence=0.99),
        TranscriptWord(index=6, start_ms=3500, end_ms=4500, text="modular", confidence=0.99),
        TranscriptWord(index=7, start_ms=4500, end_ms=5500, text="phone.", confidence=0.99),
    ]
    return Transcript(
        transcript_id="tr_pkg_100",
        production_id=test_production.production_id,
        duration_ms=113824,
        language_code="en",
        words=words,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_master_artifact(test_production: Production) -> RenderArtifact:
    now = datetime.now(timezone.utc)
    return RenderArtifact(
        artifact_id="art_master_pkg_100",
        production_id=test_production.production_id,
        edl_id="edl_pkg_100",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object=f"workspaces/ws_pkg_test/productions/{test_production.production_id}/renders/edl_pkg_100/master.mp4",
        content_type="video/mp4",
        duration_ms=113824,
        created_at=now,
        completed_at=now,
    )


@pytest.fixture
def test_short_artifact(test_production: Production) -> RenderArtifact:
    now = datetime.now(timezone.utc)
    return RenderArtifact(
        artifact_id="art_short_pkg_100",
        production_id=test_production.production_id,
        edl_id="edl_pkg_100",
        artifact_type=ArtifactType.SHORT,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object=f"workspaces/ws_pkg_test/productions/{test_production.production_id}/renders/edl_pkg_100/short.mp4",
        content_type="video/mp4",
        duration_ms=39800,
        created_at=now,
        completed_at=now,
    )


@pytest.fixture
def app_and_repos(
    test_user: User,
    test_workspace: Workspace,
    test_production: Production,
    test_transcript: Transcript,
    test_master_artifact: RenderArtifact,
    test_short_artifact: RenderArtifact,
):
    prod_repo = InMemoryProductionRepository()
    ws_repo = InMemoryWorkspaceRepository()
    transcript_repo = InMemoryTranscriptRepository()
    edl_repo = InMemoryEDLRepository()
    editorial_repo = InMemoryEditorialRepository()
    render_repo = InMemoryRenderRepository()
    render_review_repo = InMemoryRenderReviewRepository()
    packaging_repo = InMemoryPackagingRepository()
    agent_config_repo = InMemoryAgentConfigRepository()
    research_repo = InMemoryResearchRepository()
    memory_store = FakeChannelMemoryStore()
    media_storage = FakeMediaStorage()
    fake_client = FakeGenAIClient()
    # Pre-seed repositories
    ws_repo.workspaces[test_workspace.workspace_id] = {
        "workspace_id": test_workspace.workspace_id,
        "owner_user_id": test_workspace.owner_user_id,
        "name": test_workspace.name,
        "created_at": test_workspace.created_at.isoformat(),
        "updated_at": test_workspace.updated_at.isoformat(),
    }
    ws_repo.users[test_user.user_id] = {
        "user_id": test_user.user_id,
        "email": str(test_user.email),
        "display_name": test_user.display_name,
        "created_at": test_user.created_at.isoformat(),
        "updated_at": test_user.updated_at.isoformat(),
    }
    prod_repo._productions[test_production.production_id] = test_production
    transcript_repo._transcripts[test_transcript.transcript_id] = test_transcript
    transcript_repo._by_production[test_production.production_id] = test_transcript.transcript_id
    set_production_repository(prod_repo)
    set_workspace_repository(ws_repo)
    set_transcript_repository(transcript_repo)
    set_edl_repository(edl_repo)
    set_editorial_repository(editorial_repo)
    set_render_repository(render_repo)
    set_render_review_repository(render_review_repo)
    set_packaging_repository(packaging_repo)
    set_agent_config_repository(agent_config_repo)
    set_research_repository(research_repo)
    set_memory_store(memory_store)
    set_genai_client(fake_client)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_media_storage] = lambda: media_storage

    return {
        "app": app,
        "client": TestClient(app),
        "prod_repo": prod_repo,
        "render_repo": render_repo,
        "packaging_repo": packaging_repo,
        "agent_config_repo": agent_config_repo,
        "fake_client": fake_client,
        "test_production": test_production,
        "test_master_artifact": test_master_artifact,
        "test_short_artifact": test_short_artifact,
    }


def test_packaging_missing_master_fails(app_and_repos):
    client = app_and_repos["client"]
    prod = app_and_repos["test_production"]

    # No master artifact in render_repo
    response = client.post(f"/api/productions/{prod.production_id}/package", json={})
    assert response.status_code == 400
    assert "Master video must be rendered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_packaging_generation_success_and_caching(app_and_repos):
    client = app_and_repos["client"]
    prod = app_and_repos["test_production"]
    render_repo = app_and_repos["render_repo"]
    master_art = app_and_repos["test_master_artifact"]
    short_art = app_and_repos["test_short_artifact"]
    fake_client = app_and_repos["fake_client"]

    # Seed master and short
    await render_repo.save_render_artifact(master_art)
    await render_repo.save_render_artifact(short_art)

    # First generation pass
    res1 = client.post(f"/api/productions/{prod.production_id}/package", json={"force_regenerate": False})
    assert res1.status_code == 200
    data1 = res1.json()

    assert data1["production_id"] == prod.production_id
    assert data1["has_master"] is True
    assert data1["has_short"] is True
    assert data1["status"] == "completed"
    assert data1["proposal"] is not None
    assert len(data1["proposal"]["title_candidates"]) >= 3
    assert len(data1["proposal"]["thumbnail_concepts"]) == 3
    assert data1["proposal"]["thumbnail_concepts"][0]["frame_verified"] is True
    assert data1["effective_title"] == data1["proposal"]["primary_title"]
    assert "Inside the Most Repairable Modern Smartphone" in data1["effective_title"]
    assert len(fake_client.call_history) == 1

    # Second call without force_regenerate -> Idempotent, uses cached proposal without calling GenAIClient
    res2 = client.post(f"/api/productions/{prod.production_id}/package", json={"force_regenerate": False})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["proposal"]["proposal_id"] == data1["proposal"]["proposal_id"]
    assert len(fake_client.call_history) == 1  # No additional model call!

    # Third call with force_regenerate=True -> Regenerates new proposal version
    res3 = client.post(f"/api/productions/{prod.production_id}/package", json={"force_regenerate": True})
    assert res3.status_code == 200
    assert len(fake_client.call_history) == 2  # New model call triggered


@pytest.mark.asyncio
async def test_get_and_patch_packaging_overrides(app_and_repos):
    client = app_and_repos["client"]
    prod = app_and_repos["test_production"]
    render_repo = app_and_repos["render_repo"]
    master_art = app_and_repos["test_master_artifact"]
    await render_repo.save_render_artifact(master_art)

    # 1. Generate initial package
    client.post(f"/api/productions/{prod.production_id}/package", json={})

    # 2. Get packaging details
    get_res = client.get(f"/api/productions/{prod.production_id}/packaging")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["effective_title"] != ""
    assert get_data["overrides"] is None

    # 3. Patch user overrides (select a candidate, custom description)
    patch_payload = {
        "selected_title": "Fairphone 6 Plus Is the Phone Everyone Says They Want",
        "custom_description": "My custom creator description for the teardown walkthrough.",
        "selected_thumbnail_concept_id": "th_02",
    }
    patch_res = client.patch(f"/api/productions/{prod.production_id}/packaging", json=patch_payload)
    assert patch_res.status_code == 200
    patch_data = patch_res.json()

    assert patch_data["overrides"] is not None
    assert patch_data["effective_title"] == "Fairphone 6 Plus Is the Phone Everyone Says They Want"
    assert patch_data["effective_description"] == "My custom creator description for the teardown walkthrough."
    assert patch_data["effective_thumbnail_concept_id"] == "th_02"

    # 4. Overriding with custom_title takes precedence over selected_title
    patch_res2 = client.patch(
        f"/api/productions/{prod.production_id}/packaging",
        json={"custom_title": "Custom Hand-Crafted Teardown Title"},
    )
    assert patch_res2.status_code == 200
    assert patch_res2.json()["effective_title"] == "Custom Hand-Crafted Teardown Title"


@pytest.mark.asyncio
async def test_packaging_ownership_enforcement(app_and_repos, other_user):
    app = app_and_repos["app"]
    prod = app_and_repos["test_production"]
    render_repo = app_and_repos["render_repo"]
    master_art = app_and_repos["test_master_artifact"]
    await render_repo.save_render_artifact(master_art)

    # Switch authenticated user to an unauthorized user
    app.dependency_overrides[get_current_user] = lambda: other_user
    intruder_client = TestClient(app)

    res_post = intruder_client.post(f"/api/productions/{prod.production_id}/package", json={})
    assert res_post.status_code == 403

    res_get = intruder_client.get(f"/api/productions/{prod.production_id}/packaging")
    assert res_get.status_code == 403

    res_patch = intruder_client.patch(f"/api/productions/{prod.production_id}/packaging", json={"custom_title": "Hacked"})
    assert res_patch.status_code == 403


@pytest.mark.asyncio
async def test_delete_production_cleans_up_packaging(app_and_repos):
    client = app_and_repos["client"]
    prod = app_and_repos["test_production"]
    render_repo = app_and_repos["render_repo"]
    packaging_repo = app_and_repos["packaging_repo"]
    master_art = app_and_repos["test_master_artifact"]
    await render_repo.save_render_artifact(master_art)

    # Generate and patch
    client.post(f"/api/productions/{prod.production_id}/package", json={})
    client.patch(f"/api/productions/{prod.production_id}/packaging", json={"custom_title": "To be deleted"})

    assert (await packaging_repo.get_latest_packaging_proposal(prod.production_id)) is not None
    assert (await packaging_repo.get_package_overrides(prod.production_id)) is not None

    # Delete production
    del_res = client.delete(f"/api/productions/{prod.production_id}")
    assert del_res.status_code == 200

    # Packaging records should now be purged
    assert (await packaging_repo.get_latest_packaging_proposal(prod.production_id)) is None
    assert (await packaging_repo.get_package_overrides(prod.production_id)) is None
