"""Prompt templates for Leo (Video Editor) and Maya (Director) reasoning agents."""

from typing import Any, Sequence
from croviq_domain.editorial import DirectorReview, EditorDecision, EditorProposal
from croviq_domain.edl import EditDecisionList
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.render_review import RenderReview, RenderReviewIssue
from croviq_domain.transcript import Transcript

def format_silence_plan_for_prompt(silence_decisions: Sequence[EditorDecision] | None) -> str:
    """Format deterministic silence cleanup decisions into a concise agent prompt context section."""
    if not silence_decisions:
        return "Deterministic Silence Cleanup: No long dead-air pauses detected (>=1.2s)."

    lines = [
        "Deterministic Silence Cleanup Plan (Already Scheduled):",
        "The following long dead-air pauses are already scheduled for automatic cleanup.",
        "Do NOT waste editorial decisions rediscovering these obvious pauses:",
    ]
    for d in silence_decisions:
        start_tc = f"{int(d.source_start_ms // 60000):02d}:{(d.source_start_ms % 60000) / 1000.0:04.1f}"
        end_tc = f"{int(d.source_end_ms // 60000):02d}:{(d.source_end_ms % 60000) / 1000.0:04.1f}"
        dur_s = (d.source_end_ms - d.source_start_ms) / 1000.0
        lines.append(f"- {start_tc} -> {end_tc} ({dur_s:.2f}s dead air trimmed)")

    return "\n".join(lines)
def format_transcript_for_prompt(transcript: Transcript, max_words: int | None = None) -> str:
    """Format canonical transcript words into an indexed listing for model anchoring."""
    lines: list[str] = []
    words = transcript.words[:max_words] if max_words else transcript.words
    for word in words:
        lines.append(f"[{word.index}] ({word.start_ms}ms - {word.end_ms}ms) {word.text}")
    return "\n".join(lines)


def format_channel_memory_summary(
    profile: ChannelMemoryProfile | None,
    lessons: list[ChannelLesson] | None = None,
) -> str:
    """Create a concise agent context representation of Channel Memory Bank."""
    if not profile:
        return "Channel Memory: No historical profile available. Apply standard technical creator baseline."

    parts: list[str] = [
        f"Channel: {profile.channel_name}",
        f"Topics / Pillars: {', '.join(profile.content_pillars or profile.primary_topics or ['Tech Tutorials'])}",
        f"Audience: {', '.join(profile.audience_characteristics or ['Developers', 'Engineers'])}",
    ]
    if profile.recurring_retention_patterns:
        parts.append(f"Retention Patterns: {'; '.join(profile.recurring_retention_patterns[:3])}")
    if profile.editorial_directives:
        parts.append(f"Editorial Directives: {'; '.join(profile.editorial_directives[:4])}")

    if lessons:
        active_rules = [f"- {l.directive} (Target: {l.target_agent})" for l in lessons if l.status.upper() == "ACTIVE"]
        if active_rules:
            parts.append("Active Channel Lessons:\n" + "\n".join(active_rules[:5]))

    return "\n".join(parts)


def build_editor_prompt(
    transcript: Transcript,
    channel_profile: ChannelMemoryProfile | None,
    lessons: list[ChannelLesson] | None,
    production_id: str,
    media_summary: str | None = None,
    silence_decisions: Sequence[EditorDecision] | None = None,
) -> str:
    """Construct the structured editorial prompt for Leo (Video Editor)."""
    memory_context = format_channel_memory_summary(channel_profile, lessons)
    formatted_transcript = format_transcript_for_prompt(transcript)
    silence_context = format_silence_plan_for_prompt(silence_decisions or [])

    return f"""You are Leo, the Video Editor on the Croviq autonomous production team.

MANDATORY PRINCIPLE:
You are an autonomous VIDEO EDITOR. You see and hear the entire source video and audio directly.
Reason about:
- Spoken narrative & speech clarity (pacing, dead air, false starts, repetitions, filler, volume)
- Visual content (screen changes, terminal, code, slides, demonstrations, cursor navigation, camera cuts, visual reveals)
- Video structure (hook, setup, main demonstration, payoff, conclusion)
- Opportunities for cuts, tightening, B-roll coverage, chapter markers, and Short candidates

The word-timed transcript is a precision alignment tool; the ACTUAL VIDEO is your world model.

{silence_context}

EDITORIAL POLICY & HARD SAFETY PRINCIPLES:
1. 100% TIMELINE UNDERSTANDING (SECTION PLAN):
   - Inspect the entire video from 0ms to {transcript.duration_ms}ms with NO unexplained gaps.
   - Output a chronological `section_plan` of `VideoSectionDecision` items.
   - For every section, provide `visual_summary`, `speech_summary`, `editorial_intent`, `action` (`KEEP`, `TIGHTEN`, `REMOVE`, `COVERAGE`), and `confidence`.

2. TYPED EDITORIAL INSTRUCTIONS (DECISIONS):
   - Emit structured, typed editorial cut instructions for high-value improvements:
     * REMOVE_SILENCE / TRIM_PAUSE: Unproductive dead air
     * REMOVE_FALSE_START: Stumbled sentences or verbal restarts
     * REMOVE_REPETITION: Unnecessary duplicate phrasing
     * TIGHTEN_PAUSE / TIGHTEN_EXPLANATION: Tightening conversational rhythm while preserving natural cadence
     * REMOVE_LOW_VALUE_SECTION / REMOVE_FILLER: Non-essential filler
     * BROLL_COVER_CANDIDATE / BROLL_COVER: Visual coverage over abrupt cuts or abstract concepts
     * KEEP_FOR_CLARITY: Essential tutorial context, code walkthrough, command execution
   - BASELINE SILENCE ALREADY SCHEDULED: Long dead-air pauses listed above are already scheduled for automatic cleanup. Do NOT duplicate obvious dead-air trims.

3. CHAPTER MARKERS FROM FULL VIDEO (`chapters`):
   - Emit 3-8 semantic `ChapterMarker` items (`title`, `source_start_ms`, `source_end_ms`, `summary`, `confidence`).
   - Base chapters on what is visually and narratively happening (e.g. Intro, Architecture, Workflow Setup, Deployment, Results), not merely transcript punctuation.

4. SHORT CANDIDATE & VISUAL FOCUS PLAN (`short_candidate`):
   - Identify 1 standalone 20-60s candidate segment with the strongest hook, visual payoff, and self-contained value.
   - Include a `visual_plan` with normalized focus regions (`x`, `y`, `width`, `height`, `zoom`, `focus_label`) identifying the active screen region so the Short has a readable focus when reframed to 9:16.

CANONICAL WORD TIMING ANCHOR RULE:
Every decision MUST reference canonical 0-indexed transcript word boundaries:
- `transcript_start_word`: starting word index
- `transcript_end_word`: ending word index (inclusive)

PRODUCTION IDENTITY:
Production ID: {production_id}
{f"Media Info: {media_summary}" if media_summary else ""}

CHANNEL INTELLIGENCE (MEMORY BANK):
{memory_context}

WORD-INDEXED TRANSCRIPT ({len(transcript.words)} words, {transcript.duration_ms}ms total duration):
{formatted_transcript}

Produce a complete, structured EditorProposal conforming strictly to the requested schema.
"""

def build_director_prompt(
    transcript: Transcript,
    channel_profile: ChannelMemoryProfile | None,
    lessons: list[ChannelLesson] | None,
    proposal: EditorProposal,
    production_id: str,
) -> str:
    """Construct the structured review prompt for Maya (Director)."""
    memory_context = format_channel_memory_summary(channel_profile, lessons)
    formatted_transcript = format_transcript_for_prompt(transcript)

    proposal_summary_lines: list[str] = [
        f"Proposal Summary: {proposal.summary}",
        f"Proposed Decisions ({len(proposal.decisions)}):",
    ]
    for d in proposal.decisions:
        proposal_summary_lines.append(
            f"- [{d.decision_id}] Type: {d.decision_type}, Words: {d.transcript_start_word}..{d.transcript_end_word} "
            f"({d.source_start_ms}ms-{d.source_end_ms}ms), Action: {d.action}, Reason: {d.concise_reason}, Text: \"{d.original_text}\""
        )
    if proposal.short_candidate:
        sc = proposal.short_candidate
        proposal_summary_lines.append(
            f"Short Candidate: {sc.start_ms}ms-{sc.end_ms}ms (Words {sc.transcript_start_word}..{sc.transcript_end_word}) - \"{sc.hook_title}\": {sc.concise_reason}"
        )

    proposal_text = "\n".join(proposal_summary_lines)

    return f"""You are Maya, the Director on the Croviq autonomous production team.

YOUR ROLE & MISSION:
You are the orchestrator and editorial reviewer. You evaluate Leo's (Video Editor) proposed full-timeline section plan and batch of cuts against the source video, transcript, channel identity, and overall narrative coherence.
REVIEW DIRECTIVES:
1. Do not rubber-stamp everything. Evaluate each proposed decision critically.
2. APPROVE: Good cuts that improve pacing and conciseness without harming clarity or natural cadence.
3. REJECT: Risky cuts that remove essential technical context, setup, code explanation, or create jarring audio gaps.
4. MODIFY: Good editorial intent but requiring adjusted word boundaries or a different treatment (e.g. cover with B-roll instead of cutting).
5. Protect narrative flow, natural breathing rhythm, and channel editorial standards.
6. Provide a concise, clear editorial reason for every verdict suitable for creator UI display.
7. Decide whether the overall batch is approved for Edit Decision List (EDL) rendering (`approved_for_edl`).

PRODUCTION IDENTITY:
Production ID: {production_id}

CHANNEL INTELLIGENCE (MEMORY BANK):
{memory_context}

WORD-INDEXED TRANSCRIPT ({len(transcript.words)} words):
{formatted_transcript}

LEO'S PROPOSED EDIT BATCH:
{proposal_text}

Produce a complete, structured DirectorReview conforming strictly to the requested schema.
"""

def build_director_render_review_prompt(
    transcript: Transcript,
    proposal: EditorProposal,
    director_review: DirectorReview | None,
    edl: EditDecisionList,
    production_id: str,
    preview_artifact_id: str,
    channel_profile: ChannelMemoryProfile | None = None,
    lessons: list[ChannelLesson] | None = None,
) -> str:
    """Construct the structured post-render review prompt for Maya (Director)."""
    memory_context = format_channel_memory_summary(channel_profile, lessons)
    formatted_transcript = format_transcript_for_prompt(transcript)

    edl_summary_lines: list[str] = [
        f"EDL ID: {edl.edl_id}",
        f"Source Duration: {edl.source_duration_ms}ms",
        f"Active Cuts ({len(edl.cuts)}):",
    ]
    for cut in edl.cuts:
        edl_summary_lines.append(
            f"- Cut [{cut.cut_id}]: {cut.source_start_ms}ms - {cut.source_end_ms}ms (removed: {cut.removed_duration_ms}ms) "
            f"Reason: {cut.reason}, Strategy: {cut.transition_strategy}, Safety: {cut.safety_status}"
        )
    if edl.coverage_markers:
        edl_summary_lines.append(f"Coverage Markers ({len(edl.coverage_markers)}):")
        for marker in edl.coverage_markers:
            edl_summary_lines.append(
                f"- Marker [{marker.marker_id}]: {marker.source_start_ms}ms - {marker.source_end_ms}ms, Type: {marker.coverage_type}, Reason: {marker.reason}"
            )
    edl_text = "\n".join(edl_summary_lines)

    proposal_lines = [f"Proposal Summary: {proposal.summary}"]
    for d in proposal.decisions:
        proposal_lines.append(
            f"- [{d.decision_id}] {d.decision_type} ({d.source_start_ms}ms-{d.source_end_ms}ms): {d.concise_reason} (\"{d.original_text}\")"
        )
    proposal_text = "\n".join(proposal_lines)

    prior_review_text = (
        f"Prior Plan Assessment: {director_review.overall_assessment}\nEditor Feedback: {director_review.editor_feedback}"
        if director_review
        else "No prior director review recorded."
    )

    return f"""You are Maya, the Director on the Croviq autonomous production team.

YOUR ROLE & MISSION: POST-RENDER QUALITY EVALUATION
You are watching and evaluating the actual deterministic rendered preview MP4 video output against the original source reference, canonical transcript, and approved editorial intent.

EVALUATION CRITERIA:
1. Dialogue continuity: Does the spoken audio flow naturally across cut points?
2. Audible cut artifacts: Are there unnatural audio joins, mid-phoneme cutoffs, clipped breaths, or sudden room tone jumps?
3. Awkward sentence joins: Do stitched phrases make grammatical and cognitive sense?
4. Pacing: Is the video appropriately tight without feeling frantic or rushed? Is dead air removed?
5. Technical context: Did any cut inadvertently drop crucial code setup, command syntax, or demonstration steps?
6. Visual jump cuts: Are talking-head cuts jarring? Is B-roll / screen coverage needed?
7. Intent verification: Did Leo's proposed edits genuinely improve the video output?
8. Readiness for publication: Is this video ready for master export?

STRUCTURED OUTPUT RULES:
- Verdict: APPROVE or CORRECT.
- If APPROVE: `approved_for_master` = true, `issues` = []. Dialogue and visuals meet publication quality.
- If CORRECT: `approved_for_master` = false, `issues` must enumerate specific observable problems.
- Issue Types allowed: UNNATURAL_AUDIO_JOIN, VISUAL_JUMP, OVER_AGGRESSIVE_CUT, MISSED_EDIT, CONTEXT_LOSS, PACING, COVERAGE_NEEDED.
- Severity: LOW, MEDIUM, HIGH.
- Issue `message` must be a concise, product-facing explanation suitable for creator UI display (no internal chain-of-thought).
- Issue `suggested_action` must describe the semantic fix (e.g. restore context, widen boundary, mark for visual coverage).
- Note: You evaluate semantic editorial quality. You do NOT generate raw millisecond ffmpeg timestamps.

PRODUCTION & ARTIFACT METADATA:
Production ID: {production_id}
Preview Artifact ID: {preview_artifact_id}
EDL ID: {edl.edl_id}

CHANNEL INTELLIGENCE (MEMORY BANK):
{memory_context}

WORD-INDEXED TRANSCRIPT ({len(transcript.words)} words):
{formatted_transcript}

LEO'S ORIGINAL EDITORIAL PROPOSAL:
{proposal_text}

DIRECTOR PLAN REVIEW CONTEXT:
{prior_review_text}

EXECUTED EDIT DECISION LIST (EDL):
{edl_text}

Produce a complete, structured RenderReview conforming strictly to the requested schema.
"""


def build_editor_correction_prompt(
    transcript: Transcript,
    proposal: EditorProposal,
    render_review: RenderReview,
    production_id: str,
    channel_profile: ChannelMemoryProfile | None = None,
    lessons: list[ChannelLesson] | None = None,
) -> str:
    """Construct the structured editorial revision prompt for Leo (Dialogue Editor)."""
    memory_context = format_channel_memory_summary(channel_profile, lessons)
    formatted_transcript = format_transcript_for_prompt(transcript)

    issues_lines: list[str] = [
        f"Maya's Post-Render Verdict: {render_review.verdict}",
        f"Review Summary: {render_review.summary}",
        f"Issues Requiring Correction ({len(render_review.issues)}):",
    ]
    for issue in render_review.issues:
        rel = f" (Related Decision: {issue.related_decision_id})" if issue.related_decision_id else ""
        issues_lines.append(
            f"- [{issue.issue_id}] {issue.issue_type} ({issue.source_start_ms}ms - {issue.source_end_ms}ms) [{issue.severity}]{rel}: "
            f"{issue.message} -> Action: {issue.suggested_action}"
        )
    issues_text = "\n".join(issues_lines)

    prior_decisions_lines: list[str] = [f"Existing Proposed Decisions ({len(proposal.decisions)}):"]
    for d in proposal.decisions:
        prior_decisions_lines.append(
            f"- [{d.decision_id}] {d.decision_type} (Words {d.transcript_start_word}..{d.transcript_end_word}, "
            f"{d.source_start_ms}ms-{d.source_end_ms}ms): {d.concise_reason} (\"{d.original_text}\")"
        )
    prior_decisions_text = "\n".join(prior_decisions_lines)

    return f"""You are Leo, the Video Editor on the Croviq autonomous production team.
YOUR ROLE & MISSION: TARGETED EDITORIAL CORRECTION PASS
Maya (Director) has watched the rendered preview video and requested specific corrections.
Your goal is to revise ONLY affected decisions based on Maya's feedback. Do NOT start from scratch or re-cut untouched sections.

CORRECTION DIRECTIVES:
1. Address every issue identified by Maya in her post-render review.
2. Narrow over-aggressive cuts where context was lost or audio joins sounded unnatural.
3. Reject/restore cuts that Maya flagged as harming technical comprehension.
4. Mark talking-head jump cuts as BROLL_COVER_CANDIDATE where requested.
5. Maintain preserved green takes, keep crisp pacing, and anchor all decisions to exact word indices in the transcript.
6. Revise ONLY affected decisions while retaining existing valid decisions.

PRODUCTION IDENTITY:
Production ID: {production_id}
Render Review ID: {render_review.review_id}

CHANNEL INTELLIGENCE (MEMORY BANK):
{memory_context}

WORD-INDEXED TRANSCRIPT ({len(transcript.words)} words):
{formatted_transcript}

EXISTING EDITORIAL PROPOSAL:
{prior_decisions_text}

MAYA'S POST-RENDER REVIEW & ISSUES:
{issues_text}

Produce a complete, revised EditorProposal conforming strictly to the requested schema.
"""


def build_narration_rewrite_prompt(
    original_text: str,
    available_duration_s: float,
    attempt: int = 1,
) -> str:
    """Construct prompt for Leo to rewrite speech into natural professional spoken English within strict time budget."""
    target_words = max(2, int(available_duration_s * 2.3))
    shorten_guidance = (
        f" This is retry attempt {attempt}; tighten phrasing and use fewer words ({target_words} words max) to ensure the spoken duration strictly fits within {available_duration_s:.2f}s."
        if attempt > 1
        else f" Keep length under approximately {target_words} words so spoken duration fits within {available_duration_s:.2f}s."
    )
    return f"""You are Leo, the Video Editor and Voice Director on the Croviq autonomous production team.

GOAL:
Correct grammar and non-native phrasing into natural spoken English while preserving technical meaning and remaining within the exact available time budget.

GUIDELINES:
1. Fix non-native phrasing, awkward grammar, and speech stumbles into smooth, idiomatic, professional spoken English.
2. Preserve all technical concepts (e.g. GitHub Actions, Cloudflare, Google Cloud deployment, test verification, workflows).
3. Match what is visibly demonstrated on screen.
4. Do NOT make narration more verbose.
5.{shorten_guidance}
6. Return ONLY the rewritten spoken sentence without commentary, quotes, or markdown formatting.

ORIGINAL SPOKEN TEXT:
"{original_text}"

AVAILABLE TIME BUDGET: {available_duration_s:.2f} seconds
REWRITTEN SPOKEN TEXT:"""
