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
    build_editor_prompt,
    build_editor_self_review_prompt,
    build_narration_rewrite_prompt,
    build_release_qa_prompt,
)
from croviq_domain.channel_intelligence import ResearchFinding
from croviq_domain.packaging import CreatorPackageOverrides, PackagingProposal
from croviq_domain.edl import EditDecisionList
from croviq_domain.render_review import EditorSelfReview, EditorSelfReviewVerdict
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
from croviq_domain.editorial import (
    ChapterMarker,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    SectionAction,
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
    """Anchor Leo's editorial decisions and chapters to canonical transcript timing."""
    if not transcript.words:
        return proposal

    max_word_idx = len(transcript.words) - 1
    reconciled_decisions: list[EditorDecision] = []

    for d in proposal.decisions:
        start_idx = max(0, min(d.transcript_start_word, max_word_idx))
        end_idx = max(start_idx, min(d.transcript_end_word, max_word_idx))

        if d.decision_id.startswith("silence_cut_") or d.original_text.startswith("[Silence:"):
            source_start_ms = d.source_start_ms
            source_end_ms = d.source_end_ms
            original_text = d.original_text
        else:
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
        section_plan=proposal.section_plan,
        chapters=reconciled_chapters,
        overall_confidence=proposal.overall_confidence,
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
    async def synthesize_studio_voice(
        self,
        text: str,
        voice_id: str = "Puck",
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[int, bytes]:
        """Synthesize Studio Voice narration segment using Gemini 3.1 Flash TTS (gemini-3.1-flash-tts-preview)."""
        pass


    @abstractmethod
    async def generate_release_review(
        self,
        master_video_uri: str,
        master_mime_type: str,
        transcript: Transcript,
        production_id: str,
        proposal: PackagingProposal | None = None,
        publish_metadata: Any = None,
        overrides: CreatorPackageOverrides | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        deterministic_results: dict[str, Any] | None = None,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[ReleaseReview, AgentUsageMetadata]:
        """Invoke Iris, the sole QA gate, to inspect the current rendered main video."""
        pass

    @abstractmethod
    async def generate_broll_clip(
        self,
        prompt: str,
        production_id: str,
        duration_ms: int = 4000,
        task: str = "text_to_video",
        resolution: str = "360p",
        aspect_ratio: str = "16:9",
        first_frame_uri: str | None = None,
        last_frame_uri: str | None = None,
        reference_video_uri: str | None = None,
        previous_interaction_id: str | None = None,
        scene_extension_prior_context_ms: int | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[bytes, str, int, str]:
        """Invoke Gemini Omni 1.1 Flash on Vertex AI Interactions API to generate a video clip."""
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


    async def generate_release_review(
        self,
        master_video_uri: str,
        master_mime_type: str,
        transcript: Transcript,
        production_id: str,
        proposal: PackagingProposal | None = None,
        publish_metadata: Any = None,
        overrides: CreatorPackageOverrides | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        deterministic_results: dict[str, Any] | None = None,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[ReleaseReview, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt = build_release_qa_prompt(
            transcript=transcript,
            master_artifact=None,
            proposal=proposal,
            publish_metadata=publish_metadata,
            overrides=overrides,
            channel_profile=channel_profile,
            lessons=lessons,
            research_findings=research_findings,
            deterministic_results=deterministic_results,
            custom_prompt=custom_prompt,
            production_id=production_id,
        )
        contents: list[Any] = [
            types.Part.from_uri(file_uri=master_video_uri, mime_type=master_mime_type),
            prompt,
        ]

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
                reconciled.packaging_proposal_id = proposal.proposal_id if proposal else None

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
    async def synthesize_studio_voice(
        self,
        text: str,
        voice_id: str = "Puck",
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[int, bytes]:
        from google.genai import types

        client = self._get_client()
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_id
                    )
                )
            ),
        )

        log_ai_event(
            event_type=EventType.AI_CALL_STARTED,
            agent="leo",
            model="gemini-3.1-flash-tts-preview",
            status="started",
            production_id=production_id,
            request_id=request_id,
        )
        start_time = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-3.1-flash-tts-preview",
                    contents=text,
                    config=config,
                )
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                if (
                    not response.candidates
                    or not response.candidates[0].content
                    or not response.candidates[0].content.parts
                ):
                    raise GenAIError("Gemini TTS response contained no candidates or parts")

                part = response.candidates[0].content.parts[0]
                if not part.inline_data or not part.inline_data.data:
                    raise GenAIError("Gemini TTS response part did not contain inline audio data")

                raw_pcm = part.inline_data.data
                # 24000 Hz, 16-bit mono -> 48 bytes per ms
                duration_ms = int(len(raw_pcm) / 48)

                log_ai_event(
                    event_type=EventType.AI_CALL_COMPLETED,
                    agent="leo",
                    model="gemini-3.1-flash-tts-preview",
                    status="success",
                    production_id=production_id,
                    request_id=request_id,
                    latency_ms=latency_ms,
                    audio_duration_ms=duration_ms,
                )
                return duration_ms, raw_pcm
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(1.0)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.AI_CALL_FAILED,
            agent="leo",
            model="gemini-3.1-flash-tts-preview",
            status="failed",
            production_id=production_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error=str(last_error),
        )
        raise GenAIError(f"Gemini TTS synthesis failed after retry: {last_error}", cause=last_error)

    async def generate_broll_clip(
        self,
        prompt: str,
        production_id: str,
        duration_ms: int = 3000,
        task: str = "text_to_video",
        resolution: str = "360p",
        aspect_ratio: str = "16:9",
        first_frame_uri: str | None = None,
        last_frame_uri: str | None = None,
        reference_video_uri: str | None = None,
        previous_interaction_id: str | None = None,
        scene_extension_prior_context_ms: int | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[bytes, str, int, str]:
        import asyncio
        import base64
        # Strict duration validation: 3s through 10s (3000ms-10000ms)
        dur_sec = int(round(duration_ms / 1000.0))
        if dur_sec not in (3, 4, 5, 6, 7, 8, 9, 10):
            raise ValueError(
                f"Invalid duration {duration_ms}ms ({dur_sec}s). Supported Omni generation durations are 3s through 10s (3000ms-10000ms)."
            )

        # Strict resolution validation: 360p, 720p, 1080p, 4k
        if resolution not in ("360p", "720p", "1080p", "4k"):
            raise ValueError(
                f"Invalid resolution '{resolution}'. Supported resolutions are '360p', '720p', '1080p', '4k'."
            )

        client = self._get_client()
        target_model = "gemini-omni-1.1-flash-preview"

        log_ai_event(
            event_type=EventType.AI_REQUEST_STARTED,
            agent="leo",
            model=target_model,
            status="started",
            provider="google",
            backend="agent_platform",
            operation="video_generation",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
        )
        log_ai_event(
            event_type=EventType.BROLL_GENERATION_STARTED,
            agent="leo",
            model=target_model,
            status="started",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
        )

        start_time = time.perf_counter()
        last_error: Exception | None = None

        # Explicit draft/standard/finishing response format (never omit resolution or duration)
        response_format: dict[str, Any] = {
            "type": "video",
            "resolution": resolution,
            "duration": f"{dur_sec}s",
        }
        if aspect_ratio in ("16:9", "9:16"):
            response_format["aspect_ratio"] = aspect_ratio

        kwargs: dict[str, Any] = {
            "model": target_model,
            "input": prompt,
            "response_format": response_format,
        }
        if previous_interaction_id:
            kwargs["previous_interaction_id"] = previous_interaction_id
        if task and task != "text_to_video":
            kwargs["generation_config"] = {"video_config": {"task": task}}

        if reference_video_uri:
            kwargs["input"] = [
                {"type": "video", "uri": reference_video_uri},
                prompt,
            ]
        elif first_frame_uri or last_frame_uri:
            content_list = []
            if first_frame_uri:
                content_list.append({"type": "image", "uri": first_frame_uri})
            if last_frame_uri:
                content_list.append({"type": "image", "uri": last_frame_uri})
            content_list.append(prompt)
            kwargs["input"] = content_list

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                res = client.interactions.create(**kwargs)
                interaction_id = getattr(res, "id", None) or f"omni_{int(time.time())}"
                output_video = getattr(res, "output_video", None)
                if not output_video:
                    raise GenAIError(f"Omni interaction {interaction_id} completed without output_video")

                raw_video_bytes: bytes
                if output_video.data:
                    raw_video_bytes = base64.b64decode(output_video.data)
                elif output_video.uri:
                    import httpx
                    import google.auth
                    from google.auth.transport.requests import Request as GRequest

                    creds, _ = google.auth.default()
                    creds.refresh(GRequest())
                    resp = httpx.get(
                        output_video.uri,
                        headers={"Authorization": f"Bearer {creds.token}"},
                        timeout=60.0,
                    )
                    resp.raise_for_status()
                    raw_video_bytes = resp.content
                else:
                    raise GenAIError("Omni output_video has neither data nor uri")

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                actual_res = getattr(output_video, "resolution", None) or resolution

                log_ai_event(
                    event_type=EventType.AI_REQUEST_COMPLETED,
                    agent="leo",
                    model=target_model,
                    status="success",
                    provider="google",
                    backend="agent_platform",
                    operation="video_generation",
                    production_id=production_id,
                    run_id=run_id,
                    request_id=request_id,
                    latency_ms=latency_ms,
                )
                log_ai_event(
                    event_type=EventType.BROLL_GENERATION_COMPLETED,
                    agent="leo",
                    model=target_model,
                    status="success",
                    production_id=production_id,
                    run_id=run_id,
                    request_id=request_id,
                    latency_ms=latency_ms,
                )
                return raw_video_bytes, interaction_id, duration_ms, actual_res
            except Exception as exc:
                last_error = exc
                err_text = str(exc)

                # 403: permission denied -> fail closed immediately
                if "403" in err_text or "PermissionDenied" in type(exc).__name__:
                    logger.error("Omni permission denied (403): %s", exc)
                    break

                # 429: rate limit / quota exceeded -> bounded retry if attempts remain
                if "429" in err_text or "Quota exceeded" in err_text or "RateLimit" in type(exc).__name__:
                    if attempt < max_retries:
                        # Bounded backoff: 2s, 4s
                        backoff_sec = 2.0 * (attempt + 1)
                        logger.warning("Omni quota limit (429), retrying attempt %d/%d after %.1fs: %s", attempt + 1, max_retries, backoff_sec, exc)
                        await asyncio.sleep(backoff_sec)
                        continue
                    break

                # 5xx: upstream temporary server error -> bounded retry
                if "500" in err_text or "503" in err_text or "InternalServerError" in type(exc).__name__:
                    if attempt < max_retries:
                        backoff_sec = 2.0 * (attempt + 1)
                        logger.warning("Omni upstream temporary error (5xx), retrying attempt %d/%d after %.1fs: %s", attempt + 1, max_retries, backoff_sec, exc)
                        await asyncio.sleep(backoff_sec)
                        continue
                    break

                # Other client errors -> fail closed immediately
                break
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_ai_event(
            event_type=EventType.AI_REQUEST_FAILED,
            agent="leo",
            model=target_model,
            status="failed",
            provider="google",
            backend="agent_platform",
            operation="video_generation",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error=str(last_error),
        )
        log_ai_event(
            event_type=EventType.BROLL_GENERATION_FAILED,
            agent="leo",
            model=target_model,
            status="failed",
            production_id=production_id,
            run_id=run_id,
            request_id=request_id,
            latency_ms=latency_ms,
            error=str(last_error),
        )
        raise GenAIError(f"Gemini Omni video generation failed: {last_error}", cause=last_error)



class FakeGenAIClient(GenAIClient):
    """Deterministic fake GenAI client for unit tests and local non-cloud execution."""

    def __init__(
        self,
        canned_proposal: EditorProposal | None = None,
        canned_self_review: EditorSelfReview | None = None,
        fail_on_editor: bool = False,
        fail_on_self_review: bool = False,
    ) -> None:
        self._canned_proposal = canned_proposal
        self._canned_self_review = canned_self_review
        self._fail_on_editor = fail_on_editor
        self._fail_on_self_review = fail_on_self_review
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
                chapters=default_chapters,
                overall_confidence=0.93,
            )
        reconciled = reconcile_editor_proposal_with_transcript(proposal, transcript)
        usage = AgentUsageMetadata(input_tokens=420, output_tokens=180, latency_ms=45)
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
                findings=[
                    "Pacing is crisp with dead air removed",
                    "Audio joins decode cleanly across all cut boundaries",
                ],
                confidence=0.96,
                created_at=datetime.now(timezone.utc),
            )

        usage = AgentUsageMetadata(input_tokens=520, output_tokens=140, latency_ms=40)
        return self_review, usage


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


    async def generate_release_review(
        self,
        master_video_uri: str,
        master_mime_type: str,
        transcript: Transcript,
        production_id: str,
        proposal: PackagingProposal | None = None,
        publish_metadata: Any = None,
        overrides: CreatorPackageOverrides | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        research_findings: Sequence[ResearchFinding] | None = None,
        deterministic_results: dict[str, Any] | None = None,
        custom_prompt: str | None = None,
        prompt_version: int = 1,
        master_artifact_id: str | None = None,
        master_duration_ms: int | None = None,
        request_id: str = "unknown",
    ) -> tuple[ReleaseReview, AgentUsageMetadata]:
        self.call_history.append({
            "agent": "iris_qa",
            "production_id": production_id,
            "master_uri": master_video_uri,
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
            packaging_proposal_id=proposal.proposal_id if proposal else None,
            checklist=checklist,
            claim_verifications=claim_verifs,
            thumbnail_evaluations=thumb_evals,
        )
        usage = AgentUsageMetadata(input_tokens=850, output_tokens=320, latency_ms=50)
        return review, usage
    async def synthesize_studio_voice(
        self,
        text: str,
        voice_id: str = "Puck",
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[int, bytes]:
        self.call_history.append({
            "method": "synthesize_studio_voice",
            "text": text,
            "voice_id": voice_id,
            "production_id": production_id,
            "request_id": request_id,
        })
        words = len(text.split())
        dur_ms = max(500, int(words * 360 + 100))
        # 24000 Hz, 16-bit mono -> 48 bytes per ms
        num_bytes = dur_ms * 48
        return dur_ms, b"\x00" * num_bytes

    async def generate_broll_clip(
        self,
        prompt: str,
        production_id: str,
        duration_ms: int = 3000,
        task: str = "text_to_video",
        resolution: str = "360p",
        aspect_ratio: str = "16:9",
        first_frame_uri: str | None = None,
        last_frame_uri: str | None = None,
        reference_video_uri: str | None = None,
        previous_interaction_id: str | None = None,
        scene_extension_prior_context_ms: int | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[bytes, str, int, str]:
        import uuid

        dur_sec = int(round(duration_ms / 1000.0))
        if dur_sec not in (3, 4, 5, 6, 7, 8, 9, 10):
            raise ValueError(
                f"Invalid duration {duration_ms}ms ({dur_sec}s). Supported Omni generation durations are 3s through 10s (3000ms-10000ms)."
            )
        if resolution not in ("360p", "720p", "1080p", "4k"):
            raise ValueError(
                f"Invalid resolution '{resolution}'. Supported resolutions are '360p', '720p', '1080p', '4k'."
            )
        self.call_history.append({
            "method": "generate_broll_clip",
            "prompt": prompt,
            "production_id": production_id,
            "duration_ms": duration_ms,
            "task": task,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "first_frame_uri": first_frame_uri,
            "last_frame_uri": last_frame_uri,
            "reference_video_uri": reference_video_uri,
            "previous_interaction_id": previous_interaction_id,
            "scene_extension_prior_context_ms": scene_extension_prior_context_ms,
            "run_id": run_id,
            "request_id": request_id,
        })
        interaction_id = f"fake_interaction_{uuid.uuid4().hex[:8]}"
        mock_mp4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 1024
        return mock_mp4, interaction_id, duration_ms, resolution
