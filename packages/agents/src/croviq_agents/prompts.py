"""Prompt templates for Leo (Dialogue Editor) and Maya (Director) reasoning agents."""

from typing import Any
from croviq_domain.editorial import EditorProposal
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
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
