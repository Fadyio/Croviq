import json
import uuid
from typing import Any
import pytest
from fastapi.testclient import TestClient

from croviq_api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def extract_request_logs(captured_stdout: str, request_id: str) -> list[dict[str, Any]]:
    """Extract and parse structured JSON logs matching request_id."""
    logs: list[dict[str, Any]] = []
    for line in captured_stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict) and parsed.get("request_id") == request_id:
                logs.append(parsed)
        except json.JSONDecodeError:
            continue
    return logs


def test_health_returns_200_and_correct_schema(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "croviq-api"
    assert isinstance(data["git_sha"], str)
    assert len(data["git_sha"]) > 0


def test_request_id_generated_when_missing(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id is not None
    assert len(request_id) > 0


def test_request_id_preserved_when_provided(client: TestClient) -> None:
    custom_id = f"custom-req-{uuid.uuid4().hex}"
    response = client.get("/health", headers={"x-request-id": custom_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_id


def test_structured_log_emitted_to_stdout(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    custom_id = "test-log-req-123"
    response = client.get("/health", headers={"x-request-id": custom_id})
    assert response.status_code == 200

    captured = capsys.readouterr()
    structured_logs = extract_request_logs(captured.out, custom_id)
    assert len(structured_logs) == 1, f"Expected 1 structured log for request, found {len(structured_logs)} in output: {captured.out}"
    log = structured_logs[0]

    assert log["request_id"] == custom_id
    assert log["service"] == "croviq-api"
    assert log["method"] == "GET"
    assert log["path"] == "/health"
    assert log["status"] == 200
    assert isinstance(log["latency_ms"], (int, float))
    assert log["latency_ms"] >= 0
    assert log["severity"] in ("INFO", "WARNING", "ERROR")
    assert isinstance(log["timestamp"], str)
    assert isinstance(log["environment"], str)
    assert isinstance(log["git_sha"], str)


def test_not_found_returns_404_and_structured_log(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    custom_id = "test-404-req-999"
    response = client.get("/non-existent-route", headers={"x-request-id": custom_id})
    assert response.status_code == 404
    assert response.headers.get("x-request-id") == custom_id

    captured = capsys.readouterr()
    structured_logs = extract_request_logs(captured.out, custom_id)
    assert len(structured_logs) == 1
    log = structured_logs[0]
    assert log["status"] == 404
    assert log["severity"] == "WARNING"


def test_environment_and_git_sha_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROVIQ_ENV", "production")
    monkeypatch.setenv("GIT_SHA", "testsha1234567890abcdef")
    from croviq_api.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.environment == "production"
    assert settings.git_sha == "testsha1234567890abcdef"
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "origin",
    [
        "https://app.croviq.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)
def test_cors_allowed_origins(client: TestClient, origin: str) -> None:
    # Preflight request
    preflight = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-request-id",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == origin

    # Simple GET request
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_rejected_for_unauthorized_origin(client: TestClient) -> None:
    unauthorized_origin = "https://unauthorized-domain.com"
    response = client.get("/health", headers={"Origin": unauthorized_origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None
