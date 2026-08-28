from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from croviq_api.auth.dependencies import get_current_user
from croviq_api.channels.research_repository import (
    InMemoryResearchRepository,
    get_research_repository,
)
from croviq_api.main import create_app
from croviq_api.workspaces.repository import InMemoryWorkspaceRepository, get_workspace_repository
from croviq_domain.user import User


@pytest.fixture
def app() -> FastAPI:
    user = User(
        user_id="creator-1",
        email="creator@example.com",
        display_name="Creator",
        created_at=datetime(2026, 8, 28, tzinfo=UTC),
        updated_at=datetime(2026, 8, 28, tzinfo=UTC),
    )
    workspace_repo = InMemoryWorkspaceRepository()
    research_repo = InMemoryResearchRepository()
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: user
    application.dependency_overrides[get_workspace_repository] = lambda: workspace_repo
    application.dependency_overrides[get_research_repository] = lambda: research_repo
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_research_config_persists_schedule_and_public_sources(client: TestClient) -> None:
    initial = client.get("/api/channels/research/config")
    assert initial.status_code == 200
    assert initial.json()["cadence"] == "EVERY_DAY"

    response = client.put(
        "/api/channels/research/config",
        json={
            "enabled": True,
            "cadence": "EVERY_6_HOURS",
            "prompts": [
                {
                    "prompt_id": "emerging-topics",
                    "text": "Find emerging AI engineering topics relevant to this channel",
                    "enabled": True,
                    "use_broad_web_search": True,
                    "preferred_sources": ["ai.google.dev", "https://cloud.google.com/vertex-ai"],
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["cadence"] == "EVERY_6_HOURS"
    assert saved["prompts"][0]["preferred_sources"] == [
        "ai.google.dev",
        "https://cloud.google.com/vertex-ai",
    ]
    assert client.get("/api/channels/research/config").json() == saved


def test_research_config_rejects_private_source(client: TestClient) -> None:
    response = client.put(
        "/api/channels/research/config",
        json={
            "enabled": True,
            "cadence": "EVERY_HOUR",
            "prompts": [
                {
                    "prompt_id": "unsafe",
                    "text": "Inspect this URL",
                    "preferred_sources": ["http://169.254.169.254/latest/meta-data"],
                }
            ],
        },
    )

    assert response.status_code == 422
