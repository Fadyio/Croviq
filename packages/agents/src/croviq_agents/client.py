"""GenAI SDK client abstractions for Gemini 3.7 Flash multimodal reasoning agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any

from croviq_agents.prompts import (
    build_director_prompt,
    build_editor_prompt,
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

        # Strict word timing truth from Groq Whisper transcript
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
        request_id: str = "unknown",
    ) -> tuple[EditorProposal, AgentUsageMetadata]:
        """Invoke Leo (Dialogue Editor) to analyze video & transcript and propose edits."""
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


class GoogleGenAIClient(GenAIClient):
    """Official Google GenAI SDK client targeting Gemini 3.7 Flash on Vertex AI."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "us-central1",
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
        )

        video_part = types.Part.from_uri(file_uri=video_uri, mime_type=mime_type)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EditorProposal,
            temperature=0.2,
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

                # Strictly anchor word timing to canonical Groq transcript
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


class FakeGenAIClient(GenAIClient):
    """Deterministic fake GenAI client for unit tests and local non-cloud execution."""

    def __init__(
        self,
        canned_proposal: EditorProposal | None = None,
        canned_review: DirectorReview | None = None,
        fail_on_editor: bool = False,
        fail_on_director: bool = False,
    ) -> None:
        self._canned_proposal = canned_proposal
        self._canned_review = canned_review
        self._fail_on_editor = fail_on_editor
        self._fail_on_director = fail_on_director
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
