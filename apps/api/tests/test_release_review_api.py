"""Comprehensive unit and integration tests for Iris QA Release Review API and repository (Issue #33)."""

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
from croviq_api.productions.release_review_repository import (
    InMemoryReleaseReviewRepository,
    set_release_review_repository,
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
from croviq_api.workspaces.agent_config_repository import (
    InMemoryAgentConfigRepository,
    set_agent_config_repository,
)
from croviq_api.workspaces.repository import InMemoryWorkspaceRepository, set_workspace_repository
from croviq_domain.agent_config import AgentId, AgentPromptConfig
from croviq_domain.packaging import (
    PackagingChapter,
    PackagingProposal,
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
from croviq_domain.release_review import (
    ClaimSupportStatus,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseVerdict,
)
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
)
from croviq_domain.transcript import Transcript, TranscriptWord
from croviq_domain.user import User
from croviq_domain.workspace import Workspace


@pytest.fixture
def test_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="usr_test_01",
        email="creator@croviq.internal",
        display_name="Test Creator",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def test_workspace(test_user: User) -> Workspace:
    now = datetime.now(timezone.utc)
    return Workspace(
        workspace_id="ws_test_01",
        owner_user_id=test_user.user_id,
        name="Test Studio",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def test_production(test_user: User, test_workspace: Workspace) -> Production:
    now = datetime.now(timezone.utc)
    return Production(
        production_id="prod_test_01",
        workspace_id=test_workspace.workspace_id,
        owner_user_id=test_user.user_id,
        channel_id="ch_test_01",
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="upl_01",
            gcs_bucket="croviq-media-raw",
            gcs_object="workspaces/ws_test_01/productions/prod_test_01/source/upl_01/raw.mp4",
            original_filename="fairphone.mp4",
            content_type="video/mp4",
            size_bytes=50000000,
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_master_render(test_production: Production) -> RenderArtifact:
    now = datetime.now(timezone.utc)
    return RenderArtifact(
        artifact_id="art_master_01",
        production_id=test_production.production_id,
        edl_id="edl_01",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_test_01/productions/prod_test_01/renders/master.mp4",
        duration_ms=113824,
        created_at=now,
    )


@pytest.fixture
def sample_transcript(test_production: Production) -> Transcript:
    now = datetime.now(timezone.utc)
    return Transcript(
        transcript_id="tr_01",
        production_id=test_production.production_id,
        language_code="en",
        created_at=now,
        duration_ms=113824,
        words=[
            TranscriptWord(index=0, text="Welcome", start_ms=0, end_ms=500, confidence=0.99),
            TranscriptWord(index=1, text="to", start_ms=510, end_ms=700, confidence=0.99),
            TranscriptWord(index=2, text="Fairphone", start_ms=710, end_ms=1200, confidence=0.99),
            TranscriptWord(index=3, text="6", start_ms=1210, end_ms=1500, confidence=0.99),
            TranscriptWord(index=4, text="Plus", start_ms=1510, end_ms=1900, confidence=0.99),
        ],
    )


@pytest.fixture
def sample_packaging_proposal(test_production: Production) -> PackagingProposal:
    now = datetime.now(timezone.utc)
    return PackagingProposal(
        proposal_id="pkg_01",
        production_id=test_production.production_id,
        primary_title="Fairphone 6 Plus: The Modular Smartphone That Actually Makes Sense",
        title_candidates=[
            TitleCandidate(
                text="Fairphone 6 Plus: The Modular Smartphone That Actually Makes Sense",
                angle=TitleAngle.PROBLEM_SOLUTION,
                why_it_works="Highlights modularity.",
                confidence=0.96,
            )
        ],
        description="Hands-on review of Fairphone 6 Plus.\nStay tuned for the upcoming full Fairphone 6+ review!",
        chapters=[
            PackagingChapter(title="Intro", start_ms=0, end_ms=30000, formatted_time="0:00"),
            PackagingChapter(title="Modularity", start_ms=30000, end_ms=113824, formatted_time="0:30"),
        ],
        thumbnail_concepts=[
            ThumbnailConcept(
                concept_id="th_01",
                headline="MODULAR PHONE!",
                visual_subject="Disassembled phone parts",
                composition="Macro close up",
                emotion="Curiosity",
                supporting_frame_ms=28000,
                reason="Shows repairability",
                confidence=0.96,
                frame_verified=True,
            )
        ],
        packaging_summary="Modular phone review",
        channel_evidence="Channel baseline supports teardowns.",
        confidence=0.95,
        created_at=now,
        master_artifact_id="art_master_01",
    )


@pytest.fixture
def api_client(
    test_user: User,
    test_workspace: Workspace,
    test_production: Production,
    sample_master_render: RenderArtifact,
    sample_transcript: Transcript,
    sample_packaging_proposal: PackagingProposal,
) -> TestClient:
    prod_repo = InMemoryProductionRepository()
    ws_repo = InMemoryWorkspaceRepository()
    render_repo = InMemoryRenderRepository()
    transcript_repo = InMemoryTranscriptRepository()
    packaging_repo = InMemoryPackagingRepository()
    release_review_repo = InMemoryReleaseReviewRepository()
    edl_repo = InMemoryEDLRepository()
    editorial_repo = InMemoryEditorialRepository()
    agent_config_repo = InMemoryAgentConfigRepository()
    research_repo = InMemoryResearchRepository()
    memory_store = FakeChannelMemoryStore()
    media_storage = FakeMediaStorage()
    fake_client = FakeGenAIClient()

    ws_repo.workspaces[test_workspace.workspace_id] = {
        "workspace_id": test_workspace.workspace_id,
        "owner_user_id": test_user.user_id,
        "name": test_workspace.name,
        "created_at": test_workspace.created_at,
        "updated_at": test_workspace.updated_at,
    }
    ws_repo.users[test_user.user_id] = {
        "user_id": test_user.user_id,
        "email": str(test_user.email),
        "display_name": test_user.display_name,
        "created_at": test_user.created_at.isoformat(),
        "updated_at": test_user.updated_at.isoformat(),
    }
    prod_repo._productions[test_production.production_id] = test_production
    transcript_repo._transcripts[sample_transcript.transcript_id] = sample_transcript
    transcript_repo._by_production[test_production.production_id] = sample_transcript.transcript_id
    render_repo._by_production[test_production.production_id] = {
        sample_master_render.artifact_id: sample_master_render,
    }
    packaging_repo._proposals[test_production.production_id] = {
        sample_packaging_proposal.proposal_id: sample_packaging_proposal
    }

    set_production_repository(prod_repo)
    set_workspace_repository(ws_repo)
    set_render_repository(render_repo)
    set_transcript_repository(transcript_repo)
    set_packaging_repository(packaging_repo)
    set_release_review_repository(release_review_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)
    set_agent_config_repo = agent_config_repo
    set_agent_config_repository(agent_config_repo)
    set_memory_store(memory_store)
    set_research_repository(research_repo)
    set_genai_client(fake_client)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_media_storage] = lambda: media_storage

    return TestClient(app)


def test_generate_release_review_detects_unsupported_claim(api_client: TestClient, test_production: Production):
    resp = api_client.post(f"/api/productions/{test_production.production_id}/release-review", json={})
    assert resp.status_code == 200
    data = resp.json()

    assert data["production_id"] == test_production.production_id
    assert data["release_ready"] is False
    assert data["release_status"] == "Fix required"
    assert data["review"] is not None
    assert data["review"]["verdict"] == ReleaseVerdict.FIX_REQUIRED.value
    assert data["review"]["approved_for_release"] is False
    assert len(data["review"]["issues"]) >= 1
    assert data["review"]["issues"][0]["issue_type"] == ReleaseIssueType.UNSUPPORTED_CLAIM.value


def test_release_review_idempotency(api_client: TestClient, test_production: Production):
    # 1. First invocation
    resp1 = api_client.post(f"/api/productions/{test_production.production_id}/release-review", json={})
    assert resp1.status_code == 200
    review_id = resp1.json()["review"]["review_id"]

    # 2. Second invocation without force_regenerate returns cached review
    resp2 = api_client.post(f"/api/productions/{test_production.production_id}/release-review", json={"force_regenerate": False})
    assert resp2.status_code == 200
    assert resp2.json()["review"]["review_id"] == review_id

    # 3. GET endpoint also returns cached review
    resp_get = api_client.get(f"/api/productions/{test_production.production_id}/release-review")
    assert resp_get.status_code == 200
    assert resp_get.json()["review"]["review_id"] == review_id


def test_release_review_pass_on_clean_production(
    test_user: User,
    test_workspace: Workspace,
    test_production: Production,
    sample_master_render: RenderArtifact,
    sample_transcript: Transcript,
):
    prod_repo = InMemoryProductionRepository()
    ws_repo = InMemoryWorkspaceRepository()
    render_repo = InMemoryRenderRepository()
    transcript_repo = InMemoryTranscriptRepository()
    packaging_repo = InMemoryPackagingRepository()
    release_review_repo = InMemoryReleaseReviewRepository()
    edl_repo = InMemoryEDLRepository()
    editorial_repo = InMemoryEditorialRepository()
    agent_config_repo = InMemoryAgentConfigRepository()
    research_repo = InMemoryResearchRepository()
    memory_store = FakeChannelMemoryStore()
    media_storage = FakeMediaStorage()
    fake_client = FakeGenAIClient()

    ws_repo.workspaces[test_workspace.workspace_id] = {
        "workspace_id": test_workspace.workspace_id,
        "owner_user_id": test_user.user_id,
        "name": test_workspace.name,
        "created_at": test_workspace.created_at,
        "updated_at": test_workspace.updated_at,
    }
    prod_repo._productions[test_production.production_id] = test_production
    transcript_repo._transcripts[sample_transcript.transcript_id] = sample_transcript
    transcript_repo._by_production[test_production.production_id] = sample_transcript.transcript_id
    render_repo._by_production[test_production.production_id] = {
        sample_master_render.artifact_id: sample_master_render,
    }

    set_production_repository(prod_repo)
    set_workspace_repository(ws_repo)
    set_render_repository(render_repo)
    set_transcript_repository(transcript_repo)
    set_packaging_repository(packaging_repo)
    set_release_review_repository(release_review_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)
    set_agent_config_repository(agent_config_repo)
    set_memory_store(memory_store)
    set_research_repository(research_repo)
    set_genai_client(fake_client)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_media_storage] = lambda: media_storage

    client = TestClient(app)
    resp = client.post(f"/api/productions/{test_production.production_id}/release-review", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["release_ready"] is True
    assert data["release_status"] == "Ready to publish"
    assert data["review"]["verdict"] == ReleaseVerdict.PASS.value
    assert data["review"]["approved_for_release"] is True


def test_release_review_missing_prerequisites(api_client: TestClient, test_production: Production):
    # Missing master
    render_repo = InMemoryRenderRepository()
    set_render_repository(render_repo)
    resp = api_client.post(f"/api/productions/{test_production.production_id}/release-review", json={})
    assert resp.status_code == 400
    assert "Master video must be rendered" in resp.json()["detail"]
def test_release_review_mode_aware_endpoints(
    test_user: User,
    test_workspace: Workspace,
    test_production: Production,
    sample_master_render: RenderArtifact,
    sample_transcript: Transcript,
):
    prod_repo = InMemoryProductionRepository()
    ws_repo = InMemoryWorkspaceRepository()
    render_repo = InMemoryRenderRepository()
    transcript_repo = InMemoryTranscriptRepository()
    packaging_repo = InMemoryPackagingRepository()
    release_review_repo = InMemoryReleaseReviewRepository()
    edl_repo = InMemoryEDLRepository()
    editorial_repo = InMemoryEditorialRepository()
    agent_config_repo = InMemoryAgentConfigRepository()
    research_repo = InMemoryResearchRepository()
    memory_store = FakeChannelMemoryStore()
    media_storage = FakeMediaStorage()
    fake_client = FakeGenAIClient()

    from croviq_domain.render import ArtifactType, ArtifactStatus
    from croviq_domain.edl import EditDecisionList
    from datetime import datetime, timezone

    # Set up production with source media
    from croviq_domain.production import SourceMedia, SourceMediaStatus
    test_production.source_media = SourceMedia(
        upload_id="upl_01",
        original_filename="raw.mp4",
        content_type="video/mp4",
        size_bytes=1024000,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_test_01/productions/prod_test_01/source/upl_01/raw.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=datetime.now(timezone.utc),
    )
    prod_repo._productions[test_production.production_id] = test_production
    transcript_repo._transcripts[sample_transcript.transcript_id] = sample_transcript
    transcript_repo._by_production[test_production.production_id] = sample_transcript.transcript_id

    edl = EditDecisionList(
        edl_id="edl_mode_test",
        production_id=test_production.production_id,
        source_duration_ms=113824,
        cuts=[],
        created_at=datetime.now(timezone.utc),
    )
    edl_repo._by_id[(test_production.production_id, edl.edl_id)] = edl
    edl_repo._by_production[test_production.production_id] = [edl.edl_id]
    # Add PREVIEW, VOICEOVER_PREVIEW, and FINAL_MIX render artifacts
    preview_render = RenderArtifact(
        artifact_id="art_preview_01",
        production_id=test_production.production_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="renders/preview.mp4",
        duration_ms=113824,
        created_at=datetime.now(timezone.utc),
    )
    vo_render = RenderArtifact(
        artifact_id="art_vo_01",
        production_id=test_production.production_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.VOICEOVER_PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="renders/voiceover.mp4",
        duration_ms=113824,
        created_at=datetime.now(timezone.utc),
    )
    fm_render = RenderArtifact(
        artifact_id="art_fm_01",
        production_id=test_production.production_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.FINAL_MIX,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="renders/final_mix.mp4",
        duration_ms=113824,
        created_at=datetime.now(timezone.utc),
    )

    render_repo._by_production[test_production.production_id] = {
        preview_render.artifact_id: preview_render,
        vo_render.artifact_id: vo_render,
        fm_render.artifact_id: fm_render,
    }

    set_production_repository(prod_repo)
    set_workspace_repository(ws_repo)
    set_render_repository(render_repo)
    set_transcript_repository(transcript_repo)
    set_packaging_repository(packaging_repo)
    set_release_review_repository(release_review_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)
    set_agent_config_repository(agent_config_repo)
    set_memory_store(memory_store)
    set_research_repository(research_repo)
    set_genai_client(fake_client)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_media_storage] = lambda: media_storage
    client = TestClient(app)

    # 1. Original review
    resp_orig = client.post(
        f"/api/productions/{test_production.production_id}/release-review",
        json={"preview_mode": "original", "force_regenerate": True},
    )
    assert resp_orig.status_code == 200
    data_orig = resp_orig.json()
    assert data_orig["review"]["preview_mode"] == "original"
    assert "art_source_" in data_orig["review"]["reviewed_artifact_id"]

    # 2. Edited review
    resp_edit = client.post(
        f"/api/productions/{test_production.production_id}/release-review",
        json={"preview_mode": "edited", "force_regenerate": True},
    )
    assert resp_edit.status_code == 200
    data_edit = resp_edit.json()
    assert data_edit["review"]["preview_mode"] == "edited"
    assert data_edit["review"]["reviewed_artifact_id"] == "art_preview_01"

    # 3. Voiceover review
    resp_vo = client.post(
        f"/api/productions/{test_production.production_id}/release-review",
        json={"preview_mode": "voiceover", "force_regenerate": True},
    )
    assert resp_vo.status_code == 200
    data_vo = resp_vo.json()
    assert data_vo["review"]["preview_mode"] == "voiceover"
    assert data_vo["review"]["reviewed_artifact_id"] == "art_vo_01"

    # 4. Final mix review
    resp_fm = client.post(
        f"/api/productions/{test_production.production_id}/release-review",
        json={"preview_mode": "final_mix", "force_regenerate": True},
    )
    assert resp_fm.status_code == 200
    data_fm = resp_fm.json()
    assert data_fm["review"]["preview_mode"] == "final_mix"
    assert data_fm["review"]["reviewed_artifact_id"] == "art_fm_01"
