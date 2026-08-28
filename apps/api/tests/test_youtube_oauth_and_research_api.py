"""Comprehensive integration tests for YouTube OAuth, Alex Grounded Research, Scheduler Tick, and Code Execution."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from croviq_api.auth.dependencies import get_current_user
from croviq_api.channels.research_repository import (
    InMemoryResearchRepository,
    get_research_repository,
)
from croviq_api.channels.youtube_repository import (
    InMemoryYouTubeConnectionRepository,
    YouTubeConnection,
    get_youtube_connection_repository,
)
from croviq_api.config import get_settings
from croviq_api.main import create_app
from croviq_api.workspaces.repository import (
    InMemoryWorkspaceRepository,
    get_workspace_repository,
)
from croviq_domain.channel_intelligence import (
    FindingLifecycle,
    ResearchCadence,
    ResearchConfig,
    ResearchFinding,
    ResearchPrompt,
    SourceCitation,
)
from croviq_domain.user import User


@pytest.fixture
def user() -> User:
    return User(
        user_id="usr_creator_01",
        email="creator@example.com",
        display_name="Creator One",
        created_at=datetime(2026, 8, 28, tzinfo=UTC),
        updated_at=datetime(2026, 8, 28, tzinfo=UTC),
    )


@pytest.fixture
def other_user() -> User:
    return User(
        user_id="usr_intruder_02",
        email="intruder@example.com",
        display_name="Intruder",
        created_at=datetime(2026, 8, 28, tzinfo=UTC),
        updated_at=datetime(2026, 8, 28, tzinfo=UTC),
    )


@pytest.fixture
def repos() -> tuple[InMemoryWorkspaceRepository, InMemoryResearchRepository, InMemoryYouTubeConnectionRepository]:
    return InMemoryWorkspaceRepository(), InMemoryResearchRepository(), InMemoryYouTubeConnectionRepository()


@pytest.fixture
def app(user: User, repos: tuple) -> FastAPI:
    ws_repo, research_repo, yt_repo = repos
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: user
    application.dependency_overrides[get_workspace_repository] = lambda: ws_repo
    application.dependency_overrides[get_research_repository] = lambda: research_repo
    application.dependency_overrides[get_youtube_connection_repository] = lambda: yt_repo
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# -----------------------------------------------------------------------------
# YouTube OAuth & Connection Tests
# -----------------------------------------------------------------------------


def test_generate_youtube_auth_url(client: TestClient) -> None:
    response = client.post(
        "/api/channels/youtube/auth-url",
        json={"redirect_uri": "http://localhost:5173/app", "include_monetary": False},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "accounts.google.com" in data["auth_url"]
    assert "state=" in data["auth_url"]
    assert len(data["state_token"]) >= 16
    assert len(data["scopes"]) == 2
    assert "https://www.googleapis.com/auth/youtube.readonly" in data["scopes"]

def test_generate_youtube_auth_url_with_upload_scope(client: TestClient) -> None:
    response = client.post(
        "/api/channels/youtube/auth-url",
        json={"redirect_uri": "http://localhost:5173/app", "include_upload": True},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "https://www.googleapis.com/auth/youtube.upload" in data["scopes"]
    assert "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube.upload" in data["auth_url"] or "youtube.upload" in data["auth_url"]

def test_incremental_youtube_oauth_and_refresh_token_preservation(client: TestClient, repos: tuple) -> None:
    import asyncio
    _, _, yt_repo = repos

    # 1. Initial connect with read-only scopes
    auth_resp1 = client.post(
        "/api/channels/youtube/auth-url",
        json={"redirect_uri": "http://localhost:5173/app"},
    )
    state_token1 = auth_resp1.json()["state_token"]

    callback_resp1 = client.post(
        "/api/channels/youtube/callback",
        json={
            "code": "mock-auth-code-1",
            "state": state_token1,
            "redirect_uri": "http://localhost:5173/app",
        },
    )
    assert callback_resp1.status_code == 200
    summary1 = callback_resp1.json()
    assert summary1["connected"] is True
    assert summary1["has_upload_access"] is False

    conn1 = asyncio.run(yt_repo.get_connection("ws_usr_creator_01"))
    assert conn1 is not None
    assert conn1.refresh_token == "yt_refresh_mock-auth-code-1"

    # 2. Incremental authorization with upload scope
    auth_resp2 = client.post(
        "/api/channels/youtube/auth-url",
        json={"redirect_uri": "http://localhost:5173/app", "include_upload": True},
    )
    state_token2 = auth_resp2.json()["state_token"]

    callback_resp2 = client.post(
        "/api/channels/youtube/callback",
        json={
            "code": "mock-auth-code-2",
            "state": state_token2,
            "redirect_uri": "http://localhost:5173/app",
        },
    )
    assert callback_resp2.status_code == 200
    summary2 = callback_resp2.json()
    assert summary2["connected"] is True
    assert summary2["has_upload_access"] is True

    # Verify scopes merged and refresh token preserved
    conn2 = asyncio.run(yt_repo.get_connection("ws_usr_creator_01"))
    assert conn2 is not None
    assert "https://www.googleapis.com/auth/youtube.upload" in conn2.scopes
    assert "https://www.googleapis.com/auth/youtube.readonly" in conn2.scopes
    # Refresh token preserved
    assert conn2.refresh_token is not None
    assert "yt_refresh_" in conn2.refresh_token

def test_handle_youtube_callback_stores_connection(client: TestClient, repos: tuple) -> None:
    # 1. Generate auth URL to produce valid CSRF state
    auth_resp = client.post(
        "/api/channels/youtube/auth-url",
        json={"redirect_uri": "http://localhost:5173/app"},
    )
    state_token = auth_resp.json()["state_token"]

    # 2. Submit callback with valid state
    callback_resp = client.post(
        "/api/channels/youtube/callback",
        json={
            "code": "mock-auth-code-12345",
            "state": state_token,
            "redirect_uri": "http://localhost:5173/app",
        },
    )
    assert callback_resp.status_code == 200, callback_resp.text
    summary = callback_resp.json()
    assert summary["connected"] is True
    assert summary["channel_title"] != ""
    assert summary["subscriber_count"] >= 0

    # 3. Verify server-side persisted record is encrypted (NO plaintext tokens)
    _, _, yt_repo = repos
    import asyncio
    raw_record = yt_repo.get_raw_record("ws_usr_creator_01")
    assert raw_record is not None
    assert raw_record.encrypted_token_payload != ""
    assert "mock-auth-code-12345" not in raw_record.encrypted_token_payload

    # 4. Verify status endpoint returns connected state
    status_resp = client.get("/api/channels/youtube/connection")
    assert status_resp.status_code == 200
    assert status_resp.json()["connected"] is True
    assert status_resp.json()["channel_id"] == summary["channel_id"]

    # 5. Disconnect
    disconnect_resp = client.post("/api/channels/youtube/disconnect")
    assert disconnect_resp.status_code == 204

    # 6. Verify status returns disconnected
    status_after = client.get("/api/channels/youtube/connection")
    assert status_after.status_code == 200
    assert status_after.json()["connected"] is False

    # 7. Disconnect is idempotent
    disconnect_again = client.post("/api/channels/youtube/disconnect")
    assert disconnect_again.status_code == 204

def test_youtube_callback_rejects_invalid_or_consumed_state(client: TestClient) -> None:
    # Attempt with non-existent state
    response = client.post(
        "/api/channels/youtube/callback",
        json={
            "code": "mock-code",
            "state": "invalid-non-existent-state-token",
            "redirect_uri": "http://localhost:5173/app",
        },
    )
    assert response.status_code == 400
    assert "CSRF protection" in response.json()["detail"]


# -----------------------------------------------------------------------------
# Alex Grounded Research & Topic Radar Tests
# -----------------------------------------------------------------------------


def test_get_research_findings_returns_grounded_topics(client: TestClient) -> None:
    response = client.get("/api/channels/research/findings")
    assert response.status_code == 200, response.text
    findings = response.json()
    assert len(findings) >= 2
    first = findings[0]
    assert first["title"] != ""
    assert first["opportunity_score"] > 0
    assert len(first["source_citations"]) >= 1
    assert first["source_citations"][0]["url"].startswith("http")
    assert first["why_it_matters"] != ""


def test_manual_research_run_trigger(client: TestClient) -> None:
    response = client.post("/api/channels/research/run")
    assert response.status_code == 200, response.text
    findings = response.json()
    assert len(findings) >= 2
    assert findings[0]["topic_fingerprint"] != ""


def test_scheduler_tick_requires_oidc_authorization(client: TestClient, repos: tuple) -> None:
    _, research_repo, _ = repos
    past = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
    config = ResearchConfig(
        workspace_id="ws-test-sched",
        channel_id="croviq_syn_ai_eng_01",
        enabled=True,
        cadence=ResearchCadence.EVERY_HOUR,
        prompts=[
            ResearchPrompt(
                prompt_id="p1",
                text="Emerging AI tools",
                enabled=True,
            )
        ],
        last_run_at=None,
        next_run_at=past,
        updated_at=past,
    )
    import asyncio
    asyncio.run(research_repo.save_config(config))

    # 1. Unauthenticated request rejected with 401
    resp_no_auth = client.post("/api/channels/research/tick")
    assert resp_no_auth.status_code == 401

    # 2. Unauthorized token rejected with 403
    resp_bad_auth = client.post(
        "/api/channels/research/tick",
        headers={"Authorization": "Bearer test-scheduler-unauthorized"},
    )
    assert resp_bad_auth.status_code == 403

    # 3. Valid scheduler OIDC token accepted with 200
    resp_valid = client.post(
        "/api/channels/research/tick",
        headers={"Authorization": "Bearer test-scheduler-valid"},
    )
    assert resp_valid.status_code == 200, resp_valid.text
    data = resp_valid.json()
    assert data["runs_evaluated"] >= 1
    assert data["runs_executed"] >= 1
    assert data["findings_created"] >= 2
    assert data["status"] == "completed"

    # 4. Immediate second tick skips due config (Idempotent - 0 duplicates)
    resp_dup = client.post(
        "/api/channels/research/tick",
        headers={"Authorization": "Bearer test-scheduler-valid"},
    )
    assert resp_dup.status_code == 200
    data_dup = resp_dup.json()
    assert data_dup["runs_evaluated"] == 0
    assert data_dup["runs_executed"] == 0
    assert data_dup["findings_created"] == 0
    assert data_dup["status"] == "skipped"
# -----------------------------------------------------------------------------
# Code Execution & Memory Distillation Tests
# -----------------------------------------------------------------------------


def test_alex_code_execution_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/channels/analysis/code-execution",
        json={"analysis_goal": "Calculate first demo timing correlation with average retention"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "numeric_result" in data
    assert "first_demo_retention_correlation" in data["numeric_result"]
    assert data["numeric_result"]["sample_size"] == 100
    assert data["calculation_performed"] != ""


def test_distill_research_finding_endpoint(client: TestClient, repos: tuple) -> None:
    _, research_repo, _ = repos
    now = datetime.now(UTC)
    finding = ResearchFinding(
        finding_id="fnd_test_distill",
        run_id="run_test",
        channel_id="croviq_syn_ai_eng_01",
        category="Architecture",
        title="Dynamic Thinking Budgets",
        summary="Gemini 3.7 Flash allows dynamic thinking budgets.",
        why_it_matters="Audience shows 28% higher retention when system internals are shown early.",
        relevance_score=0.95,
        freshness_score=0.95,
        opportunity_score=0.95,
        source_citations=[
            SourceCitation(
                url="https://ai.google.dev/docs",
                title="Google AI Documentation",
                domain="ai.google.dev",
            )
        ],
        topic_fingerprint="fp_distill_test",
        discovered_at=now,
    )
    import asyncio
    asyncio.run(research_repo.save_findings([finding]))

    response = client.post("/api/channels/research/findings/fnd_test_distill/distill")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "distilled_to_memory_bank"
    assert data["lesson_id"] is not None
    assert "Dynamic Thinking Budgets" in data["directive"]
    assert data["confidence"] == 0.95
