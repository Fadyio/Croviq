import json
import uuid
from datetime import datetime, timezone
from typing import Any
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from croviq_api.main import create_app
from croviq_api.auth.verifier import TokenVerifier, get_token_verifier
from croviq_api.auth.exceptions import InvalidTokenError, ExpiredTokenError


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


@pytest.fixture
def fake_verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier()


@pytest.fixture
def app(fake_verifier: FakeTokenVerifier) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_token_verifier] = lambda: fake_verifier
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def extract_auth_logs(captured_stdout: str, request_id: str) -> list[dict[str, Any]]:
    """Extract and parse structured JSON logs matching request_id and auth events."""
    logs = []
    for line in captured_stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if parsed.get("request_id") == request_id and "auth." in str(parsed.get("event_type", "")):
                logs.append(parsed)
        except json.JSONDecodeError:
            continue
    return logs


def test_health_remains_public_without_auth(client: TestClient) -> None:
    """Public /api/health endpoint must remain accessible without Authorization header."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_me_missing_authorization_header_returns_401(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing Authorization header must return HTTP 401 Unauthorized."""
    req_id = f"test-missing-auth-{uuid.uuid4().hex}"
    response = client.get("/api/auth/me", headers={"x-request-id": req_id})
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "missing" in data["detail"].lower() or "unauthorized" in data["detail"].lower()

    # Verify structured logs
    captured = capsys.readouterr()
    auth_logs = extract_auth_logs(captured.out, req_id)
    assert len(auth_logs) == 1
    log = auth_logs[0]
    assert log["event_type"] == "auth.verification_failed"
    assert log["status"] == 401
    assert log["error_code"] == "missing_authorization_header"
    assert "authenticated_user_id" not in log or log["authenticated_user_id"] is None


@pytest.mark.parametrize(
    "malformed_header",
    [
        "Basic dXNlcjpwYXNz",
        "Bearer",
        "Bearer   ",
        "Token some-token",
        "Bearer token1 token2",
        "bearer_no_space",
    ],
)
def test_auth_me_malformed_bearer_header_returns_401(
    client: TestClient, malformed_header: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Malformed Authorization header must return HTTP 401 Unauthorized."""
    req_id = f"test-malformed-{uuid.uuid4().hex}"
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": malformed_header, "x-request-id": req_id},
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data

    captured = capsys.readouterr()
    auth_logs = extract_auth_logs(captured.out, req_id)
    assert len(auth_logs) == 1
    log = auth_logs[0]
    assert log["event_type"] == "auth.verification_failed"
    assert log["status"] == 401
    assert log["error_code"] == "malformed_authorization_header"

    # Ensure no token leakage
    raw_output = captured.out
    assert malformed_header not in raw_output
    if " " in malformed_header:
        token_part = malformed_header.split(" ", 1)[1].strip()
        if token_part:
            assert token_part not in raw_output


def test_auth_me_invalid_token_returns_401(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Invalid token must return HTTP 401 Unauthorized."""
    req_id = f"test-invalid-token-{uuid.uuid4().hex}"
    raw_token = "invalid-token-xyz-12345"
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {raw_token}", "x-request-id": req_id},
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data

    captured = capsys.readouterr()
    auth_logs = extract_auth_logs(captured.out, req_id)
    assert len(auth_logs) == 1
    log = auth_logs[0]
    assert log["event_type"] == "auth.verification_failed"
    assert log["status"] == 401
    assert log["error_code"] == "invalid_token"

    # Ensure no token leakage
    assert raw_token not in captured.out


def test_auth_me_expired_token_returns_401(
    client: TestClient, fake_verifier: FakeTokenVerifier, capsys: pytest.CaptureFixture[str]
) -> None:
    """Expired token must return HTTP 401 Unauthorized."""
    req_id = f"test-expired-token-{uuid.uuid4().hex}"
    expired_token = "expired-token-jwt-999"
    fake_verifier.add_expired_token(expired_token)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}", "x-request-id": req_id},
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data

    captured = capsys.readouterr()
    auth_logs = extract_auth_logs(captured.out, req_id)
    assert len(auth_logs) == 1
    log = auth_logs[0]
    assert log["event_type"] == "auth.verification_failed"
    assert log["status"] == 401
    assert log["error_code"] == "expired_token"

    # Ensure no token leakage
    assert expired_token not in captured.out


def test_auth_me_valid_token_returns_canonical_user_200(
    client: TestClient, fake_verifier: FakeTokenVerifier, capsys: pytest.CaptureFixture[str]
) -> None:
    """Valid token returns HTTP 200 with canonical User entity matching verified claims."""
    req_id = f"test-valid-user-{uuid.uuid4().hex}"
    valid_token = "valid-token-jwt-secret-xyz"
    user_uid = "firebase_user_abc123"
    user_email = "alex@example.com"
    user_name = "Alex Developer"
    user_picture = "https://lh3.googleusercontent.com/a/photo.jpg"

    claims = {
        "uid": user_uid,
        "email": user_email,
        "name": user_name,
        "picture": user_picture,
        "auth_time": int(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()),
    }
    fake_verifier.add_valid_token(valid_token, claims)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {valid_token}", "x-request-id": req_id},
    )
    assert response.status_code == 200
    user_data = response.json()

    assert user_data["user_id"] == user_uid
    assert user_data["email"] == user_email
    assert user_data["display_name"] == user_name
    assert user_data["avatar_url"] == user_picture
    assert "created_at" in user_data
    assert "updated_at" in user_data

    captured = capsys.readouterr()
    auth_logs = extract_auth_logs(captured.out, req_id)
    assert len(auth_logs) == 1
    log = auth_logs[0]
    assert log["event_type"] == "auth.verification_succeeded"
    assert log["status"] == 200
    assert log["authenticated_user_id"] == user_uid

    # Verify no token leakage
    assert valid_token not in captured.out


def test_auth_me_optional_profile_fields_handling(
    client: TestClient, fake_verifier: FakeTokenVerifier
) -> None:
    """Handle tokens with missing optional profile fields (name, picture)."""
    valid_token = "token-minimal-claims"
    user_uid = "user_minimal_999"
    user_email = "minimal@example.com"

    claims = {
        "uid": user_uid,
        "email": user_email,
        # No 'name' and no 'picture'
    }
    fake_verifier.add_valid_token(valid_token, claims)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200
    user_data = response.json()

    assert user_data["user_id"] == user_uid
    assert user_data["email"] == user_email
    assert user_data["display_name"] == "minimal"  # Derived from email prefix
    assert user_data["avatar_url"] is None
