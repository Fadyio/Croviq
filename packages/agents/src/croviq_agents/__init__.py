"""Croviq autonomous production agents: Alex (Data Scientist), Leo (Video Editor), Maya (Director), Iris (Quality Control)."""
from croviq_agents.alex import AlexDataScientist
from croviq_agents.iris import IrisQAAgent
from croviq_agents.client import (
    AgentUsageMetadata,
    FakeGenAIClient,
    GenAIClient,
    GenAIError,
    GoogleGenAIClient,
    reconcile_director_review_with_transcript,
    reconcile_editor_proposal_with_transcript,
    reconcile_packaging_proposal,
    reconcile_release_review,
)
from croviq_agents.director import MayaDirector
from croviq_agents.editor import LeoDialogueEditor, LeoVideoEditor, ensure_full_timeline_coverage
from croviq_agents.terminal import SandboxedTerminalRunner, TerminalCommandResult, TerminalExecutionError
from croviq_agents.tools import (
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    build_default_editor_tool_registry,
    build_default_iris_tool_registry,
)
from croviq_agents.voice import (
    GOOGLE_GEMINI_VOICES,
    StudioVoiceSynthesizer,
    VoiceCatalog,
    VoiceFitAttempt,
)
from croviq_agents.prompts import (
    build_director_prompt,
    build_editor_prompt,
    build_release_qa_prompt,
    DEFAULT_IRIS_PROMPT,
    format_channel_memory_summary,
    format_transcript_for_prompt,
)

__all__ = [
    "AlexDataScientist",
    "IrisQAAgent",
    "DEFAULT_IRIS_PROMPT",
    "build_release_qa_prompt",
    "reconcile_release_review",
    "build_default_iris_tool_registry",
    "reconcile_packaging_proposal",
    "FakeGenAIClient",
    "GenAIClient",
    "GenAIError",
    "GoogleGenAIClient",
    "LeoDialogueEditor",
    "LeoVideoEditor",
    "MayaDirector",
    "SandboxedTerminalRunner",
    "TerminalCommandResult",
    "TerminalExecutionError",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResult",
    "build_default_editor_tool_registry",
    "StudioVoiceSynthesizer",
    "VoiceCatalog",
    "VoiceFitAttempt",
    "ensure_full_timeline_coverage",
    "build_director_prompt",
    "build_editor_prompt",
    "format_channel_memory_summary",
    "format_transcript_for_prompt",
    "reconcile_director_review_with_transcript",
    "reconcile_editor_proposal_with_transcript",
]

__version__ = "0.1.0"
