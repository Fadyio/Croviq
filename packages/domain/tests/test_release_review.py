"""Unit tests for Iris QA and Release Review domain models (Issue #33)."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from croviq_domain.agent_config import AgentId
from croviq_domain.release_review import (
    ClaimSupportStatus,
    ClaimVerification,
    ConfidenceScoreBreakdown,
    GrammarScoreBreakdown,
    QualityScoreBreakdown,
    ReeseMetadataRecommendation,
    ReleaseChecklist,
    ReleaseIssue,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseReview,
    ReleaseStatus,
    ReleaseVerdict,
    ThumbnailEvaluation,
    build_release_fingerprint,
    compute_confidence_score,
    compute_grammar_score,
    compute_quality_score,
    generate_reese_metadata,
    get_creator_facing_release_status,
    get_issue_type_friendly_label,
    verify_release_fingerprint,
)


def test_agent_id_contains_iris():
    assert AgentId.IRIS.value == "iris"
    assert AgentId("iris") == AgentId.IRIS


def test_issue_type_friendly_labels():
    assert get_issue_type_friendly_label(ReleaseIssueType.AUDIO_ARTIFACT) == "Audio Artifact"
    assert get_issue_type_friendly_label(ReleaseIssueType.CAPTION_TIMING) == "Caption Timing Drift"
    assert get_issue_type_friendly_label(ReleaseIssueType.UNSUPPORTED_CLAIM) == "Unsupported Claim"
    assert get_issue_type_friendly_label(ReleaseIssueType.CHAPTER_TIMING) == "Chapter Timestamp Issue"


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
        packaging_proposal_id="pkg_01",
        checklist=ReleaseChecklist(
            master_video=True,
            audio=True,
            captions=True,
            chapters=True,
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
        packaging_proposal_id="pkg_01",
        checklist=ReleaseChecklist(
            master_video=True,
            audio=True,
            captions=True,
            chapters=True,
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
def test_release_fingerprint_deterministic_and_verification():
    fp1 = build_release_fingerprint(
        production_id="prod_01",
        edl_id="edl_01",
        master_artifact_id="art_master_01",
        master_hash="sha256_master_hash_abc",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_review_id="rev_01",
    )
    fp2 = build_release_fingerprint(
        production_id="prod_01",
        edl_id="edl_01",
        master_artifact_id="art_master_01",
        master_hash="sha256_master_hash_abc",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_review_id="rev_01",
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # Valid SHA256 hex string

    is_valid = verify_release_fingerprint(
        expected_fingerprint=fp1,
        production_id="prod_01",
        edl_id="edl_01",
        master_artifact_id="art_master_01",
        master_hash="sha256_master_hash_abc",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_review_id="rev_01",
    )
    assert is_valid is True


def test_release_fingerprint_detects_tampering_or_mismatch():
    base_fp = build_release_fingerprint(
        production_id="prod_01",
        edl_id="edl_01",
        master_artifact_id="art_master_01",
        master_hash="sha256_master_hash_abc",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_review_id="rev_01",
    )

    # 1. Tampered EDL
    assert verify_release_fingerprint(
        expected_fingerprint=base_fp,
        production_id="prod_01",
        edl_id="edl_02_new",
        master_artifact_id="art_master_01",
        master_hash="sha256_master_hash_abc",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_review_id="rev_01",
    ) is False

    # 2. Tampered Master artifact
    assert verify_release_fingerprint(
        expected_fingerprint=base_fp,
        production_id="prod_01",
        edl_id="edl_01",
        master_artifact_id="art_master_02",
        master_hash="sha256_master_hash_abc",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_review_id="rev_01",
    ) is False

    # 3. Tampered master content hash
    assert verify_release_fingerprint(
        expected_fingerprint=base_fp,
        production_id="prod_01",
        edl_id="edl_01",
        master_artifact_id="art_master_01",
        master_hash="sha256_master_hash_DIFFERENT",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_review_id="rev_01",
    ) is False

    # 4. Newer packaging version
    assert verify_release_fingerprint(
        expected_fingerprint=base_fp,
        production_id="prod_01",
        edl_id="edl_01",
        master_artifact_id="art_master_01",
        master_hash="sha256_master_hash_abc",
        packaging_proposal_id="pkg_01",
        package_version=2,
        release_review_id="rev_01",
    ) is False


def test_release_review_stores_lineage_and_fingerprint():
    now = datetime.now(timezone.utc)
    fp = build_release_fingerprint(
        production_id="prod_01",
        edl_id="edl_01",
        master_artifact_id="art_master_01",
        master_hash="hash_m1",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_review_id="rev_01",
    )
    review = ReleaseReview(
        review_id="rev_01",
        production_id="prod_01",
        agent="iris",
        model="gemini-3.7-flash",
        verdict=ReleaseVerdict.PASS,
        summary="Quality passed perfectly.",
        issues=[],
        approved_for_release=True,
        confidence=0.98,
        created_at=now,
        edl_id="edl_01",
        master_artifact_id="art_master_01",
        master_hash="hash_m1",
        packaging_proposal_id="pkg_01",
        package_version=1,
        release_fingerprint=fp,
    )
    assert review.release_fingerprint == fp
    assert review.compute_fingerprint() == fp
def test_compute_quality_score_rubric_weights():
    # Narrative 76 (25%), Audio 92 (20%), Captions 97 (20%), Visual 88 (15%), Factual 95 (20%)
    # Expected: 76*0.25 + 92*0.20 + 97*0.20 + 88*0.15 + 95*0.20
    # = 19.0 + 18.4 + 19.4 + 13.2 + 19.0 = 89.0
    score, breakdown = compute_quality_score(
        narrative_score=76.0,
        audio_score=92.0,
        caption_score=97.0,
        visual_score=88.0,
        factual_score=95.0,
    )
    assert score == 89.0
    assert breakdown.quality_score == 89.0
    assert breakdown.narrative_score == 76.0
    assert breakdown.audio_score == 92.0
    assert breakdown.caption_score == 97.0
    assert breakdown.visual_score == 88.0
    assert breakdown.factual_score == 95.0


def test_compute_grammar_score_normalized():
    # 1 Major error (-12) and 1 Moderate error (-6) on 200 words
    # Raw penalty = 18.0. Normalization per 100 words (200 words = 2.0x 100 words):
    # Normalized deduction = 18.0 / 2.0 = 9.0% -> Score = 91.0%
    issues = [
        ReleaseIssue(
            issue_id="iss_01",
            issue_type=ReleaseIssueType.GRAMMAR_ERROR,
            severity=ReleaseIssueSeverity.HIGH,
            source_start_ms=16000,
            source_end_ms=23000,
            message="Broken sentence structure and hesitation",
            suggested_action="Clean narration join",
            evidence="Spoken stumbles in transcript",
        ),
        ReleaseIssue(
            issue_id="iss_02",
            issue_type=ReleaseIssueType.AUDIO_ARTIFACT,
            severity=ReleaseIssueSeverity.MEDIUM,
            source_start_ms=48000,
            source_end_ms=50000,
            message="Repeated word hesitation",
            suggested_action="Trim repetition",
            evidence="Repeated words in transcript",
        ),
    ]
    score, breakdown = compute_grammar_score(
        issues=issues,
        word_count=200,
        analyzed_source="raw transcript",
    )
    assert score == 91.0
    assert breakdown.major_errors_count == 1
    assert breakdown.moderate_errors_count == 1
    assert breakdown.minor_errors_count == 0
    assert len(breakdown.deductions) == 2


def test_compute_confidence_score_evidence_coverage():
    # Full coverage: 1.0*0.30 + 1.0*0.25 + 1.0*0.25 + 1.0*0.20 = 1.0 (100%)
    score_full, b_full = compute_confidence_score(
        transcript_coverage=1.0,
        visual_coverage=1.0,
        audio_coverage=1.0,
        checks_completed=1.0,
    )
    assert score_full == 1.0

    # Missing audio inspection (e.g. 0.0 audio coverage)
    # 1.0*0.30 + 0.92*0.25 + 0.0*0.25 + 1.0*0.20 = 0.30 + 0.23 + 0.0 + 0.20 = 0.73
    score_dropped, b_dropped = compute_confidence_score(
        transcript_coverage=1.0,
        visual_coverage=0.92,
        audio_coverage=0.0,
        checks_completed=1.0,
    )
    assert score_dropped == 0.73
    assert any("Audio inspection coverage at 0%" in m for m in b_dropped.missing_evidence)


def test_generate_reese_metadata_video_understanding():
    transcript = "In this video we walk through GitHub Actions workflows for deploying to Google Cloud using Workload Identity Federation."
    meta = generate_reese_metadata(
        transcript_text=transcript,
        proposal_title=None,
        proposal_description=None,
    )
    assert "GitHub Actions" in meta.recommended_title
    assert "Google Cloud" in meta.recommended_title or "Workload Identity" in meta.recommended_title
    assert "GitHub Actions" in meta.technical_topics
    assert len(meta.recommended_description) > 30
