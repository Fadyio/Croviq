import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from croviq_api.auth.dependencies import get_current_user
from croviq_api.auth.principal import AuthenticatedPrincipal
from croviq_api.config import Settings
from croviq_api.main import create_app
from croviq_api.media.dependencies import get_fake_media_storage, get_media_storage
from croviq_api.productions.repository import (
    InMemoryProductionRepository,
    get_production_repository,
    set_production_repository,
)
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    get_workspace_repository,
    set_workspace_repository,
)
from croviq_domain.production import (
    MAX_UPLOAD_SIZE_BYTES,
    ProductionStatus,
    SourceMediaStatus,
)
from croviq_domain.user import User


@pytest.fixture
def test_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="test_user_001",
        email="demo@croviq.app",
        display_name="Demo Creator",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def unauthorized_user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        user_id="unauth_user_999",
        email="hacker@evil.com",
        display_name="Unauthorized User",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def app_and_client(test_user: User):
    in_memory_ws_repo = InMemoryWorkspaceRepository()
    in_memory_prod_repo = InMemoryProductionRepository()
    fake_storage = get_fake_media_storage()
    fake_storage.clear()

    set_workspace_repository(in_memory_ws_repo)
    set_production_repository(in_memory_prod_repo)

    app = create_app()

    # Override auth dependency to return test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_workspace_repository] = lambda: in_memory_ws_repo
    app.dependency_overrides[get_production_repository] = lambda: in_memory_prod_repo
    app.dependency_overrides[get_media_storage] = lambda: fake_storage

    client = TestClient(app)
    return client, in_memory_ws_repo, in_memory_prod_repo, fake_storage


def test_create_upload_success(app_and_client, test_user):
    client, ws_repo, prod_repo, fake_storage = app_and_client

    payload = {
        "filename": "demo_video.mp4",
        "content_type": "video/mp4",
        "size_bytes": 100_000_000,
        "channel_id": "croviq_syn_ai_eng_01",
    }

    response = client.post("/api/uploads", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "production_id" in data
    assert "upload_id" in data
    assert "upload_url" in data
    assert data["method"] == "PUT"
    assert data["required_headers"] == {"Content-Type": "video/mp4"}
    assert "mock_v4_signature" in data["upload_url"]
    assert "expires_at" in data

    # Verify Production in repository
    prod = prod_repo._productions[data["production_id"]]
    assert prod.status == ProductionStatus.PENDING
    assert prod.owner_user_id == test_user.user_id
    assert prod.channel_id == "croviq_syn_ai_eng_01"
    assert prod.source_media is not None
    assert prod.source_media.upload_id == data["upload_id"]
    assert prod.source_media.status == SourceMediaStatus.PENDING
    assert prod.source_media.original_filename == "demo_video.mp4"
    assert prod.source_media.size_bytes == 100_000_000

    # Ensure signed URL is NOT persisted in domain model
    assert not hasattr(prod.source_media, "upload_url")
    prod_dict = prod_repo.production_to_dict(prod)
    assert "upload_url" not in prod_dict
    assert "upload_url" not in prod_dict["source_media"]


def test_create_upload_unauthenticated():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/uploads",
        json={
            "filename": "demo.mp4",
            "content_type": "video/mp4",
            "size_bytes": 50_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    # Unauthenticated requests without token fail with 401
    assert response.status_code == 401


def test_create_upload_restricted_user():
    app = create_app()
    from croviq_api.auth.verifier import TokenVerifier, get_token_verifier

    class FakeVerifier(TokenVerifier):
        def verify_token(self, token: str):
            return {
                "uid": "unauth_001",
                "email": "unauth@croviq.app",
                "name": "Unauth",
            }

    app.dependency_overrides[get_token_verifier] = lambda: FakeVerifier()

    with patch(
        "croviq_api.auth.dependencies.get_settings",
        return_value=Settings(),
    ) as mock_settings:
        mock_settings.return_value.allowed_emails = ["allowed@croviq.app"]
        client = TestClient(app)
        response = client.post(
            "/api/uploads",
            headers={"Authorization": "Bearer fake_token"},
            json={
                "filename": "demo.mp4",
                "content_type": "video/mp4",
                "size_bytes": 50_000_000,
                "channel_id": "croviq_syn_ai_eng_01",
            },
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "demo_access_restricted"

def test_create_upload_invalid_mime_type(app_and_client):
    client, _, _, _ = app_and_client

    response = client.post(
        "/api/uploads",
        json={
            "filename": "image.png",
            "content_type": "image/png",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert response.status_code == 400
    assert "Unsupported content type" in response.json()["detail"]


def test_create_upload_mismatched_extension(app_and_client):
    client, _, _, _ = app_and_client

    response = client.post(
        "/api/uploads",
        json={
            "filename": "movie.mp4",
            "content_type": "video/webm",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_create_upload_boundary_1gb_accepted(app_and_client):
    client, _, _, _ = app_and_client

    response = client.post(
        "/api/uploads",
        json={
            "filename": "max_boundary.mp4",
            "content_type": "video/mp4",
            "size_bytes": 1_073_741_824,  # Exactly 1 GB (1,073,741,824 bytes)
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "upload_url" in data
    assert "upload_id" in data


def test_create_upload_boundary_over_1gb_rejected(app_and_client):
    client, _, _, _ = app_and_client

    response = client.post(
        "/api/uploads",
        json={
            "filename": "over_boundary.mp4",
            "content_type": "video/mp4",
            "size_bytes": 1_073_741_825,  # 1 GB + 1 byte (1,073,741,825 bytes)
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert response.status_code == 400
    assert "exceeds maximum allowed size of 1073741824 bytes (1 GB)" in response.json()["detail"]


def test_create_upload_path_traversal_sanitization(app_and_client):
    client, _, prod_repo, _ = app_and_client

    response = client.post(
        "/api/uploads",
        json={
            "filename": "../../../etc/passwd.mp4",
            "content_type": "video/mp4",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert response.status_code == 201
    data = response.json()
    prod = prod_repo._productions[data["production_id"]]
    assert prod.source_media.gcs_object.endswith("passwd.mp4")
    assert ".." not in prod.source_media.gcs_object


def test_complete_upload_success(app_and_client):
    client, _, prod_repo, fake_storage = app_and_client

    # 1. Create upload
    create_resp = client.post(
        "/api/uploads",
        json={
            "filename": "raw_capture.mov",
            "content_type": "video/quicktime",
            "size_bytes": 250_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    upload_id = create_data["upload_id"]
    prod_id = create_data["production_id"]

    # 2. Simulate client directly uploading to storage
    prod = prod_repo._productions[prod_id]
    fake_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=250_000_000,
        content_type="video/quicktime",
    )

    # 3. Call complete endpoint
    complete_resp = client.post(f"/api/uploads/{upload_id}/complete")
    assert complete_resp.status_code == 200
    comp_data = complete_resp.json()

    assert comp_data["production_id"] == prod_id
    assert comp_data["status"] == "uploaded"
    assert comp_data["source_media"]["status"] == "uploaded"
    assert comp_data["source_media"]["uploaded_at"] is not None


def test_complete_upload_idempotency(app_and_client):
    client, _, prod_repo, fake_storage = app_and_client

    # Create & complete
    create_resp = client.post(
        "/api/uploads",
        json={
            "filename": "sample.mp4",
            "content_type": "video/mp4",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    upload_id = create_resp.json()["upload_id"]
    prod_id = create_resp.json()["production_id"]

    prod = prod_repo._productions[prod_id]
    fake_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=10_000_000,
        content_type="video/mp4",
    )

    resp1 = client.post(f"/api/uploads/{upload_id}/complete")
    assert resp1.status_code == 200

    # Repeat complete call -> must return same uploaded production idempotently
    resp2 = client.post(f"/api/uploads/{upload_id}/complete")
    assert resp2.status_code == 200
    assert resp2.json()["production_id"] == prod_id
    assert resp2.json()["source_media"]["status"] == "uploaded"


def test_complete_upload_boundary_1gb_accepted(app_and_client):
    client, _, prod_repo, fake_storage = app_and_client

    # Create upload at 1 GB
    create_resp = client.post(
        "/api/uploads",
        json={
            "filename": "full_boundary.mp4",
            "content_type": "video/mp4",
            "size_bytes": 1_073_741_824,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    upload_id = create_data["upload_id"]
    prod_id = create_data["production_id"]

    prod = prod_repo._productions[prod_id]
    fake_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=1_073_741_824,
        content_type="video/mp4",
    )

    comp_resp = client.post(f"/api/uploads/{upload_id}/complete")
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["source_media"]["size_bytes"] == 1_073_741_824
    assert comp_data["source_media"]["status"] == "uploaded"


def test_complete_upload_boundary_over_1gb_rejected(app_and_client):
    client, _, prod_repo, fake_storage = app_and_client

    # Create initial upload within limit
    create_resp = client.post(
        "/api/uploads",
        json={
            "filename": "spoofed_boundary.mp4",
            "content_type": "video/mp4",
            "size_bytes": 100_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    upload_id = create_data["upload_id"]
    prod_id = create_data["production_id"]

    # Simulate GCS object uploaded with size > 1 GB
    prod = prod_repo._productions[prod_id]
    fake_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=1_073_741_825,
        content_type="video/mp4",
    )

    comp_resp = client.post(f"/api/uploads/{upload_id}/complete")
    assert comp_resp.status_code == 400
    assert "exceeds maximum limit of 1073741824 bytes" in comp_resp.json()["detail"]

def test_complete_upload_missing_gcs_object(app_and_client):
    client, _, _, fake_storage = app_and_client

    # Create upload without uploading bytes to GCS
    create_resp = client.post(
        "/api/uploads",
        json={
            "filename": "missing.mp4",
            "content_type": "video/mp4",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    upload_id = create_resp.json()["upload_id"]

    complete_resp = client.post(f"/api/uploads/{upload_id}/complete")
    assert complete_resp.status_code == 400
    assert "not found in storage" in complete_resp.json()["detail"]


def test_complete_upload_not_found(app_and_client):
    client, _, _, _ = app_and_client

    response = client.post("/api/uploads/non_existent_upload_id/complete")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_complete_upload_forbidden_different_owner(app_and_client, unauthorized_user):
    client, _, prod_repo, fake_storage = app_and_client

    create_resp = client.post(
        "/api/uploads",
        json={
            "filename": "secret.mp4",
            "content_type": "video/mp4",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    upload_id = create_resp.json()["upload_id"]

    # Switch authenticated user override to unauthorized user
    app = client.app
    app.dependency_overrides[get_current_user] = lambda: unauthorized_user

    complete_resp = client.post(f"/api/uploads/{upload_id}/complete")
    assert complete_resp.status_code == 403
    assert "do not own" in complete_resp.json()["detail"]


def test_list_productions(app_and_client):
    client, _, _, _ = app_and_client

    # Create 2 uploads
    client.post(
        "/api/uploads",
        json={
            "filename": "v1.mp4",
            "content_type": "video/mp4",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    client.post(
        "/api/uploads",
        json={
            "filename": "v2.mp4",
            "content_type": "video/mp4",
            "size_bytes": 20_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )

    list_resp = client.get("/api/productions")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["productions"]) == 2


def test_get_production_playback_success(app_and_client):
    client, _, prod_repo, fake_storage = app_and_client

    create_resp = client.post(
        "/api/uploads",
        json={
            "filename": "test_video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    assert create_resp.status_code == 201
    upload_data = create_resp.json()
    upload_id = upload_data["upload_id"]
    production_id = upload_data["production_id"]

    prod = prod_repo._productions[production_id]
    fake_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=10_000_000,
        content_type="video/mp4",
    )

    comp_resp = client.post(f"/api/uploads/{upload_id}/complete")
    assert comp_resp.status_code == 200

    playback_resp = client.get(f"/api/productions/{production_id}/playback")
    assert playback_resp.status_code == 200
    playback_data = playback_resp.json()
    assert playback_data["production_id"] == production_id
    assert "token=mock_v4_signed_read" in playback_data["playback_url"]
    assert "expires_at" in playback_data


def test_get_production_playback_forbidden_for_other_user(app_and_client, unauthorized_user):
    client, _, prod_repo, fake_storage = app_and_client

    create_resp = client.post(
        "/api/uploads",
        json={
            "filename": "secret_video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 10_000_000,
            "channel_id": "croviq_syn_ai_eng_01",
        },
    )
    upload_data = create_resp.json()
    upload_id = upload_data["upload_id"]
    production_id = upload_data["production_id"]

    prod = prod_repo._productions[production_id]
    fake_storage.simulate_uploaded_object(
        bucket=prod.source_media.gcs_bucket,
        object_name=prod.source_media.gcs_object,
        size_bytes=10_000_000,
        content_type="video/mp4",
    )
    client.post(f"/api/uploads/{upload_id}/complete")

    app = client.app
    app.dependency_overrides[get_current_user] = lambda: unauthorized_user

    playback_resp = client.get(f"/api/productions/{production_id}/playback")
    assert playback_resp.status_code == 403
    assert "do not own" in playback_resp.json()["detail"]
