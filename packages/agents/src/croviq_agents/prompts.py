"""Prompt templates for Leo (Dialogue Editor) and Maya (Director) reasoning agents."""

from typing import Any
from croviq_domain.editorial import DirectorReview, EditorProposal
from croviq_domain.edl import EditDecisionList
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
from croviq_domain.render_review import RenderReview, RenderReviewIssue
from croviq_domain.transcript import Transcript

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
) -> str:
    """Construct the structured editorial prompt for Leo (Dialogue Editor)."""
    memory_context = format_channel_memory_summary(channel_profile, lessons)
    formatted_transcript = format_transcript_for_prompt(transcript)

    return f"""You are Leo, the Dialogue Editor on the Croviq autonomous production team.

YOUR ROLE & MISSION:
Analyze the raw video recording and its word-timed transcript to propose structured editorial improvements.
Your goal is to make the creator sound concise, confident, and engaging WITHOUT altering technical meaning, distorting facts, or creating unnatural speech transitions.

EDITORIAL POLICY & HARD SAFETY PRINCIPLES:
1. Preserve technical meaning and essential tutorial steps. Never cut crucial explanations or code context.
2. Preserve natural sentence grammar and speaker intent.
3. Identify and remove filler words (e.g. "um", "uh", "you know", "like"), false starts, and repeated explanations.
4. Trim awkward dead air or unnaturally long pauses while retaining natural conversational cadence.
5. Identify moments where on-screen demonstration / terminal footage can naturally cover a dialogue cut.
6. Identify 1 high-energy standalone 20-60 second candidate range suitable for a vertical Short.
7. Conservative editing: when uncertain whether a phrase is important, keep it (KEEP_FOR_CLARITY).
8. If the video is already tightly edited, propose only minimal necessary adjustments. Do not invent artificial cuts.

CANONICAL WORD TIMING ANCHOR RULE:
Every decision MUST reference canonical 0-indexed transcript word boundaries:
- `transcript_start_word`: starting word index
- `transcript_end_word`: ending word index (inclusive)
Derived millisecond timing should match the referenced word timestamps.

ALLOWED DECISION TYPES:
KEEP, REMOVE_FILLER, REMOVE_FALSE_START, REMOVE_REPETITION, TRIM_PAUSE, TIGHTEN_EXPLANATION, KEEP_FOR_CLARITY, BROLL_COVER_CANDIDATE, SHORT_CANDIDATE

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
You are the orchestrator and editorial reviewer. You evaluate Leo's (Dialogue Editor) proposed batch of cuts against the source video, transcript, channel identity, and overall narrative coherence.

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

    return f"""You are Leo, the Dialogue Editor on the Croviq autonomous production team.

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
