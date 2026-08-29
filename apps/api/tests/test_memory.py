"""Unit and integration tests for Channel Memory Bank integration."""

from datetime import datetime, timezone
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from croviq_api.auth.exceptions import InvalidTokenError
from croviq_api.auth.principal import AuthenticatedPrincipal
from croviq_api.auth.verifier import TokenVerifier, get_token_verifier
from croviq_api.config import get_settings
from croviq_api.main import create_app
from croviq_api.memory import (
    ChannelMemoryStore,
    FakeChannelMemoryStore,
    GoogleMemoryBankStore,
    MemoryStoreError,
    set_memory_store,
    get_memory_store,
)
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.memory import (
    ChannelLesson,
    ChannelMemoryProfile,
    ChannelProfileBuilder,
    TargetAgent,
)


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
    monkeypatch.setenv("MEMORY_STORE_PROVIDER", "fake")
    get_settings.cache_clear()


@pytest.fixture
def fake_verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier()


@pytest.fixture
def fake_store() -> FakeChannelMemoryStore:
    store = FakeChannelMemoryStore()
    set_memory_store(store)
    return store


@pytest.fixture
def app(fake_verifier: FakeTokenVerifier, fake_store: FakeChannelMemoryStore) -> FastAPI:
    set_memory_store(fake_store)
    application = create_app()
    application.dependency_overrides[get_token_verifier] = lambda: fake_verifier
    application.dependency_overrides[get_memory_store] = lambda: fake_store
    return application

@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def extract_memory_logs(captured_stdout: str) -> list[dict[str, Any]]:
    """Extract and parse structured JSON logs matching memory events."""
    logs = []
    for line in captured_stdout.splitlines():
        line = line.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        try:
            payload = json.loads(line)
            if payload.get("event_type", "").startswith("memory."):
                logs.append(payload)
        except json.JSONDecodeError:
            continue
    return logs


# -----------------------------------------------------------------------------
# 1. FakeChannelMemoryStore Unit Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_store_profile_lifecycle(fake_store: FakeChannelMemoryStore) -> None:
    """Fake store accurately handles profile upsert, retrieval, and isolation."""
    now = datetime.now(timezone.utc)
    profile = ChannelMemoryProfile(
        channel_id="chan_alpha",
        channel_name="Alpha Tech",
        primary_topics=["AI Agents"],
        content_pillars=["Architecture"],
        language="en",
        audience_geographies=["US"],
        audience_characteristics=["Engineers"],
        historical_baselines={"mean_views": 1000.0},
        high_performing_formats=["deep_dive"],
        weak_formats=["tutorial"],
        recurring_retention_patterns=["Pattern 1"],
        packaging_patterns=["Pattern 2"],
        editorial_directives=["Directive 1"],
        updated_at=now,
    )

    assert not await fake_store.profile_exists("chan_alpha")
    assert await fake_store.get_profile("chan_alpha") is None

    # Upsert
    saved = await fake_store.upsert_profile(profile)
    assert saved.channel_id == "chan_alpha"
    assert await fake_store.profile_exists("chan_alpha")

    # Retrieve
    retrieved = await fake_store.get_profile("chan_alpha")
    assert retrieved is not None
    assert retrieved.channel_id == "chan_alpha"
    assert retrieved.channel_name == "Alpha Tech"

    # Isolation check: chan_beta does not exist
    assert not await fake_store.profile_exists("chan_beta")
    assert await fake_store.get_profile("chan_beta") is None


@pytest.mark.asyncio
async def test_fake_store_lessons_lifecycle(fake_store: FakeChannelMemoryStore) -> None:
    """Fake store handles lesson recording and target-agent filtered retrieval."""
    now = datetime.now(timezone.utc)
    lesson_dir = ChannelLesson(
        lesson_id="lsn_dir_01",
        channel_id="chan_alpha",
        directive="Hook viewers within 30s",
        target_agent=TargetAgent.DIRECTOR,
        evidence_summary="58% retention on early demos",
        confidence=0.9,
        created_at=now,
    )
    lesson_edit = ChannelLesson(
        lesson_id="lsn_edit_01",
        channel_id="chan_alpha",
        directive="Cut silence",
        target_agent=TargetAgent.EDITOR,
        evidence_summary="Drop-offs during pauses",
        confidence=0.85,
        created_at=now,
    )

    await fake_store.add_lesson(lesson_dir)
    await fake_store.add_lesson(lesson_edit)

    all_lessons = await fake_store.get_lessons("chan_alpha")
    assert len(all_lessons) == 2

    dir_lessons = await fake_store.get_lessons("chan_alpha", target_agent=TargetAgent.DIRECTOR)
    assert len(dir_lessons) == 1
    assert dir_lessons[0].lesson_id == "lsn_dir_01"

    edit_lessons = await fake_store.get_lessons("chan_alpha", target_agent="editor")
    assert len(edit_lessons) == 1
    assert edit_lessons[0].lesson_id == "lsn_edit_01"

    qa_lessons = await fake_store.get_lessons("chan_alpha", target_agent=TargetAgent.QA)
    assert len(qa_lessons) == 0


# -----------------------------------------------------------------------------
# 2. GoogleMemoryBankStore Adapter Tests (Mocked Network / GCP)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_google_store_retrieve_profile_success() -> None:
    """Google adapter successfully retrieves and parses profile memories."""
    store = GoogleMemoryBankStore(
        project_id="croviq-test-project",
        location="us-central1",
        memory_bank_id="test-bank",
    )

    fake_profile_data = {
        "channel_id": "croviq_syn_ai_eng_01",
        "channel_name": "Croviq",
        "primary_topics": ["AI Agents"],
        "content_pillars": ["Architecture"],
        "language": "en",
        "audience_geographies": ["US"],
        "audience_characteristics": ["Engineers"],
        "historical_baselines": {"mean_views": 15000.0},
        "high_performing_formats": ["deep_dive"],
        "weak_formats": ["tutorial"],
        "recurring_retention_patterns": ["Early demo"],
        "packaging_patterns": ["Outcome title"],
        "editorial_directives": ["Demo <= 30s"],
        "updated_at": "2026-08-26T12:00:00Z",
    }

    mock_memory = MagicMock()
    mock_memory.scope = {"channel_id": "croviq_syn_ai_eng_01"}
    mock_memory.fact = json.dumps(fake_profile_data)

    mock_client = MagicMock()
    mock_client.list_memories.return_value = [mock_memory]

    with patch.object(store, "_get_client", return_value=mock_client):
        profile = await store.get_profile("croviq_syn_ai_eng_01")
        assert profile is not None
        assert profile.channel_id == "croviq_syn_ai_eng_01"
        assert profile.channel_name == "Croviq"


@pytest.mark.asyncio
async def test_google_store_retrieve_profile_empty_returns_none() -> None:
    """Google adapter returns None when no memories match scope."""
    store = GoogleMemoryBankStore(
        project_id="croviq-test-project",
        location="us-central1",
        memory_bank_id="test-bank",
    )

    mock_client = MagicMock()
    mock_client.list_memories.return_value = []

    with patch.object(store, "_get_client", return_value=mock_client):
        profile = await store.get_profile("nonexistent_channel")
        assert profile is None


@pytest.mark.asyncio
async def test_google_store_retrieve_profile_error_raises_memory_store_error() -> None:
    """Google adapter translates client exceptions into MemoryStoreError."""
    store = GoogleMemoryBankStore(
        project_id="croviq-test-project",
        location="us-central1",
        memory_bank_id="test-bank",
    )

    mock_client = MagicMock()
    mock_client.list_memories.side_effect = RuntimeError("GCP connection failure")

    with patch.object(store, "_get_client", return_value=mock_client):
        with pytest.raises(MemoryStoreError, match="retrieval error"):
            await store.get_profile("chan_01")

# -----------------------------------------------------------------------------
# 3. FastAPI Endpoint Tests
# -----------------------------------------------------------------------------


def test_get_memory_profile_requires_auth(client: TestClient) -> None:
    """Accessing /api/channel/memory/profile without token returns 401."""
    response = client.get("/api/channel/memory/profile")
    assert response.status_code == 401


def test_get_memory_profile_sample_channel_auto_initializes(
    client: TestClient, fake_verifier: FakeTokenVerifier, capsys: pytest.CaptureFixture[str]
) -> None:
    """GET /api/channel/memory/profile for sample channel auto-initializes and returns 200."""
    token = "test-valid-token"
    fake_verifier.add_valid_token(
        token=token,
        claims={"uid": "user_123", "email": "fadynagh10@gmail.com", "email_verified": True},
    )

    response = client.get(
        "/api/channel/memory/profile?channel_id=croviq_syn_ai_eng_01",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["channel_id"] == "croviq_syn_ai_eng_01"
    assert data["channel_name"] == "Croviq"
    assert len(data["primary_topics"]) > 0
    assert len(data["content_pillars"]) > 0
    assert "mean_views" in data["historical_baselines"]
    assert any("00:30" in d for d in data["editorial_directives"])

    # Check Cloud Logging emission
    captured = capsys.readouterr()
    memory_logs = extract_memory_logs(captured.out)
    assert any(log.get("event_type") == "memory.profile.retrieve" for log in memory_logs)


def test_get_memory_profile_unknown_channel_returns_404(
    client: TestClient, fake_verifier: FakeTokenVerifier
) -> None:
    """GET /api/channel/memory/profile for unknown channel returns 404."""
    token = "test-valid-token"
    fake_verifier.add_valid_token(
        token=token,
        claims={"uid": "user_123", "email": "fadynagh10@gmail.com", "email_verified": True},
    )

    response = client.get(
        "/api/channel/memory/profile?channel_id=unknown_channel_999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_memory_lessons_endpoint(
    client: TestClient, fake_verifier: FakeTokenVerifier
) -> None:
    """GET /api/channel/memory/lessons returns active lessons and supports target_agent filter."""
    token = "test-valid-token"
    fake_verifier.add_valid_token(
        token=token,
        claims={"uid": "user_123", "email": "fadynagh10@gmail.com", "email_verified": True},
    )

    # 1. Fetch all lessons
    response = client.get(
        "/api/channel/memory/lessons?channel_id=croviq_syn_ai_eng_01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    lessons = response.json()
    assert len(lessons) >= 4

    # 2. Filter by director
    dir_response = client.get(
        "/api/channel/memory/lessons?channel_id=croviq_syn_ai_eng_01&target_agent=director",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dir_response.status_code == 200
    dir_lessons = dir_response.json()
    assert len(dir_lessons) >= 1
    assert all(l["target_agent"] == "director" for l in dir_lessons)
