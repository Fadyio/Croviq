from datetime import datetime, timezone
from croviq_agents.prompts import (
    build_director_prompt,
    build_editor_prompt,
    format_channel_memory_summary,
    format_transcript_for_prompt,
)
from croviq_domain.editorial import (
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    ShortCandidate,
)
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, TargetAgent
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord


def _sample_transcript() -> Transcript:
    words = [
        TranscriptWord(index=0, text="Welcome", start_ms=0, end_ms=400),
        TranscriptWord(index=1, text="to", start_ms=410, end_ms=550),
        TranscriptWord(index=2, text="Croviq.", start_ms=560, end_ms=900),
        TranscriptWord(index=3, text="GitHub", start_ms=1000, end_ms=1400),
        TranscriptWord(index=4, text="Actions", start_ms=1410, end_ms=1800),
        TranscriptWord(index=5, text="runs", start_ms=1810, end_ms=2100),
        TranscriptWord(index=6, text="the", start_ms=2110, end_ms=2250),
        TranscriptWord(index=7, text="workflow.", start_ms=2260, end_ms=2700),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_001",
            start_ms=0,
            end_ms=900,
            text="Welcome to Croviq.",
            word_start_index=0,
            word_end_index=2,
        ),
        TranscriptSegment(
            segment_id="seg_002",
            start_ms=1000,
            end_ms=2700,
            text="GitHub Actions runs the workflow.",
            word_start_index=3,
            word_end_index=7,
        ),
    ]
    return Transcript(
        transcript_id="tr_test_123",
        production_id="prod_test_123",
        language_code="en-US",
        duration_ms=2700,
        words=words,
        segments=segments,
        created_at=datetime.now(timezone.utc),
    )


def test_format_transcript_for_prompt() -> None:
    tr = _sample_transcript()
    formatted = format_transcript_for_prompt(tr)
    assert "[0] (0ms - 400ms) Welcome" in formatted
    assert "[7] (2260ms - 2700ms) workflow." in formatted


def test_format_channel_memory_summary() -> None:
    profile = ChannelMemoryProfile(
        channel_id="chan_01",
        channel_name="AI Engineering Tutorials",
        primary_topics=["Python", "Cloud Run"],
        content_pillars=["DevOps", "AI Agents"],
        language="en",
        audience_geographies=["US", "EU"],
        audience_characteristics=["Engineers", "Builders"],
        historical_baselines={"avg_retention_pct": 55.0},
        high_performing_formats=["Practical Demos"],
        weak_formats=["Lengthy Theory"],
        recurring_retention_patterns=["Drop off during setup preamble"],
        packaging_patterns=["High contrast thumbnail"],
        editorial_directives=["Demonstrate code within first 45 seconds"],
        updated_at=datetime.now(timezone.utc),
    )
    lessons = [
        ChannelLesson(
            lesson_id="les_01",
            channel_id="chan_01",
            directive="Cut preamble and jump directly into terminal",
            target_agent=TargetAgent.EDITOR,
            evidence_summary="Retention drops 20% on long spoken intros",
            confidence=0.92,
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]
    summary = format_channel_memory_summary(profile, lessons)
    assert "AI Engineering Tutorials" in summary
    assert "Demonstrate code within first 45 seconds" in summary
    assert "Cut preamble and jump directly into terminal" in summary


def test_build_editor_prompt_includes_anchors_and_policy() -> None:
    tr = _sample_transcript()
    prompt = build_editor_prompt(
        transcript=tr,
        channel_profile=None,
        lessons=None,
        production_id="prod_test_123",
        media_summary="1080p 30fps",
    )
    assert "You are Leo, the Dialogue Editor" in prompt
    assert "CANONICAL WORD TIMING ANCHOR RULE" in prompt
    assert "transcript_start_word" in prompt
    assert "transcript_end_word" in prompt
    assert "[0] (0ms - 400ms) Welcome" in prompt
    assert "prod_test_123" in prompt


def test_build_director_prompt_includes_leo_decisions() -> None:
    tr = _sample_transcript()
    proposal = EditorProposal(
        production_id="prod_test_123",
        agent="leo",
        model="gemini-3.7-flash",
        summary="Found 1 filler cut",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=1,
                transcript_end_word=1,
                source_start_ms=410,
                source_end_ms=550,
                original_text="to",
                action="remove",
                concise_reason="Remove filler hesitation",
                confidence=0.95,
            )
        ],
        short_candidate=ShortCandidate(
            start_ms=1000,
            end_ms=2700,
            transcript_start_word=3,
            transcript_end_word=7,
            hook_title="GitHub Actions demo",
            concise_reason="Concise demonstration",
            confidence=0.9,
        ),
        overall_confidence=0.94,
    )
    prompt = build_director_prompt(
        transcript=tr,
        channel_profile=None,
        lessons=None,
        proposal=proposal,
        production_id="prod_test_123",
    )
    assert "You are Maya, the Director" in prompt
    assert "dec_01" in prompt
    assert "Remove filler hesitation" in prompt
    assert "GitHub Actions demo" in prompt
