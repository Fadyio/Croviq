"""Tests for Narration, Studio Voice, and Agent Configuration domain models."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.narration import (
    NarrationSegment,
    NarrationSegmentStatus,
    StudioVoiceResult,
)
from croviq_domain.agent_config import (
    AgentId,
    AgentPromptConfig,
    NarrationMode,
    VoiceCatalogItem,
    VoiceSampleRequest,
    VoiceSampleResponse,
    VoiceSettingsConfig,
)
from croviq_domain.render import ArtifactType


def test_narration_segment_valid():
    segment = NarrationSegment(
        segment_id="seg_01",
        production_id="prod_123",
        source_start_ms=16100,
        source_end_ms=24000,
        available_duration_ms=7900,
        original_text="So here we go and install the thing",
        rewritten_text="Now, let's install the package.",
        voice_id="Puck",
        generated_duration_ms=6500,
        status=NarrationSegmentStatus.ACCEPTED,
        attempts=1,
    )
    assert segment.segment_id == "seg_01"
    assert segment.available_duration_ms == 7900
    assert segment.generated_duration_ms <= segment.available_duration_ms
    assert segment.status == NarrationSegmentStatus.ACCEPTED


def test_narration_segment_invalid_times():
    with pytest.raises(ValidationError):
        NarrationSegment(
            segment_id="seg_01",
            production_id="prod_123",
            source_start_ms=25000,
            source_end_ms=24000,
            available_duration_ms=1000,
            original_text="text",
            rewritten_text="text",
            voice_id="Puck",
        )


def test_studio_voice_result_aggregation():
    now = datetime.now(timezone.utc)
    seg1 = NarrationSegment(
        segment_id="seg_01",
        production_id="prod_123",
        source_start_ms=0,
        source_end_ms=5000,
        available_duration_ms=5000,
        original_text="Hello world",
        rewritten_text="Hello world.",
        voice_id="Puck",
        generated_duration_ms=4200,
        status=NarrationSegmentStatus.ACCEPTED,
    )
    res = StudioVoiceResult(
        production_id="prod_123",
        voice_id="Puck",
        segments=[seg1],
        total_segments=1,
        accepted_segments=1,
        all_within_budget=True,
        created_at=now,
        updated_at=now,
    )
    assert res.all_within_budget is True
    assert len(res.segments) == 1


def test_agent_prompt_config():
    now = datetime.now(timezone.utc)
    cfg = AgentPromptConfig(
        agent_id=AgentId.LEO,
        prompt_text="You are Leo, a professional video editor.",
        version=1,
        updated_at=now,
        is_custom=False,
    )
    assert cfg.agent_id == AgentId.LEO
    assert cfg.version == 1


def test_voice_settings_config():
    now = datetime.now(timezone.utc)
    voice_cfg = VoiceSettingsConfig(
        narration_mode=NarrationMode.STUDIO_VOICE,
        selected_voice="Puck",
        language="en-US",
        updated_at=now,
    )
    assert voice_cfg.narration_mode == NarrationMode.STUDIO_VOICE


def test_studio_voice_render_artifact_types():
    assert ArtifactType.STUDIO_VOICE_PREVIEW.value == "STUDIO_VOICE_PREVIEW"
    assert ArtifactType.STUDIO_VOICE_MASTER.value == "STUDIO_VOICE_MASTER"
