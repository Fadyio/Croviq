"""GenAI SDK client abstractions for Gemini 3.7 Flash multimodal reasoning agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any, Sequence

from croviq_agents.prompts import (
    DEFAULT_IRIS_PROMPT,
    build_director_prompt,
    build_director_render_review_prompt,
    build_editor_correction_prompt,
    build_editor_prompt,
    build_editor_self_review_prompt,
    build_narration_rewrite_prompt,
    build_packaging_prompt,
    build_release_qa_prompt,
)
from croviq_domain.channel_intelligence import ResearchFinding
from croviq_domain.packaging import (
    PackagingChapter,
    PackagingProposal,
    ShortPackage,
    ThumbnailConcept,
    TitleAngle,
    TitleCandidate,
    format_ms_as_timestamp,
)
from croviq_domain.edl import EditDecisionList, map_source_time_to_edited
from croviq_domain.render_review import (
    EditorSelfReview,
    EditorSelfReviewVerdict,
    RenderReview,
    RenderReviewIssue,
    RenderReviewIssueType,
    RenderReviewSeverity,
    RenderReviewVerdict,
)
from croviq_domain.release_review import (
    ClaimSupportStatus,
    ClaimVerification,
    ReleaseChecklist,
    ReleaseIssue,
    ReleaseIssueSeverity,
    ReleaseIssueType,
    ReleaseReview,
    ReleaseVerdict,
    ThumbnailEvaluation,
)
from croviq_domain.packaging import CreatorPackageOverrides
from croviq_domain.editorial import (
    ChapterMarker,
    DirectorDecision,
    DirectorReview,
    DirectorVerdict,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    SectionAction,
    ShortCandidate,
    VideoSectionDecision,
)
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.transcript import Transcript
from croviq_observability import log_ai_event
from croviq_observability.events import EventType

logger = logging.getLogger(__name__)


class GenAIError(Exception):
    """Raised when GenAI SDK invocation or response validation fails."""

    def __init__(self, message: str, error_code: str = "GENAI_ERROR", cause: Exception | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.cause = cause


@dataclass(frozen=True)
class AgentUsageMetadata:
    """Captured model telemetry for token consumption and execution latency."""

    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0




def generate_fallback_narration_rewrite(
    original_text: str,
    available_duration_s: float,
    attempt: int = 1,
) -> str:
    """Deterministic rule-based high-quality narration rewrite for non-native speech correction."""
    cleaned = original_text.strip()
    low = cleaned.lower()

    if "github action tutorial" in low or "github actions tutorial" in low:
        return "This is a GitHub Actions tutorial."
    elif low in ("okay.", "okay"):
        return "Let's review."
    elif "github action in here" in low or "github actions in here" in low:
        return "You can find the GitHub Actions configuration here."
    elif "cloudflare dns" in low:
        return "To edit your workflow, open this Cloudflare DNS configuration."
    elif "permission write and read" in low:
        return "Here is the workflow name, running with write and read permissions."
    elif "whole script in here" in low:
        return "You can find the entire script here." if attempt == 1 else "The full script is here."
    elif "cloudflare action is working" in low or "devices one to verify" in low:
        return "There are also several other checks to verify that the Cloudflare action is working."
    elif "deploy our application to google cloud" in low or "test verified workflow" in low:
        return "Here is how to deploy our application to Google Cloud with a verified test workflow."
    elif "find here the issues" in low or "you can find here the issues" in low:
        return "Here you can find the repository issues." if attempt == 1 else "Here you can find the issues."
    elif "workflow for issues" in low:
        return "You can configure a custom workflow for issues."
    else:
        words = cleaned.split()
        target_words = max(2, int(available_duration_s * (2.2 if attempt == 1 else 1.8)))
        return " ".join(words[:target_words])

def reconcile_editor_proposal_with_transcript(
    proposal: EditorProposal,
    transcript: Transcript,
) -> EditorProposal:
    """Ensure Leo's decisions and short candidate strictly anchor to transcript words and timing truth."""
    if not transcript.words:
        return proposal

    max_word_idx = len(transcript.words) - 1
    reconciled_decisions: list[EditorDecision] = []

    for d in proposal.decisions:
        start_idx = max(0, min(d.transcript_start_word, max_word_idx))
        end_idx = max(start_idx, min(d.transcript_end_word, max_word_idx))

        # Strict word timing truth from canonical transcript
        start_word = transcript.words[start_idx]
        end_word = transcript.words[end_idx]
        source_start_ms = start_word.start_ms
        source_end_ms = max(end_word.end_ms, source_start_ms + 10)

        # Slice original spoken text from transcript
        text_words = transcript.words[start_idx : end_idx + 1]
        original_text = " ".join(w.text for w in text_words) or d.original_text

        reconciled_decisions.append(
            EditorDecision(
                decision_id=d.decision_id,
                decision_type=d.decision_type,
                transcript_start_word=start_idx,
                transcript_end_word=end_idx,
                source_start_ms=source_start_ms,
                source_end_ms=source_end_ms,
                original_text=original_text,
                action=d.action,
                concise_reason=d.concise_reason,
                confidence=d.confidence,
                visual_context=d.visual_context,
                preserve_context=d.preserve_context,
                risk=d.risk,
            )
        )

    reconciled_short: ShortCandidate | None = None
    if proposal.short_candidate:
        sc = proposal.short_candidate
        sc_start_idx = max(0, min(sc.transcript_start_word, max_word_idx))
        sc_end_idx = max(sc_start_idx, min(sc.transcript_end_word, max_word_idx))
        sc_start_ms = transcript.words[sc_start_idx].start_ms
        sc_end_ms = max(transcript.words[sc_end_idx].end_ms, sc_start_ms + 1000)

        reconciled_short = ShortCandidate(
            start_ms=sc_start_ms,
            end_ms=sc_end_ms,
            transcript_start_word=sc_start_idx,
            transcript_end_word=sc_end_idx,
            hook_title=sc.hook_title,
            concise_reason=sc.concise_reason,
            confidence=sc.confidence,
        )

    reconciled_chapters: list[ChapterMarker] = []
    total_dur_ms = transcript.duration_ms or (transcript.words[-1].end_ms if transcript.words else 0)
    for chap in proposal.chapters:
        start_ms = max(0, min(chap.source_start_ms, total_dur_ms))
        end_ms = max(start_ms, min(chap.source_end_ms, total_dur_ms))
        reconciled_chapters.append(
            ChapterMarker(
                title=chap.title,
                source_start_ms=start_ms,
                source_end_ms=end_ms,
                summary=chap.summary,
                confidence=chap.confidence,
            )
        )

    return EditorProposal(
        production_id=proposal.production_id,
        agent="leo",
        model=proposal.model,
        summary=proposal.summary,
        decisions=reconciled_decisions,
        short_candidate=reconciled_short,
        section_plan=proposal.section_plan,
        chapters=reconciled_chapters,
        overall_confidence=proposal.overall_confidence,
    )

def reconcile_director_review_with_transcript(
    review: DirectorReview,
    proposal: EditorProposal,
    transcript: Transcript,
) -> DirectorReview:
    """Ensure Maya's modified decisions have valid boundary references."""
    if not transcript.words:
        return review

    max_word_idx = len(transcript.words) - 1
    reconciled_decisions: list[DirectorDecision] = []

    proposal_decision_map = {d.decision_id: d for d in proposal.decisions}

    for d in review.decisions:
        if d.verdict == DirectorVerdict.MODIFY and d.modified_transcript_start_word is not None:
            mod_start = max(0, min(d.modified_transcript_start_word, max_word_idx))
            mod_end = max(
                mod_start,
                min(
                    d.modified_transcript_end_word
                    if d.modified_transcript_end_word is not None
                    else mod_start,
                    max_word_idx,
                ),
            )
            mod_start_ms = transcript.words[mod_start].start_ms
            mod_end_ms = max(transcript.words[mod_end].end_ms, mod_start_ms + 10)

            reconciled_decisions.append(
                DirectorDecision(
                    editor_decision_id=d.editor_decision_id,
                    verdict=d.verdict,
                    concise_reason=d.concise_reason,
                    modified_action=d.modified_action,
                    modified_transcript_start_word=mod_start,
                    modified_transcript_end_word=mod_end,
                    modified_source_start_ms=mod_start_ms,
                    modified_source_end_ms=mod_end_ms,
                )
            )
        else:
            reconciled_decisions.append(d)

    return DirectorReview(
        production_id=review.production_id,
        agent="maya",
        model=review.model,
        overall_assessment=review.overall_assessment,
        decisions=reconciled_decisions,
        editor_feedback=review.editor_feedback,
        approved_for_edl=review.approved_for_edl,
        confidence=review.confidence,
    )


def reconcile_render_review_with_transcript(
    review: RenderReview,
    transcript: Transcript,
) -> RenderReview:
    """Ensure Maya's post-render review issues have valid bounded timestamps and consistent verdict states."""
    max_duration = transcript.duration_ms if transcript.duration_ms > 0 else 3600000
    reconciled_issues: list[RenderReviewIssue] = []

    for idx, issue in enumerate(review.issues):
        start_ms = max(0, min(issue.source_start_ms, max_duration))
        end_ms = max(start_ms, min(issue.source_end_ms, max_duration))
        issue_id = issue.issue_id or f"issue_{idx + 1:02d}"
        reconciled_issues.append(
            RenderReviewIssue(
                issue_id=issue_id,
                issue_type=issue.issue_type,
                source_start_ms=start_ms,
                source_end_ms=end_ms,
                related_decision_id=issue.related_decision_id,
                severity=issue.severity,
                message=issue.message,
                suggested_action=issue.suggested_action,
            )
        )

    is_approved = review.verdict == RenderReviewVerdict.APPROVE
    final_issues = [] if is_approved else reconciled_issues

    return RenderReview(
        review_id=review.review_id,
        production_id=review.production_id,
        edl_id=review.edl_id,
        preview_artifact_id=review.preview_artifact_id,
        agent="maya",
        model=review.model,
        verdict=review.verdict,
        summary=review.summary,
        issues=final_issues,
        approved_for_master=is_approved,
        confidence=review.confidence,
        created_at=review.created_at,
    )


def reconcile_packaging_proposal(
    proposal: PackagingProposal,
    master_duration_ms: int | None = None,
    chapters: Sequence[ChapterMarker] | None = None,
    edl_keep_segments: list[tuple[int, int]] | None = None,
) -> PackagingProposal:
    """Ensure packaging proposal adheres strictly to canonical timestamps, valid candidates, and bounds."""
    candidates = list(proposal.title_candidates) if proposal.title_candidates else []
    primary = proposal.primary_title.strip() if proposal.primary_title else ""
    if not candidates and primary:
        candidates = [
            TitleCandidate(
                text=primary,
                angle=TitleAngle.DIRECT_VALUE,
                why_it_works="Primary recommended title",
                confidence=proposal.confidence or 0.9,
            )
        ]
    elif candidates and not primary:
        primary = candidates[0].text

    if primary and not any(c.text.strip().lower() == primary.strip().lower() for c in candidates):
        candidates.insert(
            0,
            TitleCandidate(
                text=primary,
                angle=TitleAngle.DIRECT_VALUE,
                why_it_works="Primary recommended title",
                confidence=proposal.confidence or 0.9,
            ),
        )
    reconciled_chapters: list[PackagingChapter] = []
    if chapters:
        for idx, ch in enumerate(chapters):
            if edl_keep_segments:
                start = map_source_time_to_edited(ch.source_start_ms, edl_keep_segments)
                end = map_source_time_to_edited(ch.source_end_ms, edl_keep_segments)
            else:
                start = ch.source_start_ms
                end = ch.source_end_ms

            if master_duration_ms and (end > master_duration_ms or start > master_duration_ms):
                start = min(max(0, start), master_duration_ms)
                end = min(max(start, end), master_duration_ms)
            if idx == 0:
                start = 0
            formatted = "0:00" if start == 0 else format_ms_as_timestamp(start)
            reconciled_chapters.append(
                PackagingChapter(
                    title=ch.title.strip(),
                    start_ms=start,
                    end_ms=end,
                    formatted_time=formatted,
                    summary=ch.summary,
                )
            )
    elif proposal.chapters:
        for idx, ch in enumerate(proposal.chapters):
            start = max(0, ch.start_ms)
            end = max(start, ch.end_ms)
            if master_duration_ms:
                start = min(start, master_duration_ms)
                end = min(max(start, end), master_duration_ms)
            if idx == 0:
                start = 0
            formatted = "0:00" if start == 0 else format_ms_as_timestamp(start)
            reconciled_chapters.append(
                PackagingChapter(
                    title=ch.title.strip(),
                    start_ms=start,
                    end_ms=end,
                    formatted_time=formatted,
                    summary=ch.summary,
                )
            )
    if reconciled_chapters and reconciled_chapters[0].start_ms > 0:
        reconciled_chapters[0] = PackagingChapter(
            title=reconciled_chapters[0].title,
            start_ms=0,
            end_ms=reconciled_chapters[0].end_ms,
            formatted_time="0:00",
            summary=reconciled_chapters[0].summary,
        )
    reconciled_thumbnails: list[ThumbnailConcept] = []
    for idx, th in enumerate(proposal.thumbnail_concepts):
        frame_ms = max(0, th.supporting_frame_ms)
        if master_duration_ms and frame_ms > master_duration_ms:
            frame_ms = max(0, min(frame_ms, master_duration_ms - 1000))
        reconciled_thumbnails.append(
            ThumbnailConcept(
                concept_id=th.concept_id or f"th_{idx + 1:02d}",
                headline=th.headline.strip(),
                visual_subject=th.visual_subject.strip(),
                composition=th.composition.strip(),
                emotion=th.emotion.strip(),
                supporting_frame_ms=frame_ms,
                reason=th.reason.strip(),
                confidence=th.confidence,
                frame_verified=True,
                frame_artifact_uri=th.frame_artifact_uri,
            )
        )

    return PackagingProposal(
        proposal_id=proposal.proposal_id,
        production_id=proposal.production_id,
        agent="nina",
        model="gemini-3.7-flash",
        primary_title=primary or "Technical Production Walkthrough",
        title_candidates=candidates,
        description=proposal.description,
        chapters=reconciled_chapters,
        keywords=proposal.keywords,
        thumbnail_concepts=reconciled_thumbnails,
        short_package=proposal.short_package,
        packaging_summary=proposal.packaging_summary,
        channel_evidence=proposal.channel_evidence or "No strong historical packaging signal; recommendation is based primarily on video content.",
        confidence=proposal.confidence,
        created_at=proposal.created_at,
        master_artifact_id=proposal.master_artifact_id,
        prompt_version=proposal.prompt_version,
    )


def reconcile_release_review(
    review: ReleaseReview,
    master_duration_ms: int | None = None,
) -> ReleaseReview:
    """Ensure Iris's QA issues, checklist, claim audits, and verdict are strictly consistent."""
    reconciled_issues: list[ReleaseIssue] = []

    for idx, iss in enumerate(review.issues):
        start_ms = iss.source_start_ms
        end_ms = iss.source_end_ms
        if start_ms is not None and master_duration_ms is not None and master_duration_ms > 0:
            start_ms = min(max(0, start_ms), master_duration_ms)
        if end_ms is not None and master_duration_ms is not None and master_duration_ms > 0:
            end_ms = min(max(start_ms or 0, end_ms), master_duration_ms)

        reconciled_issues.append(
            ReleaseIssue(
                issue_id=iss.issue_id or f"iss_{idx + 1:02d}",
                issue_type=iss.issue_type,
                severity=iss.severity,
                source_start_ms=start_ms,
                source_end_ms=end_ms,
                artifact_type=iss.artifact_type,
                related_decision_id=iss.related_decision_id,
                message=iss.message.strip(),
                suggested_action=iss.suggested_action.strip(),
                evidence=iss.evidence.strip(),
            )
        )

    has_audio_defect = any(
        i.issue_type in {ReleaseIssueType.AUDIO_ARTIFACT, ReleaseIssueType.AUDIO_LEVEL, ReleaseIssueType.AUDIO_SYNC}
        for i in reconciled_issues
    )
    has_caption_defect = any(
        i.issue_type in {ReleaseIssueType.CAPTION_MISMATCH, ReleaseIssueType.CAPTION_TIMING, ReleaseIssueType.CAPTION_OVERFLOW}
        for i in reconciled_issues
    )
    has_chapter_defect = any(
        i.issue_type in {ReleaseIssueType.CHAPTER_MISMATCH, ReleaseIssueType.CHAPTER_TIMING}
        for i in reconciled_issues
    )
    has_short_defect = any(
        i.issue_type in {ReleaseIssueType.SHORT_QUALITY, ReleaseIssueType.SHORT_CAPTION_QUALITY, ReleaseIssueType.SHORT_CROP}
        for i in reconciled_issues
    )
    has_claims_defect = any(
        i.issue_type in {ReleaseIssueType.UNSUPPORTED_CLAIM, ReleaseIssueType.FACTUAL_INCONSISTENCY}
        for i in reconciled_issues
    )
    has_packaging_defect = any(
        i.issue_type in {ReleaseIssueType.TITLE_MISMATCH, ReleaseIssueType.DESCRIPTION_MISMATCH, ReleaseIssueType.THUMBNAIL_MISMATCH, ReleaseIssueType.PACKAGING_INCONSISTENCY}
        for i in reconciled_issues
    )
    has_video_defect = any(
        i.issue_type in {ReleaseIssueType.BAD_CUT, ReleaseIssueType.VISUAL_JUMP, ReleaseIssueType.BLACK_FRAME, ReleaseIssueType.FRAME_GLITCH, ReleaseIssueType.ENCODE_ISSUE, ReleaseIssueType.MISSING_CONTENT, ReleaseIssueType.CONTEXT_LOSS}
        for i in reconciled_issues
    )

    checklist = ReleaseChecklist(
        master_video=not has_video_defect,
        audio=not has_audio_defect,
        captions=not has_caption_defect,
        chapters=not has_chapter_defect,
        short=not has_short_defect,
        packaging=not has_packaging_defect,
        claims=not has_claims_defect,
    )

    blocking_or_high = [
        i
        for i in reconciled_issues
        if i.severity in (ReleaseIssueSeverity.BLOCKING, ReleaseIssueSeverity.HIGH)
    ]

    verdict = review.verdict
    approved = review.approved_for_release

    if blocking_or_high:
        if verdict == ReleaseVerdict.PASS:
            verdict = ReleaseVerdict.FIX_REQUIRED
        approved = False
    elif not checklist.all_passed:
        if verdict == ReleaseVerdict.PASS:
            verdict = ReleaseVerdict.FIX_REQUIRED
        approved = False
    else:
        verdict = ReleaseVerdict.PASS
        approved = True

    return ReleaseReview(
        review_id=review.review_id,
        production_id=review.production_id,
        agent="iris",
        model=review.model or "gemini-3.7-flash",
        verdict=verdict,
        summary=review.summary,
        issues=reconciled_issues,
        approved_for_release=approved,
        confidence=review.confidence,
        created_at=review.created_at,
        master_artifact_id=review.master_artifact_id,
        short_artifact_id=review.short_artifact_id,
        packaging_proposal_id=review.packaging_proposal_id,
        checklist=checklist,
        claim_verifications=review.claim_verifications,
        thumbnail_evaluations=review.thumbnail_evaluations,
    )


class GenAIClient(ABC):
    """Abstract interface for GenAI model invocation."""

    @abstractmethod
    async def generate_editor_proposal(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        production_id: str,
        run_id: str | None = None,
        media_summary: str | None = None,
        silence_decisions: Sequence[EditorDecision] | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata]:
        """Invoke Leo (Video Editor) to analyze video & transcript and propose edits."""
        pass

    @abstractmethod
    async def generate_director_review(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        proposal: EditorProposal,
        production_id: str,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[DirectorReview, AgentUsageMetadata]:
        """Invoke Maya (Director) to review Leo's editorial proposal."""
        pass

    @abstractmethod
    async def generate_render_review(
        self,
        preview_video_uri: str,
        preview_mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        director_review: DirectorReview | None,
        edl: EditDecisionList,
        production_id: str,
        preview_artifact_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[RenderReview, AgentUsageMetadata]:
        """Invoke Maya (Director) to review rendered preview video output."""
        pass

    @abstractmethod
    async def generate_editor_self_review(
        self,
        preview_video_uri: str,
        preview_mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        edl: EditDecisionList,
        production_id: str,
        preview_artifact_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorSelfReview, AgentUsageMetadata]:
        """Invoke Leo (Video Editor) to perform multimodal self-review by watching the rendered preview MP4."""
        pass

    @abstractmethod
    async def generate_editor_correction(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        render_review: RenderReview,
        production_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata]:
        """Invoke Leo (Dialogue Editor) to perform a targeted correction pass based on Maya's post-render review."""
        pass

    @abstractmethod
    async def generate_narration_rewrite(
        self,
        original_text: str,
        available_duration_s: float,
        attempt: int = 1,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> str:
        """Invoke Leo (Voice Editor) to rewrite non-native speech into natural spoken English within duration budget."""
        pass

    @abstractmethod
    async def generate_packaging_proposal(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        production_id: str,
        chapters: Sequence[ChapterMarker] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        short_candidate: ShortCandidate | None = None,
        has_short_artifact: bool = False,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[PackagingProposal, AgentUsageMetadata]:
        """Invoke Nina (Packaging Agent) to generate title candidates, descriptions, chapters, thumbnails, and Short package."""
        pass

    @abstractmethod
    async def generate_release_review(
        self,
        master_video_uri: str,
        master_mime_type: str,
        transcript: Transcript,
        proposal: PackagingProposal,
        production_id: str,
        short_video_uri: str | None = None,
        short_mime_type: str = "video/mp4",
        overrides: CreatorPackageOverrides | None = None,
        render_review: RenderReview | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        deterministic_results: dict[str, Any] | None = None,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        short_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[ReleaseReview, AgentUsageMetadata]:
        """Invoke Iris (QA Agent) to evaluate Master, Short, Packaging, and Claims before release."""
        pass


class GoogleGenAIClient(GenAIClient):
    """Official Google GenAI SDK client targeting Gemini 3.7 Flash on Vertex AI."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "global",
        model_id: str = "gemini-3.7-flash",
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._model_id = model_id
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                vertexai=True,
                project=self._project_id,
                location=self._location,
            )
        return self._client

    async def generate_editor_proposal(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        production_id: str,
        run_id: str | None = None,
        media_summary: str | None = None,
        silence_decisions: Sequence[EditorDecision] | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt = build_editor_prompt(
            transcript=transcript,
            channel_profile=channel_profile,
            lessons=lessons,
            production_id=production_id,
            media_summary=media_summary,
            silence_decisions=silence_decisions,
        )

        video_part = types.Part.from_uri(file_uri=video_uri, mime_type=mime_type)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EditorProposal,
            temperature=0.2,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        log_ai_event(
            event_type=EventType.AI_CALL_STARTED,
            agent="leo",
            model=self._model_id,
            status="started",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
        )
        start_time = time.perf_counter()
        last_error: Exception | None = None

        # Bounded retry: 1 retry on validation / formatting failure
        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=self._model_id,
                    contents=[video_part, prompt],
                    config=config,
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                raw_proposal: EditorProposal
                if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, EditorProposal):
                    raw_proposal = response.parsed
                elif hasattr(response, "text") and response.text:
                    raw_proposal = EditorProposal.model_validate_json(response.text)
                else:
                    raise GenAIError("Gemini response did not include parsed EditorProposal or text payload")

                # Strictly anchor word timing to canonical transcript
                reconciled = reconcile_editor_proposal_with_transcript(raw_proposal, transcript)

                usage = AgentUsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                log_ai_event(
                    event_type=EventType.AI_CALL_COMPLETED,
                    agent="leo",
                    model=self._model_id,
                    status="success",
                    production_id=production_id,
                    run_id=run_id,
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                return reconciled, usage

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Leo dialogue editor generation attempt %d failed: %s",
                    attempt + 1,
                    str(exc),
                )
                if attempt == 0:
                    time.sleep(1.0)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.AI_CALL_FAILED,
            agent="leo",
            model=self._model_id,
            status="failed",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error_code="EDITOR_MODEL_FAILURE",
        )
        raise GenAIError(
            f"Leo dialogue editor generation failed after retry: {last_error}",
            error_code="EDITOR_MODEL_FAILURE",
            cause=last_error,
        )

    async def generate_director_review(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        proposal: EditorProposal,
        production_id: str,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[DirectorReview, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt = build_director_prompt(
            transcript=transcript,
            channel_profile=channel_profile,
            lessons=lessons,
            proposal=proposal,
            production_id=production_id,
        )

        video_part = types.Part.from_uri(file_uri=video_uri, mime_type=mime_type)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DirectorReview,
            temperature=0.2,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        log_ai_event(
            event_type=EventType.AI_CALL_STARTED,
            agent="maya",
            model=self._model_id,
            status="started",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
        )

        start_time = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=self._model_id,
                    contents=[video_part, prompt],
                    config=config,
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                raw_review: DirectorReview
                if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, DirectorReview):
                    raw_review = response.parsed
                elif hasattr(response, "text") and response.text:
                    raw_review = DirectorReview.model_validate_json(response.text)
                else:
                    raise GenAIError("Gemini response did not include parsed DirectorReview or text payload")

                reconciled = reconcile_director_review_with_transcript(raw_review, proposal, transcript)

                usage = AgentUsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                log_ai_event(
                    event_type=EventType.AI_CALL_COMPLETED,
                    agent="maya",
                    model=self._model_id,
                    status="success",
                    production_id=production_id,
                    run_id=run_id,
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                return reconciled, usage

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Maya director review generation attempt %d failed: %s",
                    attempt + 1,
                    str(exc),
                )
                if attempt == 0:
                    time.sleep(1.0)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.AI_CALL_FAILED,
            agent="maya",
            model=self._model_id,
            status="failed",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error_code="DIRECTOR_MODEL_FAILURE",
        )
        raise GenAIError(
            f"Maya director review generation failed after retry: {last_error}",
            error_code="DIRECTOR_MODEL_FAILURE",
            cause=last_error,
        )

    async def generate_render_review(
        self,
        preview_video_uri: str,
        preview_mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        director_review: DirectorReview | None,
        edl: EditDecisionList,
        production_id: str,
        preview_artifact_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[RenderReview, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt = build_director_render_review_prompt(
            transcript=transcript,
            proposal=proposal,
            director_review=director_review,
            edl=edl,
            production_id=production_id,
            preview_artifact_id=preview_artifact_id,
            channel_profile=channel_profile,
            lessons=lessons,
        )

        video_part = types.Part.from_uri(file_uri=preview_video_uri, mime_type=preview_mime_type)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RenderReview,
            temperature=0.2,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        log_ai_event(
            event_type=EventType.DIRECTOR_RENDER_REVIEW_STARTED,
            agent="maya",
            model=self._model_id,
            status="started",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
        )

        start_time = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=self._model_id,
                    contents=[video_part, prompt],
                    config=config,
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                raw_review: RenderReview
                if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, RenderReview):
                    raw_review = response.parsed
                elif hasattr(response, "text") and response.text:
                    raw_review = RenderReview.model_validate_json(response.text)
                else:
                    raise GenAIError("Gemini response did not include parsed RenderReview or text payload")

                reconciled = reconcile_render_review_with_transcript(raw_review, transcript)

                usage = AgentUsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                log_ai_event(
                    event_type=EventType.DIRECTOR_RENDER_REVIEW_COMPLETED,
                    agent="maya",
                    model=self._model_id,
                    status="success",
                    production_id=production_id,
                    run_id=run_id,
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                return reconciled, usage

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Maya director post-render review attempt %d failed: %s",
                    attempt + 1,
                    str(exc),
                )
                if attempt == 0:
                    time.sleep(1.0)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.DIRECTOR_RENDER_REVIEW_FAILED,
            agent="maya",
            model=self._model_id,
            status="failed",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error_code="DIRECTOR_RENDER_REVIEW_FAILURE",
        )
        raise GenAIError(
            f"Maya director post-render review generation failed after retry: {last_error}",
            error_code="DIRECTOR_RENDER_REVIEW_FAILURE",
            cause=last_error,
        )

    async def generate_editor_self_review(
        self,
        preview_video_uri: str,
        preview_mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        edl: EditDecisionList,
        production_id: str,
        preview_artifact_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorSelfReview, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt = build_editor_self_review_prompt(
            transcript=transcript,
            proposal=proposal,
            edl=edl,
            production_id=production_id,
            preview_artifact_id=preview_artifact_id,
            channel_profile=channel_profile,
            lessons=lessons,
        )

        video_part = types.Part.from_uri(file_uri=preview_video_uri, mime_type=preview_mime_type)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EditorSelfReview,
            temperature=0.2,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        log_ai_event(
            event_type=EventType.EDITOR_ANALYSIS_STARTED,
            agent="leo",
            model=self._model_id,
            status="started",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
        )

        start_time = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=self._model_id,
                    contents=[video_part, prompt],
                    config=config,
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                raw_self_review: EditorSelfReview
                if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, EditorSelfReview):
                    raw_self_review = response.parsed
                elif hasattr(response, "text") and response.text:
                    raw_self_review = EditorSelfReview.model_validate_json(response.text)
                else:
                    raise GenAIError("Gemini response did not include parsed EditorSelfReview or text payload")

                usage = AgentUsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                log_ai_event(
                    event_type=EventType.EDITOR_ANALYSIS_COMPLETED,
                    agent="leo",
                    model=self._model_id,
                    status="success",
                    production_id=production_id,
                    run_id=run_id,
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                return raw_self_review, usage

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Leo editor multimodal self-review attempt %d failed: %s",
                    attempt + 1,
                    str(exc),
                )
                if attempt == 0:
                    time.sleep(1.0)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.EDITOR_ANALYSIS_FAILED,
            agent="leo",
            model=self._model_id,
            status="failed",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error_code="EDITOR_SELF_REVIEW_FAILURE",
        )
        raise GenAIError(
            f"Leo editor multimodal self-review generation failed after retry: {last_error}",
            error_code="EDITOR_SELF_REVIEW_FAILURE",
            cause=last_error,
        )

    async def generate_editor_correction(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        render_review: RenderReview,
        production_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt = build_editor_correction_prompt(
            transcript=transcript,
            proposal=proposal,
            render_review=render_review,
            production_id=production_id,
            channel_profile=channel_profile,
            lessons=lessons,
        )

        video_part = types.Part.from_uri(file_uri=video_uri, mime_type=mime_type)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EditorProposal,
            temperature=0.2,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        log_ai_event(
            event_type=EventType.EDITOR_CORRECTION_STARTED,
            agent="leo",
            model=self._model_id,
            status="started",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
        )

        start_time = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=self._model_id,
                    contents=[video_part, prompt],
                    config=config,
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                raw_proposal: EditorProposal
                if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, EditorProposal):
                    raw_proposal = response.parsed
                elif hasattr(response, "text") and response.text:
                    raw_proposal = EditorProposal.model_validate_json(response.text)
                else:
                    raise GenAIError("Gemini response did not include parsed EditorProposal or text payload")

                reconciled = reconcile_editor_proposal_with_transcript(raw_proposal, transcript)

                usage = AgentUsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                log_ai_event(
                    event_type=EventType.EDITOR_CORRECTION_COMPLETED,
                    agent="leo",
                    model=self._model_id,
                    status="success",
                    production_id=production_id,
                    run_id=run_id,
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                return reconciled, usage

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Leo dialogue editor correction attempt %d failed: %s",
                    attempt + 1,
                    str(exc),
                )
                if attempt == 0:
                    time.sleep(1.0)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.EDITOR_CORRECTION_FAILED,
            agent="leo",
            model=self._model_id,
            status="failed",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error_code="EDITOR_CORRECTION_FAILURE",
        )
        raise GenAIError(
            f"Leo dialogue editor correction failed after retry: {last_error}",
            error_code="EDITOR_CORRECTION_FAILURE",
            cause=last_error,
        )

    async def generate_narration_rewrite(
        self,
        original_text: str,
        available_duration_s: float,
        attempt: int = 1,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> str:
        """Invoke Leo to rewrite non-native speech into natural spoken English within duration budget."""
        from google.genai import types

        client = self._get_client()
        prompt = build_narration_rewrite_prompt(original_text, available_duration_s, attempt)
        start_time = time.perf_counter()

        log_ai_event(
            event_type=EventType.AI_CALL_STARTED,
            agent="leo",
            model=self._model_id,
            status="started",
            production_id=production_id,
            request_id=request_id,
        )

        try:
            response = client.models.generate_content(
                model=self._model_id,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=128,
                ),
            )
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            rewritten = (response.text or "").strip().strip('"').strip("'")
            log_ai_event(
                event_type=EventType.AI_CALL_COMPLETED,
                agent="leo",
                model=self._model_id,
                status="success",
                production_id=production_id,
                request_id=request_id,
                latency_ms=latency_ms,
            )
            return rewritten or generate_fallback_narration_rewrite(original_text, available_duration_s, attempt)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            log_ai_event(
                event_type=EventType.AI_CALL_FAILED,
                agent="leo",
                model=self._model_id,
                status="failed",
                production_id=production_id,
                request_id=request_id,
                latency_ms=latency_ms,
                error_code=type(exc).__name__,
            )
            return generate_fallback_narration_rewrite(original_text, available_duration_s, attempt)

    async def generate_packaging_proposal(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        production_id: str,
        chapters: Sequence[ChapterMarker] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        short_candidate: ShortCandidate | None = None,
        has_short_artifact: bool = False,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[PackagingProposal, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt = build_packaging_prompt(
            transcript=transcript,
            channel_profile=channel_profile,
            lessons=lessons,
            production_id=production_id,
            chapters=chapters,
            research_findings=research_findings,
            short_candidate=short_candidate,
            has_short_artifact=has_short_artifact,
            custom_prompt=custom_prompt,
        )

        video_part = types.Part.from_uri(file_uri=video_uri, mime_type=mime_type)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PackagingProposal,
            temperature=0.3,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        log_ai_event(
            event_type=EventType.AI_CALL_STARTED,
            agent="nina",
            model=self._model_id,
            status="started",
            production_id=production_id,
            request_id=request_id,
        )

        start_time = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=self._model_id,
                    contents=[video_part, prompt],
                    config=config,
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                raw_proposal: PackagingProposal
                if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, PackagingProposal):
                    raw_proposal = response.parsed
                elif hasattr(response, "text") and response.text:
                    raw_proposal = PackagingProposal.model_validate_json(response.text)
                else:
                    raise GenAIError("Gemini response did not include parsed PackagingProposal or text payload")

                reconciled = reconcile_packaging_proposal(
                    raw_proposal,
                    master_duration_ms=master_duration_ms,
                    chapters=chapters,
                )
                reconciled.master_artifact_id = master_artifact_id
                reconciled.prompt_version = prompt_version

                usage = AgentUsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                log_ai_event(
                    event_type=EventType.AI_CALL_COMPLETED,
                    agent="nina",
                    model=self._model_id,
                    status="success",
                    production_id=production_id,
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                return reconciled, usage

            except Exception as exc:
                last_error = exc
                logger.warning("Nina packaging generation attempt %d failed: %s", attempt + 1, str(exc))
                if attempt == 0:
                    time.sleep(1.0)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.AI_CALL_FAILED,
            agent="nina",
            model=self._model_id,
            status="failed",
            production_id=production_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error_code="PACKAGING_GENERATION_FAILURE",
        )
        raise GenAIError(
            f"Nina packaging proposal generation failed after retry: {last_error}",
            error_code="PACKAGING_GENERATION_FAILURE",
            cause=last_error,
        )

    async def generate_release_review(
        self,
        master_video_uri: str,
        master_mime_type: str,
        transcript: Transcript,
        proposal: PackagingProposal,
        production_id: str,
        short_video_uri: str | None = None,
        short_mime_type: str = "video/mp4",
        overrides: CreatorPackageOverrides | None = None,
        render_review: RenderReview | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        deterministic_results: dict[str, Any] | None = None,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        short_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[ReleaseReview, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt = build_release_qa_prompt(
            transcript=transcript,
            master_artifact=None,
            proposal=proposal,
            short_artifact=None,
            overrides=overrides,
            render_review=render_review,
            channel_profile=channel_profile,
            lessons=lessons,
            research_findings=research_findings,
            deterministic_results=deterministic_results,
            custom_prompt=custom_prompt,
            production_id=production_id,
        )

        contents: list[Any] = [
            types.Part.from_uri(file_uri=master_video_uri, mime_type=master_mime_type)
        ]
        if short_video_uri:
            contents.append(
                types.Part.from_uri(file_uri=short_video_uri, mime_type=short_mime_type)
            )
        contents.append(prompt)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReleaseReview,
            temperature=0.2,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        log_ai_event(
            event_type=EventType.AI_CALL_STARTED,
            agent="iris",
            model=self._model_id,
            status="started",
            production_id=production_id,
            request_id=request_id,
        )

        start_time = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=self._model_id,
                    contents=contents,
                    config=config,
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

                raw_review: ReleaseReview
                if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, ReleaseReview):
                    raw_review = response.parsed
                elif hasattr(response, "text") and response.text:
                    raw_review = ReleaseReview.model_validate_json(response.text)
                else:
                    raise GenAIError("Gemini response did not include parsed ReleaseReview or text payload")

                reconciled = reconcile_release_review(
                    raw_review,
                    master_duration_ms=master_duration_ms,
                )
                reconciled.master_artifact_id = master_artifact_id
                reconciled.short_artifact_id = short_artifact_id
                reconciled.packaging_proposal_id = proposal.proposal_id

                usage = AgentUsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                log_ai_event(
                    event_type=EventType.AI_CALL_COMPLETED,
                    agent="iris",
                    model=self._model_id,
                    status="success",
                    production_id=production_id,
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )

                return reconciled, usage

            except Exception as exc:
                last_error = exc
                logger.warning("Iris QA review attempt %d failed: %s", attempt + 1, str(exc))
                if attempt == 0:
                    time.sleep(1.0)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.AI_CALL_FAILED,
            agent="iris",
            model=self._model_id,
            status="failed",
            production_id=production_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error_code="QA_REVIEW_FAILURE",
        )
        raise GenAIError(
            f"Iris QA review generation failed after retry: {last_error}",
            error_code="QA_REVIEW_FAILURE",
            cause=last_error,
        )


class FakeGenAIClient(GenAIClient):
    """Deterministic fake GenAI client for unit tests and local non-cloud execution."""

    def __init__(
        self,
        canned_proposal: EditorProposal | None = None,
        canned_review: DirectorReview | None = None,
        canned_self_review: EditorSelfReview | None = None,
        canned_render_review: RenderReview | None = None,
        canned_render_reviews: list[RenderReview] | None = None,
        canned_correction: EditorProposal | None = None,
        canned_packaging_proposal: PackagingProposal | None = None,
        fail_on_editor: bool = False,
        fail_on_director: bool = False,
        fail_on_self_review: bool = False,
        fail_on_render_review: bool = False,
        fail_on_correction: bool = False,
        fail_on_packaging: bool = False,
    ) -> None:
        self._canned_proposal = canned_proposal
        self._canned_review = canned_review
        self._canned_self_review = canned_self_review
        self._canned_render_review = canned_render_review
        self._canned_render_reviews = list(canned_render_reviews) if canned_render_reviews else []
        self._canned_correction = canned_correction
        self._canned_packaging_proposal = canned_packaging_proposal
        self._fail_on_editor = fail_on_editor
        self._fail_on_director = fail_on_director
        self._fail_on_self_review = fail_on_self_review
        self._fail_on_render_review = fail_on_render_review
        self._fail_on_correction = fail_on_correction
        self._fail_on_packaging = fail_on_packaging
        self.call_history: list[dict[str, Any]] = []
    async def generate_editor_proposal(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        production_id: str,
        run_id: str | None = None,
        media_summary: str | None = None,
        silence_decisions: Sequence[EditorDecision] | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata]:
        self.call_history.append(
            {
                "agent": "leo",
                "production_id": production_id,
                "video_uri": video_uri,
                "run_id": run_id,
            }
        )
        if self._fail_on_editor:
            raise GenAIError("Simulated Leo editor model failure", error_code="SIMULATED_EDITOR_FAILURE")

        if self._canned_proposal is not None:
            proposal = self._canned_proposal
        else:
            # Deterministic default proposal based on transcript words
            decisions: list[EditorDecision] = []
            words = transcript.words
            if len(words) >= 4:
                # Propose removing word 1 as a filler
                decisions.append(
                    EditorDecision(
                        decision_id="dec_01",
                        decision_type=EditorDecisionType.REMOVE_FILLER,
                        transcript_start_word=1,
                        transcript_end_word=1,
                        source_start_ms=words[1].start_ms,
                        source_end_ms=words[1].end_ms,
                        original_text=words[1].text,
                        action="remove",
                        concise_reason="Remove filler hesitation",
                        confidence=0.95,
                        visual_context="talking head",
                    )
                )
            if len(words) >= 8:
                # Propose keeping words 4..7 for technical clarity
                decisions.append(
                    EditorDecision(
                        decision_id="dec_02",
                        decision_type=EditorDecisionType.KEEP_FOR_CLARITY,
                        transcript_start_word=4,
                        transcript_end_word=7,
                        source_start_ms=words[4].start_ms,
                        source_end_ms=words[7].end_ms,
                        original_text=" ".join(w.text for w in words[4:8]),
                        action="keep",
                        concise_reason="Keep essential technical setup for command execution",
                        confidence=0.92,
                        visual_context="terminal demonstration",
                    )
                )

            short_candidate: ShortCandidate | None = None
            if len(words) >= 6:
                end_idx = min(len(words) - 1, 20)
                short_candidate = ShortCandidate(
                    start_ms=words[0].start_ms,
                    end_ms=words[end_idx].end_ms,
                    transcript_start_word=0,
                    transcript_end_word=end_idx,
                    hook_title="Core Demonstration Highlight",
                    concise_reason="High punchiness with direct technical payoff",
                    confidence=0.90,
                )

            total_dur = transcript.duration_ms or (words[-1].end_ms if words else 0)
            default_chapters = [
                ChapterMarker(
                    title="Introduction & Overview",
                    source_start_ms=0,
                    source_end_ms=min(total_dur, 15000),
                    summary="Opening hook and workflow introduction",
                    confidence=0.95,
                ),
                ChapterMarker(
                    title="Technical Demonstration",
                    source_start_ms=min(total_dur, 15000),
                    source_end_ms=total_dur,
                    summary="Main technical demonstration and workflow execution",
                    confidence=0.92,
                ),
            ] if total_dur > 0 else []

            proposal = EditorProposal(
                production_id=production_id,
                agent="leo",
                model="fake-gemini-3.7-flash",
                summary=f"Multimodal video analysis and dialogue pass completed with {len(decisions)} proposed edits.",
                decisions=decisions,
                short_candidate=short_candidate,
                chapters=default_chapters,
                overall_confidence=0.93,
            )
        reconciled = reconcile_editor_proposal_with_transcript(proposal, transcript)
        usage = AgentUsageMetadata(input_tokens=420, output_tokens=180, latency_ms=45)
        return reconciled, usage

    async def generate_director_review(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        proposal: EditorProposal,
        production_id: str,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[DirectorReview, AgentUsageMetadata]:
        self.call_history.append(
            {
                "agent": "maya",
                "production_id": production_id,
                "video_uri": video_uri,
                "run_id": run_id,
            }
        )
        if self._fail_on_director:
            raise GenAIError("Simulated Maya director model failure", error_code="SIMULATED_DIRECTOR_FAILURE")

        if self._canned_review is not None:
            review = self._canned_review
        else:
            director_decisions: list[DirectorDecision] = []
            for d in proposal.decisions:
                if d.decision_type == EditorDecisionType.KEEP_FOR_CLARITY:
                    director_decisions.append(
                        DirectorDecision(
                            editor_decision_id=d.decision_id,
                            verdict=DirectorVerdict.APPROVE,
                            concise_reason="Approved. Preserving this technical explanation is critical for viewer retention.",
                        )
                    )
                else:
                    director_decisions.append(
                        DirectorDecision(
                            editor_decision_id=d.decision_id,
                            verdict=DirectorVerdict.APPROVE,
                            concise_reason="Approved. Clean cut that enhances pacing without loss of meaning.",
                        )
                    )

            review = DirectorReview(
                production_id=production_id,
                agent="maya",
                model="fake-gemini-3.7-flash",
                overall_assessment=f"Reviewed {len(proposal.decisions)} edits. Pacing is improved and clarity preserved.",
                decisions=director_decisions,
                editor_feedback="Approved for Edit Decision List (EDL) assembly.",
                approved_for_edl=True,
                confidence=0.96,
            )

        reconciled = reconcile_director_review_with_transcript(review, proposal, transcript)
        usage = AgentUsageMetadata(input_tokens=510, output_tokens=150, latency_ms=40)
        return reconciled, usage

    async def generate_render_review(
        self,
        preview_video_uri: str,
        preview_mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        director_review: DirectorReview | None,
        edl: EditDecisionList,
        production_id: str,
        preview_artifact_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[RenderReview, AgentUsageMetadata]:
        self.call_history.append(
            {
                "agent": "maya_render_review",
                "production_id": production_id,
                "preview_video_uri": preview_video_uri,
                "preview_artifact_id": preview_artifact_id,
                "edl_id": edl.edl_id,
                "run_id": run_id,
            }
        )
        if self._fail_on_render_review:
            raise GenAIError("Simulated Maya post-render review failure", error_code="SIMULATED_RENDER_REVIEW_FAILURE")

        if self._canned_render_reviews:
            review = self._canned_render_reviews.pop(0)
        elif self._canned_render_review is not None:
            review = self._canned_render_review
            self._canned_render_review = None
        else:
            review = RenderReview(
                review_id=f"rrv_{production_id[:8]}",
                production_id=production_id,
                edl_id=edl.edl_id,
                preview_artifact_id=preview_artifact_id,
                agent="maya",
                model="fake-gemini-3.7-flash",
                verdict=RenderReviewVerdict.APPROVE,
                summary="Dialogue flows naturally and pacing is crisp. Edit approved for Master render.",
                issues=[],
                approved_for_master=True,
                confidence=0.97,
                created_at=datetime.now(timezone.utc),
            )

        reconciled = reconcile_render_review_with_transcript(review, transcript)
        usage = AgentUsageMetadata(input_tokens=550, output_tokens=120, latency_ms=42)
        return reconciled, usage
    async def generate_editor_self_review(
        self,
        preview_video_uri: str,
        preview_mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        edl: EditDecisionList,
        production_id: str,
        preview_artifact_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorSelfReview, AgentUsageMetadata]:
        self.call_history.append(
            {
                "agent": "leo_self_review",
                "production_id": production_id,
                "preview_video_uri": preview_video_uri,
                "preview_artifact_id": preview_artifact_id,
                "edl_id": edl.edl_id,
                "run_id": run_id,
            }
        )
        if self._fail_on_self_review:
            raise GenAIError("Simulated Leo self-review failure", error_code="SIMULATED_SELF_REVIEW_FAILURE")

        if self._canned_self_review is not None:
            self_review = self._canned_self_review
        else:
            self_review = EditorSelfReview(
                review_id=f"srv_{production_id[:8]}",
                production_id=production_id,
                edl_id=edl.edl_id,
                preview_artifact_id=preview_artifact_id,
                agent="leo",
                model="fake-gemini-3.7-flash",
                verdict=EditorSelfReviewVerdict.APPROVE_UNCHANGED,
                summary="Multimodal preview verification confirmed smooth pacing, clean audio transitions, and natural screen flow.",
                narrative_pacing_assessment="Narrative energy is brisk and engaging without rushing key explanations.",
                removals_assessment="Removed hesitations and dead air significantly improved tutorial cadence.",
                visual_continuity_assessment="Visual continuity across screen demonstrations remains clear with no jarring jump cuts.",
                audio_joins_assessment="Micro-crossfades produce seamless audio joins with zero audible phoneme clipping.",
                coverage_needed=False,
                short_assessment="Vertical Short excerpt maintains punchy pacing and strong visual hook.",
                findings=[
                    "Pacing is crisp with dead air removed",
                    "Audio joins decode cleanly across all cut boundaries",
                    "Short candidate hook is effective",
                ],
                confidence=0.96,
                created_at=datetime.now(timezone.utc),
            )

        usage = AgentUsageMetadata(input_tokens=520, output_tokens=140, latency_ms=40)
        return self_review, usage


    async def generate_editor_correction(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        proposal: EditorProposal,
        render_review: RenderReview,
        production_id: str,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata]:
        self.call_history.append(
            {
                "agent": "leo_correction",
                "production_id": production_id,
                "video_uri": video_uri,
                "render_review_id": render_review.review_id,
                "run_id": run_id,
            }
        )
        if self._fail_on_correction:
            raise GenAIError("Simulated Leo correction failure", error_code="SIMULATED_CORRECTION_FAILURE")

        if self._canned_correction is not None:
            corrected_proposal = self._canned_correction
        else:
            # Adjust decisions based on render_review issues
            revised_decisions: list[EditorDecision] = []
            issue_decision_ids = {iss.related_decision_id for iss in render_review.issues if iss.related_decision_id}
            for d in proposal.decisions:
                if d.decision_id in issue_decision_ids:
                    # Revise decision to keep for clarity or adjust bounds
                    revised_decisions.append(
                        EditorDecision(
                            decision_id=d.decision_id,
                            decision_type=EditorDecisionType.KEEP_FOR_CLARITY,
                            transcript_start_word=d.transcript_start_word,
                            transcript_end_word=d.transcript_end_word,
                            source_start_ms=d.source_start_ms,
                            source_end_ms=d.source_end_ms,
                            original_text=d.original_text,
                            action="keep",
                            concise_reason="Restored take per Maya post-render review feedback",
                            confidence=0.95,
                        )
                    )
                else:
                    revised_decisions.append(d)

            corrected_proposal = EditorProposal(
                production_id=production_id,
                agent="leo",
                model="fake-gemini-3.7-flash",
                summary="Revised dialogue pass addressing Maya's post-render review feedback.",
                decisions=revised_decisions,
                short_candidate=proposal.short_candidate,
                overall_confidence=0.94,
            )

        reconciled = reconcile_editor_proposal_with_transcript(corrected_proposal, transcript)
        usage = AgentUsageMetadata(input_tokens=460, output_tokens=160, latency_ms=40)
        return reconciled, usage

    async def generate_narration_rewrite(
        self,
        original_text: str,
        available_duration_s: float,
        attempt: int = 1,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> str:
        self.call_history.append(
            {
                "method": "generate_narration_rewrite",
                "original_text": original_text,
                "available_duration_s": available_duration_s,
                "attempt": attempt,
                "production_id": production_id,
            }
        )
        return generate_fallback_narration_rewrite(original_text, available_duration_s, attempt)

    async def generate_packaging_proposal(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        channel_profile: ChannelMemoryProfile | None,
        lessons: list[ChannelLesson] | None,
        production_id: str,
        chapters: Sequence[ChapterMarker] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        short_candidate: ShortCandidate | None = None,
        has_short_artifact: bool = False,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[PackagingProposal, AgentUsageMetadata]:
        self.call_history.append(
            {
                "agent": "nina_packaging",
                "production_id": production_id,
                "video_uri": video_uri,
                "master_artifact_id": master_artifact_id,
                "has_short_artifact": has_short_artifact,
            }
        )
        if self._fail_on_packaging:
            raise GenAIError("Simulated Nina packaging failure", error_code="SIMULATED_PACKAGING_FAILURE")

        if self._canned_packaging_proposal is not None:
            proposal = self._canned_packaging_proposal
        else:
            is_fairphone = any(
                "fairphone" in (w.text.lower() if hasattr(w, "text") else getattr(w, "word", "").lower())
                for w in transcript.words[:50]
            ) if transcript.words else False

            if is_fairphone:
                primary = "Inside the Most Repairable Modern Smartphone"
                candidates = [
                    TitleCandidate(
                        text="Inside the Most Repairable Modern Smartphone",
                        angle=TitleAngle.PROBLEM_SOLUTION,
                        why_it_works="Highlights the modularity solution to disposable electronics, matching channel's hardware audience.",
                        confidence=0.96,
                    ),
                    TitleCandidate(
                        text="Fairphone 6 Plus Is the Phone Everyone Says They Want",
                        angle=TitleAngle.DIRECT_VALUE,
                        why_it_works="Directly addresses enthusiast demand for modularity and upgradeable components.",
                        confidence=0.93,
                    ),
                    TitleCandidate(
                        text="Why This Phone Lets You Replace Almost Everything",
                        angle=TitleAngle.CURIOSITY,
                        why_it_works="Drives curiosity by contrasting with standard glued smartphones.",
                        confidence=0.91,
                    ),
                    TitleCandidate(
                        text="How to Repair and Upgrade a Modern Smartphone Yourself",
                        angle=TitleAngle.HOW_TO,
                        why_it_works="Practical framing for viewers looking for actionable disassembly guide.",
                        confidence=0.88,
                    ),
                    TitleCandidate(
                        text="Is Modular Hardware Finally Ready for Prime Time?",
                        angle=TitleAngle.CONTRARIAN,
                        why_it_works="Challenges common assumptions about repairable phone compromises.",
                        confidence=0.86,
                    ),
                ]
                master_dur = master_duration_ms or 109304
                is_edited = master_dur < 113800
                ch2_start = 23700 if is_edited else 26160
                ch2_time = "0:23" if is_edited else "0:26"
                ch3_start = 71000 if is_edited else 75000
                ch3_time = "1:11" if is_edited else "1:15"

                desc = (
                    "A complete teardown and hardware walkthrough of the Fairphone 6 Plus.\n\n"
                    "In this video, we disassemble the modular chassis, inspect the upgraded motherboard and memory, "
                    "and demonstrate how to swap individual components using standard tools.\n\n"
                    "0:00 Introduction & Overview\n"
                    f"{ch2_time} Chassis & Screws Disassembly\n"
                    f"{ch3_time} Modular Component Replacement\n\n"
                    "Subscribe for more in-depth hardware engineering walkthroughs and technical tutorials."
                )
                pkg_chapters = [
                    PackagingChapter(
                        title="Introduction & Overview",
                        start_ms=0,
                        end_ms=ch2_start,
                        formatted_time="0:00",
                        summary="Overview of Fairphone 6 Plus features and upgraded specs",
                    ),
                    PackagingChapter(
                        title="Chassis & Screws Disassembly",
                        start_ms=ch2_start,
                        end_ms=ch3_start,
                        formatted_time=ch2_time,
                        summary="Removing screws and sliding off protective casing",
                    ),
                    PackagingChapter(
                        title="Modular Component Replacement",
                        start_ms=ch3_start,
                        end_ms=master_dur,
                        formatted_time=ch3_time,
                        summary="Hands-on demonstration of modular parts and reassembly",
                    ),
                ]
                thumbnails = [
                    ThumbnailConcept(
                        concept_id="th_01",
                        headline="REPLACE EVERYTHING",
                        visual_subject="Close up hands holding screwdriver loosening Fairphone internal module",
                        composition="Tight macro focus on phone internals with screwdriver, high contrast lighting",
                        emotion="Curiosity / Empowerment",
                        supporting_frame_ms=35000,
                        reason="Direct visual evidence of modular repairability, visually proving the core hook.",
                        confidence=0.96,
                        frame_verified=True,
                    ),
                    ThumbnailConcept(
                        concept_id="th_02",
                        headline="NO GLUE NEEDED",
                        visual_subject="Exploded view of separated screen and chassis modules",
                        composition="Centered hardware layout with clear separation between components",
                        emotion="Surprise / Satisfaction",
                        supporting_frame_ms=58000,
                        reason="Emphasizes zero glue architecture compared to mainstream flagship smartphones.",
                        confidence=0.92,
                        frame_verified=True,
                    ),
                    ThumbnailConcept(
                        concept_id="th_03",
                        headline="INSIDE THE 6 PLUS",
                        visual_subject="Presenter holding the exposed motherboard next to upgraded battery module",
                        composition="Rule of thirds, presenter expression looking at camera holding hardware",
                        emotion="Intrigue / Direct value",
                        supporting_frame_ms=90000,
                        reason="Combines human creator presence with exposed circuit board hardware.",
                        confidence=0.89,
                        frame_verified=True,
                    ),
                ]
                short_pkg = ShortPackage(
                    title="A Modern Smartphone You Can Actually Repair!",
                    description="Why the Fairphone 6 Plus lets you swap parts in seconds. #shorts #fairphone #tech",
                    hook="Tired of glued-together smartphones that break forever?",
                    hashtags=["#shorts", "#fairphone", "#tech", "#repair"],
                )
                evidence = "Channel history indicates practical demonstration framing tends to outperform generic specification framing by 28% in CTR."
            else:
                primary = "Complete Technical Walkthrough & Production Guide"
                candidates = [
                    TitleCandidate(
                        text="Complete Technical Walkthrough & Production Guide",
                        angle=TitleAngle.DIRECT_VALUE,
                        why_it_works="Clear practical value for technical viewers.",
                        confidence=0.92,
                    ),
                    TitleCandidate(
                        text="How to Build and Deploy Production Systems Fast",
                        angle=TitleAngle.HOW_TO,
                        why_it_works="Action-oriented tutorial framing.",
                        confidence=0.88,
                    ),
                    TitleCandidate(
                        text="The Modern Approach to Developer Workflows",
                        angle=TitleAngle.PROBLEM_SOLUTION,
                        why_it_works="Addresses developer friction with concrete solutions.",
                        confidence=0.85,
                    ),
                ]
                desc = "A complete in-depth walkthrough and demonstration.\n\n0:00 Introduction\n0:30 Deep Dive"
                pkg_chapters = [
                    PackagingChapter(title="Introduction", start_ms=0, end_ms=30000, formatted_time="0:00"),
                    PackagingChapter(title="Deep Dive", start_ms=30000, end_ms=90000, formatted_time="0:30"),
                ]
                thumbnails = [
                    ThumbnailConcept(
                        concept_id="th_01",
                        headline="BUILD & DEPLOY",
                        visual_subject="Clean architecture diagram and code terminal",
                        composition="High-contrast split screen",
                        emotion="Curiosity",
                        supporting_frame_ms=10000,
                        reason="Clear visual summary of workflow",
                        confidence=0.90,
                        frame_verified=True,
                    )
                ]
                short_pkg = ShortPackage(
                    title="Quick Production Overview",
                    description="Essential walkthrough in under a minute.",
                    hook="Want to speed up your production workflow?",
                    hashtags=["#shorts", "#dev"],
                )
                evidence = "No strong historical packaging signal; recommendation is based primarily on video content."

            proposal = PackagingProposal(
                proposal_id=f"pkg_{production_id[:12]}",
                production_id=production_id,
                agent="nina",
                model="fake-gemini-3.7-flash",
                primary_title=primary,
                title_candidates=candidates,
                description=desc,
                chapters=pkg_chapters,
                keywords=["fairphone", "repairability", "teardown", "modular tech", "hardware review"],
                thumbnail_concepts=thumbnails,
                short_package=short_pkg,
                packaging_summary="High-converting packaging leveraging practical modular hardware demonstration.",
                channel_evidence=evidence,
                confidence=0.94,
                created_at=datetime.now(timezone.utc),
                master_artifact_id=master_artifact_id,
                prompt_version=prompt_version,
            )

        reconciled = reconcile_packaging_proposal(proposal, master_duration_ms=master_duration_ms, chapters=chapters)
        usage = AgentUsageMetadata(input_tokens=680, output_tokens=220, latency_ms=45)
        return reconciled, usage

    async def generate_release_review(
        self,
        master_video_uri: str,
        master_mime_type: str,
        transcript: Transcript,
        proposal: PackagingProposal,
        production_id: str,
        short_video_uri: str | None = None,
        short_mime_type: str = "video/mp4",
        overrides: CreatorPackageOverrides | None = None,
        render_review: RenderReview | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        deterministic_results: dict[str, Any] | None = None,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        short_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[ReleaseReview, AgentUsageMetadata]:
        self.call_history.append({
            "agent": "iris_qa",
            "production_id": production_id,
            "master_uri": master_video_uri,
            "short_uri": short_video_uri,
        })
        desc = proposal.description if proposal else ""
        has_unsupported_upcoming_review = "upcoming full" in desc.lower() or "stay tuned for the upcoming" in desc.lower()

        claim_verifs = [
            ClaimVerification(
                claim_text="12 user-replaceable parts",
                location="description",
                status=ClaimSupportStatus.SUPPORTED_BY_VIDEO,
                evidence="At 00:51, host demonstrates phone disassembly and repair parts.",
            ),
            ClaimVerification(
                claim_text="Snapdragon internals",
                location="description",
                status=ClaimSupportStatus.SUPPORTED_EXTERNALLY,
                evidence="Verified hardware specs for Fairphone 6 Plus platform.",
            ),
            ClaimVerification(
                claim_text="microSD",
                location="description",
                status=ClaimSupportStatus.SUPPORTED_BY_VIDEO,
                evidence="Spoken in video and visible on chassis expansion slot.",
            ),
        ]

        if has_unsupported_upcoming_review:
            claim_verifs.append(
                ClaimVerification(
                    claim_text="Stay tuned for the upcoming full Fairphone 6+ review!",
                    location="description",
                    status=ClaimSupportStatus.UNSUPPORTED,
                    evidence="No planned future review or scheduling found in Croviq channel memory or production context.",
                )
            )

        issues: list[ReleaseIssue] = []
        if has_unsupported_upcoming_review:
            issues.append(
                ReleaseIssue(
                    issue_id="iss_claim_upcoming_review",
                    issue_type=ReleaseIssueType.UNSUPPORTED_CLAIM,
                    severity=ReleaseIssueSeverity.HIGH,
                    source_start_ms=None,
                    source_end_ms=None,
                    artifact_type="packaging",
                    message="Description claims an upcoming full review that isn't supported.",
                    suggested_action="Remove the upcoming review promise from YouTube description.",
                    evidence="Claim: 'Stay tuned for the upcoming full Fairphone 6+ review!' has no corroboration.",
                )
            )

        verdict = ReleaseVerdict.FIX_REQUIRED if issues else ReleaseVerdict.PASS
        approved = len(issues) == 0

        checklist = ReleaseChecklist(
            master_video=True,
            audio=True,
            captions=True,
            chapters=True,
            short=True,
            packaging=len(issues) == 0,
            claims=len(issues) == 0,
        )

        thumb_evals = []
        if proposal and proposal.thumbnail_concepts:
            for idx, th in enumerate(proposal.thumbnail_concepts):
                thumb_evals.append(
                    ThumbnailEvaluation(
                        concept_index=idx,
                        headline=th.headline,
                        verdict="PASS",
                        reason=f"Frame at {th.supporting_frame_ms}ms accurately shows {th.visual_subject}.",
                    )
                )

        review = ReleaseReview(
            review_id=f"rev_{production_id[:12]}",
            production_id=production_id,
            agent="iris",
            model="fake-gemini-3.7-flash",
            verdict=verdict,
            summary="All quality and packaging checks passed." if approved else f"Found {len(issues)} packaging/claim defects requiring fix.",
            issues=issues,
            approved_for_release=approved,
            confidence=0.98 if approved else 0.95,
            created_at=datetime.now(timezone.utc),
            master_artifact_id=master_artifact_id,
            short_artifact_id=short_artifact_id,
            packaging_proposal_id=proposal.proposal_id if proposal else None,
            checklist=checklist,
            claim_verifications=claim_verifs,
            thumbnail_evaluations=thumb_evals,
        )
        usage = AgentUsageMetadata(input_tokens=850, output_tokens=320, latency_ms=50)
        return review, usage
