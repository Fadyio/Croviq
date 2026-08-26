from datetime import datetime, timezone
import pytest

from croviq_agents.client import FakeGenAIClient
from croviq_agents.director import MayaDirector
from croviq_agents.editor import LeoDialogueEditor
from croviq_domain.edl import EditDecisionList
from croviq_domain.editorial import (
    DirectorDecision,
    DirectorReview,
    DirectorVerdict,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
)
from croviq_domain.render_review import (
    RenderReview,
    RenderReviewIssue,
    RenderReviewIssueType,
    RenderReviewSeverity,
    RenderReviewVerdict,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.production import SourceMedia, SourceMediaStatus
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord


def _sample_analysis_input() -> SourceVideoAnalysisInput:
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=0, end_ms=400),
        TranscriptWord(index=1, text="um", start_ms=410, end_ms=700),
        TranscriptWord(index=2, text="to", start_ms=710, end_ms=900),
        TranscriptWord(index=3, text="Croviq.", start_ms=910, end_ms=1300),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_001",
            start_ms=0,
            end_ms=1300,
            text="Welcome um to Croviq.",
            word_start_index=0,
            word_end_index=3,
        )
    ]
    transcript = Transcript(
        transcript_id="tr_dir_test",
        production_id="prod_dir_test",
        language_code="en-US",
        duration_ms=1300,
        words=words,
        segments=segments,
        created_at=datetime.now(timezone.utc),
    )
    source_media = SourceMedia(
        upload_id="up_dir_test",
        original_filename="test.mp4",
        content_type="video/mp4",
        size_bytes=1048576,
        gcs_bucket="croviq-media-raw",
        gcs_object="workspaces/ws_01/productions/prod_dir_test/source/up_dir_test/test.mp4",
        status=SourceMediaStatus.UPLOADED,
        created_at=datetime.now(timezone.utc),
        uploaded_at=datetime.now(timezone.utc),
    )
    media_metadata = MediaMetadata(
        duration_ms=1300,
        width=1920,
        height=1080,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        rotation=0,
        size_bytes=1048576,
    )
    return SourceVideoAnalysisInput(
        production_id="prod_dir_test",
        source_media=source_media,
        media_metadata=media_metadata,
        transcript=transcript,
        channel_id="chan_ai_eng",
    )


@pytest.mark.asyncio
async def test_maya_director_reviews_proposal_and_generates_verdicts() -> None:
    fake_client = FakeGenAIClient()
    director = MayaDirector(client=fake_client)
    analysis_input = _sample_analysis_input()

    proposal = EditorProposal(
        production_id="prod_dir_test",
        agent="leo",
        model="fake-gemini-3.7-flash",
        summary="Proposed 1 filler cut",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=1,
                transcript_end_word=1,
                source_start_ms=410,
                source_end_ms=700,
                original_text="um",
                action="remove",
                concise_reason="Remove filler",
                confidence=0.95,
            )
        ],
        overall_confidence=0.95,
    )

    review, usage, activities = await director.review(
        analysis_input=analysis_input,
        proposal=proposal,
        channel_profile=None,
        lessons=None,
        run_id="run_dir_01",
        request_id="req_dir_01",
    )

    assert review.production_id == "prod_dir_test"
    assert review.agent == "maya"
    assert review.approved_for_edl is True
    assert len(review.decisions) == 1
    assert review.decisions[0].verdict == DirectorVerdict.APPROVE

    # Verify activities
    assert len(activities) >= 2
    assessment_act = activities[0]
    assert assessment_act.agent == "Maya"
    assert assessment_act.role == "Director"
    assert assessment_act.activity_type == "review"
    assert assessment_act.production_id == "prod_dir_test"
    assert assessment_act.run_id == "run_dir_01"


@pytest.mark.asyncio
async def test_maya_director_can_reject_or_modify_decisions() -> None:
    custom_review = DirectorReview(
        production_id="prod_dir_test",
        agent="maya",
        model="fake-gemini-3.7-flash",
        overall_assessment="Rejected aggressive cuts to protect essential tutorial setup",
        decisions=[
            DirectorDecision(
                editor_decision_id="dec_01",
                verdict=DirectorVerdict.REJECT,
                concise_reason="Rejected. This sentence explains the security boundary and should remain.",
            )
        ],
        editor_feedback="Do not cut security explanations in the intro.",
        approved_for_edl=False,
        confidence=0.91,
    )

    fake_client = FakeGenAIClient(canned_review=custom_review)
    director = MayaDirector(client=fake_client)
    analysis_input = _sample_analysis_input()

    proposal = EditorProposal(
        production_id="prod_dir_test",
        agent="leo",
        model="fake-gemini-3.7-flash",
        summary="Proposed cut",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=1,
                transcript_end_word=1,
                source_start_ms=410,
                source_end_ms=700,
                original_text="um",
                action="remove",
                concise_reason="Remove filler",
                confidence=0.95,
            )
        ],
        overall_confidence=0.9,
    )

    review, usage, activities = await director.review(
        analysis_input=analysis_input,
        proposal=proposal,
        channel_profile=None,
        lessons=None,
        run_id="run_dir_02",
    )

    assert review.approved_for_edl is False
    assert review.decisions[0].verdict == DirectorVerdict.REJECT
    assert "security boundary" in review.decisions[0].concise_reason

    reject_acts = [a for a in activities if a.related_decision_id == "dec_01"]
    assert len(reject_acts) == 1
    assert "[REJECT]" in reject_acts[0].message


@pytest.mark.asyncio
async def test_maya_director_review_render_approve() -> None:
    fake_client = FakeGenAIClient()
    director = MayaDirector(client=fake_client)
    analysis_input = _sample_analysis_input()

    proposal = EditorProposal(
        production_id="prod_dir_test",
        model="gemini-3.7-flash",
        summary="Initial dialogue pass",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=1,
                transcript_end_word=1,
                source_start_ms=410,
                source_end_ms=550,
                original_text="to",
                action="remove",
                concise_reason="Remove filler",
                confidence=0.95,
            )
        ],
        short_candidate=None,
        overall_confidence=0.94,
    )

    edl = EditDecisionList(
        edl_id="edl_test_1",
        production_id="prod_dir_test",
        source_duration_ms=analysis_input.transcript.duration_ms,
        cuts=[],
        coverage_markers=[],
        created_at=datetime.now(timezone.utc),
    )

    render_review, usage, activities = await director.review_render(
        preview_gcs_bucket="croviq-media-raw",
        preview_gcs_object="workspaces/ws_test/productions/prod_dir_test/renders/edl_test_1/preview.mp4",
        preview_artifact_id="art_prev_01",
        edl=edl,
        proposal=proposal,
        director_review=None,
        transcript=analysis_input.transcript,
        production_id="prod_dir_test",
        run_id="run_dir_01",
    )

    assert render_review.verdict == RenderReviewVerdict.APPROVE
    assert render_review.approved_for_master is True
    assert len(render_review.issues) == 0
    assert len(activities) >= 1
    assert activities[0].agent == "Maya"
    assert activities[0].role == "Director"
    assert "Edit approved." in activities[0].message


@pytest.mark.asyncio
async def test_maya_director_review_render_correct() -> None:
    canned_issue = RenderReviewIssue(
        issue_id="iss_01",
        issue_type=RenderReviewIssueType.OVER_AGGRESSIVE_CUT,
        source_start_ms=400,
        source_end_ms=600,
        related_decision_id="dec_01",
        severity=RenderReviewSeverity.MEDIUM,
        message="One cut feels too aggressive. Restoring context.",
        suggested_action="Restore explanatory clause",
    )
    canned_review = RenderReview(
        review_id="rrv_correct",
        production_id="prod_dir_test",
        edl_id="edl_test_1",
        preview_artifact_id="art_prev_01",
        agent="maya",
        model="fake-gemini-3.7-flash",
        verdict=RenderReviewVerdict.CORRECT,
        summary="One cut near 00:00 feels too aggressive. Restoring context.",
        issues=[canned_issue],
        approved_for_master=False,
        confidence=0.89,
        created_at=datetime.now(timezone.utc),
    )
    fake_client = FakeGenAIClient(canned_render_review=canned_review)
    director = MayaDirector(client=fake_client)
    analysis_input = _sample_analysis_input()

    proposal = EditorProposal(
        production_id="prod_dir_test",
        model="gemini-3.7-flash",
        summary="Initial dialogue pass",
        decisions=[],
        short_candidate=None,
        overall_confidence=0.94,
    )
    edl = EditDecisionList(
        edl_id="edl_test_1",
        production_id="prod_dir_test",
        source_duration_ms=analysis_input.transcript.duration_ms,
        cuts=[],
        coverage_markers=[],
        created_at=datetime.now(timezone.utc),
    )

    render_review, usage, activities = await director.review_render(
        preview_gcs_bucket="croviq-media-raw",
        preview_gcs_object="workspaces/ws_test/productions/prod_dir_test/renders/edl_test_1/preview.mp4",
        preview_artifact_id="art_prev_01",
        edl=edl,
        proposal=proposal,
        director_review=None,
        transcript=analysis_input.transcript,
        production_id="prod_dir_test",
        run_id="run_dir_01",
    )

    assert render_review.verdict == RenderReviewVerdict.CORRECT
    assert render_review.approved_for_master is False
    assert len(render_review.issues) == 1
    assert any("Restoring context" in act.message for act in activities)
