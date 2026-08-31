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


