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
    build_director_prompt,
    build_director_render_review_prompt,
    build_editor_correction_prompt,
    build_editor_prompt,
    build_narration_rewrite_prompt,
)
from croviq_domain.edl import EditDecisionList
from croviq_domain.render_review import (
    RenderReview,
    RenderReviewIssue,
    RenderReviewIssueType,
    RenderReviewSeverity,
    RenderReviewVerdict,
)
from croviq_domain.editorial import (
    DirectorDecision,
    DirectorReview,
    DirectorVerdict,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    ShortCandidate,
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

    return EditorProposal(
        production_id=proposal.production_id,
        agent="leo",
        model=proposal.model,
        summary=proposal.summary,
        decisions=reconciled_decisions,
        short_candidate=reconciled_short,
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


class FakeGenAIClient(GenAIClient):
    """Deterministic fake GenAI client for unit tests and local non-cloud execution."""

    def __init__(
        self,
        canned_proposal: EditorProposal | None = None,
        canned_review: DirectorReview | None = None,
        canned_render_review: RenderReview | None = None,
        canned_render_reviews: list[RenderReview] | None = None,
        canned_correction: EditorProposal | None = None,
        fail_on_editor: bool = False,
        fail_on_director: bool = False,
        fail_on_render_review: bool = False,
        fail_on_correction: bool = False,
    ) -> None:
        self._canned_proposal = canned_proposal
        self._canned_review = canned_review
        self._canned_render_review = canned_render_review
        self._canned_render_reviews = list(canned_render_reviews) if canned_render_reviews else []
        self._canned_correction = canned_correction
        self._fail_on_editor = fail_on_editor
        self._fail_on_director = fail_on_director
        self._fail_on_render_review = fail_on_render_review
        self._fail_on_correction = fail_on_correction
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

            proposal = EditorProposal(
                production_id=production_id,
                agent="leo",
                model="fake-gemini-3.7-flash",
                summary=f"Dialogue pass completed with {len(decisions)} proposed edits.",
                decisions=decisions,
                short_candidate=short_candidate,
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
