"""Prompt templates for Croviq's Leo video editor and Iris quality gate."""

from typing import Any, Sequence
from croviq_domain.channel_intelligence import ResearchFinding
from croviq_domain.editorial import EditorDecision, EditorProposal
from croviq_domain.edl import EditDecisionList
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile
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

    topics = list(profile.primary_topics or [])
    for p in (profile.content_pillars or []):
        if p not in topics:
            topics.append(p)
    parts: list[str] = [
        f"Channel: {profile.channel_name}",
        f"Topics / Pillars: {', '.join(topics) if topics else 'Tech Tutorials'}",
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
- Opportunities for cuts, tightening, B-roll coverage, and chapter markers

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



def build_editor_self_review_prompt(
    transcript: Transcript,
    proposal: EditorProposal,
    edl: EditDecisionList,
    production_id: str,
    preview_artifact_id: str,
    channel_profile: ChannelMemoryProfile | None = None,
    lessons: list[ChannelLesson] | None = None,
) -> str:
    """Construct the structured multimodal self-review prompt for Leo (Video Editor) to evaluate rendered preview video."""
    memory_context = format_channel_memory_summary(channel_profile, lessons)
    formatted_transcript = format_transcript_for_prompt(transcript)

    edl_summary_lines: list[str] = [
        f"EDL ID: {edl.edl_id}",
        f"Source Duration: {edl.source_duration_ms}ms",
        f"Total Removed Duration: {edl.total_removed_duration_ms}ms",
        f"Estimated Target Duration: {edl.estimated_target_duration_ms}ms",
        f"Active Cuts ({len(edl.cuts)}):",
    ]
    for cut in edl.cuts:
        edl_summary_lines.append(
            f"- Cut [{cut.cut_id}]: {cut.safe_start_ms}ms - {cut.safe_end_ms}ms (removed: {cut.removed_duration_ms}ms) "
            f"Type: {cut.decision_type}, Left: '{cut.left_anchor}', Right: '{cut.right_anchor}', Safety: {cut.safety_status}"
        )
    if edl.coverage_markers:
        edl_summary_lines.append(f"Coverage Markers ({len(edl.coverage_markers)}):")
        for marker in edl.coverage_markers:
            edl_summary_lines.append(
                f"- Marker [{marker.marker_id}]: {marker.source_start_ms}ms - {marker.source_end_ms}ms, Type: {marker.coverage_type}, Reason: {marker.reason}"
            )
    edl_text = "\n".join(edl_summary_lines)

    decisions_lines = [f"Proposed Decisions ({len(proposal.decisions)}):"]
    for d in proposal.decisions:
        decisions_lines.append(
            f"- [{d.decision_id}] {d.decision_type} ({d.source_start_ms}ms-{d.source_end_ms}ms): {d.concise_reason} (\"{d.original_text}\")"
        )
    decisions_text = "\n".join(decisions_lines)


    chapters_text = (
        "\n".join(f"- Chapter: {c.title} ({c.source_start_ms}ms → {c.source_end_ms}ms) - {c.summary}" for c in proposal.chapters)
        if proposal.chapters
        else "No chapters defined."
    )

    return f"""You are Leo, the Video Editor on the Croviq autonomous production team.

YOUR ROLE & MISSION: MULTIMODAL POST-RENDER SELF-REVIEW
You are now watching and evaluating the actual rendered preview MP4 video output that was produced from your Edit Decision List.

EVALUATION CRITERIA:
1. Narrative pacing: Is the video engaging, energetic, and free of dead air without feeling unnatural or abrupt?
2. Edit removals: Did each cut/removal genuinely improve the edit, or does any cut feel too aggressive or jarring?
3. Visual continuity: Are talking-head cuts natural? Are there awkward jump cuts, cursor teleportations, or jarring screen switches?
4. Audio joins: Do audio cuts transition smoothly without clipped word tails, missing phonemes, or harsh room tone drops?
5. Coverage / B-roll: Is visual B-roll or screen coverage needed to mask any talking-head jumps or illustrate complex concepts?

STRUCTURED OUTPUT RULES:
- Verdict: APPROVE_UNCHANGED or NEEDS_REVISION.
- If APPROVE_UNCHANGED: All removals improved the video, visual and audio continuity are clean, and no further adjustments are needed.
- If NEEDS_REVISION: Specific observable problems must be identified in the assessment fields and findings.
- Assessment fields must contain concise, product-facing natural evaluations (no internal chain-of-thought).
- Findings must be concise bullet points summarizing what was observed.

PRODUCTION & ARTIFACT METADATA:
Production ID: {production_id}
Preview Artifact ID: {preview_artifact_id}
EDL ID: {edl.edl_id}

CHANNEL INTELLIGENCE (MEMORY BANK):
{memory_context}

WORD-INDEXED TRANSCRIPT ({len(transcript.words)} words):
{formatted_transcript}

YOUR EDITORIAL PROPOSAL:
{decisions_text}


CHAPTERS:
{chapters_text}

EXECUTED EDIT DECISION LIST (EDL):
{edl_text}

Produce a complete, structured EditorSelfReview conforming strictly to the requested schema.
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
    return f"""You are Leo, the Video Editor and Voice Editor on the Croviq autonomous production team.

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




DEFAULT_IRIS_PROMPT = (
    "You are Iris, Croviq's sole Quality Assurance gate for video creators.\n"
    "Your decision answers one question: Is this edited video ready?\n"
    "Inspect the ACTUAL current rendered main video (Preview or Master), its audio, transcript, and captions.\n\n"
    "Evaluate actual media quality:\n"
    "1. Video & Edit Continuity: Visual continuity, bad cuts, dead air/pauses, transitions, black/glitched frames, B-roll placement, and screen discontinuities.\n"
    "2. Narrative Pacing: The hook, section flow, clarity, energy, and whether edits preserve the intended meaning.\n"
    "3. Audio Quality: Speech clarity, loudness target (~ -16 LUFS, -1 dBTP), clipping, pops/clicks, and audio/video sync.\n"
    "4. Captions & Transcript: Timing alignment, dropped/mismatched words, and caption overflow.\n"
    "5. Factual Consistency: Audit explicit on-screen or spoken factual claims and metadata consistency.\n"
    "6. Output Format & Markdown Policy: Format responses in standard clean Markdown without raw LaTeX ($...$, \\text{}, etc.).\n"
    "Output Verdict: PASS (approved_for_release=True) if the edited video is ready, or FIX_REQUIRED with an actionable defect and exact timestamp if it is not."
)


def build_release_qa_prompt(
    transcript: Transcript,
    master_artifact: Any = None,
    proposal: Any = None,
    publish_metadata: Any = None,
    overrides: Any = None,
    channel_profile: ChannelMemoryProfile | None = None,
    lessons: list[ChannelLesson] | None = None,
    research_findings: Sequence[ResearchFinding] | None = None,
    deterministic_results: dict[str, Any] | None = None,
    custom_prompt: str | None = None,
    production_id: str = "unknown",
) -> str:
    """Construct the Quality Assurance and Verification prompt for Iris."""
    formatted_transcript = format_transcript_for_prompt(transcript, max_words=300)
    memory_context = format_channel_memory_summary(channel_profile, lessons)

    title = getattr(publish_metadata, "title", None) or getattr(proposal, "primary_title", "Technical Walkthrough")
    description = getattr(publish_metadata, "description", None) or getattr(proposal, "description", "")


    deterministic_text = "Deterministic Checks: None."
    if deterministic_results:
        parts = [f"- {k}: {v}" for k, v in deterministic_results.items()]
        deterministic_text = "\n".join(parts)

    system_role = custom_prompt if (custom_prompt and custom_prompt.strip()) else DEFAULT_IRIS_PROMPT

    return f"""{system_role}

IRIS — EDITED VIDEO QUALITY GATE
Production ID: {production_id}

CORE QUESTION:
Is this edited video ready?

EVALUATION CRITERIA:
1. CURRENT RENDERED MAIN VIDEO CONTINUITY & EDIT QUALITY (bad cuts, dead air, glitched frames, transitions)
2. NARRATIVE PACING & CLARITY (hook, section flow, energy, preserved meaning)
3. AUDIO QUALITY & LOUDNESS CONFORMANCE (-16 LUFS target, audio/video sync, clipping, clarity)
4. CAPTION TIMING & TRANSCRIPT ALIGNMENT (accurate timestamps, no word drop, active highlighting)
5. FACTUAL CONSISTENCY & CLAIM AUDIT:
   - Verify all explicit claims against the actual video footage.
   - Scrutinize unsupported promises or future commitments without evidence (flag as UNSUPPORTED_CLAIM).

VIDEO METADATA:
Title: {title}
Description: {description}
Rendered Main Context: Preview or Master video supplied to the multimodal review.

CHANNEL CONTEXT:
{memory_context}

DETERMINISTIC PRE-CHECK FINDINGS:
{deterministic_text}

TRANSCRIPT EXCERPT:
{formatted_transcript}

Output a strictly compliant ReleaseReview structured object with review_id, verdict (PASS, FIX_REQUIRED, MANUAL_REVIEW), summary, issues, approved_for_release, checklist, and claim_verifications.
"""
