from abc import ABC, abstractmethod
from datetime import UTC, datetime
import os
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.channel_intelligence import (
    ResearchCadence,
    ResearchConfig,
    ResearchPrompt,
)


SAMPLE_CHANNEL_ID = "croviq_syn_ai_eng_01"
DEFAULT_RESEARCH_PROMPT = ResearchPrompt(
    prompt_id="emerging-topics",
    text="Find emerging AI engineering topics relevant to this channel",
    enabled=True,
    use_broad_web_search=True,
)


def default_research_config(workspace_id: str) -> ResearchConfig:
    now = datetime.now(UTC)
    cadence = ResearchCadence.EVERY_DAY
    return ResearchConfig(
        workspace_id=workspace_id,
        channel_id=SAMPLE_CHANNEL_ID,
        enabled=True,
        cadence=cadence,
        prompts=[DEFAULT_RESEARCH_PROMPT],
        last_run_at=None,
        next_run_at=now + cadence.interval,
        updated_at=now,
    )


class ResearchRepository(ABC):
    @abstractmethod
    async def get_config(self, workspace_id: str) -> ResearchConfig:
        pass

    @abstractmethod
    async def save_config(self, config: ResearchConfig) -> ResearchConfig:
        pass


class InMemoryResearchRepository(ResearchRepository):
    def __init__(self) -> None:
        self._configs: dict[str, ResearchConfig] = {}

    async def get_config(self, workspace_id: str) -> ResearchConfig:
        return self._configs.setdefault(workspace_id, default_research_config(workspace_id))

    async def save_config(self, config: ResearchConfig) -> ResearchConfig:
        self._configs[config.workspace_id] = config
        return config


class FirestoreResearchRepository(ResearchRepository):
    def __init__(self, project_id: str | None = None) -> None:
        self.project_id = project_id or get_settings().gcp_project_id
        self._db: Any = None

    def _get_db(self) -> Any:
        if self._db is None:
            import firebase_admin
            from firebase_admin import firestore

            try:
                firebase_admin.get_app()
            except ValueError:
                firebase_admin.initialize_app(options={"projectId": self.project_id})
            self._db = firestore.client()
        return self._db

    def _config_ref(self, workspace_id: str) -> Any:
        return (
            self._get_db()
            .collection("workspaces")
            .document(workspace_id)
            .collection("channel_intelligence")
            .document("alex_research_config")
        )

    async def get_config(self, workspace_id: str) -> ResearchConfig:
        document = self._config_ref(workspace_id).get()
        if not document.exists:
            return default_research_config(workspace_id)
        return ResearchConfig.model_validate(document.to_dict())

    async def save_config(self, config: ResearchConfig) -> ResearchConfig:
        self._config_ref(config.workspace_id).set(config.model_dump(mode="json"))
        return config


_global_repository: ResearchRepository | None = None


def get_research_repository() -> ResearchRepository:
    global _global_repository
    if _global_repository is None:
        settings = get_settings()
        if settings.environment == "production" or os.getenv("CROVIQ_ENV") == "production":
            _global_repository = FirestoreResearchRepository(settings.gcp_project_id)
        else:
            _global_repository = InMemoryResearchRepository()
    return _global_repository


def set_research_repository(repository: ResearchRepository | None) -> None:
    global _global_repository
    _global_repository = repository
