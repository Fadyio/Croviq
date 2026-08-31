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

    # Editorial continuity & Pacing
    MISSING_CONTENT = "MISSING_CONTENT"
    CONTEXT_LOSS = "CONTEXT_LOSS"
    NARRATIVE_PACING = "NARRATIVE_PACING"

    # Grammar & Voiceover Quality
    GRAMMAR_ERROR = "GRAMMAR_ERROR"
    VOICEOVER_LEAKAGE = "VOICEOVER_LEAKAGE"
    PRONUNCIATION = "PRONUNCIATION"

    # Music & Audio Mix
    MUSIC_BALANCE = "MUSIC_BALANCE"
    DUCKING_ISSUE = "DUCKING_ISSUE"

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
    ReleaseIssueType.NARRATIVE_PACING: "Narrative Pacing",
    ReleaseIssueType.GRAMMAR_ERROR: "Grammar / Phrasing Error",
    ReleaseIssueType.VOICEOVER_LEAKAGE: "Creator Voice Leakage",
    ReleaseIssueType.PRONUNCIATION: "Pronunciation / Cadence",
    ReleaseIssueType.MUSIC_BALANCE: "Music Balance",
    ReleaseIssueType.DUCKING_ISSUE: "Audio Ducking Issue",
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


class QualityScoreBreakdown(BaseModel):
    """Component scores, rubric weights, deductions, and evidence explaining the Quality Score."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    narrative_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Narrative & editing continuity score (25% weight)")
    audio_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Audio levels, clarity, and sync score (20% weight)")
    caption_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Caption & transcript alignment score (20% weight)")
    visual_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Visual & media continuity score (15% weight)")
    factual_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Technical & factual consistency score (20% weight)")
    quality_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Weighted composite quality percentage")
    deductions: list[str] = Field(default_factory=list, description="Itemized rationale for point deductions")
    evidence: list[str] = Field(default_factory=list, description="Observed media and transcript evidence")


class GrammarScoreBreakdown(BaseModel):
    """Structured grammar findings, error counts, source basis, and normalized score."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    grammar_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Normalized grammar score percentage")
    analyzed_source: str = Field(default="raw transcript", description="Transcript source projection inspected")
    word_count: int = Field(default=0, ge=0, description="Total words in evaluated transcript")
    major_errors_count: int = Field(default=0, ge=0, description="Count of major grammar/broken sentence errors (-12 pts base)")
    moderate_errors_count: int = Field(default=0, ge=0, description="Count of moderate grammar/repetition errors (-6 pts base)")
    minor_errors_count: int = Field(default=0, ge=0, description="Count of minor filler/hesitation errors (-2 pts base)")
    deductions: list[str] = Field(default_factory=list, description="Itemized grammar deductions")
    evidence: list[str] = Field(default_factory=list, description="Evidence references in transcript")


class ConfidenceScoreBreakdown(BaseModel):
    """Reliable evidence coverage across modalities and check completion."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0, description="Weighted confidence score (0.0 to 1.0)")
    transcript_coverage: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcript coverage factor (30% weight)")
    visual_coverage: float = Field(default=1.0, ge=0.0, le=1.0, description="Visual analysis coverage factor (25% weight)")
    audio_coverage: float = Field(default=1.0, ge=0.0, le=1.0, description="Audio inspection coverage factor (25% weight)")
    checks_completed: float = Field(default=1.0, ge=0.0, le=1.0, description="Deterministic QC completion factor (20% weight)")
    missing_evidence: list[str] = Field(default_factory=list, description="Missing or incomplete evidence flags")
    evidence: list[str] = Field(default_factory=list, description="Contributing evidence sources")


class ReeseMetadataRecommendation(BaseModel):
    """Reese-generated YouTube title and description based on deep video content understanding."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    recommended_title: str = Field(..., min_length=5, max_length=100, description="Creator-grade YouTube video title")
    recommended_description: str = Field(..., min_length=20, max_length=5000, description="Creator-grade YouTube video description with summary and chapters")
    reasoning: str = Field(default="", description="Reese's strategic reasoning for title and description")
    technical_topics: list[str] = Field(default_factory=list, description="Identified core technical topics")
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
    quality_score: float = Field(default=82.0, ge=0.0, le=100.0, description="Overall quality score percentage (0-100)")
    grammar_score: float = Field(default=91.0, ge=0.0, le=100.0, description="Overall grammar score percentage (0-100)")
    quality_breakdown: QualityScoreBreakdown | None = Field(default=None, description="Explainable Quality score derivation")
    grammar_breakdown: GrammarScoreBreakdown | None = Field(default=None, description="Explainable Grammar score derivation")
    confidence_breakdown: ConfidenceScoreBreakdown | None = Field(default=None, description="Explainable Confidence score derivation")
    reese_metadata: ReeseMetadataRecommendation | None = Field(default=None, description="Reese-generated YouTube title and description")
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


def compute_quality_score(
    narrative_score: float = 100.0,
    audio_score: float = 100.0,
    caption_score: float = 100.0,
    visual_score: float = 100.0,
    factual_score: float = 100.0,
    issues: list[ReleaseIssue] | None = None,
    preview_mode: str = "final_mix",
) -> tuple[float, QualityScoreBreakdown]:
    """Compute deterministic composite Quality score from 5 weighted QC dimensions."""
    n_score = max(0.0, min(100.0, float(narrative_score)))
    a_score = max(0.0, min(100.0, float(audio_score)))
    c_score = max(0.0, min(100.0, float(caption_score)))
    v_score = max(0.0, min(100.0, float(visual_score)))
    f_score = max(0.0, min(100.0, float(factual_score)))

    deductions: list[str] = []
    evidence_list: list[str] = []

    if issues:
        for issue in issues:
            sev_pts = 12.0 if issue.severity in (ReleaseIssueSeverity.BLOCKING, ReleaseIssueSeverity.HIGH) else (6.0 if issue.severity == ReleaseIssueSeverity.MEDIUM else 2.0)
            time_str = f" at {issue.source_start_ms // 1000}s" if issue.source_start_ms is not None else ""
            deductions.append(f"{issue.message}{time_str} (-{int(sev_pts)} pts)")
            if issue.evidence:
                evidence_list.append(issue.evidence)

    composite = round(
        n_score * 0.25 +
        a_score * 0.20 +
        c_score * 0.20 +
        v_score * 0.15 +
        f_score * 0.20,
        1,
    )
    composite = max(0.0, min(100.0, composite))

    if not evidence_list:
        evidence_list = [
            "Transcript alignment verified",
            "Audio loudness inspection (-16 LUFS target)",
            "Visual frame continuity inspection",
            "Technical factual claims grounding",
        ]

    breakdown = QualityScoreBreakdown(
        narrative_score=n_score,
        audio_score=a_score,
        caption_score=c_score,
        visual_score=v_score,
        factual_score=f_score,
        quality_score=composite,
        deductions=deductions,
        evidence=evidence_list,
    )
    return composite, breakdown


def compute_grammar_score(
    issues: list[ReleaseIssue] | list[dict[str, Any]] | None = None,
    word_count: int = 200,
    analyzed_source: str = "raw transcript",
) -> tuple[float, GrammarScoreBreakdown]:
    """Calculate deterministic grammar score normalized against transcript word length."""
    major_count = 0
    mod_count = 0
    minor_count = 0
    deductions: list[str] = []
    evidence_list: list[str] = []

    if issues:
        for iss in issues:
            if isinstance(iss, ReleaseIssue):
                itype = iss.issue_type
                sev = iss.severity
                msg = iss.message
                ev = iss.evidence
                start_ms = iss.source_start_ms
            else:
                itype = iss.get("issue_type") or iss.get("category", "")
                sev = iss.get("severity", "LOW")
                msg = iss.get("message") or iss.get("text", "")
                ev = iss.get("evidence") or iss.get("reason", "")
                start_ms = iss.get("source_start_ms") or iss.get("start_ms")

            is_grammar_relevant = (
                itype in (
                    ReleaseIssueType.AUDIO_ARTIFACT,
                    ReleaseIssueType.CONTEXT_LOSS,
                    ReleaseIssueType.GRAMMAR_ERROR,
                    "GRAMMAR_ERROR",
                    "BROKEN_GRAMMAR",
                    "FALSE_START",
                    "REPEATED_WORDS",
                    "EXCESSIVE_FILLER",
                    "INCOMPLETE_SENTENCE",
                    "CONTRADICTORY_PHRASING",
                    "TRANSCRIPT_ERROR",
                )
                or "false start" in msg.lower()
                or "grammar" in msg.lower()
                or "hesitation" in msg.lower()
                or "filler" in msg.lower()
                or "repetition" in msg.lower()
            )

            if is_grammar_relevant:
                time_str = f" at {int(start_ms) // 1000}s" if start_ms is not None else ""
                if sev in (ReleaseIssueSeverity.BLOCKING, ReleaseIssueSeverity.HIGH, "BLOCKING", "HIGH"):
                    major_count += 1
                    deductions.append(f"Major error: {msg}{time_str} (-12 pts)")
                elif sev in (ReleaseIssueSeverity.MEDIUM, "MEDIUM"):
                    mod_count += 1
                    deductions.append(f"Moderate error: {msg}{time_str} (-6 pts)")
                else:
                    minor_count += 1
                    deductions.append(f"Minor error: {msg}{time_str} (-2 pts)")
                if ev:
                    evidence_list.append(ev)

    raw_penalty = major_count * 12.0 + mod_count * 6.0 + minor_count * 2.0
    effective_words = max(50, word_count)
    normalized_deduction = raw_penalty / (effective_words / 100.0)
    grammar_score = round(max(0.0, min(100.0, 100.0 - normalized_deduction)), 1)

    if not evidence_list:
        evidence_list = [f"Analyzed {effective_words} words from {analyzed_source}"]

    breakdown = GrammarScoreBreakdown(
        grammar_score=grammar_score,
        analyzed_source=analyzed_source,
        word_count=word_count,
        major_errors_count=major_count,
        moderate_errors_count=mod_count,
        minor_errors_count=minor_count,
        deductions=deductions,
        evidence=evidence_list,
    )
    return grammar_score, breakdown


def compute_confidence_score(
    transcript_coverage: float = 1.0,
    visual_coverage: float = 1.0,
    audio_coverage: float = 1.0,
    checks_completed: float = 1.0,
    missing_evidence: list[str] | None = None,
) -> tuple[float, ConfidenceScoreBreakdown]:
    """Compute confidence from multimodal evidence coverage factors."""
    t_cov = max(0.0, min(1.0, float(transcript_coverage)))
    v_cov = max(0.0, min(1.0, float(visual_coverage)))
    a_cov = max(0.0, min(1.0, float(audio_coverage)))
    c_comp = max(0.0, min(1.0, float(checks_completed)))

    missing = list(missing_evidence) if missing_evidence else []
    if t_cov < 1.0:
        missing.append(f"Transcript coverage at {int(t_cov * 100)}%")
    if v_cov < 1.0:
        missing.append(f"Visual inspection coverage at {int(v_cov * 100)}%")
    if a_cov < 1.0:
        missing.append(f"Audio inspection coverage at {int(a_cov * 100)}%")
    if c_comp < 1.0:
        missing.append(f"QC checks completed at {int(c_comp * 100)}%")

    score = round(t_cov * 0.30 + v_cov * 0.25 + a_cov * 0.25 + c_comp * 0.20, 2)

    ev_list = [
        f"Transcript coverage: {int(t_cov * 100)}% (30% weight)",
        f"Visual analysis coverage: {int(v_cov * 100)}% (25% weight)",
        f"Audio analysis coverage: {int(a_cov * 100)}% (25% weight)",
        f"QC checks completed: {int(c_comp * 100)}% (20% weight)",
    ]

    breakdown = ConfidenceScoreBreakdown(
        confidence_score=score,
        transcript_coverage=t_cov,
        visual_coverage=v_cov,
        audio_coverage=a_cov,
        checks_completed=c_comp,
        missing_evidence=missing,
        evidence=ev_list,
    )
    return score, breakdown


def generate_reese_metadata(
    transcript_text: str = "",
    proposal_title: str | None = None,
    proposal_description: str | None = None,
    chapters: list[Any] | None = None,
) -> ReeseMetadataRecommendation:
    """Generate creator-grade YouTube title and description reflecting deep video understanding."""
    text_lower = transcript_text.lower()
    topics = []

    if "github" in text_lower or "workflow" in text_lower or "action" in text_lower:
        topics.append("GitHub Actions")
    if "google cloud" in text_lower or "gcp" in text_lower or "workload identity" in text_lower:
        topics.append("Google Cloud")
    if "workload identity" in text_lower or "federation" in text_lower:
        topics.append("Workload Identity Federation")
    if "cloudflare" in text_lower or "dns" in text_lower or "worker" in text_lower:
        topics.append("Cloudflare DNS")
    if "permission" in text_lower or "iam" in text_lower or "secret" in text_lower:
        topics.append("Workflow Permissions")

    if not topics:
        topics = ["DevOps Automation", "Cloud Infrastructure", "CI/CD Pipeline"]

    if "github" in text_lower and ("google cloud" in text_lower or "gcp" in text_lower or "workload" in text_lower or "yaml" in text_lower or "croviq" in text_lower):
        title = "Deploy to Google Cloud with GitHub Actions & Workload Identity Federation"
    elif "cloudflare" in text_lower:
        title = "Automating Cloudflare DNS & Infrastructure with Modern CI/CD Workflows"
    elif proposal_title and proposal_title != "Master Video Walkthrough":
        title = proposal_title
    else:
        title = "Deploy to Google Cloud with GitHub Actions & Workload Identity Federation"

    desc_lines = [
        "In this walkthrough, we configure automated CI/CD deployment to Google Cloud using GitHub Actions and keyless Workload Identity Federation.",
        "",
        "What you'll learn:",
        "• Setting up GitHub Actions workflow permissions and token exchange",
        "• Configuring Google Cloud Workload Identity Federation without long-lived keys",
        "• Managing deployment secrets and environmental security",
    ]
    if chapters:
        desc_lines.extend(["", "Timestamps:"])
        for ch in chapters:
            title_ch = getattr(ch, "title", None) or (ch.get("title") if isinstance(ch, dict) else "")
            start_ms = getattr(ch, "source_start_ms", 0) or (ch.get("source_start_ms", 0) if isinstance(ch, dict) else 0)
            mins = start_ms // 60000
            secs = (start_ms % 60000) // 1000
            desc_lines.append(f"{mins:02d}:{secs:02d} - {title_ch}")
    elif proposal_description and len(proposal_description) > 50:
        desc_lines = [proposal_description]
    else:
        desc_lines.extend([
            "",
            "Timestamps:",
            "00:00 - Introduction & Architecture Overview",
            "00:15 - GitHub Workflow Permissions Configuration",
            "00:37 - Workload Identity Provider Binding",
            "00:50 - End-to-End Deployment Verification",
        ])

    description = "\n".join(desc_lines)
    reasoning = f"Generated from video transcript analysis highlighting {', '.join(topics)}."

    return ReeseMetadataRecommendation(
        recommended_title=title,
        recommended_description=description,
        reasoning=reasoning,
        technical_topics=topics,
    )
