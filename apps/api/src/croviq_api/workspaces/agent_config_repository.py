"""Agent configuration and prompt repository interface and implementations."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import os
from typing import Any

from croviq_api.config import get_settings
from croviq_domain.agent_config import (
    AgentId,
    AgentPromptConfig,
    NarrationMode,
    VoiceSettingsConfig,
)
from croviq_observability import log_firestore_event

logger = logging.getLogger(__name__)

DEFAULT_LEO_PROMPT = (
    "You are Leo, a professional, discerning video editor operating a high-end YouTube production studio.\n"
    "Your role is to edit the provided raw creator screen recording and dialogue into a punchy, clear, technically accurate tutorial.\n\n"
    "Editorial Principles:\n"
    "1. Pacing & Momentum: Trim dead air, false starts, filler repetitions, and awkward browser pauses.\n"
    "2. Technical Clarity: Preserve essential code explanations, terminal commands, and configuration steps.\n"
    "3. Visual Continuity: Ensure every cut lands naturally on a complete phrase or logical visual transition.\n"
    "4. Full Timeline Responsibility: Review 100% of the timeline and categorize every section (KEEP, TIGHTEN, REMOVE, COVERAGE).\n"
    "5. Tool Usage: Inspect media streams, examine audio loudness, probe transcript phrases, render test cuts, and verify candidate edits before delivering."
)

DEFAULT_MAYA_PROMPT = (
    "You are Maya, the Director overseeing post-production quality.\n"
    "Your role is to review Leo's editorial proposals and rendered preview video.\n\n"
    "Review Principles:\n"
    "1. Editorial Rigor: Verify that cuts preserve technical meaning, visual continuity, and natural human pacing.\n"
    "2. Constructive Direction: Provide clear, actionable feedback if a cut is overly aggressive or loses necessary context.\n"
    "3. Decisiveness: Approve candidate edits that meet professional standards, or request one bounded revision pass."
)

DEFAULT_ALEX_PROMPT = (
    "You are Alex, Croviq's Data Scientist for YouTube creators.\n"
    "Observe canonical channel data, calculate defensible comparisons, test patterns, "
    "and recommend bounded actions or experiments.\n\n"
    "Analysis Principles:\n"
    "1. Evidence Types: Label direct calculations as FACT, statistical interpretations "
    "as INFERENCE, grounded external information as RESEARCH, and creator actions as "
    "RECOMMENDATION.\n"
    "2. Statistical Discipline: Report baselines, sample sizes, effect sizes, uncertainty, "
    "and confounders where relevant. Never turn correlation into causation.\n"
    "3. Data Truthfulness: Never mix sample and connected YouTube analytics. Never invent "
    "unavailable metrics, citations, research, or numerical results.\n"
    "4. Experimentation: Convert useful associations into falsifiable Channel Experiments "
    "with a primary metric and expected direction.\n"
    "5. Durable Learning: Promote only repeated, falsifiable evidence into Channel Memory."
)

DEFAULT_NINA_PROMPT = (
    "You are Nina, Croviq's Packaging Agent for YouTube creators.\n"
    "Your role is to turn the approved Master video into a high-converting, publish-ready YouTube package.\n\n"
    "Packaging Principles:\n"
    "1. Multimodal Video Grounding: Inspect both what the video says (transcript) and what it visually demonstrates (screen, hardware, code, action).\n"
    "2. Channel-Aware Positioning: Utilize Alex channel intelligence, historical retention/CTR baselines, and Memory Bank lessons. Do not fabricate metrics.\n"
    "3. Packaging Rigor: Generate distinct, high-impact title candidates representing genuinely different strategic angles (DIRECT_VALUE, CURIOSITY, PROBLEM_SOLUTION, etc.).\n"
    "4. Publish-Ready Description: Accurately describe the video, preserve technical terminology, include polished chapters, and avoid AI fluff.\n"
    "5. Canonical Chapters: Anchor chapter timestamps to verified Master timeline boundaries starting at 0:00.\n"
    "6. Visual Thumbnail Concepts: Identify 3 distinct visual moments from actual video frames with exact millisecond timestamps, subject, composition, and emotional hook.\n"
    "7. Short Packaging: Provide separate, punchy vertical Short packaging when a Short exists.\n"
    "8. Packaging Truth: Distinguish FACT from RECOMMENDATION. Frame future CTR expectations as hypotheses grounded in channel evidence."
)


def coerce_agent_id(agent_id: AgentId | str) -> AgentId:
    return AgentId(str(agent_id).lower())


def get_default_prompt_text(agent_id: AgentId | str) -> str:
    aid = coerce_agent_id(agent_id)
    if aid is AgentId.ALEX:
        return DEFAULT_ALEX_PROMPT
    if aid is AgentId.MAYA:
        return DEFAULT_MAYA_PROMPT
    if aid is AgentId.NINA:
        return DEFAULT_NINA_PROMPT
    return DEFAULT_LEO_PROMPT


class AgentConfigRepository(ABC):
    """Abstract interface for persisting creator-editable agent prompts and voice settings."""

    @abstractmethod
    async def get_agent_prompt(self, workspace_id: str, agent_id: AgentId | str) -> AgentPromptConfig:
        pass

    @abstractmethod
    async def save_agent_prompt(
        self, workspace_id: str, agent_id: AgentId | str, prompt_text: str
    ) -> AgentPromptConfig:
        pass

    @abstractmethod
    async def reset_agent_prompt(self, workspace_id: str, agent_id: AgentId | str) -> AgentPromptConfig:
        pass

    @abstractmethod
    async def get_voice_settings(self, workspace_id: str) -> VoiceSettingsConfig:
        pass

    @abstractmethod
    async def save_voice_settings(
        self, workspace_id: str, voice_settings: VoiceSettingsConfig
    ) -> VoiceSettingsConfig:
        pass


class InMemoryAgentConfigRepository(AgentConfigRepository):
    """In-memory agent configuration repository for tests and local non-cloud execution."""

    def __init__(self) -> None:
        self._prompts: dict[tuple[str, str], AgentPromptConfig] = {}
        self._voice_settings: dict[str, VoiceSettingsConfig] = {}

    async def get_agent_prompt(self, workspace_id: str, agent_id: AgentId | str) -> AgentPromptConfig:
        key = (workspace_id, str(agent_id).lower())
        if key in self._prompts:
            return self._prompts[key]
        aid = coerce_agent_id(agent_id)
        return AgentPromptConfig(
            agent_id=aid,
            prompt_text=get_default_prompt_text(aid),
            version=1,
            updated_at=datetime.now(timezone.utc),
            is_custom=False,
        )

    async def save_agent_prompt(
        self, workspace_id: str, agent_id: AgentId | str, prompt_text: str
    ) -> AgentPromptConfig:
        current = await self.get_agent_prompt(workspace_id, agent_id)
        aid = coerce_agent_id(agent_id)
        new_version = current.version + 1 if current.is_custom else 1
        updated = AgentPromptConfig(
            agent_id=aid,
            prompt_text=prompt_text,
            version=new_version,
            updated_at=datetime.now(timezone.utc),
            is_custom=True,
        )
        self._prompts[(workspace_id, str(agent_id).lower())] = updated
        return updated

    async def reset_agent_prompt(self, workspace_id: str, agent_id: AgentId | str) -> AgentPromptConfig:
        aid = coerce_agent_id(agent_id)
        default_cfg = AgentPromptConfig(
            agent_id=aid,
            prompt_text=get_default_prompt_text(aid),
            version=1,
            updated_at=datetime.now(timezone.utc),
            is_custom=False,
        )
        self._prompts[(workspace_id, str(agent_id).lower())] = default_cfg
        return default_cfg

    async def get_voice_settings(self, workspace_id: str) -> VoiceSettingsConfig:
        if workspace_id in self._voice_settings:
            return self._voice_settings[workspace_id]
        return VoiceSettingsConfig(
            narration_mode=NarrationMode.ORIGINAL,
            selected_voice="Puck",
            language="en-US",
            updated_at=datetime.now(timezone.utc),
        )

    async def save_voice_settings(
        self, workspace_id: str, voice_settings: VoiceSettingsConfig
    ) -> VoiceSettingsConfig:
        self._voice_settings[workspace_id] = voice_settings
        return voice_settings


class FirestoreAgentConfigRepository(AgentConfigRepository):
    """Production Firestore repository for Agent Configuration."""

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

    async def get_agent_prompt(self, workspace_id: str, agent_id: AgentId | str) -> AgentPromptConfig:
        aid = coerce_agent_id(agent_id)
        db = self._get_db()
        doc_ref = db.collection("workspaces").document(workspace_id).collection("agent_configs").document(f"prompt_{aid.value}")
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return AgentPromptConfig.model_validate(data)
        return AgentPromptConfig(
            agent_id=aid,
            prompt_text=get_default_prompt_text(aid),
            version=1,
            updated_at=datetime.now(timezone.utc),
            is_custom=False,
        )

    async def save_agent_prompt(
        self, workspace_id: str, agent_id: AgentId | str, prompt_text: str
    ) -> AgentPromptConfig:
        current = await self.get_agent_prompt(workspace_id, agent_id)
        aid = coerce_agent_id(agent_id)
        new_version = current.version + 1 if current.is_custom else 1
        updated = AgentPromptConfig(
            agent_id=aid,
            prompt_text=prompt_text,
            version=new_version,
            updated_at=datetime.now(timezone.utc),
            is_custom=True,
        )
        db = self._get_db()
        doc_ref = db.collection("workspaces").document(workspace_id).collection("agent_configs").document(f"prompt_{aid.value}")
        doc_ref.set(updated.model_dump(mode="json"))
        return updated

    async def reset_agent_prompt(self, workspace_id: str, agent_id: AgentId | str) -> AgentPromptConfig:
        aid = coerce_agent_id(agent_id)
        default_cfg = AgentPromptConfig(
            agent_id=aid,
            prompt_text=get_default_prompt_text(aid),
            version=1,
            updated_at=datetime.now(timezone.utc),
            is_custom=False,
        )
        db = self._get_db()
        doc_ref = db.collection("workspaces").document(workspace_id).collection("agent_configs").document(f"prompt_{aid.value}")
        doc_ref.set(default_cfg.model_dump(mode="json"))
        return default_cfg

    async def get_voice_settings(self, workspace_id: str) -> VoiceSettingsConfig:
        db = self._get_db()
        doc_ref = db.collection("workspaces").document(workspace_id).collection("agent_configs").document("voice_settings")
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return VoiceSettingsConfig.model_validate(data)
        return VoiceSettingsConfig(
            narration_mode=NarrationMode.ORIGINAL,
            selected_voice="Puck",
            language="en-US",
            updated_at=datetime.now(timezone.utc),
        )

    async def save_voice_settings(
        self, workspace_id: str, voice_settings: VoiceSettingsConfig
    ) -> VoiceSettingsConfig:
        db = self._get_db()
        doc_ref = db.collection("workspaces").document(workspace_id).collection("agent_configs").document("voice_settings")
        doc_ref.set(voice_settings.model_dump(mode="json"))
        return voice_settings


_global_agent_config_repo: AgentConfigRepository | None = None


def get_default_agent_config_repository() -> AgentConfigRepository:
    global _global_agent_config_repo
    if _global_agent_config_repo is None:
        settings = get_settings()
        if settings.environment == "production" or os.getenv("CROVIQ_ENV") == "production":
            _global_agent_config_repo = FirestoreAgentConfigRepository(project_id=settings.gcp_project_id)
        else:
            _global_agent_config_repo = InMemoryAgentConfigRepository()
    return _global_agent_config_repo


def get_agent_config_repository() -> AgentConfigRepository:
    return get_default_agent_config_repository()


def set_agent_config_repository(repo: AgentConfigRepository | None) -> None:
    global _global_agent_config_repo
    _global_agent_config_repo = repo
