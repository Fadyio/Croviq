"""Comprehensive integration tests for YouTube Publishing API, release gates, idempotency, and security."""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from croviq_agents.client import FakeGenAIClient
from croviq_api.auth.dependencies import get_current_user
from croviq_api.channels.youtube_provider import SCOPE_ANALYTICS_READONLY, SCOPE_YOUTUBE_READONLY, SCOPE_YOUTUBE_UPLOAD
from croviq_api.channels.youtube_publisher import FakeYouTubePublishClient, set_youtube_publish_client
from croviq_api.channels.youtube_repository import (
    InMemoryYouTubeConnectionRepository,
    YouTubeConnection,
    get_youtube_connection_repository,
    set_youtube_connection_repository,
)
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_media_storage
from croviq_api.media.fake import FakeMediaStorage
from croviq_api.productions.dependencies import (
    get_publish_job_repository,
    get_publish_service,
    get_thumbnail_repository,
    set_publish_job_repository,
    set_publish_service,
    set_thumbnail_repository,
)
from croviq_api.productions.edl_repository import (
    InMemoryEDLRepository,
    get_edl_repository,
)
from croviq_domain.edl import EditDecisionList
from croviq_api.productions.packaging_repository import (
    InMemoryPackagingRepository,
    get_packaging_repository,
    set_packaging_repository,
)
from croviq_api.productions.publish_job_repository import (
    InMemoryPublishJobRepository,
)
from croviq_api.productions.release_review_repository import (
    InMemoryReleaseReviewRepository,
    get_release_review_repository,
    set_release_review_repository,
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
from croviq_api.productions.thumbnail_repository import (
    InMemoryThumbnailRepository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    get_workspace_repository,
    set_workspace_repository,
)
from croviq_domain.packaging import (
    PackagingChapter,
    PackagingProposal,
    ThumbnailConcept,
    TitleAngle,
    TitleCandidate,
)
from croviq_domain.production import Production, ProductionStatus, SourceMedia
from croviq_domain.publish import PublishJobStatus, ThumbnailUploadStatus
from croviq_domain.release_review import (
    ReleaseChecklist,
    ReleaseReview,
    ReleaseVerdict,
)
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.user import User
from croviq_domain.workspace import Workspace
from croviq_media.thumbnail import FakeThumbnailExtractor


@pytest.fixture
def user_a() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="usr_creator_a",
        email="creator_a@croviq.app",
        display_name="Creator A",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def user_b() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="usr_intruder_b",
        email="intruder_b@croviq.app",
        display_name="Intruder B",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def workspace_a(user_a: User) -> Workspace:
    now = datetime.now(timezone.utc)
    return Workspace(
        workspace_id="ws_creator_a",
        owner_user_id=user_a.user_id,
        name="Creator Studio",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_production(user_a: User, workspace_a: Workspace) -> Production:
    now = datetime.now(timezone.utc)
    return Production(
        production_id="prod_sample_01",
        workspace_id=workspace_a.workspace_id,
        owner_user_id=user_a.user_id,
        channel_id="sample_tech_channel",
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="upl_01",
            original_filename="raw.mp4",
            gcs_bucket="croviq-media-raw",
            gcs_object="source/raw.mp4",
            content_type="video/mp4",
            size_bytes=10485760,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def real_production(user_a: User, workspace_a: Workspace) -> Production:
    now = datetime.now(timezone.utc)
    return Production(
        production_id="prod_real_01",
        workspace_id=workspace_a.workspace_id,
        owner_user_id=user_a.user_id,
        channel_id="UC_connected_creator",
        status=ProductionStatus.UPLOADED,
        source_media=SourceMedia(
            upload_id="upl_02",
            original_filename="real_raw.mp4",
            gcs_bucket="croviq-media-raw",
            gcs_object="source/real_raw.mp4",
            content_type="video/mp4",
            size_bytes=10485760,
            created_at=now,
        ),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_master_artifact(sample_production: Production) -> RenderArtifact:
    now = datetime.now(timezone.utc)
    return RenderArtifact(
        artifact_id="art_master_sample",
        production_id=sample_production.production_id,
        edl_id="edl_sample",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-renders",
        gcs_object="renders/master_sample.mp4",
        content_type="video/mp4",
        size_bytes=20485760,
        duration_ms=60000,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        created_at=now,
    )


@pytest.fixture
def real_master_artifact(real_production: Production) -> RenderArtifact:
    now = datetime.now(timezone.utc)
    return RenderArtifact(
        artifact_id="art_master_real",
        production_id=real_production.production_id,
        edl_id="edl_real",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-renders",
        gcs_object="renders/master_real.mp4",
        content_type="video/mp4",
        size_bytes=20485760,
        duration_ms=60000,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        created_at=now,
    )


@pytest.fixture
def sample_packaging(sample_production: Production) -> PackagingProposal:
    now = datetime.now(timezone.utc)
    return PackagingProposal(
        proposal_id="pkg_sample_01",
        production_id=sample_production.production_id,
        primary_title="Building Autonomous AI Systems in 2026",
        title_candidates=[
            TitleCandidate(
                text="Building Autonomous AI Systems in 2026",
                angle=TitleAngle.HOW_TO,
                why_it_works="Actionable tutorial for engineers",
                confidence=0.95,
            )
        ],
        description="Full tutorial on autonomous AI systems.\n\n0:00 Intro\n1:00 Demo",
        chapters=[
            PackagingChapter(
                title="Intro",
                start_ms=0,
                end_ms=60000,
                formatted_time="0:00",
            )
        ],
        thumbnail_concepts=[
            ThumbnailConcept(
                concept_id="tc_01",
                headline="AI Systems 2026",
                visual_subject="Engineer with glowing architecture diagram",
                composition="Wide framing with glowing UI elements",
                emotion="Intrigue",
                supporting_frame_ms=12000,
                reason="Strong click-through curiosity",
                confidence=0.94,
            )
        ],
        keywords=["AI", "Engineering"],
        packaging_summary="Strong technical hook tailored to AI engineers",
        confidence=0.95,
        created_at=now,
    )


@pytest.fixture
def real_packaging(real_production: Production) -> PackagingProposal:
    now = datetime.now(timezone.utc)
    return PackagingProposal(
        proposal_id="pkg_real_01",
        production_id=real_production.production_id,
        primary_title="Deploying Multi-Agent Systems on Cloud Run",
        title_candidates=[
            TitleCandidate(
                text="Deploying Multi-Agent Systems on Cloud Run",
                angle=TitleAngle.HOW_TO,
                why_it_works="High value technical guide",
                confidence=0.96,
            )
        ],
        description="Complete guide to multi-agent deployment.\n\n0:00 Overview\n1:00 Setup",
        chapters=[
            PackagingChapter(
                title="Overview",
                start_ms=0,
                end_ms=60000,
                formatted_time="0:00",
            )
        ],
        thumbnail_concepts=[
            ThumbnailConcept(
                concept_id="tc_02",
                headline="Multi-Agent Deploy",
                visual_subject="Architecture diagram with Cloud Run logo",
                composition="Centered focal point with high contrast text",
                emotion="Confidence",
                supporting_frame_ms=15000,
                reason="Clear technical value proposition",
                confidence=0.95,
            )
        ],
        keywords=["CloudRun", "Agents"],
        packaging_summary="Direct value positioning with production cloud deployment",
        confidence=0.96,
        created_at=now,
    )

@pytest.fixture
def passed_review(real_production: Production, real_master_artifact: RenderArtifact, real_packaging: PackagingProposal) -> ReleaseReview:
    now = datetime.now(timezone.utc)
    return ReleaseReview(
        review_id="rev_real_pass",
        production_id=real_production.production_id,
        verdict=ReleaseVerdict.PASS,
        summary="All media and packaging claims passed inspection.",
        issues=[],
        approved_for_release=True,
        confidence=0.98,
        master_artifact_id=real_master_artifact.artifact_id,
        packaging_proposal_id=real_packaging.proposal_id,
        checklist=ReleaseChecklist(
            master_video=True,
            audio=True,
            captions=True,
            chapters=True,
            packaging=True,
            claims=True,
        ),
        created_at=now,
    )


@pytest.fixture
def test_setup(
    user_a: User,
    workspace_a: Workspace,
    sample_production: Production,
    real_production: Production,
    sample_master_artifact: RenderArtifact,
    real_master_artifact: RenderArtifact,
    sample_packaging: PackagingProposal,
    real_packaging: PackagingProposal,
    passed_review: ReleaseReview,
):
    prod_repo = InMemoryProductionRepository()
    ws_repo = InMemoryWorkspaceRepository()
    yt_repo = InMemoryYouTubeConnectionRepository()
    pkg_repo = InMemoryPackagingRepository()
    edl_repo = InMemoryEDLRepository()
    render_repo = InMemoryRenderRepository()
    release_repo = InMemoryReleaseReviewRepository()
    thumb_repo = InMemoryThumbnailRepository()
    job_repo = InMemoryPublishJobRepository()
    storage = FakeMediaStorage()
    fake_yt_client = FakeYouTubePublishClient()

    # Seed data
    import asyncio
    now = datetime.now(timezone.utc)
    edl_real = EditDecisionList(
        edl_id="edl_real",
        production_id=real_production.production_id,
        source_duration_ms=60000,
        cuts=[],
        created_at=now,
    )
    asyncio.run(edl_repo.save_edl(edl_real))
    asyncio.run(ws_repo.create_workspace(workspace_a))
    asyncio.run(prod_repo.create_production(sample_production))
    asyncio.run(prod_repo.create_production(real_production))
    asyncio.run(render_repo.save_render_artifact(sample_master_artifact))
    asyncio.run(render_repo.save_render_artifact(real_master_artifact))
    asyncio.run(pkg_repo.save_packaging_proposal(sample_packaging))
    asyncio.run(pkg_repo.save_packaging_proposal(real_packaging))
    asyncio.run(release_repo.save_release_review(passed_review))
    # Setup fake storage files
    storage.simulate_uploaded_object(
        bucket=real_master_artifact.gcs_bucket,
        object_name=real_master_artifact.gcs_object,
        size_bytes=real_master_artifact.size_bytes or 1048576,
        content_type="video/mp4",
        content=b"dummy master video bytes" * 100,
    )

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_production_repository] = lambda: prod_repo
    app.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    app.dependency_overrides[get_youtube_connection_repository] = lambda: yt_repo
    app.dependency_overrides[get_packaging_repository] = lambda: pkg_repo
    app.dependency_overrides[get_edl_repository] = lambda: edl_repo
    app.dependency_overrides[get_render_repository] = lambda: render_repo
    app.dependency_overrides[get_release_review_repository] = lambda: release_repo
    app.dependency_overrides[get_thumbnail_repository] = lambda: thumb_repo
    app.dependency_overrides[get_publish_job_repository] = lambda: job_repo
    app.dependency_overrides[get_media_storage] = lambda: storage
    set_youtube_publish_client(fake_yt_client)

    client = TestClient(app)

    return {
        "client": client,
        "app": app,
        "prod_repo": prod_repo,
        "ws_repo": ws_repo,
        "yt_repo": yt_repo,
        "pkg_repo": pkg_repo,
        "edl_repo": edl_repo,
        "render_repo": render_repo,
        "release_repo": release_repo,
        "thumb_repo": thumb_repo,
        "job_repo": job_repo,
        "storage": storage,
        "fake_yt_client": fake_yt_client,
        "user_a": user_a,
        "workspace_a": workspace_a,
        "real_prod": real_production,
        "sample_prod": sample_production,
        "real_packaging": real_packaging,
        "sample_packaging": sample_packaging,
    }

def test_publish_prep_sample_channel(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    sample_prod: Production = test_setup["sample_prod"]

    resp = client.get(f"/api/productions/{sample_prod.production_id}/publish/prep")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_sample_channel"] is True
    assert data["can_publish"] is False
    assert data["channel_title"] == "Croviq Sample Channel"
    assert data["suggested_title"] != ""
    assert len(data["verified_thumbnail_frames"]) > 0


def test_publish_prep_real_channel(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    real_prod: Production = test_setup["real_prod"]
    yt_repo = test_setup["yt_repo"]
    workspace_a = test_setup["workspace_a"]

    # Connect channel with read-only
    now = datetime.now(timezone.utc)
    conn = YouTubeConnection(
        workspace_id=workspace_a.workspace_id,
        user_id=test_setup["user_a"].user_id,
        channel_id="UC_connected_creator",
        channel_title="Real Creator Channel",
        avatar_url="https://yt3.example/avatar.jpg",
        subscriber_count=50000,
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        scopes=[SCOPE_YOUTUBE_READONLY, SCOPE_ANALYTICS_READONLY],
        connected_at=now,
        last_sync_at=now,
    )
    import asyncio
    asyncio.run(yt_repo.save_connection(conn))

    resp = client.get(f"/api/productions/{real_prod.production_id}/publish/prep")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_sample_channel"] is False
    assert data["can_publish"] is True
    assert data["has_upload_access"] is False
    assert data["channel_title"] == "Real Creator Channel"
    assert data["release_ready"] is True


def test_publish_blocked_on_sample_channel(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    sample_prod: Production = test_setup["sample_prod"]

    resp = client.post(
        f"/api/productions/{sample_prod.production_id}/publish",
        json={
            "requested_privacy": "private",
            "made_for_kids": False,
            "contains_synthetic_media": False,
        },
    )
    assert resp.status_code == 400
    assert "Sample Channel cannot publish" in resp.json()["detail"]


def test_publish_blocked_on_canonical_croviq_syn_channel(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    sample_prod: Production = test_setup["sample_prod"]
    prod_repo = test_setup["prod_repo"]

    # Update channel_id to canonical sample channel id
    updated = sample_prod.model_copy(update={"channel_id": "croviq_syn_ai_eng_01"})
    import asyncio
    asyncio.run(prod_repo.create_production(updated))

    resp_prep = client.get(f"/api/productions/{updated.production_id}/publish/prep")
    assert resp_prep.status_code == 200
    assert resp_prep.json()["is_sample_channel"] is True
    assert resp_prep.json()["can_publish"] is False

    resp = client.post(
        f"/api/productions/{updated.production_id}/publish",
        json={
            "requested_privacy": "private",
            "made_for_kids": False,
            "contains_synthetic_media": False,
        },
    )
    assert resp.status_code == 400
    assert "Sample Channel cannot publish" in resp.json()["detail"]

def test_publish_blocked_if_iris_gate_locked(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    real_prod: Production = test_setup["real_prod"]
    release_repo = test_setup["release_repo"]
    workspace_a = test_setup["workspace_a"]
    yt_repo = test_setup["yt_repo"]

    # Save connection with upload scope
    now = datetime.now(timezone.utc)
    conn = YouTubeConnection(
        workspace_id=workspace_a.workspace_id,
        user_id=test_setup["user_a"].user_id,
        channel_id="UC_connected_creator",
        channel_title="Real Creator Channel",
        avatar_url="",
        subscriber_count=50000,
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        scopes=[SCOPE_YOUTUBE_READONLY, SCOPE_YOUTUBE_UPLOAD],
        connected_at=now,
        last_sync_at=now,
    )
    import asyncio
    asyncio.run(yt_repo.save_connection(conn))

    # Overwrite review with FIX_REQUIRED
    locked_review = ReleaseReview(
        review_id="rev_locked",
        production_id=real_prod.production_id,
        verdict=ReleaseVerdict.FIX_REQUIRED,
        summary="Audio levels out of bounds.",
        issues=[],
        approved_for_release=False,
        created_at=now,
    )
    asyncio.run(release_repo.save_release_review(locked_review))

    resp = client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={
            "requested_privacy": "private",
            "made_for_kids": False,
            "contains_synthetic_media": False,
        },
    )
    assert resp.status_code == 400
    assert "Release Gate check failed" in resp.json()["detail"]


def test_publish_creates_auth_required_job_if_upload_scope_missing(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    real_prod: Production = test_setup["real_prod"]
    workspace_a = test_setup["workspace_a"]
    yt_repo = test_setup["yt_repo"]

    # Connect with read-only scopes only
    now = datetime.now(timezone.utc)
    conn = YouTubeConnection(
        workspace_id=workspace_a.workspace_id,
        user_id=test_setup["user_a"].user_id,
        channel_id="UC_connected_creator",
        channel_title="Real Creator Channel",
        avatar_url="",
        subscriber_count=50000,
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        scopes=[SCOPE_YOUTUBE_READONLY, SCOPE_ANALYTICS_READONLY],
        connected_at=now,
        last_sync_at=now,
    )
    import asyncio
    asyncio.run(yt_repo.save_connection(conn))

    resp = client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={
            "requested_privacy": "private",
            "made_for_kids": False,
            "contains_synthetic_media": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["job"]["status"] == "auth_required"
    assert data["has_upload_access"] is False
    assert "YouTube upload access required" in data["status_message"]


def test_publish_success_flow_and_idempotency(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    real_prod: Production = test_setup["real_prod"]
    workspace_a = test_setup["workspace_a"]
    yt_repo = test_setup["yt_repo"]
    fake_yt_client: FakeYouTubePublishClient = test_setup["fake_yt_client"]

    # Connect with upload scope
    now = datetime.now(timezone.utc)
    conn = YouTubeConnection(
        workspace_id=workspace_a.workspace_id,
        user_id=test_setup["user_a"].user_id,
        channel_id="UC_connected_creator",
        channel_title="Real Creator Channel",
        avatar_url="",
        subscriber_count=50000,
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        scopes=[SCOPE_YOUTUBE_READONLY, SCOPE_YOUTUBE_UPLOAD],
        connected_at=now,
        last_sync_at=now,
    )
    import asyncio
    asyncio.run(yt_repo.save_connection(conn))

    # 1. Initiate Publish
    resp1 = client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={
            "requested_privacy": "private",
            "made_for_kids": False,
            "contains_synthetic_media": True,
            "thumbnail_frame_ms": 15000,
        },
    )
    assert resp1.status_code == 200, resp1.text
    job_data1 = resp1.json()["job"]
    assert job_data1["publish_job_id"] != ""

    # Allow background task to finish in loop
    import time
    time.sleep(0.1)

    # 2. Poll Status
    status_resp = client.get(f"/api/productions/{real_prod.production_id}/publish")
    assert status_resp.status_code == 200
    data = status_resp.json()
    job = data["job"]
    assert job["status"] == "completed"
    assert job["youtube_video_id"] is not None
    assert job["youtube_url"] == f"https://youtu.be/{job['youtube_video_id']}"
    assert job["actual_privacy"] == "private"
    assert job["thumbnail_status"] == "completed"
    assert data["status_message"] == "Uploaded privately"

    # Verify Fake YouTube client received calls
    assert len(fake_yt_client.uploaded_videos) == 1
    assert job["youtube_video_id"] in fake_yt_client.thumbnails_set

    # 3. Idempotency Check: Calling publish again returns the SAME job
    resp2 = client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={
            "requested_privacy": "private",
            "made_for_kids": False,
            "contains_synthetic_media": True,
            "thumbnail_frame_ms": 15000,
        },
    )
    assert resp2.status_code == 200
    job_data2 = resp2.json()["job"]
    assert job_data2["publish_job_id"] == job_data1["publish_job_id"]
    assert len(fake_yt_client.uploaded_videos) == 1  # NO duplicate video created!


def test_publish_detects_privacy_audit_restriction(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    real_prod: Production = test_setup["real_prod"]
    workspace_a = test_setup["workspace_a"]
    yt_repo = test_setup["yt_repo"]

    # Configure fake client to simulate YouTube API audit restriction
    fake_client = FakeYouTubePublishClient(simulate_audit_restriction=True)
    set_youtube_publish_client(fake_client)

    now = datetime.now(timezone.utc)
    conn = YouTubeConnection(
        workspace_id=workspace_a.workspace_id,
        user_id=test_setup["user_a"].user_id,
        channel_id="UC_connected_creator",
        channel_title="Real Creator Channel",
        avatar_url="",
        subscriber_count=50000,
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        scopes=[SCOPE_YOUTUBE_READONLY, SCOPE_YOUTUBE_UPLOAD],
        connected_at=now,
        last_sync_at=now,
    )
    import asyncio
    asyncio.run(yt_repo.save_connection(conn))

    resp = client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={
            "requested_privacy": "public",
            "made_for_kids": False,
            "contains_synthetic_media": False,
        },
    )
    assert resp.status_code == 200

    import time
    time.sleep(0.1)

    status_resp = client.get(f"/api/productions/{real_prod.production_id}/publish")
    assert status_resp.status_code == 200
    data = status_resp.json()
    job = data["job"]
    assert job["status"] == "completed"
    assert job["requested_privacy"] == "public"
    assert job["actual_privacy"] == "private"
    assert job["audit_restriction_detected"] is True
    assert "YouTube restricted this API project to private uploads" in data["status_message"]


def test_publish_idor_security_rejection(test_setup: dict) -> None:
    app = test_setup["app"]
    real_prod: Production = test_setup["real_prod"]
    user_b = User(
        user_id="usr_intruder_99",
        email="intruder@example.com",
        display_name="Intruder",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Intrude with User B identity
    app.dependency_overrides[get_current_user] = lambda: user_b
    intruder_client = TestClient(app)

    # Prep
    prep_resp = intruder_client.get(f"/api/productions/{real_prod.production_id}/publish/prep")
    assert prep_resp.status_code == 403

    # Publish
    pub_resp = intruder_client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={"requested_privacy": "private"},
    )
    assert pub_resp.status_code == 403

    # Status
    status_resp = intruder_client.get(f"/api/productions/{real_prod.production_id}/publish")
    assert status_resp.status_code == 403
def test_publish_rejects_master_from_different_edl(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    real_prod: Production = test_setup["real_prod"]
    workspace_a = test_setup["workspace_a"]
    yt_repo = test_setup["yt_repo"]
    render_repo = test_setup["render_repo"]

    now = datetime.now(timezone.utc)
    conn = YouTubeConnection(
        workspace_id=workspace_a.workspace_id,
        user_id=test_setup["user_a"].user_id,
        channel_id="UC_connected_creator",
        channel_title="Real Creator Channel",
        avatar_url="",
        subscriber_count=50000,
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        scopes=[SCOPE_YOUTUBE_READONLY, SCOPE_YOUTUBE_UPLOAD],
        connected_at=now,
        last_sync_at=now,
    )
    import asyncio
    asyncio.run(yt_repo.save_connection(conn))

    # Overwrite master with a different EDL
    mismatched_master = RenderArtifact(
        artifact_id="art_wrong_edl_master",
        production_id=real_prod.production_id,
        edl_id="edl_old_zero_cut_wrong",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_test_01/productions/prod_real_01/renders/edl_old_zero_cut_wrong/master.mp4",
        duration_ms=113824,
        created_at=now,
    )
    asyncio.run(render_repo.save_render_artifact(mismatched_master))

    # Update release review to point to mismatched master
    release_repo = test_setup["release_repo"]
    review = ReleaseReview(
        review_id="rev_mismatched",
        production_id=real_prod.production_id,
        verdict=ReleaseVerdict.PASS,
        summary="Review on wrong master.",
        issues=[],
        approved_for_release=True,
        master_artifact_id="art_wrong_edl_master",
        packaging_proposal_id="pkg_real_01",
        edl_id="edl_old_zero_cut_wrong",
        created_at=now,
    )
    asyncio.run(release_repo.save_release_review(review))

    resp = client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={"requested_privacy": "private"},
    )
    assert resp.status_code == 400
    assert "belongs to EDL" in resp.json()["detail"] or "does not match active Master" in resp.json()["detail"]


def test_publish_rejects_stale_iris_review_when_proposal_version_is_newer(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    real_prod: Production = test_setup["real_prod"]
    workspace_a = test_setup["workspace_a"]
    yt_repo = test_setup["yt_repo"]
    pkg_repo = test_setup["pkg_repo"]
    release_repo = test_setup["release_repo"]

    now = datetime.now(timezone.utc)
    conn = YouTubeConnection(
        workspace_id=workspace_a.workspace_id,
        user_id=test_setup["user_a"].user_id,
        channel_id="UC_connected_creator",
        channel_title="Real Creator Channel",
        avatar_url="",
        subscriber_count=50000,
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        scopes=[SCOPE_YOUTUBE_READONLY, SCOPE_YOUTUBE_UPLOAD],
        connected_at=now,
        last_sync_at=now,
    )
    import asyncio
    asyncio.run(yt_repo.save_connection(conn))

    # Iris review was on version 1
    review = ReleaseReview(
        review_id="rev_v1",
        production_id=real_prod.production_id,
        verdict=ReleaseVerdict.PASS,
        summary="Iris passed v1",
        issues=[],
        approved_for_release=True,
        master_artifact_id="art_master_real",
        packaging_proposal_id="pkg_real_01",
        package_version=1,
        created_at=now,
    )
    asyncio.run(release_repo.save_release_review(review))

    # Proposal was updated to version 2
    real_pkg: PackagingProposal = test_setup["real_packaging"]
    prop_v2 = real_pkg.model_copy(
        update={
            "version": 2,
            "primary_title": "Updated Title V2",
            "description": "Updated description V2",
        }
    )
    asyncio.run(pkg_repo.save_packaging_proposal(prop_v2))
    resp = client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={"requested_privacy": "private"},
    )
    assert resp.status_code == 400
    assert "newer than Iris review" in resp.json()["detail"]


def test_publish_rejects_release_fingerprint_mismatch(test_setup: dict) -> None:
    client: TestClient = test_setup["client"]
    real_prod: Production = test_setup["real_prod"]
    workspace_a = test_setup["workspace_a"]
    yt_repo = test_setup["yt_repo"]
    release_repo = test_setup["release_repo"]

    now = datetime.now(timezone.utc)
    conn = YouTubeConnection(
        workspace_id=workspace_a.workspace_id,
        user_id=test_setup["user_a"].user_id,
        channel_id="UC_connected_creator",
        channel_title="Real Creator Channel",
        avatar_url="",
        subscriber_count=50000,
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        scopes=[SCOPE_YOUTUBE_READONLY, SCOPE_YOUTUBE_UPLOAD],
        connected_at=now,
        last_sync_at=now,
    )
    import asyncio
    asyncio.run(yt_repo.save_connection(conn))

    # Review has a fingerprint locked to a different hash
    review = ReleaseReview(
        review_id="rev_fp_test",
        production_id=real_prod.production_id,
        verdict=ReleaseVerdict.PASS,
        summary="Iris passed with locked fingerprint",
        issues=[],
        approved_for_release=True,
        master_artifact_id="art_master_real",
        packaging_proposal_id="pkg_real_01",
        package_version=1,
        release_fingerprint="0000000000000000000000000000000000000000000000000000000000000000",
        created_at=now,
    )
    asyncio.run(release_repo.save_release_review(review))

    resp = client.post(
        f"/api/productions/{real_prod.production_id}/publish",
        json={"requested_privacy": "private"},
    )
    assert resp.status_code == 400
    assert "release fingerprint mismatch" in resp.json()["detail"]
