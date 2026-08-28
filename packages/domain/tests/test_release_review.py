"""Unit tests for Iris QA and Release Review domain models (Issue #33)."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.agent_config import AgentId
from croviq_domain.release_review import (
    ClaimSupportStatus,
    ClaimVerification,
    ReleaseChecklist,
    ReleaseIssue,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseReview,
    ReleaseStatus,
    ReleaseVerdict,
    ThumbnailEvaluation,
    get_creator_facing_release_status,
    get_issue_type_friendly_label,
)


def test_agent_id_contains_iris():
    assert AgentId.IRIS.value == "iris"
    assert AgentId("iris") == AgentId.IRIS


def test_issue_type_friendly_labels():
    assert get_issue_type_friendly_label(ReleaseIssueType.AUDIO_ARTIFACT) == "Audio Artifact"
    assert get_issue_type_friendly_label(ReleaseIssueType.CAPTION_TIMING) == "Caption Timing Drift"
    assert get_issue_type_friendly_label(ReleaseIssueType.UNSUPPORTED_CLAIM) == "Unsupported Claim"
    assert get_issue_type_friendly_label(ReleaseIssueType.CHAPTER_TIMING) == "Chapter Timestamp Issue"
    assert get_issue_type_friendly_label(ReleaseIssueType.SHORT_CROP) == "Short Vertical Framing Issue"


def test_creator_facing_release_status():
    assert get_creator_facing_release_status(ReleaseStatus.PACKAGING) == "Packaging"
    assert get_creator_facing_release_status(ReleaseStatus.CHECKING) == "Checking final output"
    assert get_creator_facing_release_status(ReleaseStatus.FIX_REQUIRED) == "Fix required"
    assert get_creator_facing_release_status(ReleaseStatus.MANUAL_REVIEW) == "Manual review"
    assert get_creator_facing_release_status(ReleaseStatus.READY_TO_PUBLISH) == "Ready to publish"


def test_release_review_validation_pass():
    now = datetime.now(timezone.utc)
    review = ReleaseReview(
        review_id="rev_01",
        production_id="prod_01",
        agent="iris",
        model="gemini-3.7-flash",
        verdict=ReleaseVerdict.PASS,
        summary="All quality and packaging verification checks passed.",
        issues=[],
        approved_for_release=True,
        confidence=0.98,
        created_at=now,
        master_artifact_id="art_master_01",
        short_artifact_id="art_short_01",
        packaging_proposal_id="pkg_01",
        checklist=ReleaseChecklist(
            master_video=True,
            audio=True,
            captions=True,
            chapters=True,
            short=True,
            packaging=True,
            claims=True,
        ),
        claim_verifications=[
            ClaimVerification(
                claim_text="12 user-replaceable parts",
                location="description",
                status=ClaimSupportStatus.SUPPORTED_BY_VIDEO,
                evidence="At 00:51, host demonstrates phone disassembly and repair parts.",
            )
        ],
        thumbnail_evaluations=[
            ThumbnailEvaluation(
                concept_index=0,
                headline="MODULAR PHONE!",
                verdict="PASS",
                reason="Clear sharp frame with phone backplate being unscrewed.",
            )
        ],
    )

    assert review.agent == "iris"
    assert review.verdict == ReleaseVerdict.PASS
    assert review.approved_for_release is True
    assert len(review.issues) == 0
    assert review.checklist.all_passed is True


def test_release_review_validation_fix_required():
    now = datetime.now(timezone.utc)
    review = ReleaseReview(
        review_id="rev_02",
        production_id="prod_01",
        agent="iris",
        model="gemini-3.7-flash",
        verdict=ReleaseVerdict.FIX_REQUIRED,
        summary="Found 1 unsupported future promise in description.",
        issues=[
            ReleaseIssue(
                issue_id="iss_01",
                issue_type=ReleaseIssueType.UNSUPPORTED_CLAIM,
                severity=ReleaseIssueSeverity.HIGH,
                source_start_ms=None,
                source_end_ms=None,
                artifact_type="packaging",
                related_decision_id=None,
                message="Description claims an upcoming full review that isn't supported.",
                suggested_action="Remove the upcoming review promise from YouTube description.",
                evidence="Claim: 'Stay tuned for the upcoming full Fairphone 6+ review!' has no corroboration.",
            )
        ],
        approved_for_release=False,
        confidence=0.95,
        created_at=now,
        master_artifact_id="art_master_01",
        packaging_proposal_id="pkg_01",
        checklist=ReleaseChecklist(
            master_video=True,
            audio=True,
            captions=True,
            chapters=True,
            short=True,
            packaging=False,
            claims=False,
        ),
    )

    assert review.verdict == ReleaseVerdict.FIX_REQUIRED
    assert review.approved_for_release is False
    assert len(review.issues) == 1
    assert review.issues[0].severity == ReleaseIssueSeverity.HIGH
    assert review.checklist.all_passed is False


def test_release_review_fails_when_pass_has_blocking_issues():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ReleaseReview(
            review_id="rev_03",
            production_id="prod_01",
            agent="iris",
            model="gemini-3.7-flash",
            verdict=ReleaseVerdict.PASS,
            summary="Invalid pass with blocking issue",
            issues=[
                ReleaseIssue(
                    issue_id="iss_02",
                    issue_type=ReleaseIssueType.BAD_CUT,
                    severity=ReleaseIssueSeverity.BLOCKING,
                    message="Broken cut",
                    suggested_action="Fix cut",
                    evidence="Jump cut at 00:12",
                )
            ],
            approved_for_release=True,
            confidence=0.95,
            created_at=now,
            master_artifact_id="art_master_01",
            packaging_proposal_id="pkg_01",
        )
