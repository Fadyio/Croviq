"""Unit tests for Nina (Packaging Agent), prompt generation, tools, and GenAI client."""

import pytest
from datetime import datetime, timezone

from croviq_agents.client import FakeGenAIClient
from croviq_agents.nina import NinaPackagingAgent
from croviq_agents.prompts import DEFAULT_NINA_PROMPT, build_packaging_prompt
from croviq_agents.tools import build_default_packaging_tool_registry
from croviq_domain.channel_intelligence import ResearchFinding, SourceCitation
from croviq_domain.editorial import ChapterMarker, ShortCandidate
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.packaging import TitleAngle
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.transcript import Transcript, TranscriptWord


@pytest.fixture
def sample_transcript() -> Transcript:
    words = [
        TranscriptWord(index=0, start_ms=0, end_ms=500, text="The", confidence=0.99),
        TranscriptWord(index=1, start_ms=500, end_ms=1200, text="Fairphone", confidence=0.99),
        TranscriptWord(index=2, start_ms=1200, end_ms=1800, text="6", confidence=0.99),
        TranscriptWord(index=3, start_ms=1800, end_ms=2500, text="Plus", confidence=0.99),
        TranscriptWord(index=4, start_ms=2500, end_ms=3000, text="is", confidence=0.99),
        TranscriptWord(index=5, start_ms=3000, end_ms=3500, text="a", confidence=0.99),
        TranscriptWord(index=6, start_ms=3500, end_ms=4500, text="modular", confidence=0.99),
        TranscriptWord(index=7, start_ms=4500, end_ms=5500, text="repairable", confidence=0.99),
        TranscriptWord(index=8, start_ms=5500, end_ms=6200, text="phone.", confidence=0.99),
    ]
    return Transcript(
        transcript_id="tr_test_01",
        production_id="prod_01",
        duration_ms=113824,
        language_code="en",
        words=words,
        created_at=datetime.now(timezone.utc),
    )

@pytest.fixture
def sample_master_artifact() -> RenderArtifact:
    return RenderArtifact(
        artifact_id="art_master_01",
        production_id="prod_01",
        edl_id="edl_01",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_01/renders/edl_01/master.mp4",
        duration_ms=113824,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_channel_profile() -> ChannelMemoryProfile:
    return ChannelMemoryProfile(
        channel_id="ch_01",
        channel_name="Hardware teardowns & engineering",
        primary_topics=["Smartphones", "Hardware Repair", "Teardowns"],
        content_pillars=["Modular Hardware", "DIY Electronics"],
        language="en",
        audience_geographies=["US", "EU"],
        audience_characteristics=["Engineers", "Hardware Enthusiasts"],
        historical_baselines={"avg_ctr": 0.082, "avg_view_duration": 420.0},
        high_performing_formats=["Step-by-step disassembly", "Practical teardowns"],
        weak_formats=["Pure specification readings"],
        recurring_retention_patterns=["High retention during component removal demonstrations"],
        packaging_patterns=["Question-based curiosity titles perform well"],
        editorial_directives=["Focus on component-level clarity"],
        updated_at=datetime.now(timezone.utc),
    )


def test_build_packaging_prompt(sample_transcript, sample_channel_profile):
    chapters = [
        ChapterMarker(
            title="Introduction",
            source_start_ms=0,
            source_end_ms=26000,
            summary="Intro to Fairphone",
        )
    ]
    prompt = build_packaging_prompt(
        transcript=sample_transcript,
        channel_profile=sample_channel_profile,
        lessons=[],
        production_id="prod_01",
        chapters=chapters,
    )
    assert "Nina" in prompt
    assert "Hardware teardowns & engineering" in prompt
    assert "Smartphones" in prompt
    assert "Introduction" in prompt
    assert "MULTIMODAL VIDEO UNDERSTANDING" in prompt


@pytest.mark.asyncio
async def test_nina_packaging_agent_with_fake_client(
    sample_transcript, sample_master_artifact, sample_channel_profile
):
    fake_client = FakeGenAIClient()
    agent = NinaPackagingAgent(genai_client=fake_client)

    proposal, usage = await agent.package_production(
        production_id="prod_01",
        master_artifact=sample_master_artifact,
        transcript=sample_transcript,
        channel_profile=sample_channel_profile,
        lessons=[],
        chapters=[
            ChapterMarker(
                title="Introduction & Overview",
                source_start_ms=0,
                source_end_ms=26160,
                summary="Overview",
            )
        ],
    )

    assert proposal.production_id == "prod_01"
    assert proposal.agent == "nina"
    assert len(proposal.title_candidates) >= 3
    assert len(proposal.thumbnail_concepts) == 3
    assert proposal.thumbnail_concepts[0].frame_verified is True
    assert proposal.short_package is not None
    assert "Fairphone" in proposal.primary_title or "Repairable" in proposal.primary_title
    assert usage.input_tokens > 0
    assert len(fake_client.call_history) == 1
    assert fake_client.call_history[0]["agent"] == "nina_packaging"


def test_packaging_tool_registry(
    sample_transcript, sample_master_artifact, sample_channel_profile
):
    registry = build_default_packaging_tool_registry(
        production_id="prod_01",
        master_artifact=sample_master_artifact,
        transcript=sample_transcript,
        channel_profile=sample_channel_profile,
    )

    assert registry.has_tool("inspect_video")
    assert registry.has_tool("inspect_transcript")
    assert registry.has_tool("inspect_channel_metrics")
    assert registry.has_tool("inspect_research")
    assert registry.has_tool("inspect_memory")
    assert registry.has_tool("extract_frame")
    assert registry.has_tool("compare_title_history")
    assert registry.has_tool("create_packaging_proposal")

    # Test tool execution
    res_video = registry.execute("inspect_video", {"start_ms": 0, "end_ms": 50000})
    assert res_video.status == "success"
    assert res_video.output["duration_ms"] == 113824

    res_frame = registry.execute("extract_frame", {"frame_ms": 35000})
    assert res_frame.status == "success"
    assert res_frame.output["verified"] is True
    assert res_frame.output["formatted_time"] == "0:35"

    res_title = registry.execute("compare_title_history", {"proposed_title": "Inside the Most Repairable Phone"})
    assert res_title.status == "success"
    assert res_title.output["char_count"] > 0
