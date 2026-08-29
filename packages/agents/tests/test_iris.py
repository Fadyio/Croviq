"""Unit tests for Iris (QA Agent), prompts, tools, and GenAI client integration (Issue #33)."""

from datetime import datetime, timezone
import pytest

from croviq_agents.client import FakeGenAIClient
from croviq_agents.iris import IrisQAAgent
from croviq_agents.prompts import DEFAULT_IRIS_PROMPT, build_release_qa_prompt
from croviq_agents.tools import build_default_iris_tool_registry
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.release_review import ReleaseVerdict
from croviq_domain.transcript import Transcript, TranscriptWord


@pytest.fixture
def sample_transcript() -> Transcript:
    now = datetime.now(timezone.utc)
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=0, end_ms=500, confidence=0.99),
        TranscriptWord(index=1, text="to", start_ms=510, end_ms=700, confidence=0.99),
        TranscriptWord(index=2, text="Fairphone", start_ms=710, end_ms=1200, confidence=0.99),
        TranscriptWord(index=3, text="6", start_ms=1210, end_ms=1500, confidence=0.99),
        TranscriptWord(index=4, text="Plus", start_ms=1510, end_ms=1900, confidence=0.99),
        TranscriptWord(index=5, text="hands-on", start_ms=1910, end_ms=2500, confidence=0.98),
        TranscriptWord(index=6, text="with", start_ms=2510, end_ms=2800, confidence=0.99),
        TranscriptWord(index=7, text="twelve", start_ms=2810, end_ms=3200, confidence=0.99),
        TranscriptWord(index=8, text="replaceable", start_ms=3210, end_ms=3900, confidence=0.99),
        TranscriptWord(index=9, text="parts.", start_ms=3910, end_ms=4500, confidence=0.99),
    ]
    return Transcript(
        transcript_id="tr_iris_01",
        production_id="prod_0b7657f515ae",
        language_code="en",
        created_at=now,
        duration_ms=113824,
        words=words,
    )


@pytest.fixture
def sample_master_artifact() -> RenderArtifact:
    return RenderArtifact(
        artifact_id="art_mast_01",
        production_id="prod_0b7657f515ae",
        edl_id="edl_01",
        artifact_type=ArtifactType.MASTER,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_0b7657f515ae/renders/master.mp4",
        duration_ms=113824,
        created_at=datetime.now(timezone.utc),
    )




def test_build_release_qa_prompt(
    sample_transcript,
    sample_master_artifact,
):
    prompt = build_release_qa_prompt(
        transcript=sample_transcript,
        master_artifact=sample_master_artifact,
        production_id="prod_0b7657f515ae",
    )

    assert "IRIS — EDITED VIDEO QUALITY GATE" in prompt
    assert "Is this edited video ready?" in prompt
    assert "CURRENT RENDERED MAIN VIDEO" in prompt
    assert "NARRATIVE PACING" in prompt
    assert "CAPTION TIMING" in prompt
    assert "Short" not in prompt

@pytest.mark.asyncio
async def test_iris_pass_on_clean_production(
    sample_transcript,
    sample_master_artifact,
):
    fake_client = FakeGenAIClient()
    iris = IrisQAAgent(genai_client=fake_client, model_id="gemini-3.7-flash")

    review, _ = await iris.review_production(
        production_id="prod_0b7657f515ae",
        master_artifact=sample_master_artifact,
        transcript=sample_transcript,
        request_id="test_qa_clean",
    )

    assert review.agent == "iris"
    assert review.verdict == ReleaseVerdict.PASS
    assert review.approved_for_release is True
    assert len(review.issues) == 0
    assert review.checklist.all_passed is True


def test_iris_tool_registry(
    sample_transcript,
    sample_master_artifact,
):
    registry = build_default_iris_tool_registry(
        master_artifact=sample_master_artifact,
        transcript=sample_transcript,
        proposal=None,
    )
    assert registry.has_tool("inspect_media")
    assert registry.has_tool("probe_media")
    assert registry.has_tool("analyze_audio")
    assert registry.has_tool("extract_frames")
    assert registry.has_tool("extract_clip")
    assert registry.has_tool("inspect_transcript")
    assert registry.has_tool("inspect_captions")
    assert registry.has_tool("inspect_chapters")
    assert registry.has_tool("inspect_packaging")
    assert registry.has_tool("verify_claim")
    assert registry.has_tool("compare_timeline")
