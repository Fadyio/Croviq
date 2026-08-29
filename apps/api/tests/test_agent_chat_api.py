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


def test_alex_chat_answers_simple_greeting(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    resp = client.post(
        "/api/workspace/agents/alex/chat",
        headers=headers,
        json={"message": "hi"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"
    assert len(data["content"]) > 10
    assert "alex" in data["content"].lower() or "channel" in data["content"].lower() or "croviq" in data["content"].lower()


def test_alex_chat_topic_recommendation_and_prompt_override(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    # 1. Save a custom prompt override
    custom_instruction = "When answering analytical questions, begin with EVIDENCE."
    save_resp = client.put(
        "/api/workspace/agent-settings/prompts/alex",
        headers=headers,
        json={"prompt_text": f"You are Alex. {custom_instruction}"},
    )
    assert save_resp.status_code == 200

    # 2. Ask what to make next
    resp = client.post(
        "/api/workspace/agents/alex/chat",
        headers=headers,
        json={"message": "What should I make next?"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"
    assert "opportunity" in data["content"].lower() or "recommend" in data["content"].lower() or "evidence" in data["content"].lower()
    assert any(t["tool_name"] == "channel_interest_profile_match" for t in data.get("tool_executions", []))

    # 3. Reset prompt back to default
    reset_resp = client.post(
        "/api/workspace/agent-settings/prompts/alex/reset",
        headers=headers,
    )
    assert reset_resp.status_code == 200

def test_clear_agent_chat_history(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    # 1. Send a message to ensure history exists
    client.post(
        "/api/workspace/agents/alex/chat",
        headers=headers,
        json={"message": "hello alex"},
    )
    hist_before = client.get("/api/workspace/agents/alex/chat", headers=headers)
    assert hist_before.status_code == 200
    assert len(hist_before.json()["messages"]) > 0

    # 2. Clear conversation
    clear_resp = client.delete("/api/workspace/agents/alex/chat", headers=headers)
    assert clear_resp.status_code == 200
    assert clear_resp.json()["agent_id"] == "alex"
    assert clear_resp.json()["messages"] == []

    # 3. Verify history is empty
    hist_after = client.get("/api/workspace/agents/alex/chat", headers=headers)
    assert hist_after.status_code == 200
    assert hist_after.json()["messages"] == []


def test_latest_video_selection_provenance_and_shuffled_ordering(client: TestClient) -> None:
    headers = {"Authorization": "Bearer creator-token"}
    resp = client.post(
        "/api/workspace/agents/alex/chat",
        headers=headers,
        json={"message": "How did my last video perform?"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "assistant"
    tool_execs = data.get("tool_executions", [])
    inspection_tool = next((t for t in tool_execs if t["tool_name"] == "channel_analytics_inspection"), None)
    assert inspection_tool is not None
    assert inspection_tool["video_id"] == "vid_syn_100"
    assert inspection_tool["title"] == "Google GenAI SDK Tutorial for Beginners (Part 5)"
    assert inspection_tool["published_at"] is not None
    assert inspection_tool["source_provider"] == "sample"
    assert inspection_tool["channel_median_views"] > 0
    assert inspection_tool["channel_median_retention"] > 0


def test_bounded_conversation_store_eviction_and_isolation() -> None:
    from croviq_api.workspaces.chat_service import BoundedConversationStore

    store = BoundedConversationStore(max_messages=5, max_chars=50, ttl_hours=1)
    ws_id = "ws_test_bound"
    agent_id = "alex"
    user_a = "user_a"
    user_b = "user_b"

    # 1. Test user isolation
    store.append_message(ws_id, agent_id, "user", "Message from user A", user_id=user_a)
    assert len(store.get_history(ws_id, agent_id, user_id=user_a)) == 1
    assert len(store.get_history(ws_id, agent_id, user_id=user_b)) == 0

    # 2. Test max_chars bounding
    long_content = "A" * 100
    msg = store.append_message(ws_id, agent_id, "user", long_content, user_id=user_a)
    assert len(msg["content"]) == 50

    # 3. Test FIFO message eviction (cap=5)
    for i in range(10):
        store.append_message(ws_id, agent_id, "user", f"msg {i}", user_id=user_a)

    hist = store.get_history(ws_id, agent_id, user_id=user_a)
    assert len(hist) == 5
    assert hist[-1]["content"] == "msg 9"
    assert hist[0]["content"] == "msg 5"
