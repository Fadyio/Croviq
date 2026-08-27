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


def test_sample_channel_dashboard_returns_computed_fixture_data(client: TestClient) -> None:
    response = client.get(
        "/api/channels/sample/dashboard?days=28&endDate=2026-08-26",
        headers={"Authorization": "Bearer creator-token"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["channel"]["channel_id"] == "croviq_syn_ai_eng_01"
    assert payload["channel"]["source_type"] == "synthetic"
    assert len(payload["kpis"]) == 4
    assert len(payload["trend"]) == 28
    assert payload["latest_video"]["video_id"] == "vid_syn_100"
    assert payload["latest_video"]["net_subscribers"] == 303
    assert payload["insights"][0]["evidence"]
    assert payload["proposed_experiment"]["status"] == "PROPOSED"


def test_sample_channel_dashboard_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/channels/sample/dashboard?days=28")

    assert response.status_code == 401


def test_sample_channel_dashboard_rejects_unsupported_period(client: TestClient) -> None:
    response = client.get(
        "/api/channels/sample/dashboard?days=30",
        headers={"Authorization": "Bearer creator-token"},
    )

    assert response.status_code == 422
