"""Tests for ToolRegistry and agent internal media tools."""

import pytest
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from croviq_agents.tools import ToolRegistry, ToolDefinition, ToolResult, build_default_editor_tool_registry
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import SourceMedia, SourceMediaStatus
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord


class DummyArgs(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(default=5, description="Max results")


def test_tool_registry_registration_and_execution():
    registry = ToolRegistry()

    def dummy_search(query: str, limit: int = 5) -> dict:
        return {"query": query, "results": [f"item_{i}" for i in range(limit)]}

    tool = ToolDefinition(
        name="dummy_search",
        description="Search for items",
        parameters_schema=DummyArgs,
        handler=dummy_search,
    )
    registry.register(tool)

    assert registry.has_tool("dummy_search")
    res = registry.execute("dummy_search", {"query": "test", "limit": 2})
    assert res.status == "success"
    assert res.output["results"] == ["item_0", "item_1"]


def test_tool_registry_handles_missing_tool():
    registry = ToolRegistry()
    res = registry.execute("non_existent_tool", {})
    assert res.status == "error"
    assert "Tool 'non_existent_tool' not registered" in res.error_message


def test_tool_registry_handles_invalid_arguments():
    registry = ToolRegistry()

    def dummy_search(query: str, limit: int = 5) -> dict:
        return {"query": query}

    tool = ToolDefinition(
        name="dummy_search",
        description="Search for items",
        parameters_schema=DummyArgs,
        handler=dummy_search,
    )
    registry.register(tool)

    res = registry.execute("dummy_search", {"limit": 2})  # Missing required 'query'
    assert res.status == "error"
    assert "Validation error" in res.error_message


def test_tool_registry_generates_genai_declarations():
    registry = ToolRegistry()

    def dummy_search(query: str, limit: int = 5) -> dict:
        return {}

    tool = ToolDefinition(
        name="dummy_search",
        description="Search for items",
        parameters_schema=DummyArgs,
        handler=dummy_search,
    )
    registry.register(tool)

    declarations = registry.to_genai_function_declarations()
    assert len(declarations) == 1
    decl = declarations[0]
    assert decl["name"] == "dummy_search"
    assert decl["description"] == "Search for items"
    assert "properties" in decl["parameters"]
    assert "query" in decl["parameters"]["properties"]


def test_tool_registry_logs_execution_with_context():
    registry = ToolRegistry(production_id="prod_123", run_id="run_456")

    def inspect_sample(query: str, limit: int = 1) -> dict:
        return {"found": query}

    tool = ToolDefinition(
        name="inspect_sample",
        description="Sample inspect",
        parameters_schema=DummyArgs,
        handler=inspect_sample,
    )
    registry.register(tool)

    res = registry.execute("inspect_sample", {"query": "test_inspect"})
    assert res.status == "success"
    assert res.latency_ms >= 0
    assert res.output["found"] == "test_inspect"


def test_default_editor_tool_registry_generate_broll_omni_1_1():
    now = datetime.now(timezone.utc)
    analysis_input = SourceVideoAnalysisInput(
        production_id="prod_omni_test",
        channel_id="croviq_syn_ai_eng_01",
        source_media=SourceMedia(
            upload_id="up_01",
            original_filename="sample.mp4",
            content_type="video/mp4",
            size_bytes=1000000,
            gcs_bucket="croviq-media-raw",
            gcs_object="workspaces/ws_1/productions/prod_omni_test/source/sample.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        media_metadata=MediaMetadata(
            duration_ms=60000,
            size_bytes=1000000,
            width=1920,
            height=1080,
            frame_rate=30.0,
        ),
        transcript=Transcript(
            transcript_id="tr_01",
            production_id="prod_omni_test",
            language_code="en-US",
            duration_ms=60000,
            words=[TranscriptWord(index=0, text="hello", start_ms=0, end_ms=1000)],
            segments=[TranscriptSegment(segment_id="s1", start_ms=0, end_ms=1000, text="hello", word_start_index=0, word_end_index=0)],
            created_at=now,
        ),
    )
    registry = build_default_editor_tool_registry(production_id="prod_omni_test", analysis_input=analysis_input)
    assert registry.has_tool("generate_broll")

    res = registry.execute(
        "generate_broll",
        {
            "prompt": "Cinematic camera orbit around modular smartphone hardware",
            "duration_ms": 6000,
            "source_start_ms": 10000,
            "source_end_ms": 16000,
            "resolution": "360p",
            "aspect_ratio": "9:16",
            "first_frame_uri": "gs://croviq-media-raw/frames/frame_before_cut.jpg",
            "last_frame_uri": "gs://croviq-media-raw/frames/frame_after_cut.jpg",
            "scene_extension_prior_context_ms": 5000,
        },
    )
    assert res.status == "success"
    assert res.output["model"] == "gemini-omni-1.1-flash-preview"
    assert res.output["resolution"] == "360p"
    assert res.output["is_draft"] is True
    assert res.output["duration_ms"] == 6000
    assert res.output["first_frame_uri"] == "gs://croviq-media-raw/frames/frame_before_cut.jpg"
    assert res.output["last_frame_uri"] == "gs://croviq-media-raw/frames/frame_after_cut.jpg"
    assert res.output["scene_extension_prior_context_ms"] == 5000
    assert "360p" in res.human_summary
