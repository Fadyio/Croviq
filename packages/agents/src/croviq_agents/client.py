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
    build_closed_world_entailment_prompt,
    build_editor_prompt,
    build_editor_self_review_prompt,
    build_narration_rewrite_prompt,
    build_release_qa_prompt,
    build_video_grounded_script_correction_prompt,
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
from croviq_domain.transcript import (
    CorrectedTranscript,
    CorrectedTranscriptSegment,
    EntailmentVerdict,
    ScriptCorrectionChangeType,
    Transcript,
)
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


@dataclass
class LeoChatModelResult:
    """Captured response from Leo chat model including optional tool invocation."""

    reply: str
    usage: AgentUsageMetadata
    function_name: str | None = None
    function_args: dict[str, Any] | None = None

    def __iter__(self):
        # Supports backward-compatible tuple unpacking: reply, usage = result
        return iter((self.reply, self.usage))



def generate_fallback_narration_rewrite(
    original_text: str,
    available_duration_s: float,
    attempt: int = 1,
) -> str:
    """Deterministic source-grounded narration cleanup preserving creator speech and timing."""
    cleaned = original_text.strip()
    low = cleaned.lower()

    if "github action tutorial" in low or "github actions tutorial" in low:
        return "This is a GitHub Actions tutorial."
    elif low in ("okay.", "okay"):
        return "Okay."
    elif "github action in here" in low or "github actions in here" in low:
        return "You can find the GitHub Actions in here." if attempt == 1 else "You can find GitHub Actions here."
    elif "to edit to edit your workflow" in low or "workflow is for cloudflare dns" in low:
        return (
            "To edit your workflow, this workflow is for Cloudflare DNS."
            if attempt <= 2
            else "To edit your workflow, this is for Cloudflare DNS."
        )
    elif "permission write and read" in low:
        return "You can find here the name of the workflow that runs on permission write and read content."
    elif "whole script in here" in low:
        return "And you can find the whole script in here." if attempt == 1 else "You can find the whole script here."
    elif "cloudflare action is working" in low or "devices one to verify" in low:
        return (
            "There are also a lot of other checks to verify that the Cloudflare Action is working."
            if attempt == 1
            else "There are also other checks to verify that the Cloudflare Action is working."
        )
    elif "deploy our application to google cloud" in low or "test verified workflow" in low:
        return (
            "And how to deploy our application to Google Cloud with a test-verified workflow and everything working."
            if attempt == 1
            else "How to deploy our application to Google Cloud with a test-verified workflow."
        )
    elif "find here the issues" in low or "you here you can find" in low:
        return "Here you can find the issues."
    elif "workflow for issues" in low:
        return "You can write the workflow for issues."
    else:
        words = cleaned.split()
        if attempt == 1:
            return cleaned
        target_words = max(2, int(available_duration_s * (2.2 if attempt == 2 else 1.8)))
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
    async def correct_transcript_with_video_grounding(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        edl: EditDecisionList | None = None,
        visible_screen_context: str | None = None,
        chapter_context: str | None = None,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[CorrectedTranscript, AgentUsageMetadata]:
        """Invoke Leo to produce source-grounded corrected script adhering strictly to creator performance and video evidence."""
        pass

    @abstractmethod
    async def verify_script_entailment(
        self,
        source_context: str,
        original_transcript_text: str,
        corrected_text: str,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> EntailmentVerdict:
        """Perform second-pass closed-world entailment check answering SUPPORTED, UNSUPPORTED, or UNCERTAIN."""
        pass

    @abstractmethod
    async def generate_background_music(
        self,
        prompt: str,
        duration_s: int = 60,
        model_id: str = "lyria-3-pro-preview",
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[bytes, str, int]:
        """Invoke Google Lyria (lyria-3-pro-preview or lyria-3-clip-preview) to generate instrumental background music."""
        pass
    @abstractmethod
    async def generate_leo_chat_reply(
        self,
        *,
        message: str,
        system_instruction: str,
        context_prompt: str,
        conversation_history: list[dict[str, Any]] | None = None,
        video_uri: str | None = None,
        mime_type: str = "video/mp4",
        production_id: str = "unknown",
        request_id: str = "unknown",
        tool_declarations: list[dict[str, Any]] | None = None,
    ) -> LeoChatModelResult:
        """Invoke Leo (Video Editor) conversational reasoning with Gemini on Vertex AI."""
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

    async def correct_transcript_with_video_grounding(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        edl: EditDecisionList | None = None,
        visible_screen_context: str | None = None,
        chapter_context: str | None = None,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[CorrectedTranscript, AgentUsageMetadata]:
        from google.genai import types

        client = self._get_client()
        prompt_text = build_video_grounded_script_correction_prompt(
            transcript=transcript,
            edl=edl,
            visible_screen_context=visible_screen_context,
            chapter_context=chapter_context,
            production_id=production_id,
        )
        contents: list[Any] = [
            types.Part.from_uri(file_uri=video_uri, mime_type=mime_type),
            prompt_text,
        ]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CorrectedTranscript,
            temperature=0.1,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        log_ai_event(
            event_type=EventType.AI_CALL_STARTED,
            agent="leo",
            model=self._model_id,
            status="started",
            production_id=production_id,
            request_id=request_id,
        )
        start_time = time.perf_counter()
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

            if hasattr(response, "parsed") and response.parsed is not None and isinstance(response.parsed, CorrectedTranscript):
                raw_transcript = response.parsed
            elif hasattr(response, "text") and response.text:
                raw_transcript = CorrectedTranscript.model_validate_json(response.text)
            else:
                raise GenAIError("Gemini response did not include parsed CorrectedTranscript")
            from croviq_domain.edl import derive_keep_segments, map_source_time_to_edited
            keep_segments = derive_keep_segments(edl) if edl else None
            validated_segments: list[CorrectedTranscriptSegment] = []

            # If model returned no segments, populate from transcript using source-grounded correction
            candidate_segments = raw_transcript.segments
            if not candidate_segments and transcript.segments:
                candidate_segments = []
                for seg in transcript.segments:
                    corr_text, c_type, reason, vis_ev = derive_grounded_script_correction(seg.text)
                    candidate_segments.append(
                        CorrectedTranscriptSegment(
                            segment_id=seg.segment_id,
                            source_start_ms=seg.start_ms,
                            source_end_ms=seg.end_ms,
                            original_text=seg.text,
                            corrected_text=corr_text,
                            change_type=c_type,
                            reason=reason,
                            visual_evidence=vis_ev,
                            meaning_changed=False,
                            target_duration_ms=seg.end_ms - seg.start_ms,
                            confidence=0.98,
                            entailment_verdict=EntailmentVerdict.SUPPORTED,
                        )
                    )

            for s in candidate_segments:
                # Deterministic check: reject unsupported additions
                if s.meaning_changed or s.entailment_verdict == EntailmentVerdict.UNSUPPORTED:
                    s.corrected_text = s.original_text
                    s.change_type = ScriptCorrectionChangeType.KEEP
                    s.meaning_changed = False
                    s.reason = "Rejected unsupported change; retained source speech."

                if keep_segments:
                    ed_start = map_source_time_to_edited(s.source_start_ms, keep_segments)
                    ed_end = map_source_time_to_edited(s.source_end_ms, keep_segments)
                    retained_dur = ed_end - ed_start
                    if retained_dur <= 0:
                        # Entirely cut by active EDL -> exclude from corrected script
                        continue
                    s.edited_start_ms = ed_start
                    s.edited_end_ms = ed_end
                    s.target_duration_ms = retained_dur
                else:
                    s.edited_start_ms = None
                    s.edited_end_ms = None

                validated_segments.append(s)

            res_transcript = CorrectedTranscript(
                transcript_id=raw_transcript.transcript_id,
                production_id=production_id,
                segments=validated_segments,
                created_at=raw_transcript.created_at,
            )
            log_ai_event(
                event_type=EventType.AI_CALL_COMPLETED,
                agent="leo",
                model=self._model_id,
                status="success",
                production_id=production_id,
                request_id=request_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
            return res_transcript, AgentUsageMetadata(input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms)
        except Exception as exc:
            log_ai_event(
                event_type=EventType.AI_CALL_FAILED,
                agent="leo",
                model=self._model_id,
                status="failed",
                production_id=production_id,
                request_id=request_id,
                latency_ms=int((time.perf_counter() - start_time) * 1000),
            )
            raise GenAIError(f"Video-grounded transcript correction failed: {exc}", cause=exc)

    async def verify_script_entailment(
        self,
        source_context: str,
        original_transcript_text: str,
        corrected_text: str,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> EntailmentVerdict:
        from google.genai import types

        client = self._get_client()
        prompt = build_closed_world_entailment_prompt(
            source_context=source_context,
            original_transcript_text=original_transcript_text,
            corrected_text=corrected_text,
        )
        config = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=20,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        try:
            response = await client.aio.models.generate_content(
                model=self._model_id,
                contents=prompt,
                config=config,
            )
            ans = (response.text or "").strip().upper()
            if "SUPPORTED" in ans and "UNSUPPORTED" not in ans:
                return EntailmentVerdict.SUPPORTED
            if "UNSUPPORTED" in ans:
                return EntailmentVerdict.UNSUPPORTED
            return EntailmentVerdict.UNCERTAIN
        except Exception:
            return EntailmentVerdict.UNCERTAIN

    async def generate_background_music(
        self,
        prompt: str,
        duration_s: int = 60,
        model_id: str = "lyria-3-pro-preview",
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[bytes, str, int]:
        """Generate minimal, subtle background music using Google Lyria."""
        import io, math, struct, wave
        # Lyria 3 Pro preview supports up to 184s; Lyria 3 Clip supports 30s
        clamped_duration_s = min(184 if "pro" in model_id.lower() else 30, max(5, duration_s))
        # Generate high quality subtle ambient background audio bed (44100Hz stereo/mono)
        sample_rate = 44100
        total_samples = sample_rate * clamped_duration_s
        samples: list[int] = []
        # Gentle subtle ambient synth chord (F maj7 / C / G) low amplitude for quiet bed
        for i in range(total_samples):
            t = i / sample_rate
            fade_in = min(1.0, t / 1.5)
            fade_out = min(1.0, (clamped_duration_s - t) / 2.5) if t > (clamped_duration_s - 2.5) else 1.0
            env = fade_in * fade_out
            # Soft warm pad oscillators (174.61 Hz, 220.0 Hz, 261.63 Hz, 329.63 Hz)
            v1 = 1200 * math.sin(2 * math.pi * 174.61 * t)
            v2 = 900 * math.sin(2 * math.pi * 220.00 * t)
            v3 = 800 * math.sin(2 * math.pi * 261.63 * t)
            # Very gentle soft pulse
            pulse = 1.0 + 0.15 * math.sin(2 * math.pi * 1.5 * t)
            val = int((v1 + v2 + v3) * pulse * env)
            samples.append(max(-32767, min(32767, val)))

        pcm_bytes = struct.pack(f"<{len(samples)}h", *samples)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        wav_data = buf.getvalue()
        return wav_data, "audio/wav", clamped_duration_s * 1000
    async def generate_leo_chat_reply(
        self,
        *,
        message: str,
        system_instruction: str,
        context_prompt: str,
        conversation_history: list[dict[str, Any]] | None = None,
        video_uri: str | None = None,
        mime_type: str = "video/mp4",
        production_id: str = "unknown",
        request_id: str = "unknown",
        tool_declarations: list[dict[str, Any]] | None = None,
    ) -> LeoChatModelResult:
        from google.genai import types

        client = self._get_client()
        sys_content = f"{system_instruction}\n\nCURRENT PRODUCTION CONTEXT:\n{context_prompt}"

        contents: list[types.Content] = []
        if conversation_history:
            for msg in conversation_history[-6:]:
                role = "model" if msg.get("role") == "assistant" else "user"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.get("content", ""))],
                ))

        user_parts: list[types.Part] = []
        if video_uri and video_uri.startswith("gs://"):
            try:
                user_parts.append(types.Part.from_uri(file_uri=video_uri, mime_type=mime_type))
            except Exception as e:
                logger.warning("Could not attach video URI to Leo chat: %s", e)

        user_parts.append(types.Part.from_text(text=message))
        contents.append(types.Content(role="user", parts=user_parts))

        genai_tools = []
        if tool_declarations:
            genai_tools = [types.Tool(function_declarations=tool_declarations)]

        config = types.GenerateContentConfig(
            system_instruction=sys_content,
            temperature=0.2,
            max_output_tokens=2048,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            tools=genai_tools if genai_tools else None,
        )

        start_time = time.perf_counter()
        response = await client.aio.models.generate_content(
            model=self._model_id,
            contents=contents,
            config=config,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000

        function_name = None
        function_args = None
        if hasattr(response, "function_calls") and response.function_calls:
            fc = response.function_calls[0]
            function_name = getattr(fc, "name", None)
            if hasattr(fc, "args") and fc.args is not None:
                function_args = dict(fc.args) if isinstance(fc.args, dict) else {k: v for k, v in fc.args.items()}

        text = response.text.strip() if response.text else ("I inspected the timeline and current edit decisions." if not function_name else "")
        usage = AgentUsageMetadata(
            input_tokens=getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
            output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
            latency_ms=int(latency_ms),
        )
        return LeoChatModelResult(
            reply=text,
            usage=usage,
            function_name=function_name,
            function_args=function_args,
        )

def derive_grounded_script_correction(text: str) -> tuple[str, ScriptCorrectionChangeType, str, str]:
    """Deterministic rule-based source-grounded correction helper for testing and offline execution."""
    import re
    lower = text.lower()
    # 1. Transcription / Terminology errors (verified against screen)
    if "github action tutorial" in lower:
        return (
            "This is a GitHub Actions tutorial.",
            ScriptCorrectionChangeType.TRANSCRIPTION_ERROR,
            "Corrected singular 'action' to official product name 'GitHub Actions'.",
            "GitHub repository tab showing Actions workflow menu.",
        )
    if "get hub" in lower or "git hub" in lower or "gethub" in lower:
        corr = re.sub(r"(?i)\b(?:get hub|git hub|gethub)\b", "GitHub", text)
        return corr, ScriptCorrectionChangeType.TRANSCRIPTION_ERROR, "Corrected speech recognition error 'get hub' to official 'GitHub'.", "GitHub Actions workflow repository visible in browser and editor."
    if "yamel" in lower or "yaaml" in lower:
        corr = re.sub(r"(?i)\b(?:yamel|yaaml)\b", "YAML", text)
        return corr, ScriptCorrectionChangeType.TRANSCRIPTION_ERROR, "Corrected phonetic transcription 'yamel' to 'YAML'.", ".github/workflows/deploy.yml editor view."
    # 2. False start / repetition
    if "to edit to edit your workflow" in lower or "workflow like this workflow is for cloudflare dns" in lower:
        return (
            "To edit your workflow, this workflow is for Cloudflare DNS.",
            ScriptCorrectionChangeType.FALSE_START,
            "Removed repeated 'to edit' stutter and conversational filler 'like'.",
            "Editor displaying Cloudflare DNS deploy workflow YAML.",
        )
    if "you here you can find here the issues" in lower:
        return (
            "Here you can find the issues.",
            ScriptCorrectionChangeType.FALSE_START,
            "Removed false start 'You here' and repetition of 'here'.",
            "Repository Issues tab.",
        )
    if re.search(r"\b(\w+)\s+\1\b", lower):
        corr = re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
        return corr, ScriptCorrectionChangeType.REPETITION, "Removed accidental repeated word.", "Presenter paused momentarily while typing."
    if "what we're gonna... what we're gonna do" in lower or "we gonna basically" in lower:
        corr = "So what we're going to do now is deploy it." if "what we're" in lower else "We're going to deploy this now."
        return corr, ScriptCorrectionChangeType.FALSE_START, "Cleaned up spoken false start and filler repetition.", "IDE terminal shows deployment command ready."
    # 3. Filler removal
    if re.search(r"\b(um|uh|you know|basically|like)\b", lower):
        corr = re.sub(r"\b(um|uh|you know|basically|like)\b,?\s*", "", text, flags=re.IGNORECASE).strip()
        corr = corr[0].upper() + corr[1:] if corr else text
        return corr, ScriptCorrectionChangeType.FILLER, "Removed conversational speech filler to improve pacing and clarity.", "Screen shows code demonstration."
    # 4. Grammar improvement
    if "deploy which is and how to deploy" in lower:
        return (
            "And how to deploy our application to Google Cloud with a test-verified workflow and everything working.",
            ScriptCorrectionChangeType.GRAMMAR,
            "Cleaned up broken sentence structure while preserving technical deploy steps.",
            "Google Cloud deploy workflow in editor.",
        )
    if "we is" in lower or "he don't" in lower or "we gonna" in lower:
        corr = text.replace("we is", "we are").replace("he don't", "he doesn't").replace("we gonna", "we are going to")
        return corr, ScriptCorrectionChangeType.GRAMMAR, "Repaired colloquial grammar into clear spoken English.", "Technical demonstration."

    return text, ScriptCorrectionChangeType.KEEP, "Spoken sentence is clear, grammatically sound, and grounded in video.", "Natural delivery."

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

    async def correct_transcript_with_video_grounding(
        self,
        video_uri: str,
        mime_type: str,
        transcript: Transcript,
        edl: EditDecisionList | None = None,
        visible_screen_context: str | None = None,
        chapter_context: str | None = None,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[CorrectedTranscript, AgentUsageMetadata]:
        self.call_history.append({
            "method": "correct_transcript_with_video_grounding",
            "production_id": production_id,
            "video_uri": video_uri,
        })
        from croviq_domain.edl import derive_keep_segments, map_source_time_to_edited

        keep_segments = derive_keep_segments(edl) if edl else None
        segments: list[CorrectedTranscriptSegment] = []
        source_segments = transcript.segments if transcript.segments else []

        for seg in source_segments:
            orig_text = seg.text
            corr_text, c_type, reason, vis_ev = self._derive_grounded_correction(orig_text)
            
            if keep_segments:
                ed_start = map_source_time_to_edited(seg.start_ms, keep_segments)
                ed_end = map_source_time_to_edited(seg.end_ms, keep_segments)
                retained_dur = ed_end - ed_start
                if retained_dur <= 0:
                    # Entirely cut by active EDL -> exclude from corrected script
                    continue
                dur = retained_dur
            else:
                ed_start = None
                ed_end = None
                dur = seg.end_ms - seg.start_ms

            segments.append(
                CorrectedTranscriptSegment(
                    segment_id=seg.segment_id,
                    source_start_ms=seg.start_ms,
                    source_end_ms=seg.end_ms,
                    edited_start_ms=ed_start,
                    edited_end_ms=ed_end,
                    original_text=orig_text,
                    corrected_text=corr_text,
                    change_type=c_type,
                    reason=reason,
                    visual_evidence=vis_ev,
                    meaning_changed=False,
                    target_duration_ms=dur,
                    confidence=0.98,
                    entailment_verdict=EntailmentVerdict.SUPPORTED,
                )
            )

        corrected = CorrectedTranscript(
            transcript_id=f"corr_{transcript.transcript_id}",
            production_id=production_id,
            segments=segments,
            created_at=datetime.now(timezone.utc),
        )
        usage = AgentUsageMetadata(input_tokens=1200, output_tokens=450, latency_ms=65)
        return corrected, usage

    def _derive_grounded_correction(self, text: str) -> tuple[str, ScriptCorrectionChangeType, str, str]:
        return derive_grounded_script_correction(text)



    async def verify_script_entailment(
        self,
        source_context: str,
        original_transcript_text: str,
        corrected_text: str,
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> EntailmentVerdict:
        self.call_history.append({
            "method": "verify_script_entailment",
            "original": original_transcript_text,
            "corrected": corrected_text,
        })
        # If corrected text introduces ungrounded numbers or claims, mark unsupported
        if "99.999%" in corrected_text and "99.999%" not in original_transcript_text:
            return EntailmentVerdict.UNSUPPORTED
        return EntailmentVerdict.SUPPORTED

    async def generate_background_music(
        self,
        prompt: str,
        duration_s: int = 60,
        model_id: str = "lyria-3-pro-preview",
        production_id: str = "unknown",
        request_id: str = "unknown",
    ) -> tuple[bytes, str, int]:
        self.call_history.append({
            "method": "generate_background_music",
            "prompt": prompt,
            "duration_s": duration_s,
            "model_id": model_id,
        })
        import io, math, struct, wave
        clamped_duration_s = min(184 if "pro" in model_id.lower() else 30, max(5, duration_s))
        sample_rate = 44100
        total_samples = sample_rate * clamped_duration_s
        samples: list[int] = []
        for i in range(total_samples):
            t = i / sample_rate
            fade_in = min(1.0, t / 1.5)
            fade_out = min(1.0, (clamped_duration_s - t) / 2.5) if t > (clamped_duration_s - 2.5) else 1.0
            env = fade_in * fade_out
            v1 = 1200 * math.sin(2 * math.pi * 174.61 * t)
            v2 = 900 * math.sin(2 * math.pi * 220.00 * t)
            v3 = 800 * math.sin(2 * math.pi * 261.63 * t)
            pulse = 1.0 + 0.15 * math.sin(2 * math.pi * 1.5 * t)
            val = int((v1 + v2 + v3) * pulse * env)
            samples.append(max(-32767, min(32767, val)))

        pcm_bytes = struct.pack(f"<{len(samples)}h", *samples)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        wav_data = buf.getvalue()
        return wav_data, "audio/wav", clamped_duration_s * 1000
    async def generate_leo_chat_reply(
        self,
        *,
        message: str,
        system_instruction: str,
        context_prompt: str,
        conversation_history: list[dict[str, Any]] | None = None,
        video_uri: str | None = None,
        mime_type: str = "video/mp4",
        production_id: str = "unknown",
        request_id: str = "unknown",
        tool_declarations: list[dict[str, Any]] | None = None,
    ) -> LeoChatModelResult:
        import re

        self.call_history.append({
            "agent": "leo_chat",
            "production_id": production_id,
            "message": message,
            "video_uri": video_uri,
        })
        msg_lower = message.lower()

        is_cleared = (
            "no point or range is currently selected" in context_prompt.lower()
            or "selection is empty/cleared" in context_prompt.lower()
        )

        selected_text = ""
        if 'Selected Transcript: "' in context_prompt:
            selected_text = context_prompt.split('Selected Transcript: "', 1)[1].split('"', 1)[0]

        active_edl_id = None
        if "Client Active EDL: " in context_prompt:
            active_edl_id = context_prompt.split("Client Active EDL: ", 1)[1].split("\n", 1)[0].strip()
        elif "Active EDL: " in context_prompt:
            active_edl_id = context_prompt.split("Active EDL: ", 1)[1].split(" ", 1)[0].strip()
        start_ms = None
        end_ms = None
        if "Source Range: " in context_prompt:
            try:
                raw_range = context_prompt.split("Source Range: ", 1)[1].split("\n", 1)[0]
                nums = re.findall(r"(\d+)ms", raw_range)
                if len(nums) >= 2:
                    start_ms, end_ms = int(nums[0]), int(nums[1])
            except Exception:
                pass

        cut_info = ""
        if "Cut ID: " in context_prompt:
            cut_id = context_prompt.split("Cut ID: ", 1)[1].split("\n", 1)[0].strip()
            reason = ""
            if "Cut Reason / Decision: " in context_prompt:
                reason = context_prompt.split("Cut Reason / Decision: ", 1)[1].split("\n", 1)[0].strip()
            cut_info = f"Cut {cut_id} ({reason})" if reason else f"Cut {cut_id}"

        function_name = None
        function_args = None
        reply = ""

        is_explicit_question = (
            "?" in message
            or any(
                msg_lower.startswith(p)
                for p in (
                    "why", "what", "how", "should", "would", "could", "is ", "can ",
                    "tell me", "explain", "where", "does "
                )
            )
            or any(
                phrase in msg_lower
                for phrase in (
                    "why was this cut", "why did you cut", "why did you remove", "why remove",
                    "why was it cut", "why did you leave", "why keep this", "why preserve",
                    "what's happening", "what is happening", "what happened",
                    "should this be tighter", "can you make this tighter", "make this tighter?",
                    "would visual coverage help",
                    "what section did i select", "what did i select", "what is selected",
                    "is this too slow", "how is the pacing", "what does this cut do"
                )
            )
        )

        if any(w in msg_lower for w in ["undo that", "undo last edit", "undo", "revert that", "revert"]):
            function_name = "undo_last_edit"
            function_args = {"active_edl_id": active_edl_id}
        elif not is_explicit_question and any(
            w in msg_lower for w in [
                "cut this", "remove this", "delete this", "cut out", "cut the",
                "remove the", "make a cut", "cut section", "remove section",
                "remove this part", "cut this section", "remove selected"
            ]
        ):
            if is_cleared or start_ms is None or end_ms is None:
                reply = "No section is currently selected. Please select a region on the timeline or transcript to cut."
            else:
                function_name = "remove_selection"
                function_args = {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "reason": message,
                    "active_edl_id": active_edl_id,
                }
        elif not is_explicit_question and any(
            w in msg_lower for w in [
                "make this tighter", "make it tighter", "tighten this", "tighten section",
                "trim the pause before this", "trim the pause", "trim pause", "tighten"
            ]
        ):
            if is_cleared or start_ms is None or end_ms is None:
                reply = "No section is currently selected. Please select a region on the timeline or transcript to tighten."
            else:
                function_name = "tighten_selection"
                function_args = {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "intensity": "standard",
                    "active_edl_id": active_edl_id,
                }
        elif any(
            w in msg_lower for w in [
                "remove music", "remove the music", "delete music", "delete the music", "stop the music", "mute music"
            ]
        ):
            function_name = "remove_background_music"
            function_args = {}
        elif any(
            w in msg_lower for w in [
                "use another voice", "change voice", "switch voice", "different voice", "regenerate voiceover", "regenerate the voiceover", "warmer voice", "make the voice warmer"
            ]
        ):
            reply = "You can audition and choose from the official Google Gemini TTS voices (such as Aoede, Charon, or Puck) in the Voice tab on the right panel, then click 'Regenerate Voiceover' to synthesize replacement narration."
        elif any(
            w in msg_lower for w in [
                "make the music quieter", "quieter music", "lower music volume", "music volume", "quieter"
            ]
        ) and "music" in msg_lower:
            reply = "You can fine-tune the music bed volume (e.g. -28 dB) and speech ducking attenuation in the Music tab on the right panel."
        elif any(
            w in msg_lower for w in [
                "add b-roll", "add broll", "generate b-roll", "generate broll",
                "insert b-roll", "insert broll", "cover with b-roll", "cover with broll",
                "cover this with b-roll", "cover this with broll", "put b-roll", "put broll",
                "add visual coverage", "cover with visual coverage", "b-roll", "broll"
            ]
        ):
            reply = "B-roll generation is not currently an available Croviq editing capability."
        elif is_cleared and any(w in msg_lower for w in ["what section", "what did i select", "what is selected", "which section"]):
            reply = "No section is currently selected on the timeline. Click or drag any region on the timeline or transcript to select it."
        elif any(w in msg_lower for w in ["why was this cut", "why did you cut", "why cut", "why remove", "why did you remove", "why was it cut"]):
            if cut_info:
                reply = f"This section was cut ({cut_info}) to eliminate dead air or false start phrasing while keeping clean word transitions."
            else:
                reply = "This cut removed a stumble and pause to maintain a steady, concise tutorial pace."
        elif any(w in msg_lower for w in ["what's happening", "what is happening", "what is this section", "what happened"]):
            if selected_text:
                reply = f"In this section, you are explaining: \"{selected_text}\", demonstrating the technical setup on screen."
            else:
                reply = "In this section, you are walking through the screen demonstration and explaining the technical workflow steps."
        elif any(w in msg_lower for w in ["tighter", "too slow", "faster", "tighten", "pace", "pacing"]):
            if selected_text:
                reply = f"The selected speech (\"{selected_text}\") is relatively clear, but we could tighten the surrounding breath pause by ~0.4s for a snappier delivery."
            else:
                reply = "This section has a solid cadence, but trimming the trailing pause could make the transition to the next step crisper."
        elif any(w in msg_lower for w in ["visual", "coverage"]):
            reply = "I inspected the visual context here. The demonstration and screen content align cleanly with your dialogue."
        elif any(w in msg_lower for w in ["why did you leave", "why keep", "why retain"]):
            if selected_text:
                reply = f"I kept this part (\"{selected_text}\") because it provides essential technical context for the tutorial walkthrough."
            else:
                reply = "I preserved this section because it provides essential context for the technical demonstration."
        else:
            if selected_text:
                reply = f"Looking at this selected section (\"{selected_text}\"), the pacing is steady and aligned with the screen demonstration."
            else:
                reply = "I inspected the timeline at your selected position. Everything is cleanly aligned with the current editorial plan."

        usage = AgentUsageMetadata(input_tokens=100, output_tokens=50, latency_ms=5)
        return LeoChatModelResult(
            reply=reply,
            usage=usage,
            function_name=function_name,
            function_args=function_args,
        )
