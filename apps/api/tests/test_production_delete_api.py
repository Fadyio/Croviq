"""Comprehensive unit and integration tests for the DELETE /api/productions/{production_id} endpoint."""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from croviq_api.auth.dependencies import get_current_user
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_media_storage, set_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.productions.broll_repository import (
    InMemoryBRollRepository,
    get_broll_repository,
    set_broll_repository,
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
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    get_production_repository,
    set_production_repository,
)
from croviq_api.productions.studio_voice_repository import (
    InMemoryStudioVoiceRepository,
    get_studio_voice_repository,
    set_studio_voice_repository,
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
from croviq_domain.edl import EditDecisionList
from croviq_domain.editorial import (
    EditorialRun,
    EditorialRunStatus,
    EditorProposal,
)
from croviq_domain.narration import (
    BRollArtifact,
    BRollArtifactStatus,
    NarrationSegment,
    NarrationSegmentStatus,
    StudioVoiceResult,
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
from croviq_domain.render_review import RenderReview, RenderReviewVerdict
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from croviq_domain.user import User


@pytest.fixture
def user_a() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="user_owner_a",
        email="owner_a@croviq.app",
        display_name="Owner A",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def user_b() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="user_intruder_b",
        email="intruder_b@croviq.app",
        display_name="Intruder B",
        created_at=now,
        updated_at=now,
    )

@pytest.fixture
def test_setup(user_a: User):
    prod_repo = InMemoryProductionRepository()
    workspace_repo = InMemoryWorkspaceRepository()
    transcript_repo = InMemoryTranscriptRepository()
    editorial_repo = InMemoryEditorialRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    studio_voice_repo = InMemoryStudioVoiceRepository()
    broll_repo = InMemoryBRollRepository()
    media_storage = FakeMediaStorage()

    set_production_repository(prod_repo)
    set_workspace_repository(workspace_repo)
    set_transcript_repository(transcript_repo)
    set_editorial_repository(editorial_repo)
    set_edl_repository(edl_repo)
    set_render_repository(render_repo)
    set_studio_voice_repository(studio_voice_repo)
    set_broll_repository(broll_repo)
    set_media_storage(media_storage)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_workspace_repository] = lambda: workspace_repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    app.dependency_overrides[get_editorial_repository] = lambda: editorial_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_studio_voice_repository] = lambda: studio_voice_repo
    app.dependency_overrides[get_broll_repository] = lambda: broll_repo
    app.dependency_overrides[get_media_storage] = lambda: media_storage

    client = TestClient(app)

    yield {
        "client": client,
        "app": app,
        "prod_repo": prod_repo,
        "workspace_repo": workspace_repo,
        "transcript_repo": transcript_repo,
        "editorial_repo": editorial_repo,
        "edl_repo": edl_repo,
        "render_repo": render_repo,
        "studio_voice_repo": studio_voice_repo,
        "broll_repo": broll_repo,
        "media_storage": media_storage,
    }

    set_production_repository(None)
    set_workspace_repository(None)
    set_transcript_repository(None)
    set_editorial_repository(None)
    set_edl_repository(None)
    set_render_repository(None)
    set_studio_voice_repository(None)
    set_broll_repository(None)
    set_media_storage(None)


@pytest.mark.asyncio
async def test_delete_production_success(test_setup, user_a: User):
    client: TestClient = test_setup["client"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]
    transcript_repo: InMemoryTranscriptRepository = test_setup["transcript_repo"]
    editorial_repo: InMemoryEditorialRepository = test_setup["editorial_repo"]
    edl_repo: InMemoryEDLRepository = test_setup["edl_repo"]
    render_repo: InMemoryRenderRepository = test_setup["render_repo"]
    studio_voice_repo: InMemoryStudioVoiceRepository = test_setup["studio_voice_repo"]
    broll_repo: InMemoryBRollRepository = test_setup["broll_repo"]
    media_storage: FakeMediaStorage = test_setup["media_storage"]

    now = datetime.now(timezone.utc)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(user_a)

    production_id = "prod_del_test_01"
    bucket = "croviq-506602-croviq-media-raw"

    # 1. Seed Production
    prod = Production(
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        source_media=SourceMedia(
            upload_id="upl_01",
            original_filename="raw_interview.mp4",
            content_type="video/mp4",
            size_bytes=10_000_000,
            gcs_bucket=bucket,
            gcs_object=f"workspaces/{workspace.workspace_id}/productions/{production_id}/source/upl_01/raw_interview.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # 2. Seed Transcript
    transcript = Transcript(
        transcript_id="tr_01",
        production_id=production_id,
        language_code="en",
        duration_ms=60000,
        words=[
            TranscriptWord(index=0, text="Hello", start_ms=0, end_ms=1000, confidence=0.99),
            TranscriptWord(index=1, text="world", start_ms=1000, end_ms=2000, confidence=0.99),
            TranscriptWord(index=2, text="test", start_ms=2000, end_ms=3000, confidence=0.99),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=0,
                end_ms=5000,
                text="Hello world test",
                word_start_index=0,
                word_end_index=2,
            )
        ],
        created_at=now,
    )
    await transcript_repo.save_transcript(transcript)

    # 3. Seed Editorial Run & Proposal
    editorial_run = EditorialRun(
        run_id="run_01",
        production_id=production_id,
        status=EditorialRunStatus.COMPLETED,
        started_at=now,
        completed_at=now,
    )
    await editorial_repo.save_editorial_run(editorial_run)

    # 4. Seed EDL
    edl = EditDecisionList(
        edl_id="edl_01",
        production_id=production_id,
        source_duration_ms=60000,
        version=1,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    await edl_repo.save_edl(edl)

    # 5. Seed Render Artifact
    render_art = RenderArtifact(
        artifact_id="art_prev_01",
        production_id=production_id,
        edl_id="edl_01",
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket=bucket,
        gcs_object=f"workspaces/{workspace.workspace_id}/productions/{production_id}/renders/edl_01/preview.mp4",
        created_at=now,
        completed_at=now,
    )
    await render_repo.save_render_artifact(render_art)

    # 7. Seed Studio Voice
    sv_result = StudioVoiceResult(
        production_id=production_id,
        voice_id="Puck",
        total_segments=1,
        accepted_segments=1,
        created_at=now,
        updated_at=now,
        segments=[
            NarrationSegment(
                segment_id="ns_01",
                production_id=production_id,
                source_start_ms=0,
                source_end_ms=4000,
                available_duration_ms=4000,
                original_text="Original speech",
                rewritten_text="Clean concise rewrite",
                voice_id="Puck",
                generated_duration_ms=3200,
                status=NarrationSegmentStatus.ACCEPTED,
            )
        ],
    )
    await studio_voice_repo.save(sv_result)

    # 8. Seed B-roll
    broll = BRollArtifact(
        artifact_id="broll_01",
        production_id=production_id,
        source_start_ms=0,
        source_end_ms=4000,
        gcs_bucket=bucket,
        gcs_object=f"workspaces/{workspace.workspace_id}/productions/{production_id}/broll/broll_01.mp4",
        duration_ms=4000,
        status=BRollArtifactStatus.ACCEPTED,
        created_at=now,
    )
    await broll_repo.save(broll)

    # 9. Seed GCS Storage objects
    media_storage.simulate_uploaded_object(bucket, prod.source_media.gcs_object, 10_000_000, "video/mp4", b"raw video")
    media_storage.simulate_uploaded_object(bucket, render_art.gcs_object, 5_000_000, "video/mp4", b"preview video")
    media_storage.simulate_uploaded_object(bucket, broll.gcs_object, 2_000_000, "video/mp4", b"broll video")

    # Act: DELETE /api/productions/{production_id}
    response = client.delete(f"/api/productions/{production_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["production_id"] == production_id
    assert data["deleted_storage_objects_count"] == 3
    assert "deleted_at" in data

    # Verify Firestore state is gone
    assert await prod_repo.get_production(production_id) is None
    assert await transcript_repo.get_transcript_by_production_id(production_id) is None
    assert await editorial_repo.get_latest_editorial_run(production_id) is None
    assert await edl_repo.get_latest_edl(production_id) is None
    assert len(await render_repo.list_render_artifacts(production_id)) == 0
    assert await studio_voice_repo.get_by_production_id(production_id) is None
    assert len(await broll_repo.list_by_production_id(production_id)) == 0

    # Verify GCS objects are deleted
    assert (await media_storage.get_object_metadata(bucket, prod.source_media.gcs_object)).exists is False
    assert (await media_storage.get_object_metadata(bucket, render_art.gcs_object)).exists is False
    assert (await media_storage.get_object_metadata(bucket, broll.gcs_object)).exists is False

    # Subsequent GET returns 404
    get_res = client.get(f"/api/productions/{production_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_production_not_found(test_setup):
    client: TestClient = test_setup["client"]
    response = client.delete("/api/productions/non_existent_prod_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_production_cross_workspace_forbidden(test_setup, user_a: User, user_b: User):
    client: TestClient = test_setup["client"]
    app = test_setup["app"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]

    now = datetime.now(timezone.utc)
    workspace_a, _ = await workspace_repo.get_or_create_default_workspace(user_a)

    prod = Production(
        production_id="prod_victim_01",
        workspace_id=workspace_a.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # Intruder user B attempts deletion
    app.dependency_overrides[get_current_user] = lambda: user_b

    response = client.delete("/api/productions/prod_victim_01")
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]

    # Verify user A's production was NOT deleted
    assert await prod_repo.get_production("prod_victim_01") is not None


@pytest.mark.asyncio
async def test_delete_production_missing_storage_succeeds_cleanly(test_setup, user_a: User):
    client: TestClient = test_setup["client"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]

    now = datetime.now(timezone.utc)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(user_a)

    prod = Production(
        production_id="prod_empty_01",
        workspace_id=workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        status=ProductionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    response = client.delete("/api/productions/prod_empty_01")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["production_id"] == "prod_empty_01"
    assert data["deleted_storage_objects_count"] == 0



@pytest.mark.asyncio
async def test_delete_production_partial_gcs_source_already_missing(test_setup, user_a: User):
    """Partial failure case: GCS source object already missing or deleted."""
    client: TestClient = test_setup["client"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]
    media_storage: FakeMediaStorage = test_setup["media_storage"]
    render_repo: InMemoryRenderRepository = test_setup["render_repo"]

    now = datetime.now(timezone.utc)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(user_a)
    production_id = "prod_partial_gcs_01"
    bucket = "croviq-506602-croviq-media-raw"

    prod = Production(
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        source_media=SourceMedia(
            upload_id="upl_missing_01",
            original_filename="raw_interview.mp4",
            content_type="video/mp4",
            size_bytes=10_000_000,
            gcs_bucket=bucket,
            gcs_object=f"workspaces/{workspace.workspace_id}/productions/{production_id}/source/upl_missing_01/raw_interview.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # Add render artifact in GCS, but NO source video in GCS (source already missing)
    render_obj = f"workspaces/{workspace.workspace_id}/productions/{production_id}/renders/edl_01/preview.mp4"
    render_art = RenderArtifact(
        artifact_id="art_prev_missing",
        production_id=production_id,
        edl_id="edl_01",
        artifact_type=ArtifactType.PREVIEW,
        status=ArtifactStatus.completed,
        gcs_bucket=bucket,
        gcs_object=render_obj,
        created_at=now,
        completed_at=now,
    )
    await render_repo.save_render_artifact(render_art)
    media_storage.simulate_uploaded_object(bucket, render_obj, 5_000_000, "video/mp4", b"preview")

    response = client.delete(f"/api/productions/{production_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["deleted_storage_objects_count"] == 1
    assert await prod_repo.get_production(production_id) is None


@pytest.mark.asyncio
async def test_delete_production_renders_already_missing(test_setup, user_a: User):
    """Partial failure case: renders already deleted or missing."""
    client: TestClient = test_setup["client"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]
    media_storage: FakeMediaStorage = test_setup["media_storage"]
    transcript_repo: InMemoryTranscriptRepository = test_setup["transcript_repo"]

    now = datetime.now(timezone.utc)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(user_a)
    production_id = "prod_partial_render_01"
    bucket = "croviq-506602-croviq-media-raw"

    prod = Production(
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # Only transcript exists; renders do not exist
    transcript = Transcript(
        transcript_id="tr_missing_render",
        production_id=production_id,
        language_code="en",
        duration_ms=5000,
        words=[],
        segments=[],
        created_at=now,
    )
    await transcript_repo.save_transcript(transcript)

    response = client.delete(f"/api/productions/{production_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert await prod_repo.get_production(production_id) is None
    assert await transcript_repo.get_transcript_by_production_id(production_id) is None


@pytest.mark.asyncio
async def test_delete_production_subcollection_missing(test_setup, user_a: User):
    """Partial failure case: some Firestore subcollections are absent."""
    client: TestClient = test_setup["client"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]
    broll_repo: InMemoryBRollRepository = test_setup["broll_repo"]

    now = datetime.now(timezone.utc)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(user_a)
    production_id = "prod_partial_subcoll_01"

    prod = Production(
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # Only BRoll exists; no transcript, no renders, no edl, no editorial
    broll = BRollArtifact(
        artifact_id="broll_only_01",
        production_id=production_id,
        source_start_ms=0,
        source_end_ms=2000,
        gcs_bucket="croviq-506602-croviq-media-raw",
        gcs_object=f"workspaces/{workspace.workspace_id}/productions/{production_id}/broll/broll.mp4",
        duration_ms=2000,
        status=BRollArtifactStatus.ACCEPTED,
        created_at=now,
    )
    await broll_repo.save(broll)

    response = client.delete(f"/api/productions/{production_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert await prod_repo.get_production(production_id) is None
    assert len(await broll_repo.list_by_production_id(production_id)) == 0


@pytest.mark.asyncio
async def test_delete_production_root_exists_artifacts_missing(test_setup, user_a: User):
    """Case: Root production exists, but zero artifacts/subcollections exist."""
    client: TestClient = test_setup["client"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]

    now = datetime.now(timezone.utc)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(user_a)
    production_id = "prod_root_only_01"

    prod = Production(
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        status=ProductionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    response = client.delete(f"/api/productions/{production_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["deleted_storage_objects_count"] == 0
    assert await prod_repo.get_production(production_id) is None


@pytest.mark.asyncio
async def test_delete_production_second_delete_returns_404(test_setup, user_a: User):
    """Case: Second DELETE after successful deletion returns 404."""
    client: TestClient = test_setup["client"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]

    now = datetime.now(timezone.utc)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(user_a)
    production_id = "prod_second_del_01"

    prod = Production(
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)

    # First DELETE -> 200 OK
    res1 = client.delete(f"/api/productions/{production_id}")
    assert res1.status_code == 200
    assert res1.json()["status"] == "deleted"

    # Second DELETE -> 404 Not Found
    res2 = client.delete(f"/api/productions/{production_id}")
    assert res2.status_code == 404
    assert "not found" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_production_zero_orphaned_gcs_objects(test_setup, user_a: User):
    """Verify zero orphaned GCS objects remain for the deleted production."""
    client: TestClient = test_setup["client"]
    prod_repo: InMemoryProductionRepository = test_setup["prod_repo"]
    workspace_repo: InMemoryWorkspaceRepository = test_setup["workspace_repo"]
    media_storage: FakeMediaStorage = test_setup["media_storage"]

    now = datetime.now(timezone.utc)
    workspace, _ = await workspace_repo.get_or_create_default_workspace(user_a)
    production_id = "prod_orphan_check_01"
    bucket = "croviq-506602-croviq-media-raw"
    prod = Production(
        production_id=production_id,
        workspace_id=workspace.workspace_id,
        channel_id="croviq_syn_ai_eng_01",
        owner_user_id=user_a.user_id,
        source_media=SourceMedia(
            upload_id="upl_orphan_01",
            original_filename="raw.mp4",
            content_type="video/mp4",
            size_bytes=1000,
            gcs_bucket=bucket,
            gcs_object=f"workspaces/{workspace.workspace_id}/productions/{production_id}/source/upl_orphan_01/raw.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        status=ProductionStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    await prod_repo.create_production(prod)
    # Seed 5 objects in this production prefix and 2 objects in another production prefix
    prefix = f"workspaces/{workspace.workspace_id}/productions/{production_id}/"
    other_prefix = f"workspaces/{workspace.workspace_id}/productions/prod_other_999/"

    for i in range(5):
        media_storage.simulate_uploaded_object(
            bucket, f"{prefix}artifact_{i}.mp4", 1000, "video/mp4", b"data"
        )
    for i in range(2):
        media_storage.simulate_uploaded_object(
            bucket, f"{other_prefix}artifact_{i}.mp4", 1000, "video/mp4", b"other"
        )

    # Delete target production
    res = client.delete(f"/api/productions/{production_id}")
    assert res.status_code == 200
    assert res.json()["deleted_storage_objects_count"] == 5

    # Verify 0 objects remain in target production prefix
    remaining_target = [
        meta.object_name for meta in media_storage._objects.values()
        if meta.bucket == bucket and meta.object_name.startswith(prefix)
    ]
    assert len(remaining_target) == 0, f"Found orphaned GCS objects: {remaining_target}"

    # Verify unrelated production objects remain intact
    remaining_other = [
        meta.object_name for meta in media_storage._objects.values()
        if meta.bucket == bucket and meta.object_name.startswith(other_prefix)
    ]
    assert len(remaining_other) == 2
    assert await prod_repo.get_production("prod_empty_01") is None
