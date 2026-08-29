from datetime import datetime, timezone
import pytest

from croviq_agents.client import (
    FakeGenAIClient,
    GenAIError,
    reconcile_editor_proposal_with_transcript,
)
from croviq_domain.editorial import EditorDecision, EditorDecisionType, EditorProposal
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord


def _sample_transcript() -> Transcript:
    words = [
        TranscriptWord(index=0, text="First", start_ms=0, end_ms=300),
        TranscriptWord(index=1, text="second", start_ms=310, end_ms=600),
        TranscriptWord(index=2, text="third", start_ms=610, end_ms=900),
        TranscriptWord(index=3, text="fourth", start_ms=910, end_ms=1200),
    ]
    segments = [
        TranscriptSegment(
            segment_id="seg_001",
            start_ms=0,
            end_ms=1200,
            text="First second third fourth",
            word_start_index=0,
            word_end_index=3,
        )
    ]
    return Transcript(
        transcript_id="tr_123",
        production_id="prod_123",
        language_code="en-US",
        duration_ms=1200,
        words=words,
        segments=segments,
        created_at=datetime.now(timezone.utc),
    )


def test_reconcile_editor_proposal_with_transcript_anchors_timestamps_and_text() -> None:
    tr = _sample_transcript()
    # Model returned slightly approximate timestamps
    proposal = EditorProposal(
        production_id="prod_123",
        agent="leo",
        model="gemini-3.7-flash",
        summary="Test summary",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=1,
                transcript_end_word=2,
                source_start_ms=300,  # Approximate
                source_end_ms=950,  # Approximate
                original_text="approximate text",
                action="remove",
                concise_reason="Remove filler",
                confidence=0.9,
            )
        ],
        overall_confidence=0.9,
    )

    reconciled = reconcile_editor_proposal_with_transcript(proposal, tr)
    assert len(reconciled.decisions) == 1
    d = reconciled.decisions[0]
    # Authoritative word timestamps
    assert d.source_start_ms == 310
    assert d.source_end_ms == 900
    assert d.original_text == "second third"
    assert "short_candidate" not in reconciled.model_dump()


def test_reconcile_editor_proposal_clamps_out_of_bounds_words() -> None:
    tr = _sample_transcript()
    proposal = EditorProposal(
        production_id="prod_123",
        agent="leo",
        model="gemini-3.7-flash",
        summary="Test summary",
        decisions=[
            EditorDecision(
                decision_id="dec_01",
                decision_type=EditorDecisionType.REMOVE_FILLER,
                transcript_start_word=0,
                transcript_end_word=99,  # Out of bounds
                source_start_ms=0,
                source_end_ms=5000,
                original_text="out of bounds",
                action="remove",
                concise_reason="Clamped test",
                confidence=0.9,
            )
        ],
        overall_confidence=0.9,
    )
    reconciled = reconcile_editor_proposal_with_transcript(proposal, tr)
    d = reconciled.decisions[0]
    assert d.transcript_end_word == 3
    assert d.source_end_ms == 1200
    assert d.original_text == "First second third fourth"


def test_reconcile_editor_proposal_preserves_silence_cuts() -> None:
    tr = _sample_transcript()
    silence_cut = EditorDecision(
        decision_id="silence_cut_001",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=1,
        transcript_end_word=2,
        source_start_ms=350,
        source_end_ms=550,
        original_text="[Silence: second ... third]",
        action="trim",
        concise_reason="Deterministic silence trim",
        confidence=1.0,
    )
    proposal = EditorProposal(
        production_id="prod_123",
        agent="leo",
        model="gemini-3.7-flash",
        summary="Test proposal",
        decisions=[silence_cut],
        section_plan=[],
        chapters=[],
        overall_confidence=1.0,
    )
    reconciled = reconcile_editor_proposal_with_transcript(proposal, tr)
    rec_dec = reconciled.decisions[0]
    assert rec_dec.source_start_ms == 350
    assert rec_dec.source_end_ms == 550
    assert rec_dec.original_text == "[Silence: second ... third]"

@pytest.mark.asyncio
async def test_fake_genai_client_deterministic_flow() -> None:
    client = FakeGenAIClient()
    tr = _sample_transcript()

    proposal, usage = await client.generate_editor_proposal(
        video_uri="gs://bucket/video.mp4",
        mime_type="video/mp4",
        transcript=tr,
        channel_profile=None,
        lessons=None,
        production_id="prod_123",
    )
    assert proposal.production_id == "prod_123"
    assert proposal.agent == "leo"
    assert "short_candidate" not in proposal.model_dump()
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0
    assert not hasattr(client, "generate_director_review")
    assert not hasattr(client, "generate_render_review")
    assert not hasattr(client, "generate_editor_correction")

@pytest.mark.asyncio
async def test_fake_genai_client_handles_failures() -> None:
    client = FakeGenAIClient(fail_on_editor=True)
    tr = _sample_transcript()
    with pytest.raises(GenAIError, match="Simulated Leo editor"):
        await client.generate_editor_proposal(
            video_uri="gs://bucket/video.mp4",
            mime_type="video/mp4",
            transcript=tr,
            channel_profile=None,
            lessons=None,
            production_id="prod_123",
        )


