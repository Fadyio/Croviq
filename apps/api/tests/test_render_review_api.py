"""Comprehensive unit and integration tests for Director post-render review and Master gating (Issue #30)."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
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
from croviq_api.productions.render_review_repository import (
    InMemoryRenderReviewRepository,
    RenderReviewRepository,
    get_render_review_repository,
    set_render_review_repository,
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
from croviq_domain.edl import EditDecisionList
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
from croviq_domain.production import Production, ProductionStatus, SourceMedia, SourceMediaStatus
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
    build_render_artifact_gcs_object_path,
)
from croviq_domain.render_review import (
    RenderReview,
    RenderReviewIssue,
    RenderReviewIssueType,
    RenderReviewSeverity,
    RenderReviewVerdict,
)
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User
from croviq_media.render import FakeRenderService


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


def _make_production(prod_id: str, owner_id: str) -> Production:
    now = datetime.now(timezone.utc)
    return Production(
        production_id=prod_id,
        workspace_id="ws_default",
        owner_user_id=owner_id,
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id=f"up_{prod_id}",
            original_filename="demo.mp4",
            content_type="video/mp4",
            size_bytes=1048576,
            gcs_bucket="croviq-media-raw",
            gcs_object=f"workspaces/ws_default/productions/{prod_id}/source/demo.mp4",
            status=SourceMediaStatus.UPLOADED,
            uploaded_at=now,
            created_at=now,
        ),
        channel_id="chan_sample_ai_eng",
        created_at=now,
        updated_at=now,
    )


def _make_transcript(prod_id: str) -> Transcript:
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=0, end_ms=400),
        TranscriptWord(index=1, text="to", start_ms=410, end_ms=550),
        TranscriptWord(index=2, text="the", start_ms=560, end_ms=700),
        TranscriptWord(index=3, text="demo.", start_ms=710, end_ms=1100),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_01",
            start_ms=0,
            end_ms=1100,
            text="Welcome to the demo.",
            word_start_index=0,
            word_end_index=3,
        )
    ]
    return Transcript(
        transcript_id=f"tr_{prod_id}",
        production_id=prod_id,
        language_code="en-US",
        duration_ms=1100,
        words=words,
        segments=segments,
        created_at=now,
    )


@pytest.fixture
def app_and_deps(test_user: User):
    ws_repo = InMemoryWorkspaceRepository()
    prod_repo = InMemoryProductionRepository()
    transcript_repo = InMemoryTranscriptRepository()
    editorial_repo = InMemoryEditorialRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    render_review_repo = InMemoryRenderReviewRepository()
    media_storage = FakeMediaStorage()
    render_service = FakeRenderService()
    memory_store = FakeChannelMemoryStore()
    fake_genai = FakeGenAIClient()

    set_workspace_repository(ws_repo)
    set_production_repository(prod_repo)
    set_transcript_repository(transcript_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)
    set_render_repository(render_repo)
    set_render_review_repository(render_review_repo)
    set_render_service(render_service)
    set_memory_store(memory_store)
    set_genai_client(fake_genai)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_editorial_repository] = lambda: editorial_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_render_review_repository] = lambda: render_review_repo
    app.dependency_overrides[get_media_storage] = lambda: media_storage

    client = TestClient(app)
    return (
        client,
        prod_repo,
        transcript_repo,
        edl_repo,
        render_repo,
        render_review_repo,
        media_storage,
        fake_genai,
    )


@pytest.mark.asyncio
async def test_review_preview_approve_gates_master_render(app_and_deps, test_user: User) -> None:
    client, prod_repo, transcript_repo, edl_repo, render_repo, render_review_repo, media_storage, fake_genai = (
        app_and_deps
    )
    prod_id = "prod_review_approve"
    prod = _make_production(prod_id, test_user.user_id)
    await prod_repo.create_production(prod)
    await transcript_repo.save_transcript(_make_transcript(prod_id))

    media_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=1048576,
        content_type="video/mp4",
        content=b"fake-mp4-video-data",
    )

    now = datetime.now(timezone.utc)
    edl_id = "edl_01"
    edl = EditDecisionList(
        edl_id=edl_id,
        production_id=prod_id,
        source_duration_ms=1100,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    # Save completed PREVIEW artifact
    preview_artifact_id = "art_preview_01"
    preview_object = build_render_artifact_gcs_object_path(
        workspace_id=prod.workspace_id,
        production_id=prod_id,
        edl_id=edl_id,
        artifact_type=ArtifactType.PREVIEW,
    )
    media_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=preview_object,
        size_bytes=524288,
        content_type="video/mp4",
        content=b"fake-preview-video-data",
    )
    preview_art = RenderArtifact(
        artifact_id=preview_artifact_id,
        production_id=prod_id,
        edl_id=edl_id,
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket=prod.source_media.gcs_bucket,
        gcs_object=preview_object,
        content_type="video/mp4",
        created_at=now,
        completed_at=now,
    )
    await render_repo.save_render_artifact(preview_art)

    # Execute review-preview endpoint
    response = client.post(f"/api/productions/{prod_id}/review-preview")
    assert response.status_code == 200
    data = response.json()

    assert data["production_id"] == prod_id
    assert data["review"]["verdict"] == "APPROVE"
    assert data["review"]["approved_for_master"] is True
    assert data["status"] == "complete"
    assert data["master_artifact"] is not None
    assert data["master_artifact"]["artifact_type"] == "MASTER"
    assert data["master_artifact"]["status"] == "completed"
    assert "playback_url" in data["master_artifact"]

    # Verify RenderReview persisted
    persisted = await render_review_repo.get_latest_render_review(prod_id)
    assert persisted is not None
    assert persisted.verdict == RenderReviewVerdict.APPROVE
    assert persisted.approved_for_master is True

    # Verify MASTER artifact persisted in RenderRepository
    master_art = await render_repo.get_render_artifact_by_type(prod_id, edl_id, ArtifactType.MASTER)
    assert master_art is not None
    assert master_art.status == ArtifactStatus.completed


@pytest.mark.asyncio
async def test_review_preview_idempotency_returns_cached_review(app_and_deps, test_user: User) -> None:
    client, prod_repo, transcript_repo, edl_repo, render_repo, render_review_repo, media_storage, fake_genai = (
        app_and_deps
    )
    prod_id = "prod_review_idempotent"
    prod = _make_production(prod_id, test_user.user_id)
    await prod_repo.create_production(prod)
    await transcript_repo.save_transcript(_make_transcript(prod_id))
    media_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=1048576,
        content_type="video/mp4",
        content=b"fake-mp4-video-data",
    )

    now = datetime.now(timezone.utc)
    edl_id = "edl_01"
    edl = EditDecisionList(
        edl_id=edl_id,
        production_id=prod_id,
        source_duration_ms=1100,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    preview_object = build_render_artifact_gcs_object_path(
        workspace_id=prod.workspace_id,
        production_id=prod_id,
        edl_id=edl_id,
        artifact_type=ArtifactType.PREVIEW,
    )
    media_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=preview_object,
        size_bytes=524288,
        content_type="video/mp4",
        content=b"fake-preview-video-data",
    )
    preview_art = RenderArtifact(
        artifact_id="art_prev_01",
        production_id=prod_id,
        edl_id=edl_id,
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket=prod.source_media.gcs_bucket,
        gcs_object=preview_object,
        content_type="video/mp4",
        created_at=now,
        completed_at=now,
    )
    await render_repo.save_render_artifact(preview_art)

    # First call
    first_resp = client.post(f"/api/productions/{prod_id}/review-preview")
    assert first_resp.status_code == 200
    first_data = first_resp.json()

    # Second call (Idempotency test)
    call_count_before = len(fake_genai.call_history)
    second_resp = client.post(f"/api/productions/{prod_id}/review-preview")
    assert second_resp.status_code == 200
    second_data = second_resp.json()

    assert second_data["review"]["review_id"] == first_data["review"]["review_id"]
    # 0 additional GenAI model calls made on reload!
    assert len(fake_genai.call_history) == call_count_before


@pytest.mark.asyncio
async def test_review_preview_bounded_correction_loop(app_and_deps, test_user: User) -> None:
    client, prod_repo, transcript_repo, edl_repo, render_repo, render_review_repo, media_storage, fake_genai = (
        app_and_deps
    )
    prod_id = "prod_review_correct"
    prod = _make_production(prod_id, test_user.user_id)
    await prod_repo.create_production(prod)
    await transcript_repo.save_transcript(_make_transcript(prod_id))
    media_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=1048576,
        content_type="video/mp4",
        content=b"fake-mp4-video-data",
    )

    now = datetime.now(timezone.utc)
    edl_id = "edl_01"
    edl = EditDecisionList(
        edl_id=edl_id,
        production_id=prod_id,
        source_duration_ms=1100,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    preview_object = build_render_artifact_gcs_object_path(
        workspace_id=prod.workspace_id,
        production_id=prod_id,
        edl_id=edl_id,
        artifact_type=ArtifactType.PREVIEW,
    )
    media_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=preview_object,
        size_bytes=524288,
        content_type="video/mp4",
        content=b"fake-preview-video-data",
    )
    preview_art = RenderArtifact(
        artifact_id="art_prev_01",
        production_id=prod_id,
        edl_id=edl_id,
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket=prod.source_media.gcs_bucket,
        gcs_object=preview_object,
        content_type="video/mp4",
        created_at=now,
        completed_at=now,
    )
    await render_repo.save_render_artifact(preview_art)

    # First review returns CORRECT
    first_canned_review = RenderReview(
        review_id="rrv_first_correct",
        production_id=prod_id,
        edl_id=edl_id,
        preview_artifact_id="art_prev_01",
        agent="maya",
        model="fake-gemini-3.7-flash",
        verdict=RenderReviewVerdict.CORRECT,
        summary="One cut near 00:00 feels too aggressive. Restoring context.",
        issues=[
            RenderReviewIssue(
                issue_id="iss_01",
                issue_type=RenderReviewIssueType.OVER_AGGRESSIVE_CUT,
                source_start_ms=400,
                source_end_ms=550,
                related_decision_id="dec_01",
                severity=RenderReviewSeverity.MEDIUM,
                message="One cut feels too aggressive. Restoring context.",
                suggested_action="Restore take",
            )
        ],
        approved_for_master=False,
        confidence=0.9,
        created_at=now,
    )
    correct_genai = FakeGenAIClient(canned_render_review=first_canned_review)
    set_genai_client(correct_genai)

    # Trigger review-preview: executes Leo correction + Maya review + new preview + second review
    response = client.post(f"/api/productions/{prod_id}/review-preview")
    assert response.status_code == 200
    data = response.json()

    assert data["review"]["verdict"] == "CORRECT"
    assert data["second_review"] is not None
    # Second review (by default in fake) returns APPROVE -> master rendered
    assert data["second_review"]["verdict"] == "APPROVE"
    assert data["status"] == "complete"
    assert data["master_artifact"] is not None


@pytest.mark.asyncio
async def test_review_preview_second_failure_marks_needs_manual_review(app_and_deps, test_user: User) -> None:
    client, prod_repo, transcript_repo, edl_repo, render_repo, render_review_repo, media_storage, fake_genai = (
        app_and_deps
    )
    prod_id = "prod_review_double_fail"
    prod = _make_production(prod_id, test_user.user_id)
    await prod_repo.create_production(prod)
    await transcript_repo.save_transcript(_make_transcript(prod_id))
    media_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=1048576,
        content_type="video/mp4",
        content=b"fake-mp4-video-data",
    )

    now = datetime.now(timezone.utc)
    edl_id = "edl_01"
    edl = EditDecisionList(
        edl_id=edl_id,
        production_id=prod_id,
        source_duration_ms=1100,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    preview_object = build_render_artifact_gcs_object_path(
        workspace_id=prod.workspace_id,
        production_id=prod_id,
        edl_id=edl_id,
        artifact_type=ArtifactType.PREVIEW,
    )
    media_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=preview_object,
        size_bytes=524288,
        content_type="video/mp4",
        content=b"fake-preview-video-data",
    )
    preview_art = RenderArtifact(
        artifact_id="art_prev_01",
        production_id=prod_id,
        edl_id=edl_id,
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket=prod.source_media.gcs_bucket,
        gcs_object=preview_object,
        content_type="video/mp4",
        created_at=now,
        completed_at=now,
    )
    await render_repo.save_render_artifact(preview_art)

    # Persist 2 prior reviews that both returned CORRECT (exhausting the single bounded correction loop)
    r1 = RenderReview(
        review_id="rrv_01",
        production_id=prod_id,
        edl_id=edl_id,
        preview_artifact_id="art_prev_01",
        agent="maya",
        model="fake-gemini-3.7-flash",
        verdict=RenderReviewVerdict.CORRECT,
        summary="First correction required",
        issues=[],
        approved_for_master=False,
        confidence=0.85,
        created_at=now,
    )
    r2 = RenderReview(
        review_id="rrv_02",
        production_id=prod_id,
        edl_id=edl_id,
        preview_artifact_id="art_prev_01",
        agent="maya",
        model="fake-gemini-3.7-flash",
        verdict=RenderReviewVerdict.CORRECT,
        summary="Second review still found issues",
        issues=[],
        approved_for_master=False,
        confidence=0.85,
        created_at=now,
    )
    await render_review_repo.save_render_review(r1)
    await render_review_repo.save_render_review(r2)

    # Call review-preview: should immediately return needs_manual_review without looping
    response = client.post(f"/api/productions/{prod_id}/review-preview")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_manual_review"
    assert data["master_artifact"] is None


@pytest.mark.asyncio
async def test_get_render_reviews_endpoints(app_and_deps, test_user: User) -> None:
    client, prod_repo, transcript_repo, edl_repo, render_repo, render_review_repo, media_storage, fake_genai = (
        app_and_deps
    )
    prod_id = "prod_get_reviews"
    prod = _make_production(prod_id, test_user.user_id)
    await prod_repo.create_production(prod)

    now = datetime.now(timezone.utc)
    review = RenderReview(
        review_id="rrv_01",
        production_id=prod_id,
        edl_id="edl_01",
        preview_artifact_id="art_prev_01",
        agent="maya",
        model="gemini-3.7-flash",
        verdict=RenderReviewVerdict.APPROVE,
        summary="Dialogue flows naturally. Edit approved.",
        issues=[],
        approved_for_master=True,
        confidence=0.95,
        created_at=now,
    )
    await render_review_repo.save_render_review(review)

    resp_plural = client.get(f"/api/productions/{prod_id}/render-reviews")
    assert resp_plural.status_code == 200
    data_plural = resp_plural.json()
    assert data_plural["production_id"] == prod_id
    assert data_plural["review"]["review_id"] == "rrv_01"
    assert len(data_plural["reviews"]) == 1

    resp_singular = client.get(f"/api/productions/{prod_id}/render-review")
    assert resp_singular.status_code == 200
    data_singular = resp_singular.json()
    assert data_singular["review"]["review_id"] == "rrv_01"
