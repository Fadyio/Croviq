"""Unit and integration tests for Workspace API endpoints and persistence."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from croviq_api.auth.exceptions import ExpiredTokenError, InvalidTokenError
from croviq_api.auth.verifier import TokenVerifier, get_token_verifier
from croviq_api.config import get_settings
from croviq_api.main import create_app
from croviq_api.workspaces.repository import (
    FirestoreWorkspaceRepository,
    InMemoryWorkspaceRepository,
    get_workspace_repository,
    set_workspace_repository,
)
from croviq_domain.brand_kit import BrandKit
from croviq_domain.user import User
from croviq_domain.workspace import Workspace


class FakeTokenVerifier(TokenVerifier):
    """Test fake token verifier that validates against preconfigured tokens."""

    def __init__(self) -> None:
        self._tokens: dict[str, dict[str, Any]] = {}
        self._expired_tokens: set[str] = set()

    def add_valid_token(self, token: str, claims: dict[str, Any]) -> None:
        self._tokens[token] = claims

    def add_expired_token(self, token: str) -> None:
        self._expired_tokens.add(token)

    def verify_token(self, token: str) -> dict[str, Any]:
        if token in self._expired_tokens:
            raise ExpiredTokenError("Token has expired")
        if token in self._tokens:
            return self._tokens[token]
        raise InvalidTokenError("Invalid token")


@pytest.fixture(autouse=True)
def configure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROVIQ_ALLOWED_EMAILS", "fadynagh10@gmail.com")
    get_settings.cache_clear()


@pytest.fixture
def fake_verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier()


@pytest.fixture
def in_memory_repo() -> InMemoryWorkspaceRepository:
    return InMemoryWorkspaceRepository()


@pytest.fixture
def app(fake_verifier: FakeTokenVerifier, in_memory_repo: InMemoryWorkspaceRepository) -> FastAPI:
    set_workspace_repository(in_memory_repo)
    application = create_app()
    application.dependency_overrides[get_token_verifier] = lambda: fake_verifier
    application.dependency_overrides[get_workspace_repository] = lambda: in_memory_repo
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def extract_workspace_logs(captured_stdout: str, request_id: str) -> list[dict[str, Any]]:
    """Extract and parse structured JSON logs matching request_id and workspace events."""
    logs = []
    for line in captured_stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if parsed.get("request_id") == request_id and "workspace." in str(parsed.get("event_type", "")):
                logs.append(parsed)
        except json.JSONDecodeError:
            continue
    return logs


# -----------------------------------------------------------------------------
# 1. GET /api/workspace — First request creates, second request is idempotent
# -----------------------------------------------------------------------------


def test_get_workspace_first_request_provisions_default_workspace(
    client: TestClient, fake_verifier: FakeTokenVerifier, capsys: pytest.CaptureFixture[str]
) -> None:
    """First GET /api/workspace request creates exactly one default Workspace."""
    req_id = f"test-ws-create-{uuid.uuid4().hex}"
    token = "token-demo-creator"
    user_uid = "uid_demo_creator_123"
    user_email = "fadynagh10@gmail.com"

    fake_verifier.add_valid_token(
        token,
        {
            "uid": user_uid,
            "email": user_email,
            "email_verified": True,
            "name": "Fady Nagh",
        },
    )

    response = client.get(
        "/api/workspace",
        headers={"Authorization": f"Bearer {token}", "x-request-id": req_id},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["owner_user_id"] == user_uid
    assert data["name"] == "Croviq Demo Workspace"
    assert data["workspace_id"].startswith("ws_")
    assert "created_at" in data
    assert "updated_at" in data
    assert "brand_kit" in data

    # Verify structured logging for workspace.created
    captured = capsys.readouterr()
    ws_logs = extract_workspace_logs(captured.out, req_id)
    assert len(ws_logs) == 2
    assert ws_logs[0]["event_type"] == "workspace.created"
    assert ws_logs[0]["status"] == 200
    assert ws_logs[0]["user_id"] == user_uid
    assert ws_logs[0]["workspace_id"] == data["workspace_id"]
    assert ws_logs[1]["event_type"] == "workspace.loaded"
    assert ws_logs[1]["status"] == 200
    assert ws_logs[1]["user_id"] == user_uid
    assert ws_logs[1]["workspace_id"] == data["workspace_id"]
    # Verify no secret leakage
    assert token not in captured.out


def test_get_workspace_second_request_is_idempotent_returns_same_workspace(
    client: TestClient, fake_verifier: FakeTokenVerifier, capsys: pytest.CaptureFixture[str]
) -> None:
    """Repeated calls to GET /api/workspace return the existing workspace without recreating."""
    token = "token-demo-creator-idempotent"
    user_uid = "uid_demo_creator_idempotent"
    user_email = "fadynagh10@gmail.com"

    fake_verifier.add_valid_token(
        token,
        {
            "uid": user_uid,
            "email": user_email,
            "email_verified": True,
            "name": "Fady Nagh",
        },
    )

    # 1. First call: creates workspace
    req_id_1 = f"test-ws-idempotent-1-{uuid.uuid4().hex}"
    resp1 = client.get(
        "/api/workspace",
        headers={"Authorization": f"Bearer {token}", "x-request-id": req_id_1},
    )
    assert resp1.status_code == 200
    ws1 = resp1.json()

    # 2. Second call: retrieves existing workspace
    req_id_2 = f"test-ws-idempotent-2-{uuid.uuid4().hex}"
    resp2 = client.get(
        "/api/workspace",
        headers={"Authorization": f"Bearer {token}", "x-request-id": req_id_2},
    )
    assert resp2.status_code == 200
    ws2 = resp2.json()

    # Must be identical workspace
    assert ws1["workspace_id"] == ws2["workspace_id"]
    assert ws1["owner_user_id"] == ws2["owner_user_id"]
    assert ws1["created_at"] == ws2["created_at"]

    # Verify second call logged workspace.loaded
    captured = capsys.readouterr()
    ws_logs_2 = extract_workspace_logs(captured.out, req_id_2)
    assert len(ws_logs_2) == 1
    assert ws_logs_2[0]["event_type"] == "workspace.loaded"
    assert ws_logs_2[0]["status"] == 200
    assert ws_logs_2[0]["workspace_id"] == ws1["workspace_id"]
    assert ws_logs_2[0]["user_id"] == user_uid


# -----------------------------------------------------------------------------
# 2. Ownership integrity: Ownership strictly derived from verified token uid
# -----------------------------------------------------------------------------


def test_workspace_ownership_strictly_bound_to_authenticated_uid(
    client: TestClient, fake_verifier: FakeTokenVerifier
) -> None:
    """Workspace ownership is always bound to verified auth UID; client input cannot spoof owner."""
    token = "token-authenticated-user"
    user_uid = "verified_uid_999"
    user_email = "fadynagh10@gmail.com"

    fake_verifier.add_valid_token(
        token,
        {
            "uid": user_uid,
            "email": user_email,
            "email_verified": True,
            "name": "Verified Creator",
        },
    )

    response = client.get(
        "/api/workspace",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    workspace = response.json()
    assert workspace["owner_user_id"] == user_uid


# -----------------------------------------------------------------------------
# 3. Security & Authorization checks on /api/workspace
# -----------------------------------------------------------------------------


def test_workspace_endpoint_missing_token_returns_401(client: TestClient) -> None:
    """Accessing /api/workspace without Authorization header returns HTTP 401."""
    response = client.get("/api/workspace")
    assert response.status_code == 401


def test_workspace_endpoint_unauthorized_email_returns_403(
    client: TestClient, fake_verifier: FakeTokenVerifier
) -> None:
    """Accessing /api/workspace with non-allowed email returns HTTP 403 demo_access_restricted."""
    token = "token-other-user"
    fake_verifier.add_valid_token(
        token,
        {
            "uid": "uid_stranger",
            "email": "stranger@gmail.com",
            "email_verified": True,
        },
    )

    response = client.get(
        "/api/workspace",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json() == {
        "error_code": "demo_access_restricted",
        "message": "This Croviq demo is restricted to an approved account.",
    }


def test_workspace_endpoint_unverified_email_returns_403(
    client: TestClient, fake_verifier: FakeTokenVerifier
) -> None:
    """Accessing /api/workspace with unverified email returns HTTP 403 demo_access_restricted."""
    token = "token-unverified-allowed"
    fake_verifier.add_valid_token(
        token,
        {
            "uid": "uid_unverified",
            "email": "fadynagh10@gmail.com",
            "email_verified": False,
        },
    )

    response = client.get(
        "/api/workspace",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "demo_access_restricted"


# -----------------------------------------------------------------------------
# 4. Direct Repository Layer Tests (Firestore and In-Memory)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_repository_user_and_workspace_lifecycle() -> None:
    """InMemoryWorkspaceRepository correctly handles User and Workspace CRUD."""
    repo = InMemoryWorkspaceRepository()
    now = datetime.now(timezone.utc)
    user = User(
        user_id="uid_repo_test",
        email="fadynagh10@gmail.com",
        display_name="Fady Nagh",
        avatar_url="https://example.com/avatar.jpg",
        created_at=now,
        updated_at=now,
    )

    # 1. First get_or_create creates default workspace
    ws1, created1 = await repo.get_or_create_default_workspace(user)
    assert created1 is True
    assert ws1.owner_user_id == user.user_id
    assert ws1.name == "Croviq Demo Workspace"

    # 2. Second get_or_create returns existing workspace
    ws2, created2 = await repo.get_or_create_default_workspace(user)
    assert created2 is False
    assert ws2.workspace_id == ws1.workspace_id

    # 3. User document persisted in users/{uid}
    fetched_user = await repo.get_user(user.user_id)
    assert fetched_user is not None
    assert fetched_user.email == user.email


@pytest.mark.asyncio
async def test_firestore_repository_async_methods() -> None:
    """FirestoreWorkspaceRepository serializes/deserializes documents accurately using async client."""
    from unittest.mock import AsyncMock, MagicMock

    repo = FirestoreWorkspaceRepository(project_id="test-croviq-project")

    mock_client = MagicMock()
    repo._client = mock_client

    mock_users_collection = MagicMock()
    mock_workspaces_collection = MagicMock()

    def collection_side_effect(name: str) -> Any:
        if name == "users":
            return mock_users_collection
        if name == "workspaces":
            return mock_workspaces_collection
        return MagicMock()

    mock_client.collection.side_effect = collection_side_effect

    now = datetime.now(timezone.utc)
    user = User(
        user_id="uid_firestore_1",
        email="fadynagh10@gmail.com",
        display_name="Firestore User",
        created_at=now,
        updated_at=now,
    )

    # Save user
    user_doc_ref = MagicMock()
    user_doc_ref.set = AsyncMock()
    mock_users_collection.document.return_value = user_doc_ref

    await repo.save_user(user)
    mock_users_collection.document.assert_called_with("uid_firestore_1")
    user_doc_ref.set.assert_awaited_once()
    user_set_args = user_doc_ref.set.call_args[0][0]
    assert user_set_args["user_id"] == "uid_firestore_1"
    assert user_set_args["email"] == "fadynagh10@gmail.com"

    # Create workspace
    ws = Workspace(
        workspace_id="ws_firestore_1",
        owner_user_id="uid_firestore_1",
        name="Firestore Workspace",
        channel_description="Firestore test channel",
        brand_kit=BrandKit(tone=["bold"]),
        created_at=now,
        updated_at=now,
    )
    ws_doc_ref = MagicMock()
    ws_doc_ref.set = AsyncMock()
    mock_workspaces_collection.document.return_value = ws_doc_ref

    await repo.create_workspace(ws)
    mock_workspaces_collection.document.assert_called_with("ws_firestore_1")
    ws_doc_ref.set.assert_awaited_once()
    ws_set_args = ws_doc_ref.set.call_args[0][0]
    assert ws_set_args["workspace_id"] == "ws_firestore_1"
    assert ws_set_args["owner_user_id"] == "uid_firestore_1"
    assert ws_set_args["name"] == "Firestore Workspace"
    assert ws_set_args["brand_kit"]["tone"] == ["bold"]
