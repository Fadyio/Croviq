import asyncio

from datetime import datetime, timezone
import pytest

import croviq_agents.client as client_module
from croviq_agents.client import (
    FakeGenAIClient,
    GenAIError,
    GoogleGenAIClient,
    reconcile_editor_proposal_with_transcript,
)
from unittest.mock import AsyncMock, MagicMock, patch
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


@pytest.mark.asyncio
async def test_fake_genai_client_lyria_music_generation():
    client = FakeGenAIClient()
    wav_bytes, fmt, dur_ms = await client.generate_background_music(
        prompt="Minimal modern technology documentary underscore",
        duration_s=10,
        model_id="lyria-3-pro-preview",
        production_id="prod_music_test",
    )
    assert fmt == "audio/wav"
    assert dur_ms == 10000
    assert len(wav_bytes) > 0
    assert wav_bytes.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_google_genai_client_iris_hanging_provider_falls_back_within_bounded_timeout_without_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GoogleGenAIClient(project_id="test-proj", location="global")
    raw_client = MagicMock()
    provider_started = asyncio.Event()
    provider_attempts = 0
    cancelled_attempts = 0

    async def hang_forever(**kwargs):
        nonlocal provider_attempts, cancelled_attempts
        provider_attempts += 1
        provider_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled_attempts += 1
            raise

    raw_client.aio.models.generate_content = AsyncMock(side_effect=hang_forever)
    client._client = raw_client
    monkeypatch.setattr(
        client_module,
        "IRIS_RELEASE_REVIEW_TIMEOUT_SECONDS",
        0.01,
        raising=False,
    )
    monkeypatch.setattr(
        client_module,
        "IRIS_RELEASE_REVIEW_RETRY_DELAY_SECONDS",
        0.0,
        raising=False,
    )

    with (
        patch("croviq_agents.client.time.sleep") as blocking_sleep,
        patch("croviq_agents.client.log_ai_event"),
    ):
        review_task = asyncio.create_task(
            client.generate_release_review(
                master_video_uri="gs://bucket/master.mp4",
                master_mime_type="video/mp4",
                transcript=_sample_transcript(),
                production_id="prod_123",
                preview_mode="final_mix",
                master_artifact_id="artifact_master_123",
                master_duration_ms=1200,
            )
        )
        await asyncio.wait_for(provider_started.wait(), timeout=0.1)
        heartbeat = asyncio.create_task(asyncio.sleep(0))
        await asyncio.wait_for(heartbeat, timeout=0.1)
        review, usage = await asyncio.wait_for(review_task, timeout=0.5)

    blocking_sleep.assert_not_called()
    assert provider_attempts == 2
    assert cancelled_attempts == 2
    assert review.verdict.value == "PASS"
    assert review.approved_for_release is True
    assert review.reviewed_artifact_id == "artifact_master_123"
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0

