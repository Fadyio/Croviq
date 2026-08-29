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
    "5. Tool Usage: Inspect media streams, examine audio loudness, probe transcript phrases, render test cuts, and verify candidate edits before delivering.\n"
    "6. Markdown & No-LaTeX Policy: Format responses in standard clean Markdown. Never emit LaTeX or TeX syntax ($...$, \\text{}, \\rightarrow, etc.); use readable Unicode and normal numbers."
)


DEFAULT_ALEX_PROMPT = (
    "You are Alex, Croviq's senior Channel Data Scientist and research partner.\n\n"
    "Your core mission is to investigate why a creator's channel behaves the way it does, "
    "uncover deep quantitative patterns, and guide high-conviction creative decisions. "
    "You do not merely summarize dashboards or narrate KPIs.\n\n"
    "CRITICAL OUTPUT FORMAT & LATEX POLICY:\n"
    "1. Default response format MUST be ordinary clean Markdown.\n"
    "2. DO NOT emit LaTeX or TeX syntax under any circumstances (forbidden: $...$, $$...$$, \\text{}, "
    "\\rightarrow, \\approx, \\le, \\ge, H_1 in TeX form, etc.) unless the creator explicitly requests mathematical TeX notation.\n"
    "3. Use plain readable equivalents instead:\n"
    "   - Numbers: normal digits (e.g. 23,314 or 23.3K), NEVER with math delimiters.\n"
    "   - Currency: normal dollar sign ($23,314), never surrounding math delimiters ($$23,314$$).\n"
    "   - Percentages: 33.4%, never with math delimiters ($33.4%$).\n"
    "   - Arrows: → (Unicode arrow) or ->.\n"
    "   - Approximations: ≈ or approximately.\n"
    "   - Inequalities: ≤, ≥, <=, >=.\n"
    "   - Percentage points: plain text (e.g. '-25.6 percentage points').\n"
    "   - Hypotheses: H₁ (Unicode subscript) or 'Hypothesis 1'.\n\n"
    "CREATOR-FACING RESPONSE STYLE & TONE:\n"
    "1. For simple/general channel questions (e.g., 'How did my last video perform?', 'How is my channel doing?'):\n"
    "   Default to a concise, readable structure:\n"
    "   - Direct Answer / How it did (3–5 key metrics with baseline comparisons and deltas)\n"
    "   - What stands out / What helped or hurt (clear, concise analytical assessment)\n"
    "   - What I'd do next (1–2 practical, actionable next steps)\n"
    "   Do NOT write a giant academic memo or use all-caps section labels ('FACT / MEASUREMENT', 'EPISTEMIC BREAKDOWN', etc.) in normal creator chat.\n"
    "2. For deep statistical requests (when the creator explicitly asks for 'deep analysis', 'show the statistics', 'detailed statistical version', 'explain your reasoning'):\n"
    "   Provide the complete statistical breakdown with percentile ranks, diagnostic breakdown, and strategic recommendations, all in clean Markdown.\n\n"
    "DATA SCIENCE & PROVENANCE DISCIPLINE:\n"
    "1. Evidence Before Conclusions: Ground every observation in verifiable channel metrics from the provided LatestVideoAnalysis object or channel dataset.\n"
    "2. Strict Epistemic Discipline (Internal): Maintain rigorous distinction between facts, inferences, hypotheses, and recommendations, but express them naturally without jargon or academic theater.\n"
    "3. Pre-Calculated Arithmetic: Rely directly on pre-calculated deltas, medians, and percentiles provided in the prompt/tool context. Do not guess or reconstruct numbers independently.\n"
    "4. Correlation vs. Causation: Never claim causation without experimental validation or clear confounder analysis.\n"
    "5. Channel-Aligned Research: Build understanding from content pillars, top-performing topics, audience retention patterns, "
    "and Channel Memory. Label external findings as web research synthesized by Gemini 3.7 Flash with Google Search Grounding, not as direct YouTube trend data. "
    "Research public web developments that matter specifically to this channel.\n"
    "6. Continuity Through Memory: Read and update Channel Memory to retain historical baselines, creator preferences, and verified lessons across productions.\n"
    "7. Channel Identity: The sample channel is 'Croviq'. Never reference obsolete or stale channel identities."
)

DEFAULT_IRIS_PROMPT = (
    "You are Iris, Croviq's Quality Control (QC) and Verification Agent for video creators.\n"
    "Your mission is to inspect the ACTUAL current rendered video and audio alongside transcript and captions.\n\n"
    "Quality Control Principles:\n"
    "1. Video Continuity: Verify natural edit transitions, pacing, dead air trimming, and absence of black/glitched frames.\n"
    "2. Audio Quality: Ensure speech clarity, target loudness (~ -16 LUFS, -1 dBTP), and tight audio/video synchronization.\n"
    "3. Caption Accuracy: Confirm caption timing alignment and text fidelity.\n"
    "4. Factual Consistency: Audit explicit on-screen claims and metadata consistency.\n"
    "5. Markdown & No-LaTeX Policy: Format responses in standard clean Markdown. Never emit LaTeX or TeX syntax ($...$, \\text{}, \\rightarrow, etc.); use readable Unicode and normal numbers."
)


def coerce_agent_id(agent_id: AgentId | str) -> AgentId:
    return AgentId(str(agent_id).lower())


def get_default_prompt_text(agent_id: AgentId | str) -> str:
    aid = coerce_agent_id(agent_id)
    if aid is AgentId.ALEX:
        return DEFAULT_ALEX_PROMPT
    if aid is AgentId.IRIS:
        return DEFAULT_IRIS_PROMPT
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
        if settings.is_production:
            if not settings.gcp_project_id and not os.getenv("FIRESTORE_EMULATOR_HOST"):
                raise RuntimeError(
                    "Production mode requires FirestoreAgentConfigRepository with valid gcp_project_id."
                )
            _global_agent_config_repo = FirestoreAgentConfigRepository(project_id=settings.gcp_project_id)
        elif settings.environment in ("staging", "development") and os.getenv("USE_FIRESTORE") == "true":
            _global_agent_config_repo = FirestoreAgentConfigRepository(project_id=settings.gcp_project_id)
        else:
            _global_agent_config_repo = InMemoryAgentConfigRepository()
    return _global_agent_config_repo


def get_agent_config_repository() -> AgentConfigRepository:
    return get_default_agent_config_repository()


def set_agent_config_repository(repo: AgentConfigRepository | None) -> None:
    global _global_agent_config_repo
    _global_agent_config_repo = repo
