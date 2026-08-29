"""Repository and Firestore persistence for Alex research settings, runs, and grounded findings."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
import os
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.channel_intelligence import (
    FindingLifecycle,
    ResearchCadence,
    ResearchConfig,
    ResearchFinding,
    ResearchPrompt,
    ResearchRun,
)

SAMPLE_CHANNEL_ID = "croviq_syn_ai_eng_01"
DEFAULT_RESEARCH_PROMPT = ResearchPrompt(
    prompt_id="emerging-opportunities",
    text="Discover high-conviction video opportunities, emerging tools, and architecture breakdowns for this channel",
    enabled=True,
    use_broad_web_search=True,
    preferred_sources=[],
)
DEFAULT_RESEARCH_PROMPTS = [
    DEFAULT_RESEARCH_PROMPT,
    ResearchPrompt(
        prompt_id="developer-tooling-sdks",
        text="Investigate production developer tooling, agent evaluation benchmarks, and open-source frameworks",
        enabled=True,
        use_broad_web_search=True,
        preferred_sources=[],
    ),
    ResearchPrompt(
        prompt_id="multimodal-pacing-patterns",
        text="Explore streaming multimodal architectures, video engineering standards, and audience retention dynamics",
        enabled=True,
        use_broad_web_search=True,
        preferred_sources=[],
    ),
]

def filter_findings_diversity(
    findings: list[ResearchFinding], max_per_cluster: int = 2, limit: int = 10
) -> list[ResearchFinding]:
    """Filter findings to ensure diversity across topic clusters and primary entities."""
    from croviq_agents.alex import derive_primary_entity, derive_topic_cluster

    cluster_counts: dict[str, int] = {}
    seen_entities_top: set[str] = set()
    diverse: list[ResearchFinding] = []
    sorted_findings = sorted(
        findings, key=lambda x: (x.opportunity_score, x.discovered_at), reverse=True
    )
    remaining: list[ResearchFinding] = []
    for f in sorted_findings:
        cluster = f.topic_cluster or derive_topic_cluster(f.title, f.category)
        entity = (f.primary_entity or derive_primary_entity(f.title, f.category)).strip().lower()
        if cluster_counts.get(cluster, 0) < max_per_cluster and (
            entity not in seen_entities_top or len(diverse) >= 3
        ):
            diverse.append(f)
            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1
            seen_entities_top.add(entity)
        else:
            remaining.append(f)
        if len(diverse) >= limit:
            break
    if len(diverse) < limit:
        diverse.extend(remaining[: limit - len(diverse)])
    return diverse[:limit]

def default_research_config(workspace_id: str) -> ResearchConfig:
    now = datetime.now(UTC)
    return ResearchConfig(
        workspace_id=workspace_id,
        channel_id=SAMPLE_CHANNEL_ID,
        enabled=True,
        cadence=ResearchCadence.EVERY_DAY,
        prompts=DEFAULT_RESEARCH_PROMPTS,
        last_run_at=None,
        next_run_at=now,
        updated_at=now,
    )

class ResearchRepository(ABC):
    @abstractmethod
    async def get_config(self, workspace_id: str) -> ResearchConfig:
        pass

    @abstractmethod
    async def save_config(self, config: ResearchConfig) -> ResearchConfig:
        pass

    @abstractmethod
    async def list_due_configs(self, now: datetime | None = None) -> list[ResearchConfig]:
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> ResearchRun | None:
        pass

    @abstractmethod
    async def save_run(self, run: ResearchRun) -> ResearchRun:
        pass

    @abstractmethod
    async def save_findings(self, findings: list[ResearchFinding]) -> list[ResearchFinding]:
        pass

    @abstractmethod
    async def list_findings(
        self,
        workspace_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 10,
    ) -> list[ResearchFinding]:
        pass

    @abstractmethod
    async def get_finding(self, finding_id: str) -> ResearchFinding | None:
        pass

    @abstractmethod
    async def update_finding_lifecycle(
        self,
        finding_id: str,
        lifecycle: FindingLifecycle,
    ) -> None:
        pass


class InMemoryResearchRepository(ResearchRepository):
    def __init__(self) -> None:
        self._configs: dict[str, ResearchConfig] = {}
        self._runs: dict[str, ResearchRun] = {}
        self._findings: dict[str, ResearchFinding] = {}

    async def get_config(self, workspace_id: str) -> ResearchConfig:
        if workspace_id not in self._configs:
            self._configs[workspace_id] = default_research_config(workspace_id)
        return self._configs[workspace_id]

    async def save_config(self, config: ResearchConfig) -> ResearchConfig:
        self._configs[config.workspace_id] = config
        return config

    async def list_due_configs(self, now: datetime | None = None) -> list[ResearchConfig]:
        current_time = now or datetime.now(UTC)
        return [
            config
            for config in self._configs.values()
            if config.enabled and config.next_run_at <= current_time
        ]

    async def get_run(self, run_id: str) -> ResearchRun | None:
        return self._runs.get(run_id)

    async def save_run(self, run: ResearchRun) -> ResearchRun:
        self._runs[run.run_id] = run
        return run

    async def save_findings(self, findings: list[ResearchFinding]) -> list[ResearchFinding]:
        for finding in findings:
            self._findings[finding.finding_id] = finding
        return findings

    async def list_findings(
        self,
        workspace_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 10,
    ) -> list[ResearchFinding]:
        results = [
            f
            for f in self._findings.values()
            if (channel_id is None or f.channel_id == channel_id)
            and f.lifecycle != FindingLifecycle.EXPIRED
        ]
        return filter_findings_diversity(results, max_per_cluster=2, limit=limit)

    async def get_finding(self, finding_id: str) -> ResearchFinding | None:
        return self._findings.get(finding_id)

    async def update_finding_lifecycle(
        self,
        finding_id: str,
        lifecycle: FindingLifecycle,
    ) -> None:
        if finding_id in self._findings:
            f = self._findings[finding_id]
            self._findings[finding_id] = f.model_copy(
                update={"lifecycle": lifecycle, "updated_at": datetime.now(UTC)}
            )


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

    def _runs_collection(self) -> Any:
        return self._get_db().collection("research_runs")

    def _findings_collection(self) -> Any:
        return self._get_db().collection("research_findings")

    async def get_config(self, workspace_id: str) -> ResearchConfig:
        document = self._config_ref(workspace_id).get()
        if not document.exists:
            return default_research_config(workspace_id)
        return ResearchConfig.model_validate(document.to_dict())

    async def save_config(self, config: ResearchConfig) -> ResearchConfig:
        self._config_ref(config.workspace_id).set(config.model_dump(mode="json"))
        return config

    async def list_due_configs(self, now: datetime | None = None) -> list[ResearchConfig]:
        current_time = now or datetime.now(UTC)
        query = self._get_db().collection_group("channel_intelligence")
        configs: list[ResearchConfig] = []
        for doc in query.stream():
            try:
                data = doc.to_dict()
                if not data:
                    continue
                cfg = ResearchConfig.model_validate(data)
                if cfg.enabled and cfg.next_run_at <= current_time:
                    configs.append(cfg)
            except Exception:
                pass
        return configs

    async def get_run(self, run_id: str) -> ResearchRun | None:
        doc = self._runs_collection().document(run_id).get()
        if not doc.exists:
            return None
        return ResearchRun.model_validate(doc.to_dict())

    async def save_run(self, run: ResearchRun) -> ResearchRun:
        self._runs_collection().document(run.run_id).set(run.model_dump(mode="json"))
        return run

    async def save_findings(self, findings: list[ResearchFinding]) -> list[ResearchFinding]:
        batch = self._get_db().batch()
        for finding in findings:
            ref = self._findings_collection().document(finding.finding_id)
            batch.set(ref, finding.model_dump(mode="json"))
        batch.commit()
        return findings

    async def list_findings(
        self,
        workspace_id: str | None = None,
        channel_id: str | None = None,
        limit: int = 10,
    ) -> list[ResearchFinding]:
        query = self._findings_collection()
        if channel_id:
            query = query.where("channel_id", "==", channel_id)
        docs = query.stream()
        results: list[ResearchFinding] = []
        for doc in docs:
            try:
                f = ResearchFinding.model_validate(doc.to_dict())
                if f.lifecycle != FindingLifecycle.EXPIRED:
                    results.append(f)
            except Exception:
                pass
        return filter_findings_diversity(results, max_per_cluster=2, limit=limit)

    async def get_finding(self, finding_id: str) -> ResearchFinding | None:
        doc = self._findings_collection().document(finding_id).get()
        if not doc.exists:
            return None
        return ResearchFinding.model_validate(doc.to_dict())

    async def update_finding_lifecycle(
        self,
        finding_id: str,
        lifecycle: FindingLifecycle,
    ) -> None:
        ref = self._findings_collection().document(finding_id)
        ref.update({"lifecycle": lifecycle.value, "updated_at": datetime.now(UTC).isoformat()})


_global_repository: ResearchRepository | None = None


def get_research_repository() -> ResearchRepository:
    global _global_repository
    if _global_repository is None:
        settings = get_settings()
        if settings.is_production:
            if not settings.gcp_project_id and not os.getenv("FIRESTORE_EMULATOR_HOST"):
                raise RuntimeError(
                    "Production mode requires FirestoreResearchRepository with valid gcp_project_id."
                )
            _global_repository = FirestoreResearchRepository(project_id=settings.gcp_project_id)
        else:
            _global_repository = InMemoryResearchRepository()
    return _global_repository


def set_research_repository(repository: ResearchRepository | None) -> None:
    global _global_repository
    _global_repository = repository
