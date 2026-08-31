"""Canonical domain models for Iris QA Agent and Release Gate (Issue #33)."""

from datetime import datetime, timezone
from enum import StrEnum
import hashlib
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from croviq_domain.validators import validate_timezone_aware


class ReleaseVerdict(StrEnum):
    """Evaluation verdict issued by Iris (QA Agent) for publishing gate."""

    PASS = "PASS"
    FIX_REQUIRED = "FIX_REQUIRED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ReleaseIssueSeverity(StrEnum):
    """Severity classification of identified quality or packaging defects."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKING = "BLOCKING"


class ReleaseIssueType(StrEnum):
    """Categorized quality and factual issues evaluated by Iris."""

    # Audio issues
    AUDIO_ARTIFACT = "AUDIO_ARTIFACT"
    AUDIO_LEVEL = "AUDIO_LEVEL"
    AUDIO_SYNC = "AUDIO_SYNC"

    # Video & Edit issues
    BAD_CUT = "BAD_CUT"
    VISUAL_JUMP = "VISUAL_JUMP"
    BLACK_FRAME = "BLACK_FRAME"
    FRAME_GLITCH = "FRAME_GLITCH"
    ENCODE_ISSUE = "ENCODE_ISSUE"

    # Caption issues
    CAPTION_MISMATCH = "CAPTION_MISMATCH"
    CAPTION_TIMING = "CAPTION_TIMING"
    CAPTION_OVERFLOW = "CAPTION_OVERFLOW"

    # Chapter issues
    CHAPTER_MISMATCH = "CHAPTER_MISMATCH"
    CHAPTER_TIMING = "CHAPTER_TIMING"

    # Claim & Factual issues
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    FACTUAL_INCONSISTENCY = "FACTUAL_INCONSISTENCY"

    # Packaging issues
    TITLE_MISMATCH = "TITLE_MISMATCH"
    DESCRIPTION_MISMATCH = "DESCRIPTION_MISMATCH"
    THUMBNAIL_MISMATCH = "THUMBNAIL_MISMATCH"
    PACKAGING_INCONSISTENCY = "PACKAGING_INCONSISTENCY"


    # Editorial continuity
    MISSING_CONTENT = "MISSING_CONTENT"
    CONTEXT_LOSS = "CONTEXT_LOSS"


ISSUE_TYPE_FRIENDLY_NAMES: dict[ReleaseIssueType, str] = {
    ReleaseIssueType.AUDIO_ARTIFACT: "Audio Artifact",
    ReleaseIssueType.AUDIO_LEVEL: "Audio Level",
    ReleaseIssueType.AUDIO_SYNC: "Audio / Video Sync",
    ReleaseIssueType.BAD_CUT: "Bad Cut / Edit Gap",
    ReleaseIssueType.VISUAL_JUMP: "Visual Jump Cut",
    ReleaseIssueType.BLACK_FRAME: "Black Frame / Freeze",
    ReleaseIssueType.FRAME_GLITCH: "Visual Glitch",
    ReleaseIssueType.ENCODE_ISSUE: "Encoding Issue",
    ReleaseIssueType.CAPTION_MISMATCH: "Caption Text Mismatch",
    ReleaseIssueType.CAPTION_TIMING: "Caption Timing Drift",
    ReleaseIssueType.CAPTION_OVERFLOW: "Caption Overflow",
    ReleaseIssueType.CHAPTER_MISMATCH: "Chapter Topic Mismatch",
    ReleaseIssueType.CHAPTER_TIMING: "Chapter Timestamp Issue",
    ReleaseIssueType.UNSUPPORTED_CLAIM: "Unsupported Claim",
    ReleaseIssueType.FACTUAL_INCONSISTENCY: "Factual Inconsistency",
    ReleaseIssueType.TITLE_MISMATCH: "Title Content Mismatch",
    ReleaseIssueType.DESCRIPTION_MISMATCH: "Description Mismatch",
    ReleaseIssueType.THUMBNAIL_MISMATCH: "Thumbnail Concept Mismatch",
    ReleaseIssueType.PACKAGING_INCONSISTENCY: "Packaging Inconsistency",
    ReleaseIssueType.MISSING_CONTENT: "Missing Content / Demo",
    ReleaseIssueType.CONTEXT_LOSS: "Context Loss",
}


def get_issue_type_friendly_label(issue_type: ReleaseIssueType | str) -> str:
    """Return product-facing friendly name for a ReleaseIssueType."""
    if isinstance(issue_type, ReleaseIssueType) and issue_type in ISSUE_TYPE_FRIENDLY_NAMES:
        return ISSUE_TYPE_FRIENDLY_NAMES[issue_type]
    try:
        typed = ReleaseIssueType(str(issue_type))
        return ISSUE_TYPE_FRIENDLY_NAMES.get(
            typed, str(issue_type).replace("_", " ").title()
        )
    except ValueError:
        return str(issue_type).replace("_", " ").title()


class ClaimSupportStatus(StrEnum):
    """Categorized status for claim evaluation."""

    SUPPORTED_BY_VIDEO = "SUPPORTED_BY_VIDEO"
    SUPPORTED_EXTERNALLY = "SUPPORTED_EXTERNALLY"
    UNSUPPORTED = "UNSUPPORTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ClaimVerification(BaseModel):
    """Individual factual or packaging claim verification result."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    claim_text: str = Field(..., min_length=2, max_length=500, description="Specific factual claim examined")
    location: str = Field(default="description", description="Where the claim appears (title, description, video, or chapter)")
    status: ClaimSupportStatus = Field(..., description="Claim support status")
    evidence: str = Field(..., min_length=2, max_length=1000, description="Evidence or rationale supporting status")
    source_url: str | None = Field(default=None, description="External reference URL if verified externally")


class ThumbnailEvaluation(BaseModel):
    """Evaluation of a specific creator thumbnail concept."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    concept_index: int = Field(..., ge=0, description="Index of evaluated thumbnail concept")
    headline: str = Field(..., min_length=1, max_length=100, description="Thumbnail headline text")
    verdict: str = Field(..., description="PASS or REJECT")
    reason: str = Field(..., min_length=2, max_length=500, description="Concise visual QA assessment")


class ReleaseChecklist(BaseModel):
    """Compact status checklist for release components."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    master_video: bool = Field(default=True, description="Master video continuity and encoding status")
    audio: bool = Field(default=True, description="Audio level, peak, and sync status")
    captions: bool = Field(default=True, description="Caption accuracy, timing, and bounds status")
    chapters: bool = Field(default=True, description="Chapter timestamp ordering and topic accuracy")
    packaging: bool = Field(default=True, description="Packaging title, description, and thumbnail status")
    claims: bool = Field(default=True, description="Factual and packaging claims validity status")

    @property
    def all_passed(self) -> bool:
        return (
            self.master_video
            and self.audio
            and self.captions
            and self.chapters
            and self.packaging
            and self.claims
        )


class ReleaseStatus(StrEnum):
    """Creator-facing release pipeline status."""

    PACKAGING = "packaging"
    CHECKING = "checking"
    FIX_REQUIRED = "fix_required"
    MANUAL_REVIEW = "manual_review"
    READY_TO_PUBLISH = "ready_to_publish"


def get_creator_facing_release_status(status: ReleaseStatus | str) -> str:
    """Return user-facing text for release status without exposing raw enums."""
    mapping = {
        ReleaseStatus.PACKAGING: "Packaging",
        ReleaseStatus.CHECKING: "Checking final output",
        ReleaseStatus.FIX_REQUIRED: "Fix required",
        ReleaseStatus.MANUAL_REVIEW: "Manual review",
        ReleaseStatus.READY_TO_PUBLISH: "Ready to publish",
    }
    if isinstance(status, ReleaseStatus) and status in mapping:
        return mapping[status]
    try:
        typed = ReleaseStatus(str(status).lower())
        return mapping.get(typed, str(status).replace("_", " ").title())
    except ValueError:
        return str(status).replace("_", " ").title()


class ReleaseIssue(BaseModel):
    """Specific defect, inconsistency, or unverified claim flagged by Iris."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    issue_id: str = Field(..., min_length=3, max_length=64, description="Unique identifier for the issue")
    issue_type: ReleaseIssueType = Field(..., description="Categorized issue type")
    severity: ReleaseIssueSeverity = Field(..., description="Severity level")
    source_start_ms: int | None = Field(default=None, ge=0, description="Start timestamp in video ms if time-bound")
    source_end_ms: int | None = Field(default=None, ge=0, description="End timestamp in video ms if time-bound")
    artifact_type: str | None = Field(default=None, description="Affected artifact type (master, packaging, caption, or chapter)")
    related_decision_id: str | None = Field(default=None, description="Related editorial or packaging decision ID if applicable")
    message: str = Field(..., min_length=5, max_length=1000, description="Concise creator-facing description of defect")
    suggested_action: str = Field(..., min_length=5, max_length=1000, description="Concrete suggested fix or routing")
    evidence: str = Field(..., min_length=2, max_length=2000, description="Objective factual or media evidence observed")

    @model_validator(mode="after")
    def validate_timestamps(self) -> "ReleaseIssue":
        if (
            self.source_start_ms is not None
            and self.source_end_ms is not None
            and self.source_end_ms < self.source_start_ms
        ):
            raise ValueError(
                f"source_end_ms ({self.source_end_ms}) cannot be before source_start_ms ({self.source_start_ms})"
            )
        return self


class ReleaseReview(BaseModel):
    """Canonical release evaluation emitted by Iris (QA Agent)."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    review_id: str = Field(..., min_length=3, max_length=64, description="Unique review identifier")
    production_id: str = Field(..., min_length=3, max_length=64, description="Parent production ID")
    agent: str = Field(default="iris", description="Evaluating agent identifier (must be iris)")
    model: str = Field(default="gemini-3.7-flash", description="Underlying multimodal GenAI model ID")
    verdict: ReleaseVerdict = Field(..., description="Overall gate verdict (PASS, FIX_REQUIRED, MANUAL_REVIEW)")
    summary: str = Field(..., min_length=5, max_length=2000, description="Concise synthesis of evaluation findings")
    issues: list[ReleaseIssue] = Field(default_factory=list, description="List of identified issues")
    approved_for_release: bool = Field(default=False, description="True if output satisfies all quality thresholds")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0, description="Iris assessment confidence score")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of evaluation generation",
    )
    preview_mode: str = Field(default="final_mix", description="Reviewed preview mode: original | edited | voiceover | final_mix")
    reviewed_artifact_id: str | None = Field(default=None, description="Exact RenderArtifact ID or source artifact ID reviewed")
    reviewed_artifact_uri: str | None = Field(default=None, description="Exact GCS URI or object reviewed")
    reviewed_voice_id: str | None = Field(default=None, description="Rendered voice ID if voiceover or final_mix")
    edl_id: str | None = Field(default=None, description="Evaluated EditDecisionList ID")
    master_artifact_id: str | None = Field(default=None, description="Evaluated Master RenderArtifact ID")
    master_hash: str | None = Field(default=None, description="SHA-256 hash of evaluated Master RenderArtifact")
    packaging_proposal_id: str | None = Field(default=None, description="Evaluated PackagingProposal ID")
    package_version: int = Field(default=1, ge=1, description="Evaluated PackagingProposal version number")
    release_fingerprint: str | None = Field(
        default=None,
        description="SHA-256 cryptographic release fingerprint binding immutable pipeline inputs",
    )
    checklist: ReleaseChecklist = Field(
        default_factory=ReleaseChecklist,
        description="Compact component checklist summary",
    )
    claim_verifications: list[ClaimVerification] = Field(
        default_factory=list,
        description="Itemized factual and packaging claim audits",
    )
    thumbnail_evaluations: list[ThumbnailEvaluation] = Field(
        default_factory=list,
        description="Evaluations of thumbnail concepts",
    )

    @field_validator("created_at")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime:
        return validate_timezone_aware(v)

    @model_validator(mode="after")
    def validate_verdict_consistency(self) -> "ReleaseReview":
        blocking_or_high = [
            i
            for i in self.issues
            if i.severity in (ReleaseIssueSeverity.BLOCKING, ReleaseIssueSeverity.HIGH)
        ]
        if self.verdict == ReleaseVerdict.PASS:
            if blocking_or_high:
                raise ValueError("Verdict PASS cannot contain BLOCKING or HIGH severity issues.")
            if not self.approved_for_release:
                raise ValueError("Verdict PASS must have approved_for_release=True.")
        elif self.verdict == ReleaseVerdict.FIX_REQUIRED:
            if self.approved_for_release:
                raise ValueError("Verdict FIX_REQUIRED cannot have approved_for_release=True.")
        elif self.verdict == ReleaseVerdict.MANUAL_REVIEW:
            if self.approved_for_release:
                raise ValueError("Verdict MANUAL_REVIEW cannot have approved_for_release=True.")
        return self

    def compute_fingerprint(self) -> str:
        """Compute and return canonical release fingerprint for this review instance."""
        return build_release_fingerprint(
            production_id=self.production_id,
            edl_id=self.edl_id or "unknown_edl",
            master_artifact_id=self.master_artifact_id or "unknown_master",
            master_hash=self.master_hash or "unknown_master_hash",
            packaging_proposal_id=self.packaging_proposal_id or "unknown_pkg",
            package_version=self.package_version,
            release_review_id=self.review_id,
        )


def build_release_fingerprint(
    production_id: str,
    edl_id: str,
    master_artifact_id: str,
    master_hash: str,
    packaging_proposal_id: str,
    package_version: int = 1,
    release_review_id: str | None = None,
) -> str:
    """Build canonical SHA-256 release fingerprint binding immutable release inputs."""
    payload = (
        f"{production_id}:{edl_id}:{master_artifact_id}:{master_hash}:"
        f"{packaging_proposal_id}:{package_version}:{release_review_id or 'pending'}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_release_fingerprint(
    expected_fingerprint: str,
    production_id: str,
    edl_id: str,
    master_artifact_id: str,
    master_hash: str,
    packaging_proposal_id: str,
    package_version: int = 1,
    release_review_id: str | None = None,
) -> bool:
    """Verify that current production state matches the locked release fingerprint."""
    computed = build_release_fingerprint(
        production_id=production_id,
        edl_id=edl_id,
        master_artifact_id=master_artifact_id,
        master_hash=master_hash,
        packaging_proposal_id=packaging_proposal_id,
        package_version=package_version,
        release_review_id=release_review_id,
    )
    return computed == expected_fingerprint
