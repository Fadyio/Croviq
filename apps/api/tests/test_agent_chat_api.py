"""Tests for Agent Chat API endpoints."""

from typing import Any
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from croviq_api.auth.exceptions import InvalidTokenError
from croviq_api.auth.verifier import TokenVerifier, get_token_verifier
from croviq_api.config import get_settings
from croviq_api.main import create_app


class FakeTokenVerifier(TokenVerifier):
    def __init__(self) -> None:
        self.tokens: dict[str, dict[str, Any]] = {}

    def verify_token(self, token: str) -> dict[str, Any]:
        try:
            return self.tokens[token]
        except KeyError as exc:
            raise InvalidTokenError("Invalid token") from exc


@pytest.fixture(autouse=True)
def configure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROVIQ_ALLOWED_EMAILS", "creator@example.com")
    get_settings.cache_clear()


@pytest.fixture
def verifier() -> FakeTokenVerifier:
    verifier = FakeTokenVerifier()
    verifier.tokens["creator-token"] = {
        "uid": "creator-1",
        "email": "creator@example.com",
        "name": "Creator",
    }
    return verifier


@pytest.fixture
def app(verifier: FakeTokenVerifier) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_token_verifier] = lambda: verifier
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_alex_chat_answers_last_video_query_with_tools(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    resp = client.post(
        "/api/workspace/agents/alex/chat",
        headers=headers,
        json={"message": "How did my last video perform?"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "role" in data
    assert data["role"] == "assistant"
    assert "latest" in data["content"].lower() or "video" in data["content"].lower()
    assert len(data["tool_executions"]) >= 1
    assert data["structured_artifact"] is not None


def test_alex_chat_runs_quantitative_analysis(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    resp = client.post(
        "/api/workspace/agents/alex/chat",
        headers=headers,
        json={"message": "Calculate the correlation between demo timing and retention."},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "correlation" in data["content"].lower() or "retention" in data["content"].lower()
    assert any(t["tool_name"] == "python_code_execution" for t in data["tool_executions"])


def test_alex_chat_cadence_scenario_analysis(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    resp = client.post(
        "/api/workspace/agents/alex/chat",
        headers=headers,
        json={"message": "What if I upload every week for the next 90 days?"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "subscribers" in data["content"].lower()
    assert any(t["tool_name"] == "scenario_projection_modeling" for t in data["tool_executions"])


def test_leo_and_iris_chat_endpoints(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    leo_resp = client.post(
        "/api/workspace/agents/leo/chat",
        headers=headers,
        json={"message": "Can you tighten the intro and find a Short?"},
    )
    assert leo_resp.status_code == 200
    assert "Leo" in leo_resp.json()["content"]

    iris_resp = client.post(
        "/api/workspace/agents/iris/chat",
        headers=headers,
        json={"message": "Is this video ready for release?"},
    )
    assert iris_resp.status_code == 200
    assert "Iris" in iris_resp.json()["content"]


def test_agent_chat_history_persists(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    hist_resp = client.get("/api/workspace/agents/alex/chat", headers=headers)
    assert hist_resp.status_code == 200
    data = hist_resp.json()
    assert data["agent_id"] == "alex"
    assert len(data["messages"]) >= 2
