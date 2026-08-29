"""Unit tests for RenderReview domain models (Issue #30)."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.render_review import (
    RenderReview,
    RenderReviewIssue,
    RenderReviewIssueType,
    RenderReviewSeverity,
    RenderReviewVerdict,
)


def test_render_review_issue_valid() -> None:
    issue = RenderReviewIssue(
        issue_id="issue_01",
        issue_type=RenderReviewIssueType.OVER_AGGRESSIVE_CUT,
        source_start_ms=12000,
        source_end_ms=14500,
        related_decision_id="dec_01",
        severity=RenderReviewSeverity.MEDIUM,
        message="One cut feels too aggressive. Restoring context.",
        suggested_action="Restore explanatory clause",
    )
    assert issue.issue_id == "issue_01"
    assert issue.issue_type == RenderReviewIssueType.OVER_AGGRESSIVE_CUT
    assert issue.severity == RenderReviewSeverity.MEDIUM
    assert issue.related_decision_id == "dec_01"


def test_render_review_issue_rejects_inverted_times() -> None:
    with pytest.raises(ValidationError, match="source_end_ms"):
        RenderReviewIssue(
            issue_id="issue_02",
            issue_type=RenderReviewIssueType.VISUAL_JUMP,
            source_start_ms=10000,
            source_end_ms=9000,
            severity=RenderReviewSeverity.HIGH,
            message="Visual jump cut detected",
            suggested_action="Cover with B-roll",
        )


def test_render_review_approve_valid() -> None:
    now = datetime.now(timezone.utc)
    review = RenderReview(
        review_id="rrv_12345",
        production_id="prod_test",
        edl_id="edl_test",
        preview_artifact_id="art_prev_1",
        agent="iris",
        model="gemini-3.7-flash",
        verdict=RenderReviewVerdict.APPROVE,
        summary="Dialogue flows naturally and pacing is crisp. Ready for master.",
        issues=[],
        approved_for_master=True,
        confidence=0.95,
        created_at=now,
    )
    assert review.verdict == RenderReviewVerdict.APPROVE
    assert review.approved_for_master is True
    assert len(review.issues) == 0


def test_render_review_correct_valid() -> None:
    now = datetime.now(timezone.utc)
    review = RenderReview(
        review_id="rrv_67890",
        production_id="prod_test",
        edl_id="edl_test",
        preview_artifact_id="art_prev_1",
        agent="iris",
        model="gemini-3.7-flash",
        verdict=RenderReviewVerdict.CORRECT,
        summary="One unnatural audio cut near 00:14 needs context restoration.",
        issues=[
            RenderReviewIssue(
                issue_id="issue_01",
                issue_type=RenderReviewIssueType.UNNATURAL_AUDIO_JOIN,
                source_start_ms=14000,
                source_end_ms=16000,
                severity=RenderReviewSeverity.HIGH,
                message="Sentence join sounds clipped at the transition.",
                suggested_action="Widen boundary or keep previous sentence",
            )
        ],
        approved_for_master=False,
        confidence=0.88,
        created_at=now,
    )
    assert review.verdict == RenderReviewVerdict.CORRECT
    assert review.approved_for_master is False
    assert len(review.issues) == 1
    assert review.issues[0].issue_type == RenderReviewIssueType.UNNATURAL_AUDIO_JOIN


def test_render_review_requires_timezone_aware() -> None:
    naive_dt = datetime.now()
    with pytest.raises(ValidationError, match="timezone-aware"):
        RenderReview(
            review_id="rrv_invalid_dt",
            production_id="prod_test",
            edl_id="edl_test",
            preview_artifact_id="art_prev_1",
            agent="iris",
            model="gemini-3.7-flash",
            verdict=RenderReviewVerdict.APPROVE,
            summary="Looks good.",
            issues=[],
            approved_for_master=True,
            confidence=0.9,
            created_at=naive_dt,
        )
