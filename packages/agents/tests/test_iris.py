"""Unit tests for Iris (QA Agent), prompts, tools, and GenAI client integration (Issue #33)."""

from datetime import datetime, timezone
import pytest

from croviq_agents.client import FakeGenAIClient
from croviq_agents.iris import IrisQAAgent
from croviq_agents.nina import NinaPackagingAgent
from croviq_agents.prompts import DEFAULT_IRIS_PROMPT, build_release_qa_prompt
from croviq_agents.tools import build_default_iris_tool_registry
from croviq_domain.agent_config import AgentId
from croviq_domain.channel_intelligence import ResearchFinding
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.packaging import (
    PackagingChapter,
    PackagingProposal,
    ShortPackage,
    ThumbnailConcept,
    TitleAngle,
    TitleCandidate,
)
from croviq_domain.release_review import (
    ClaimSupportStatus,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseVerdict,
)
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
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


@pytest.fixture
def sample_short_artifact() -> RenderArtifact:
    return RenderArtifact(
        artifact_id="art_short_01",
        production_id="prod_0b7657f515ae",
        edl_id="edl_01",
        artifact_type=ArtifactType.SHORT,
        status=ArtifactStatus.completed,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_0b7657f515ae/renders/short.mp4",
        duration_ms=39800,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_packaging_proposal_with_unsupported_claim() -> PackagingProposal:
    now = datetime.now(timezone.utc)
    return PackagingProposal(
        proposal_id="pkg_fairphone6p_001",
        production_id="prod_0b7657f515ae",
        agent="nina",
        model="gemini-3.7-flash",
        primary_title="Fairphone 6 Plus: The Modular Smartphone That Actually Makes Sense",
        title_candidates=[
            TitleCandidate(
                text="Fairphone 6 Plus: The Modular Smartphone That Actually Makes Sense",
                angle=TitleAngle.PROBLEM_SOLUTION,
                why_it_works="Highlights modularity and practical repair.",
                confidence=0.96,
            )
        ],
        description=(
            "Here is our hands-on look at the Fairphone 6 Plus! Featuring upgraded Snapdragon internals, "
            "12GB RAM, microSD card expansion, swappable modular backplates, and up to 12 user-replaceable parts.\n\n"
            "Stay tuned for the upcoming full Fairphone 6+ review!\n\n"
            "0:00 Introduction & Unboxing\n0:18 Modular Accessories"
        ),
        chapters=[
            PackagingChapter(start_ms=0, end_ms=18000, formatted_time="0:00", title="Introduction & Unboxing"),
            PackagingChapter(start_ms=18000, end_ms=51000, formatted_time="0:18", title="Modular Accessories & Swapping Backplates"),
            PackagingChapter(start_ms=51000, end_ms=113824, formatted_time="0:51", title="Repairability & 12 Replaceable Parts"),
        ],
        keywords=["fairphone", "repairability", "modular tech", "hardware teardown"],
        thumbnail_concepts=[
            ThumbnailConcept(
                concept_id="th_01",
                headline="MODULAR PHONE!",
                visual_subject="Fairphone 6 Plus cobalt blue backplate being removed",
                composition="Close up hands holding screwdriver loosening Fairphone module",
                emotion="Curiosity",
                supporting_frame_ms=28000,
                reason="Shows modular repairability clearly",
                confidence=0.96,
                frame_verified=True,
            )
        ],
        short_package=ShortPackage(
            title="A Modern Smartphone You Can Actually Repair! 📱 #Shorts",
            description="The Fairphone 6 Plus lets you replace up to 12 parts yourself. #fairphone #tech #shorts",
            hook="You can actually repair this smartphone yourself!",
            hashtags=["#fairphone", "#tech", "#shorts"],
        ),
        packaging_summary="Modular phone teardown and repairability overview.",
        channel_evidence="Channel baseline supports technical hardware teardowns.",
        confidence=0.95,
        created_at=now,
        master_artifact_id="art_mast_01",
    )


def test_build_release_qa_prompt(
    sample_transcript,
    sample_master_artifact,
    sample_short_artifact,
    sample_packaging_proposal_with_unsupported_claim,
):
    prompt = build_release_qa_prompt(
        transcript=sample_transcript,
        master_artifact=sample_master_artifact,
        short_artifact=sample_short_artifact,
        proposal=sample_packaging_proposal_with_unsupported_claim,
        production_id="prod_0b7657f515ae",
    )

    assert "IRIS — QUALITY ASSURANCE RELEASE GATE" in prompt
    assert "Fairphone 6 Plus" in prompt
    assert "CLAIM AUDIT & FACT CHECKING" in prompt
    assert "Stay tuned for the upcoming full Fairphone 6+ review!" in prompt


@pytest.mark.asyncio
async def test_iris_flags_unsupported_upcoming_review_claim(
    sample_transcript,
    sample_master_artifact,
    sample_short_artifact,
    sample_packaging_proposal_with_unsupported_claim,
):
    fake_client = FakeGenAIClient()
    iris = IrisQAAgent(genai_client=fake_client, model_id="gemini-3.7-flash")

    review, usage = await iris.review_production(
        production_id="prod_0b7657f515ae",
        master_artifact=sample_master_artifact,
        short_artifact=sample_short_artifact,
        transcript=sample_transcript,
        proposal=sample_packaging_proposal_with_unsupported_claim,
        request_id="test_qa_01",
    )

    assert review.agent == "iris"
    assert review.verdict == ReleaseVerdict.FIX_REQUIRED
    assert review.approved_for_release is False
    assert len(review.issues) >= 1
    assert any(
        "upcoming full" in issue.message.lower() or "upcoming full" in issue.evidence.lower()
        for issue in review.issues
    )
    assert any(
        issue.issue_type == ReleaseIssueType.UNSUPPORTED_CLAIM
        for issue in review.issues
    )
    # Check claim audit
    claim_statuses = {c.claim_text: c.status for c in review.claim_verifications}
    assert any("upcoming full" in k.lower() for k in claim_statuses)


@pytest.mark.asyncio
async def test_nina_correction_and_iris_pass(
    sample_transcript,
    sample_master_artifact,
    sample_short_artifact,
    sample_packaging_proposal_with_unsupported_claim,
):
    fake_client = FakeGenAIClient()
    iris = IrisQAAgent(genai_client=fake_client, model_id="gemini-3.7-flash")
    nina = NinaPackagingAgent(genai_client=fake_client, model_id="gemini-3.7-flash")

    # 1. Initial Iris check -> FIX_REQUIRED
    initial_review, _ = await iris.review_production(
        production_id="prod_0b7657f515ae",
        master_artifact=sample_master_artifact,
        short_artifact=sample_short_artifact,
        transcript=sample_transcript,
        proposal=sample_packaging_proposal_with_unsupported_claim,
        request_id="test_qa_01",
    )
    assert initial_review.verdict == ReleaseVerdict.FIX_REQUIRED

    # 2. Nina executes 1-cycle auto-correction based on QA issues
    corrected_proposal, _ = await nina.revise_packaging_for_qa(
        production_id="prod_0b7657f515ae",
        current_proposal=sample_packaging_proposal_with_unsupported_claim,
        qa_issues=initial_review.issues,
        master_artifact=sample_master_artifact,
        transcript=sample_transcript,
        request_id="test_qa_correct_01",
    )
    assert "upcoming full" not in corrected_proposal.description.lower()

    # 3. Iris re-evaluates corrected proposal -> PASS
    final_review, _ = await iris.review_production(
        production_id="prod_0b7657f515ae",
        master_artifact=sample_master_artifact,
        short_artifact=sample_short_artifact,
        transcript=sample_transcript,
        proposal=corrected_proposal,
        request_id="test_qa_02",
    )

    assert final_review.verdict == ReleaseVerdict.PASS
    assert final_review.approved_for_release is True
    assert len(final_review.issues) == 0
    assert final_review.checklist.all_passed is True


def test_iris_tool_registry(
    sample_transcript,
    sample_master_artifact,
    sample_short_artifact,
    sample_packaging_proposal_with_unsupported_claim,
):
    registry = build_default_iris_tool_registry(
        master_artifact=sample_master_artifact,
        short_artifact=sample_short_artifact,
        transcript=sample_transcript,
        proposal=sample_packaging_proposal_with_unsupported_claim,
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
    assert registry.has_tool("inspect_short")
    # Execute verify_claim tool on unsupported claim
    res = registry.execute(
        "verify_claim",
        {
            "claim_text": "Stay tuned for the upcoming full Fairphone 6+ review!",
            "location": "description",
        },
    )
    assert res.status == "success"
    assert res.output["status"] == "UNSUPPORTED"
