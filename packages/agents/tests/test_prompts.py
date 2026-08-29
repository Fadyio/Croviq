from datetime import datetime, timezone
from croviq_agents.prompts import (
    build_editor_prompt,
    build_narration_rewrite_prompt,
    format_channel_memory_summary,
    format_transcript_for_prompt,
)
from croviq_domain.editorial import EditorDecision, EditorDecisionType
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
            target_agent=TargetAgent.LEO,
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
    assert "You are Leo, the Video Editor" in prompt
    assert "CANONICAL WORD TIMING ANCHOR RULE" in prompt
    assert "transcript_start_word" in prompt
    assert "transcript_end_word" in prompt
    assert "[0] (0ms - 400ms) Welcome" in prompt
    assert "prod_test_123" in prompt
    assert "short_candidate" not in prompt
    assert "Short candidate" not in prompt
    assert "filler" in prompt.lower()
    assert "false start" in prompt.lower()
    assert "B-roll" in prompt
    assert "chapter" in prompt.lower()
def test_build_editor_prompt_includes_silence_plan() -> None:
    tr = _sample_transcript()
    silence_dec = EditorDecision(
        decision_id="silence_01",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=0,
        transcript_end_word=1,
        source_start_ms=2125,
        source_end_ms=9575,
        original_text="[Silence]",
        action="trim",
        concise_reason="Deterministic silence cleanup: trimmed 7.45s dead air",
        confidence=1.0,
    )
    prompt = build_editor_prompt(
        transcript=tr,
        channel_profile=None,
        lessons=None,
        production_id="prod_test_123",
        silence_decisions=[silence_dec],
    )
    assert "Deterministic Silence Cleanup Plan (Already Scheduled)" in prompt
    assert "00:02.1 -> 00:09.6" in prompt
    assert "7.45s dead air trimmed" in prompt
    assert "BASELINE SILENCE ALREADY SCHEDULED" in prompt



def test_build_narration_rewrite_prompt() -> None:
    prompt = build_narration_rewrite_prompt(
        original_text="Also there is a lot of other devices one to verify that the GitHub the Cloudflare action is working.",
        available_duration_s=10.2,
        attempt=1,
    )
    assert "Correct grammar and non-native phrasing into natural spoken English" in prompt
    assert "remaining within the exact available time budget" in prompt
    assert "Do NOT make narration more verbose" in prompt
    assert "10.20 seconds" in prompt
