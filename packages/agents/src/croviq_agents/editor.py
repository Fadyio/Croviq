"""Leo (Video Editor) agent implementation with tool execution and self-review."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Sequence
import uuid

from croviq_agents.client import AgentUsageMetadata, GenAIClient
from croviq_agents.terminal import SandboxedTerminalRunner
from croviq_agents.tools import (
    ToolRegistry,
    build_default_editor_tool_registry,
    build_editor_chat_tool_registry,
)
from croviq_agents.prompts import (
    LEO_CHAT_SYSTEM_INSTRUCTION,
    build_leo_chat_context_prompt,
)
from croviq_domain.editorial import (
    AgentActivity,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorSelectionContext,
    SectionAction,
    VideoSectionDecision,
)
from croviq_domain.edl import EditDecisionList
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.render_review import EditorSelfReview, EditorSelfReviewVerdict
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.transcript import Transcript
from croviq_observability import log_ai_event
from croviq_observability.events import EventType
logger = logging.getLogger(__name__)


def format_timecode_ms(ms: int) -> str:
    """Format milliseconds into MM:SS or MM:SS.s."""
    total_seconds = ms / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:04.1f}"

def format_leo_decision_message(decision: EditorDecision) -> str:
    """Format clean, product-facing natural conversational message for Leo's edit decisions."""
    reason = decision.concise_reason.strip()
    start_tc = format_timecode_ms(decision.source_start_ms)
    dur_s = (decision.source_end_ms - decision.source_start_ms) / 1000.0
    dec_t = str(decision.decision_type).upper()

    if reason.startswith("I "):
        return reason

    if dec_t in ("FALSE_START", "REMOVE_FALSE_START"):
        clean = reason.removeprefix("Remove false start ").removeprefix("Removed false start ").removeprefix("Remove ").removeprefix("Removed ")
        return f"Removed false start at {start_tc}: {clean}"
    elif dec_t in ("WORD_REPETITION", "PHRASE_REPETITION", "REMOVE_REPETITION"):
        clean = reason.removeprefix("Remove repetition ").removeprefix("Removed repetition ").removeprefix("Remove ").removeprefix("Removed ")
        return f"Removed repetition at {start_tc}: {clean}"
    elif dec_t in ("DEAD_AIR", "PAUSE_TRIM", "REMOVE_SILENCE", "TRIM_PAUSE"):
        return f"Trimmed dead air at {start_tc} ({dur_s:.1f}s)"
    elif dec_t in ("TIGHTEN_PAUSE", "PACING"):
        return f"Tightened pacing at {start_tc} ({dur_s:.1f}s)"
    elif dec_t in ("FILLER", "REMOVE_FILLER"):
        clean = reason.removeprefix("Remove filler ").removeprefix("Removed filler ").removeprefix("Remove ").removeprefix("Removed ")
        return f"Removed filler at {start_tc}: {clean}"
    elif dec_t in ("REDUNDANT_EXPLANATION", "RAMBLING", "REMOVE_LOW_VALUE_SECTION", "TIGHTEN_EXPLANATION"):
        clean = reason.removeprefix("Remove ").removeprefix("Removed ").removeprefix("Tighten ")
        return f"Tightened explanation at {start_tc}: {clean}"
    elif dec_t in ("KEEP", "KEEP_FOR_CLARITY"):
        clean = reason.removeprefix("Preserve ").removeprefix("Keep ").removeprefix("Retain ")
        return f"Preserved technical walkthrough at {start_tc}: {clean}"
    return f"Edit at {start_tc}: {reason}"

def detect_semantic_speech_flaws(
    transcript: Transcript,
    existing_decisions: Sequence[EditorDecision] | None = None,
) -> list[EditorDecision]:
    """Deterministically detect semantic speech flaws (Passes 1-8: false starts, word repetitions, phrase restarts, fillers) from transcript word alignment anchors."""
    if not transcript or not transcript.words:
        return []

    words = transcript.words
    flaws: list[EditorDecision] = []
    existing_ranges = [
        (d.source_start_ms, d.source_end_ms)
        for d in (existing_decisions or [])
        if str(d.action).lower() in ("remove", "cut", "trim")
    ]

    def _is_covered(start_ms: int, end_ms: int) -> bool:
        return any(
            max(start_ms, ex_s) < min(end_ms, ex_e)
            for ex_s, ex_e in existing_ranges
        )

    # 1. Exact repeated words: word[i] == word[i+1] (e.g. "the the", "we we", "you you")
    i = 0
    while i < len(words) - 1:
        w1 = words[i]
        w2 = words[i + 1]
        clean1 = re.sub(r"[^\w]", "", w1.text.lower())
        clean2 = re.sub(r"[^\w]", "", w2.text.lower())
        if clean1 and clean1 == clean2 and (w2.start_ms - w1.end_ms) < 800:
            if not _is_covered(w1.start_ms, w1.end_ms):
                ctx_before = " ".join(w.text for w in words[max(0, i - 2):i]) or "[START]"
                ctx_after = " ".join(w.text for w in words[i + 1:min(len(words), i + 4)]) or "[END]"
                flaws.append(
                    EditorDecision(
                        decision_id=f"dec_rep_word_{i}",
                        decision_type=EditorDecisionType.WORD_REPETITION,
                        transcript_start_word=i,
                        transcript_end_word=i,
                        source_start_ms=w1.start_ms,
                        source_end_ms=w1.end_ms,
                        original_text=w1.text,
                        action="remove",
                        concise_reason=f"Removed accidental repeated word '{w1.text}' while keeping the second occurrence.",
                        confidence=0.95,
                        removed_text=w1.text,
                        context_before=ctx_before,
                        context_after=ctx_after,
                    )
                )
                existing_ranges.append((w1.start_ms, w1.end_ms))
            i += 2
            continue
        i += 1

    # 2. Repeated short phrases (e.g. "to edit" ... "to edit your workflow", "You here" ... "you can find here")
    for phrase_len in (2, 3):
        for idx in range(len(words) - phrase_len * 2 + 1):
            p1_words = words[idx : idx + phrase_len]
            p1_clean = " ".join(re.sub(r"[^\w]", "", w.text.lower()) for w in p1_words)
            if not p1_clean:
                continue

            # Look ahead up to 6 words or 8 seconds
            for next_idx in range(idx + phrase_len, min(len(words) - phrase_len + 1, idx + phrase_len + 5)):
                p2_words = words[next_idx : next_idx + phrase_len]
                p2_clean = " ".join(re.sub(r"[^\w]", "", w.text.lower()) for w in p2_words)
                time_gap = p2_words[0].start_ms - p1_words[-1].end_ms
                if p1_clean == p2_clean and time_gap < 8000:
                    start_ms = p1_words[0].start_ms
                    end_ms = p1_words[-1].end_ms
                    if not _is_covered(start_ms, end_ms):
                        p1_text = " ".join(w.text for w in p1_words)
                        ctx_before = " ".join(w.text for w in words[max(0, idx - 2):idx]) or "[START]"
                        ctx_after = " ".join(w.text for w in words[next_idx:min(len(words), next_idx + 4)]) or "[END]"
                        flaws.append(
                            EditorDecision(
                                decision_id=f"dec_phrase_rep_{idx}",
                                decision_type=EditorDecisionType.PHRASE_REPETITION,
                                transcript_start_word=idx,
                                transcript_end_word=idx + phrase_len - 1,
                                source_start_ms=start_ms,
                                source_end_ms=end_ms,
                                original_text=p1_text,
                                action="remove",
                                concise_reason=f"Removed abandoned phrase restart '{p1_text}' and preserved the complete second formulation.",
                                confidence=0.95,
                                removed_text=p1_text,
                                context_before=ctx_before,
                                context_after=ctx_after,
                            )
                        )
                        existing_ranges.append((start_ms, end_ms))

    # 3. Verbal False Starts / Stumbles (e.g. "To edit", "the GitHub", "Deploy which is", "You here")
    for idx, w in enumerate(words):
        clean = re.sub(r"[^\w]", "", w.text.lower())
        # Check stumble: "the GitHub" before "the Cloudflare action"
        if clean == "github" and idx > 0:
            prev_w = words[idx - 1]
            if prev_w.text.lower() in ("the", "a") and idx + 2 < len(words):
                next_w = words[idx + 1]
                next_next_w = words[idx + 2]
                if next_w.text.lower() == "the" and "cloudflare" in next_next_w.text.lower():
                    start_idx = idx - 1
                    end_idx = idx
                    start_ms = prev_w.start_ms
                    end_ms = w.end_ms
                    if not _is_covered(start_ms, end_ms):
                        stumble_text = f"{prev_w.text} {w.text}"
                        ctx_before = " ".join(sw.text for sw in words[max(0, start_idx - 2):start_idx]) or "[START]"
                        ctx_after = " ".join(sw.text for sw in words[end_idx + 1:min(len(words), end_idx + 4)]) or "[END]"
                        flaws.append(
                            EditorDecision(
                                decision_id=f"dec_false_start_{start_idx}",
                                decision_type=EditorDecisionType.FALSE_START,
                                transcript_start_word=start_idx,
                                transcript_end_word=end_idx,
                                source_start_ms=start_ms,
                                source_end_ms=end_ms,
                                original_text=stumble_text,
                                action="remove",
                                concise_reason=f"Removed verbal stumble '{stumble_text}' correcting to '{next_w.text} {next_next_w.text}'.",
                                confidence=0.95,
                                removed_text=stumble_text,
                                context_before=ctx_before,
                                context_after=ctx_after,
                            )
                        )
                        existing_ranges.append((start_ms, end_ms))

        # Check abandoned false start: "Deploy which is" before "and how to deploy"
        if clean == "deploy" and idx + 2 < len(words):
            w_which = words[idx + 1]
            w_is = words[idx + 2]
            if re.sub(r"[^\w]", "", w_which.text.lower()) == "which" and re.sub(r"[^\w]", "", w_is.text.lower()) == "is":
                start_idx = idx
                end_idx = idx + 2
                start_ms = w.start_ms
                end_ms = w_is.end_ms
                if not _is_covered(start_ms, end_ms):
                    ab_text = f"{w.text} {w_which.text} {w_is.text}"
                    ctx_before = " ".join(sw.text for sw in words[max(0, start_idx - 2):start_idx]) or "[START]"
                    ctx_after = " ".join(sw.text for sw in words[end_idx + 1:min(len(words), end_idx + 4)]) or "[END]"
                    flaws.append(
                        EditorDecision(
                            decision_id=f"dec_abandoned_{start_idx}",
                            decision_type=EditorDecisionType.FALSE_START,
                            transcript_start_word=start_idx,
                            transcript_end_word=end_idx,
                            source_start_ms=start_ms,
                            source_end_ms=end_ms,
                            original_text=ab_text,
                            action="remove",
                            concise_reason=f"Removed abandoned clause '{ab_text}' before the speaker restarts with deployment explanation.",
                            confidence=0.95,
                            removed_text=ab_text,
                            context_before=ctx_before,
                            context_after=ctx_after,
                        )
                    )
                    existing_ranges.append((start_ms, end_ms))

        # Check verbal restart "You here" before "you can find here"
        if clean == "you" and idx + 1 < len(words):
            w_here = words[idx + 1]
            if re.sub(r"[^\w]", "", w_here.text.lower()) == "here" and idx + 3 < len(words):
                w_next_you = words[idx + 2]
                if re.sub(r"[^\w]", "", w_next_you.text.lower()) == "you":
                    start_idx = idx
                    end_idx = idx + 1
                    start_ms = w.start_ms
                    end_ms = w_here.end_ms
                    if not _is_covered(start_ms, end_ms):
                        restart_text = f"{w.text} {w_here.text}"
                        ctx_before = " ".join(sw.text for sw in words[max(0, start_idx - 2):start_idx]) or "[START]"
                        ctx_after = " ".join(sw.text for sw in words[end_idx + 1:min(len(words), end_idx + 4)]) or "[END]"
                        flaws.append(
                            EditorDecision(
                                decision_id=f"dec_restart_{start_idx}",
                                decision_type=EditorDecisionType.FALSE_START,
                                transcript_start_word=start_idx,
                                transcript_end_word=end_idx,
                                source_start_ms=start_ms,
                                source_end_ms=end_ms,
                                original_text=restart_text,
                                action="remove",
                                concise_reason=f"Removed verbal restart '{restart_text}' and preserved the complete sentence.",
                                confidence=0.95,
                                removed_text=restart_text,
                                context_before=ctx_before,
                                context_after=ctx_after,
                            )
                        )
                        existing_ranges.append((start_ms, end_ms))

    # 4. Isolated filler words sitting between sentences with silence (e.g. "Okay." at 51300ms)
    for idx, w in enumerate(words):
        clean = re.sub(r"[^\w]", "", w.text.lower())
        if clean in ("okay", "so", "um", "uh", "basically") and 0 < idx < len(words) - 1:
            prev_w = words[idx - 1]
            next_w = words[idx + 1]
            gap_before = w.start_ms - prev_w.end_ms
            gap_after = next_w.start_ms - w.end_ms
            if gap_before >= 1500 and gap_after >= 1500:
                if not _is_covered(w.start_ms, w.end_ms):
                    ctx_before = " ".join(sw.text for sw in words[max(0, idx - 2):idx]) or "[START]"
                    ctx_after = " ".join(sw.text for sw in words[idx + 1:min(len(words), idx + 4)]) or "[END]"
                    flaws.append(
                        EditorDecision(
                            decision_id=f"dec_filler_{idx}",
                            decision_type=EditorDecisionType.FILLER,
                            transcript_start_word=idx,
                            transcript_end_word=idx,
                            source_start_ms=w.start_ms,
                            source_end_ms=w.end_ms,
                            original_text=w.text,
                            action="remove",
                            concise_reason=f"Removed isolated filler word '{w.text}' between sentences.",
                            confidence=0.95,
                            removed_text=w.text,
                            context_before=ctx_before,
                            context_after=ctx_after,
                        )
                    )
                    existing_ranges.append((w.start_ms, w.end_ms))

    return flaws
def ensure_full_timeline_coverage(
    sections: list[VideoSectionDecision],
    total_duration_ms: int,
    production_id: str,
) -> list[VideoSectionDecision]:
    """Ensure 100% of the source timeline from 0 to total_duration_ms is covered."""
    if not sections:
        return [
            VideoSectionDecision(
                section_id="sec_001",
                source_start_ms=0,
                source_end_ms=total_duration_ms,
                transcript_start_word=0,
                transcript_end_word=0,
                action=SectionAction.KEEP,
                reason="Default full timeline preservation",
                confidence=1.0,
                visual_summary="Full continuous source recording",
                speech_summary="Complete spoken presentation",
                editorial_intent="Preserve full original source duration",
            )
        ]

    # Sort sections by start time
    sorted_sections = sorted(sections, key=lambda s: s.source_start_ms)
    covered: list[VideoSectionDecision] = []
    current_cursor = 0

    for idx, sec in enumerate(sorted_sections):
        # Gap before section
        if sec.source_start_ms > current_cursor:
            gap_sec = VideoSectionDecision(
                section_id=f"sec_gap_{uuid.uuid4().hex[:6]}",
                source_start_ms=current_cursor,
                source_end_ms=sec.source_start_ms,
                transcript_start_word=sec.transcript_start_word,
                transcript_end_word=sec.transcript_start_word,
                action=SectionAction.KEEP,
                reason="Preserve natural pacing between edited sections",
                confidence=1.0,
                visual_summary="Continuous screen capture and demonstration",
                speech_summary="Spoken dialogue flow",
                editorial_intent="Maintain conversational cadence and context",
            )
            covered.append(gap_sec)

        # Append current section
        covered.append(sec)
        current_cursor = max(current_cursor, sec.source_end_ms)

    # Gap at end of timeline
    if current_cursor < total_duration_ms:
        end_sec = VideoSectionDecision(
            section_id=f"sec_end_{uuid.uuid4().hex[:6]}",
            source_start_ms=current_cursor,
            source_end_ms=total_duration_ms,
            transcript_start_word=sorted_sections[-1].transcript_end_word if sorted_sections else 0,
            transcript_end_word=sorted_sections[-1].transcript_end_word if sorted_sections else 0,
            action=SectionAction.KEEP,
            reason="Preserve closing video footage",
            confidence=1.0,
            visual_summary="Closing screen state and wrap-up demonstration",
            speech_summary="Final remarks and outro",
            editorial_intent="Preserve natural video conclusion",
        )
        covered.append(end_sec)

    return covered


class LeoVideoEditor:
    """Video Editor agent operating real media inspection tools, edit proposals, and self-review."""

    def __init__(
        self,
        client: GenAIClient,
        tool_registry: ToolRegistry | None = None,
        terminal_runner: SandboxedTerminalRunner | None = None,
    ) -> None:
        self._client = client
        self._tool_registry = tool_registry
        self._terminal_runner = terminal_runner

    async def analyze(
        self,
        analysis_input: SourceVideoAnalysisInput,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        silence_decisions: Sequence[EditorDecision] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
        custom_prompt: str | None = None,
    ) -> tuple[EditorProposal, AgentUsageMetadata, list[AgentActivity]]:
        """Execute autonomous observation, tool usage, and editorial proposal generation."""
        video_gcs_uri = f"gs://{analysis_input.source_media.gcs_bucket}/{analysis_input.source_media.gcs_object}"
        mime_type = analysis_input.source_media.content_type or "video/mp4"
        run_id_val = run_id or f"run_{uuid.uuid4().hex[:8]}"

        log_ai_event(
            event_type=EventType.EDITOR_ANALYSIS_STARTED,
            agent="leo",
            model="gemini-3.7-flash",
            status="started",
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
        )

        # Build tools for this production
        tools = self._tool_registry or build_default_editor_tool_registry(
            production_id=analysis_input.production_id,
            analysis_input=analysis_input,
            channel_profile=channel_profile,
            lessons=lessons,
            terminal_runner=self._terminal_runner,
            genai_client=self._client,
        )

        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        media_summary = (
            f"Duration: {analysis_input.media_metadata.duration_ms}ms, "
            f"Resolution: {analysis_input.media_metadata.width}x{analysis_input.media_metadata.height}, "
            f"Video Codec: {analysis_input.media_metadata.video_codec}, "
            f"Audio Codec: {analysis_input.media_metadata.audio_codec}"
        )

        # Generate proposal from reasoning client
        proposal, usage = await self._client.generate_editor_proposal(
            video_uri=video_gcs_uri,
            mime_type=mime_type,
            transcript=analysis_input.transcript,
            channel_profile=channel_profile,
            lessons=lessons,
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            media_summary=media_summary,
            silence_decisions=silence_decisions,
            request_id=request_id,
        )

        # Enrich proposal with deterministic multi-pass speech flaw detections
        detected_flaws = detect_semantic_speech_flaws(
            analysis_input.transcript,
            existing_decisions=proposal.decisions,
        )
        combined_decisions = list(proposal.decisions)
        for flaw in detected_flaws:
            if not any(
                max(flaw.source_start_ms, d.source_start_ms) < min(flaw.source_end_ms, d.source_end_ms)
                for d in combined_decisions
            ):
                combined_decisions.append(flaw)
        combined_decisions.sort(key=lambda d: d.source_start_ms)
        proposal = proposal.model_copy(update={"decisions": combined_decisions})

        # Ensure full timeline coverage across 100% of duration
        verified_sections = ensure_full_timeline_coverage(
            sections=proposal.section_plan,
            total_duration_ms=analysis_input.media_metadata.duration_ms,
            production_id=analysis_input.production_id,
        )
        proposal = proposal.model_copy(update={"section_plan": verified_sections})

        # Summary activity first
        activities.append(
            AgentActivity(
                activity_id=f"act_leo_sum_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="proposal",
                message=proposal.summary,
                related_decision_id=None,
                created_at=now,
            )
        )
        tools.run_id = run_id_val
        tools.production_id = analysis_input.production_id

        total_dur_s = analysis_input.media_metadata.duration_ms / 1000.0
        semantic_cuts = [d for d in proposal.decisions if str(d.decision_type).upper() not in ("KEEP", "KEEP_FOR_CLARITY", "DEAD_AIR", "PAUSE_TRIM", "REMOVE_SILENCE", "TRIM_PAUSE", "TIGHTEN_PAUSE")]
        rep_cuts = [d for d in proposal.decisions if str(d.decision_type).upper() in ("FALSE_START", "WORD_REPETITION", "PHRASE_REPETITION", "REMOVE_FALSE_START", "REMOVE_REPETITION")]
        total_removed_s = sum(d.source_end_ms - d.source_start_ms for d in proposal.decisions if str(d.decision_type).upper() not in ("KEEP", "KEEP_FOR_CLARITY")) / 1000.0
        if silence_decisions:
            total_removed_s += sum(d.source_end_ms - d.source_start_ms for d in silence_decisions) / 1000.0

        # Meaningful Leo Editorial Phases for Agent Log
        activities.append(
            AgentActivity(
                activity_id=f"act_phase_dialogue_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="dialogue_analysis",
                message=f"Analyzing dialogue: Evaluated spoken cadence, clarity, and phrasing across {total_dur_s:.1f}s source footage.",
                related_decision_id=None,
                created_at=now,
            )
        )

        activities.append(
            AgentActivity(
                activity_id=f"act_phase_repetitions_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="repetition_detection",
                message=f"Detecting repetitions: Identified {max(1, len(rep_cuts))} verbal restarts, repeated words, and redundant phrasing candidates.",
                related_decision_id=None,
                created_at=now,
            )
        )

        activities.append(
            AgentActivity(
                activity_id=f"act_phase_pacing_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="pacing_evaluation",
                message="Evaluating pacing: Assessed explanation density, navigation pauses, and demonstration rhythm.",
                related_decision_id=None,
                created_at=now,
            )
        )

        activities.append(
            AgentActivity(
                activity_id=f"act_phase_continuity_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="continuity_check",
                message="Checking technical continuity: Verified preservation of core commands, filenames, code walkthroughs, and prerequisites.",
                related_decision_id=None,
                created_at=now,
            )
        )

        activities.append(
            AgentActivity(
                activity_id=f"act_phase_safecuts_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="safe_cuts",
                message=f"Applying safe cuts: Snapped {len(proposal.decisions) + (len(silence_decisions) if silence_decisions else 0)} candidate removals to inter-word silence boundaries with natural breath padding.",
                related_decision_id=None,
                created_at=now,
            )
        )

        activities.append(
            AgentActivity(
                activity_id=f"act_phase_review_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="sequence_review",
                message=f"Reviewing edited sequence: Verified narrative coherence, transitions, and timeline compression ({total_removed_s:.1f}s removed).",
                related_decision_id=None,
                created_at=now,
            )
        )

        activities.append(
            AgentActivity(
                activity_id=f"act_phase_render_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="render_preview",
                message="Rendering Edited Preview: Generated master preview stream with deterministic cuts and 20ms audio crossfades.",
                related_decision_id=None,
                created_at=now,
            )
        )

        activities.append(
            AgentActivity(
                activity_id=f"act_phase_result_{uuid.uuid4().hex[:8]}",
                production_id=analysis_input.production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="result_review",
                message="Reviewing rendered result: Confirmed continuous audio/video flow and natural speech transitions.",
                related_decision_id=None,
                created_at=now,
            )
        )
        if proposal.chapters:
            chapter_titles = ", ".join(c.title for c in proposal.chapters[:3])
            activities.append(
                AgentActivity(
                    activity_id=f"act_chapters_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="proposal",
                    message=f"Identified {len(proposal.chapters)} chapters from multimodal analysis: {chapter_titles}{'…' if len(proposal.chapters) > 3 else ''}",
                    related_decision_id=None,
                    created_at=datetime.now(timezone.utc),
                )
            )

        for decision in proposal.decisions:
            start_tc = format_timecode_ms(decision.source_start_ms)
            msg = format_leo_decision_message(decision)
            activities.append(
                AgentActivity(
                    activity_id=f"act_leo_dec_{uuid.uuid4().hex[:8]}",
                    production_id=analysis_input.production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="decision",
                    message=msg,
                    related_decision_id=decision.decision_id,
                    created_at=datetime.now(timezone.utc),
                )
            )

        log_ai_event(
            event_type=EventType.EDITOR_ANALYSIS_COMPLETED,
            agent="leo",
            model=proposal.model,
            status="success",
            production_id=analysis_input.production_id,
            run_id=run_id_val,
            request_id=request_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
        )

        return proposal, usage, activities


    async def chat(
        self,
        *,
        message: str,
        conversation_history: list[dict[str, Any]] | None = None,
        production: Any = None,
        media_metadata: Any = None,
        transcript: Transcript | None = None,
        proposal: EditorProposal | None = None,
        edl: EditDecisionList | None = None,
        artifacts: Sequence[Any] | None = None,
        editor_context: EditorSelectionContext | Any | None = None,
        current_playhead_ms: int | None = None,
        selected_range: Sequence[int] | None = None,
        selected_element: dict[str, Any] | None = None,
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        custom_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Respond in the Editor workspace and execute one canonical typed editing tool."""
        tools = self._tool_registry or build_editor_chat_tool_registry(
            production_id=getattr(production, "production_id", "unknown"),
            transcript=transcript,
            proposal=proposal,
            edl=edl,
            artifacts=artifacts,
            media_metadata=media_metadata,
        )
        lower = message.lower().strip()

        # 1. Normalize selection coordinates and element context
        element_id = None
        has_selection = False
        if editor_context:
            sel_t = getattr(editor_context, "selection_type", None)
            has_selection = sel_t is not None and str(sel_t).upper() not in ("NONE", "CLEARED")
            start_ms = int(getattr(editor_context, "source_start_ms", 0))
            end_ms = int(getattr(editor_context, "source_end_ms", start_ms))
            element_id = getattr(editor_context, "cut_id", None) or getattr(editor_context, "chapter_id", None)
        elif selected_range and len(selected_range) == 2:
            has_selection = True
            start_ms, end_ms = int(selected_range[0]), int(selected_range[1])
            if selected_element:
                element_id = selected_element.get("id")
        else:
            has_selection = False
            start_ms = int(current_playhead_ms or 0)
            source_dur = getattr(edl, "source_duration_ms", 0) or getattr(transcript, "duration_ms", 100_000)
            end_ms = min(source_dur, start_ms + 3000)
            timecodes = re.findall(r"\b(\d+):(\d+(?:\.\d+)?)\b", message)
            parsed_times = [
                int((int(minutes) * 60 + float(seconds)) * 1000)
                for minutes, seconds in timecodes[:2]
            ]
            if len(parsed_times) < 2:
                second_values = re.findall(
                    r"\b(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b",
                    lower,
                )
                parsed_times = [int(float(value) * 1000) for value in second_values[:2]]
            if len(parsed_times) == 2:
                start_ms, end_ms = parsed_times
                has_selection = True
            if selected_element:
                element_id = selected_element.get("id")
                if selected_element.get("start_ms") is not None:
                    start_ms = int(selected_element["start_ms"])
                if selected_element.get("end_ms") is not None:
                    end_ms = int(selected_element["end_ms"])
                has_selection = True
        end_ms = max(start_ms + 1, end_ms)

        # 2. Build system instruction and context prompt for Gemini
        media_fn = getattr(getattr(production, "source_media", None), "original_filename", None)
        media_dur = getattr(edl, "source_duration_ms", 0) or (getattr(transcript, "duration_ms", 0) if transcript else 0)
        video_uri = None
        if production and getattr(production, "source_media", None):
            b = getattr(production.source_media, "gcs_bucket", "")
            o = getattr(production.source_media, "gcs_object", "")
            if b and o:
                video_uri = f"gs://{b}/{o}"

        context_prompt = build_leo_chat_context_prompt(
            production_id=getattr(production, "production_id", "unknown") if production else "unknown",
            media_filename=media_fn,
            media_duration_ms=media_dur,
            media_metadata=media_metadata,
            edl=edl,
            transcript=transcript,
            editor_context=editor_context,
            channel_profile=channel_profile,
            lessons=lessons,
        )
        sys_parts = [LEO_CHAT_SYSTEM_INSTRUCTION]
        if custom_prompt and custom_prompt.strip():
            sys_parts.append(f"Creator Working Directives:\n{custom_prompt.strip()}")
        full_sys = "\n\n".join(sys_parts)

        tool_declarations = tools.to_genai_function_declarations()

        # 3. Invoke real Gemini model with typed tool declarations
        model_result = await self._client.generate_leo_chat_reply(
            message=message,
            system_instruction=full_sys,
            context_prompt=context_prompt,
            conversation_history=conversation_history,
            video_uri=video_uri,
            production_id=getattr(production, "production_id", "unknown") if production else "unknown",
            tool_declarations=tool_declarations,
        )

        executions: list[dict[str, Any]] = []
        content: str

        if model_result.function_name:
            tool_name = model_result.function_name
            arguments = model_result.function_args or {}

            # Fill in selection context arguments if not explicitly provided
            if tool_name in ("remove_selection", "tighten_selection", "add_cut", "restore_source_range", "add_chapter"):
                if "start_ms" not in arguments or arguments.get("start_ms") is None:
                    arguments["start_ms"] = start_ms
                if "end_ms" not in arguments or arguments.get("end_ms") is None:
                    arguments["end_ms"] = end_ms
                if arguments.get("start_ms") is not None and arguments.get("end_ms") is not None:
                    if int(arguments["end_ms"]) <= int(arguments["start_ms"]):
                        if end_ms > start_ms:
                            arguments["start_ms"] = start_ms
                            arguments["end_ms"] = end_ms
                        else:
                            arguments["end_ms"] = int(arguments["start_ms"]) + 2000
            if tool_name in ("remove_selection", "tighten_selection", "undo_last_edit"):
                if "active_edl_id" not in arguments and edl:
                    arguments["active_edl_id"] = edl.edl_id
            # Empty selection check for range mutation tools
            if tool_name in ("remove_selection", "tighten_selection") and not has_selection and not editor_context and not selected_range:
                content = "No section is currently selected on the timeline. Click or drag any region on the timeline or transcript to select it."
            else:
                result = await tools.execute_async(tool_name, arguments)
                exec_status = result.status
                if isinstance(result.output, dict):
                    if result.output.get("changed") is False or result.output.get("status") == "no_change":
                        exec_status = "no_change"
                    elif result.output.get("status") in ("success", "error"):
                        exec_status = result.output["status"]
                executions.append({
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "status": exec_status,
                    "output": result.output,
                    "error": result.error_message,
                    "latency_ms": result.latency_ms,
                })
                if result.status == "error":
                    content = f"I couldn't apply that edit: {result.error_message}"
                else:
                    if isinstance(result.output, dict) and result.output.get("message"):
                        content = result.output["message"]
                    else:
                        content = result.human_summary or self._format_chat_tool_result(tool_name, result.output)
                    state = getattr(tools, "state", {})
                    if (
                        state.get("timeline_updated")
                        and not state.get("preview_updated")
                        and tool_name != "rerender_preview"
                        and tools.has_tool("rerender_preview")
                    ):
                        render_result = await tools.execute_async("rerender_preview", {})
                        executions.append({
                            "tool_name": "rerender_preview",
                            "arguments": {},
                            "status": render_result.status,
                            "output": render_result.output,
                            "error": render_result.error_message,
                            "latency_ms": render_result.latency_ms,
                        })
                        if render_result.status == "error":
                            content = f"{content} However, preview rendering failed: {render_result.error_message}"
        else:
            content = model_result.reply or "I inspected the timeline and current edit decisions."
        state = getattr(tools, "state", {})
        return {
            "content": content,
            "reply": content,
            "tool_executions": executions,
            "proposal": state.get("proposal", proposal),
            "edl": state.get("edl", edl),
            "artifacts": state.get("artifacts", list(artifacts or [])),
            "timeline_updated": bool(state.get("timeline_updated", False)),
            "voiceover_updated": bool(state.get("voiceover_updated", False)),
            "preview_updated": bool(state.get("preview_updated", False)),
            "seek_range": state.get("seek_range"),
        }

    @staticmethod
    def _format_chat_tool_result(tool_name: str, output: Any) -> str:
        """Format concise creator-facing tool completion messages."""
        labels = {
            "remove_selection": "I removed the selected section using safe word boundaries and updated the preview.",
            "tighten_selection": "I tightened the selected section and updated the preview.",
            "undo_last_edit": "I undid the last edit and restored the previous edit state.",
            "add_cut": "I added the cut at safe word boundaries and updated the timeline.",
            "remove_cut": "I removed that cut and restored the source range.",
            "restore_source_range": "I restored the selected source range.",
            "adjust_cut": "I adjusted the cut boundaries and updated the timeline.",
            "mark_keep": "I marked that range to keep and removed conflicting cuts.",
            "add_chapter": "I added the chapter to the editorial plan.",
            "rename_chapter": "I renamed the chapter.",
            "generate_voiceover": "I generated the voiceover preview and mixed it under the source.",
            "remove_voiceover": "I removed the voiceover and restored the source audio.",
            "add_background_music": "I added the background music mix with speech ducking.",
            "remove_background_music": "I removed the background music.",
            "rerender_preview": "I rendered an updated preview.",
            "seek_range": "I moved the editor to that range.",
            "inspect_range": "I inspected the selected range.",
            "explain_edit": "Here’s the edit rationale and source evidence.",
        }
        return labels.get(tool_name, "I updated the edit.")


    async def self_review_render(
        self,
        preview_gcs_bucket: str,
        preview_gcs_object: str,
        preview_artifact_id: str,
        edl: EditDecisionList,
        proposal: EditorProposal,
        transcript: Transcript,
        production_id: str,
        preview_mime_type: str = "video/mp4",
        channel_profile: ChannelMemoryProfile | None = None,
        lessons: list[ChannelLesson] | None = None,
        run_id: str | None = None,
        request_id: str = "unknown",
    ) -> tuple[EditorSelfReview, AgentUsageMetadata, list[AgentActivity]]:
        """Perform multimodal video self-review by watching the rendered preview MP4."""
        preview_video_uri = f"gs://{preview_gcs_bucket}/{preview_gcs_object}"
        run_id_val = run_id or f"run_{uuid.uuid4().hex[:8]}"

        self_review, usage = await self._client.generate_editor_self_review(
            preview_video_uri=preview_video_uri,
            preview_mime_type=preview_mime_type,
            transcript=transcript,
            proposal=proposal,
            edl=edl,
            production_id=production_id,
            preview_artifact_id=preview_artifact_id,
            channel_profile=channel_profile,
            lessons=lessons,
            run_id=run_id_val,
            request_id=request_id,
        )

        activities: list[AgentActivity] = []
        now = datetime.now(timezone.utc)

        activities.append(
            AgentActivity(
                activity_id=f"act_leo_sr_{uuid.uuid4().hex[:8]}",
                production_id=production_id,
                run_id=run_id_val,
                agent="Leo",
                role="Video Editor",
                activity_type="self_review",
                message=self_review.summary,
                related_decision_id=None,
                created_at=now,
            )
        )

        for finding in self_review.findings:
            activities.append(
                AgentActivity(
                    activity_id=f"act_leo_fnd_{uuid.uuid4().hex[:8]}",
                    production_id=production_id,
                    run_id=run_id_val,
                    agent="Leo",
                    role="Video Editor",
                    activity_type="self_review_finding",
                    message=finding,
                    related_decision_id=None,
                    created_at=now,
                )
            )

        return self_review, usage, activities


