"""Croviq autonomous production agents: Leo (Dialogue Editor) and Maya (Director)."""

from croviq_agents.client import (
    AgentUsageMetadata,
    FakeGenAIClient,
    GenAIClient,
    GenAIError,
    GoogleGenAIClient,
    reconcile_director_review_with_transcript,
    reconcile_editor_proposal_with_transcript,
)
from croviq_agents.director import MayaDirector
from croviq_agents.editor import LeoDialogueEditor
from croviq_agents.prompts import (
    build_director_prompt,
    build_editor_prompt,
    format_channel_memory_summary,
    format_transcript_for_prompt,
)

__all__ = [
    "AgentUsageMetadata",
    "FakeGenAIClient",
    "GenAIClient",
    "GenAIError",
    "GoogleGenAIClient",
    "LeoDialogueEditor",
    "MayaDirector",
    "build_director_prompt",
    "build_editor_prompt",
    "format_channel_memory_summary",
    "format_transcript_for_prompt",
    "reconcile_director_review_with_transcript",
    "reconcile_editor_proposal_with_transcript",
]

__version__ = "0.1.0"
