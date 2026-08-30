"""Unit tests for closed-world entailment check, video grounding prompt, and GenAI client methods."""

import pytest
from croviq_agents.client import FakeGenAIClient
from croviq_agents.prompts import (
    build_closed_world_entailment_prompt,
    build_video_grounded_script_correction_prompt,
)
from croviq_domain.transcript import (
    CorrectedTranscript,
    EntailmentVerdict,
    ScriptCorrectionChangeType,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from datetime import datetime, timezone


def test_build_script_correction_prompt():
    t = Transcript(
        transcript_id="tr_01",
        production_id="prod_01",
        language_code="en-US",
        duration_ms=10000,
        words=[
            TranscriptWord(index=0, text="Hello", start_ms=0, end_ms=1000),
            TranscriptWord(index=1, text="world", start_ms=1000, end_ms=2000),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=0,
                end_ms=2000,
                text="Hello world",
                word_start_index=0,
                word_end_index=1,
            )
        ],
        created_at=datetime.now(timezone.utc),
    )
    prompt = build_video_grounded_script_correction_prompt(
        transcript=t,
        visible_screen_context="IDE terminal window open",
        chapter_context="Intro",
        production_id="prod_01",
    )
    assert "CORRECTED PERFORMANCE, not NEW SCRIPT" in prompt
    assert "NEVER freely rewrite the creator's video" in prompt
    assert "TRANSCRIPTION_ERROR" in prompt
    assert "GRAMMAR" in prompt
    assert "IDE terminal window open" in prompt


def test_build_closed_world_entailment_prompt():
    prompt = build_closed_world_entailment_prompt(
        source_context="Terminal showing workflow file",
        original_transcript_text="So we is going to deploy",
        corrected_text="So we are going to deploy",
    )
    assert "Closed-World Entailment Verifier" in prompt
    assert "SUPPORTED" in prompt
    assert "UNSUPPORTED" in prompt
    assert "UNCERTAIN" in prompt


@pytest.mark.asyncio
async def test_fake_genai_client_script_correction_and_entailment():
    client = FakeGenAIClient()
    t = Transcript(
        transcript_id="tr_02",
        production_id="prod_02",
        language_code="en-US",
        duration_ms=25000,
        words=[
            TranscriptWord(index=0, text="So", start_ms=0, end_ms=500),
            TranscriptWord(index=1, text="uh", start_ms=500, end_ms=1000),
            TranscriptWord(index=2, text="what", start_ms=1000, end_ms=1500),
            TranscriptWord(index=3, text="we're", start_ms=1500, end_ms=2000),
            TranscriptWord(index=4, text="gonna...", start_ms=2000, end_ms=2500),
            TranscriptWord(index=5, text="what", start_ms=2500, end_ms=3000),
            TranscriptWord(index=6, text="we're", start_ms=3000, end_ms=3500),
            TranscriptWord(index=7, text="gonna", start_ms=3500, end_ms=4000),
            TranscriptWord(index=8, text="do", start_ms=4000, end_ms=4500),
            TranscriptWord(index=9, text="now", start_ms=4500, end_ms=5000),
            TranscriptWord(index=10, text="is", start_ms=5000, end_ms=5500),
            TranscriptWord(index=11, text="deploy", start_ms=5500, end_ms=6000),
            TranscriptWord(index=12, text="it.", start_ms=6000, end_ms=6500),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=0,
                end_ms=6500,
                text="So uh what we're gonna... what we're gonna do now is deploy it.",
                word_start_index=0,
                word_end_index=12,
            )
        ],
        created_at=datetime.now(timezone.utc),
    )

    corrected, usage = await client.correct_transcript_with_video_grounding(
        video_uri="gs://bucket/video.mp4",
        mime_type="video/mp4",
        transcript=t,
        production_id="prod_02",
    )
    assert len(corrected.segments) >= 1
    first_seg = corrected.segments[0]
    assert first_seg.change_type == ScriptCorrectionChangeType.FALSE_START
    assert "So what we're going to do now is deploy it." in first_seg.corrected_text
    assert first_seg.meaning_changed is False
    assert first_seg.entailment_verdict == EntailmentVerdict.SUPPORTED

    # Test entailment check on supported vs unsupported
    res_supported = await client.verify_script_entailment(
        source_context="IDE showing deployment",
        original_transcript_text="So we gonna deploy",
        corrected_text="So we are going to deploy",
    )
    assert res_supported == EntailmentVerdict.SUPPORTED

    res_unsupported = await client.verify_script_entailment(
        source_context="IDE showing deployment",
        original_transcript_text="So we gonna deploy",
        corrected_text="So we guarantee 99.999% uptime when we deploy",
    )
    assert res_unsupported == EntailmentVerdict.UNSUPPORTED
