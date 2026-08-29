"""Unit and integration tests for Gemini Omni 1.1 Flash Interactions API and B-roll generation."""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from croviq_agents.client import FakeGenAIClient, GoogleGenAIClient, GenAIError
from croviq_agents.tools import (
    GenerateBRollArgs,
    InspectBRollArgs,
    build_default_editor_tool_registry,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.narration import BRollArtifact, BRollArtifactStatus
from croviq_domain.production import SourceMedia, SourceMediaStatus
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord


def _sample_analysis_input() -> SourceVideoAnalysisInput:
    now = datetime.now(timezone.utc)
    return SourceVideoAnalysisInput(
        production_id="prod_omni_unit_01",
        channel_id="croviq_syn_ai_eng_01",
        source_media=SourceMedia(
            upload_id="up_01",
            original_filename="sample.mp4",
            content_type="video/mp4",
            size_bytes=1000000,
            gcs_bucket="croviq-506602-croviq-media-raw",
            gcs_object="workspaces/ws_unit/productions/prod_omni_unit_01/source/sample.mp4",
            status=SourceMediaStatus.UPLOADED,
            created_at=now,
            uploaded_at=now,
        ),
        media_metadata=MediaMetadata(
            duration_ms=30000,
            size_bytes=1000000,
            width=1920,
            height=1080,
            frame_rate=30.0,
        ),
        transcript=Transcript(
            transcript_id="tr_unit_01",
            production_id="prod_omni_unit_01",
            language_code="en-US",
            duration_ms=30000,
            words=[TranscriptWord(index=0, text="hello", start_ms=0, end_ms=1000)],
            segments=[
                TranscriptSegment(
                    segment_id="s1",
                    start_ms=0,
                    end_ms=1000,
                    text="hello",
                    word_start_index=0,
                    word_end_index=0,
                )
            ],
            created_at=now,
        ),
    )


def test_interactions_api_client_construction():
    """Verify GoogleGenAIClient configures location='global' and project for Vertex AI Interactions."""
    client = GoogleGenAIClient(
        project_id="croviq-506602",
        location="global",
        model_id="gemini-3.7-flash",
    )
    assert client._project_id == "croviq-506602"
    assert client._location == "global"


def test_broll_args_duration_and_resolution_validation():
    """Verify GenerateBRollArgs validates 360p draft default, 3s default duration, and quality modes."""
    # Valid default draft
    args = GenerateBRollArgs(
        prompt="Cinematic drone shot of modern server room",
        source_start_ms=1000,
        source_end_ms=4000,
    )
    assert args.resolution == "360p"
    assert args.quality_mode == "draft"
    assert args.duration_ms == 3000
    assert args.aspect_ratio == "16:9"
    assert args.task == "text_to_video"

    # Invalid duration below 3000ms
    with pytest.raises(Exception):
        GenerateBRollArgs(
            prompt="Too short clip",
            duration_ms=2000,
            source_start_ms=0,
            source_end_ms=2000,
        )

    # Invalid duration above 10000ms
    with pytest.raises(Exception):
        GenerateBRollArgs(
            prompt="Too long single shot",
            duration_ms=15000,
            source_start_ms=0,
            source_end_ms=15000,
        )
def test_broll_args_reference_media_serialization():
    """Verify reference media and first/last frame controls are captured."""
    args = GenerateBRollArgs(
        prompt="Interpolated camera transition between two scenes",
        source_start_ms=2000,
        source_end_ms=6000,
        task="reference_to_video",
        first_frame_uri="gs://bucket/frames/frame_01.jpg",
        last_frame_uri="gs://bucket/frames/frame_02.jpg",
        reference_video_uri="gs://bucket/ref/style_sample.mp4",
        previous_interaction_id="inter_prior_123",
        scene_extension_prior_context_ms=4000,
    )
    assert args.task == "reference_to_video"
    assert args.first_frame_uri == "gs://bucket/frames/frame_01.jpg"
    assert args.last_frame_uri == "gs://bucket/frames/frame_02.jpg"
    assert args.reference_video_uri == "gs://bucket/ref/style_sample.mp4"
    assert args.previous_interaction_id == "inter_prior_123"
    assert args.scene_extension_prior_context_ms == 4000


@pytest.mark.asyncio
async def test_fake_genai_client_generate_broll():
    """Verify FakeGenAIClient returns mock video bytes and records history."""
    client = FakeGenAIClient()
    bytes_out, inter_id, dur, res = await client.generate_broll_clip(
        prompt="Test B-roll prompt",
        production_id="prod_fake_01",
        duration_ms=3000,
        resolution="360p",
    )
    assert len(bytes_out) > 0
    assert inter_id.startswith("fake_interaction_")
    assert dur == 3000
    assert res == "360p"
    assert len(client.call_history) == 1
    assert client.call_history[0]["method"] == "generate_broll_clip"


def test_tool_registry_generate_broll_with_fake_client():
    """Verify ToolRegistry generate_broll executes with client and returns structured media artifact."""
    analysis_input = _sample_analysis_input()
    fake_client = FakeGenAIClient()

    registry = build_default_editor_tool_registry(
        production_id="prod_omni_unit_01",
        analysis_input=analysis_input,
        genai_client=fake_client,
        gcs_bucket="croviq-506602-croviq-media-raw",
    )

    result = registry.execute(
        "generate_broll",
        {
            "prompt": "Developer analyzing logs on a split-screen monitor",
            "duration_ms": 3000,
            "source_start_ms": 5000,
            "source_end_ms": 8000,
            "resolution": "360p",
            "aspect_ratio": "16:9",
        },
    )

    assert result.status == "success"
    assert result.output["prompt_summary"] == "Developer analyzing logs on a split-screen monitor"
    assert result.output["duration_ms"] == 3000
    assert result.output["source_start_ms"] == 5000
    assert result.output["source_end_ms"] == 8000
    assert result.output["status"] == "accepted"
    assert result.output["video_size_bytes"] > 0
    assert "workspaces/default/productions/prod_omni_unit_01/broll/" in result.output["gcs_object"]


def test_tool_registry_generate_broll_fails_closed_on_client_error():
    """Verify tool failure handling: API errors fail closed and do not create fake success artifacts."""
    analysis_input = _sample_analysis_input()

    class FailingGenAIClient(FakeGenAIClient):
        async def generate_broll_clip(self, *args, **kwargs):
            raise GenAIError("Google Interactions API unavailable (500)")

    failing_client = FailingGenAIClient()
    registry = build_default_editor_tool_registry(
        production_id="prod_omni_unit_01",
        analysis_input=analysis_input,
        genai_client=failing_client,
    )

    result = registry.execute(
        "generate_broll",
        {
            "prompt": "This should fail",
            "duration_ms": 4000,
            "source_start_ms": 0,
            "source_end_ms": 4000,
        },
    )

    assert result.status == "error"
    assert "Google Interactions API unavailable" in (result.error_message or "")


def test_inspect_broll_self_review():
    """Verify inspect_broll provides bounded evaluation of generated media."""
    analysis_input = _sample_analysis_input()
    registry = build_default_editor_tool_registry(
        production_id="prod_omni_unit_01",
        analysis_input=analysis_input,
    )

    result = registry.execute(
        "inspect_broll",
        {"artifact_id": "broll_art_123"},
    )
    assert result.status == "success"
    assert result.output["verdict"] == "ACCEPT"
    assert result.output["resolution_verified"] is True


@pytest.mark.asyncio
async def test_google_genai_client_request_serialization_360p_draft():
    """Verify 360p draft request is strictly serialized to Interactions API without omission."""
    import json
    from unittest.mock import MagicMock, patch

    client = GoogleGenAIClient(project_id="croviq-506602", location="global")
    fake_raw_client = MagicMock()

    mock_resp = MagicMock()
    mock_resp.id = "inter_draft_360p_01"
    mock_output_video = MagicMock()
    mock_output_video.data = "AAAA"
    mock_output_video.resolution = "360p"
    mock_resp.output_video = mock_output_video
    fake_raw_client.interactions.create.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=fake_raw_client):
        raw_bytes, inter_id, dur, res = await client.generate_broll_clip(
            prompt="Draft shot of laptop screen",
            production_id="prod_draft_test",
            duration_ms=3000,
            resolution="360p",
            aspect_ratio="16:9",
        )

        assert res == "360p"
        assert dur == 3000
        assert inter_id == "inter_draft_360p_01"

        # Verify outgoing kwargs to interactions.create
        call_kwargs = fake_raw_client.interactions.create.call_args[1]
        assert call_kwargs["model"] == "gemini-omni-1.1-flash-preview"
        assert call_kwargs["response_format"]["resolution"] == "360p"
        assert call_kwargs["response_format"]["duration"] == "3s"
        assert call_kwargs["response_format"]["aspect_ratio"] == "16:9"
        assert call_kwargs["response_format"]["type"] == "video"


@pytest.mark.asyncio
async def test_google_genai_client_quality_modes_standard_and_finishing():
    """Verify 720p standard and 1080p finishing requests are explicitly serialized."""
    from unittest.mock import MagicMock, patch

    client = GoogleGenAIClient(project_id="croviq-506602", location="global")
    fake_raw_client = MagicMock()

    mock_resp = MagicMock()
    mock_resp.id = "inter_finishing_01"
    mock_output_video = MagicMock()
    mock_output_video.data = "AAAA"
    mock_output_video.resolution = "1080p"
    mock_resp.output_video = mock_output_video
    fake_raw_client.interactions.create.return_value = mock_resp

    with patch.object(client, "_get_client", return_value=fake_raw_client):
        # Test 1080p finishing
        raw_bytes, inter_id, dur, res = await client.generate_broll_clip(
            prompt="Finishing master shot",
            production_id="prod_finish_test",
            duration_ms=5000,
            resolution="1080p",
            aspect_ratio="16:9",
        )
        call_kwargs = fake_raw_client.interactions.create.call_args[1]
        assert call_kwargs["response_format"]["resolution"] == "1080p"
        assert call_kwargs["response_format"]["duration"] == "5s"

        # Test 720p standard
        await client.generate_broll_clip(
            prompt="Standard shot",
            production_id="prod_standard_test",
            duration_ms=4000,
            resolution="720p",
            aspect_ratio="16:9",
        )
        call_kwargs = fake_raw_client.interactions.create.call_args[1]
        assert call_kwargs["response_format"]["resolution"] == "720p"
        assert call_kwargs["response_format"]["duration"] == "4s"


def test_no_autonomous_4k_default_and_draft_quality_contract():
    """Verify Leo tool registry defaults to draft 360p and rejects autonomous 4k defaulting."""
    analysis_input = _sample_analysis_input()
    fake_client = FakeGenAIClient()

    registry = build_default_editor_tool_registry(
        production_id="prod_quality_mode_test",
        analysis_input=analysis_input,
        genai_client=fake_client,
    )

    # Default execution: must be draft (360p), 3000ms duration
    res = registry.execute(
        "generate_broll",
        {
            "prompt": "Default visual coverage shot",
            "source_start_ms": 0,
            "source_end_ms": 3000,
        },
    )
    assert res.status == "success"
    assert res.output["quality_mode"] == "draft"
    assert res.output["requested_resolution"] == "360p"
    assert res.output["resolution"] == "360p"
    assert res.output["is_draft"] is True
    assert res.output["audio_used_in_master"] is False
    assert res.output["has_generated_audio"] is True
    assert res.output["placement_duration_ms"] == 3000
    assert res.output["requested_duration_ms"] == 3000
    assert res.output["actual_width"] == 640
    assert res.output["actual_height"] == 360


@pytest.mark.asyncio
async def test_429_quota_exceeded_never_falls_back_to_legacy_omni():
    """Verify 429 quota error fails closed after bounded retries and NEVER calls legacy gemini-omni-flash-preview."""
    from unittest.mock import MagicMock, patch

    client = GoogleGenAIClient(project_id="croviq-506602", location="global")
    fake_raw_client = MagicMock()

    # Simulate 429 on all attempts
    fake_raw_client.interactions.create.side_effect = Exception("Error code: 429 - {'error': {'message': 'Quota exceeded'}}")

    with patch.object(client, "_get_client", return_value=fake_raw_client), patch("asyncio.sleep") as mock_sleep:
        with pytest.raises(GenAIError, match="Gemini Omni video generation failed"):
            await client.generate_broll_clip(
                prompt="Test quota failure",
                production_id="prod_quota_fail",
                duration_ms=3000,
                resolution="360p",
            )

        # Total attempts must be exactly 3 (1 initial + 2 retries)
        assert fake_raw_client.interactions.create.call_count == 3
        # Verify ALL attempts called ONLY gemini-omni-1.1-flash-preview (0 legacy calls)
        for call in fake_raw_client.interactions.create.call_args_list:
            assert call[1]["model"] == "gemini-omni-1.1-flash-preview"
            assert call[1]["model"] != "gemini-omni-flash-preview"


@pytest.mark.asyncio
async def test_403_permission_denied_fails_closed_immediately():
    """Verify 403 permission denied fails closed immediately with 0 retries and no legacy fallback."""
    from unittest.mock import MagicMock, patch

    client = GoogleGenAIClient(project_id="croviq-506602", location="global")
    fake_raw_client = MagicMock()
    fake_raw_client.interactions.create.side_effect = Exception("Error code: 403 - PermissionDenied")

    with patch.object(client, "_get_client", return_value=fake_raw_client), patch("asyncio.sleep") as mock_sleep:
        with pytest.raises(GenAIError):
            await client.generate_broll_clip(
                prompt="Test 403 failure",
                production_id="prod_403_fail",
                duration_ms=3000,
                resolution="360p",
            )

        # Immediate failure: exactly 1 attempt
        assert fake_raw_client.interactions.create.call_count == 1
        assert fake_raw_client.interactions.create.call_args[1]["model"] == "gemini-omni-1.1-flash-preview"
        mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_5xx_upstream_failure_bounded_retries_and_fails_closed():
    """Verify 5xx server errors retry max 2 times and fail closed without calling legacy model."""
    from unittest.mock import MagicMock, patch

    client = GoogleGenAIClient(project_id="croviq-506602", location="global")
    fake_raw_client = MagicMock()
    fake_raw_client.interactions.create.side_effect = Exception("Error code: 503 - Service Unavailable")

    with patch.object(client, "_get_client", return_value=fake_raw_client), patch("asyncio.sleep") as mock_sleep:
        with pytest.raises(GenAIError):
            await client.generate_broll_clip(
                prompt="Test 503 failure",
                production_id="prod_503_fail",
                duration_ms=3000,
                resolution="360p",
            )

        assert fake_raw_client.interactions.create.call_count == 3
        for call in fake_raw_client.interactions.create.call_args_list:
            assert call[1]["model"] == "gemini-omni-1.1-flash-preview"
