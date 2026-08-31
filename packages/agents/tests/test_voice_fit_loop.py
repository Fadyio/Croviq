"""Tests for Studio Voice TTS fit loop, hard duration budgets, and retry logic."""

import asyncio
import base64
import io
import wave

from datetime import datetime, timezone
import pytest

from croviq_agents.voice import (
    StudioVoiceSynthesizer,
    VoiceCatalog,
    VoiceFitAttempt,
    VoiceReplicationService,
    find_candidate_voice_sample_interval,
    fit_pcm_to_duration,
)
from croviq_domain.agent_config import (
    GOOGLE_VOICE_CONSENT_PHRASE_EN,
    NarrationMode,
    VoiceReplicationConfig,
    VoiceReplicationStatus,
    VoiceSettingsConfig,
)
from croviq_domain.narration import NarrationSegment, NarrationSegmentStatus
from croviq_domain.transcript import Transcript, TranscriptSegment, TranscriptWord
from unittest.mock import AsyncMock, MagicMock, patch
from croviq_agents.client import FakeGenAIClient, GoogleGenAIClient

def test_voice_catalog_contains_standard_google_voices():
    catalog = VoiceCatalog.list_voices()
    assert len(catalog) >= 4
    voice_ids = [v.voice_id for v in catalog]
    assert "Puck" in voice_ids
    assert "Aoede" in voice_ids


@pytest.mark.asyncio
async def test_tts_fit_loop_accepts_when_within_budget():
    synthesizer = StudioVoiceSynthesizer()

    # Mock generator returning audio shorter than available duration
    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        # Returns 4000ms audio
        return 4000, b"fake_audio_bytes"

    async def mock_rewrite(text: str, max_dur_s: float, attempt: int) -> str:
        return text

    segment = await synthesizer.fit_narration_segment(
        segment_id="seg_01",
        production_id="prod_test",
        source_start_ms=10000,
        source_end_ms=16000,
        available_duration_ms=6000,
        original_text="So here is the complete explanation of our database schema.",
        voice_id="Puck",
        tts_fn=mock_tts,
        rewrite_fn=mock_rewrite,
    )

    assert segment.status == NarrationSegmentStatus.ACCEPTED
    assert segment.generated_duration_ms == 4000
    assert segment.generated_duration_ms <= segment.available_duration_ms
    assert segment.attempts == 1


@pytest.mark.asyncio
async def test_tts_fit_loop_retries_on_overrun_and_accepts():
    synthesizer = StudioVoiceSynthesizer()

    # Mock TTS: attempt 1 returns 7000ms (exceeds 5000ms), attempt 2 returns 4500ms (fits 5000ms)
    call_count = 0

    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return 7000, b"long_audio"
        return 4500, b"short_audio"

    async def mock_rewrite(text: str, max_dur_s: float, attempt: int) -> str:
        if attempt == 1:
            return "Here is the explanation of the database schema."
        return "Here is the database schema."

    segment = await synthesizer.fit_narration_segment(
        segment_id="seg_02",
        production_id="prod_test",
        source_start_ms=0,
        source_end_ms=5000,
        available_duration_ms=5000,
        original_text="So here is the very long explanation of our database schema in full detail.",
        voice_id="Puck",
        tts_fn=mock_tts,
        rewrite_fn=mock_rewrite,
    )

    assert segment.status == NarrationSegmentStatus.ACCEPTED
    assert segment.generated_duration_ms == 4500
    assert segment.generated_duration_ms <= segment.available_duration_ms
    assert segment.attempts == 2


@pytest.mark.asyncio
async def test_tts_fit_loop_applies_deterministic_final_fit_after_max_attempts():
    synthesizer = StudioVoiceSynthesizer()

    # Mock TTS always returning over-budget valid PCM audio (e.g. 8000ms for 4000ms window)
    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        return 8000, b"\x01\x00" * (24000 * 8)

    async def mock_rewrite(text: str, max_dur_s: float, attempt: int) -> str:
        return f"Attempt {attempt} text"

    segment = await synthesizer.fit_narration_segment(
        segment_id="seg_03",
        production_id="prod_test",
        source_start_ms=0,
        source_end_ms=4000,
        available_duration_ms=4000,
        original_text="A very long sentence that never fits naturally in the window.",
        voice_id="Puck",
        tts_fn=mock_tts,
        rewrite_fn=mock_rewrite,
        max_attempts=3,
    )

    # Bounded semantic rewrites exhausted -> deterministic final-fit accepts
    assert segment.status == NarrationSegmentStatus.ACCEPTED
    assert segment.attempts == 3
    assert segment.generated_duration_ms == 4000
    assert segment.available_duration_ms == 4000
    assert segment.tempo_adjustment == 2.0


def test_fit_pcm_to_duration_resamples_cleanly():
    # 1000ms source at 24kHz = 24,000 samples = 48,000 bytes
    sample_pcm = b"\x05\x00\x10\x00" * 12_000
    # Fit into 500ms (12,000 samples = 24,000 bytes)
    fitted = fit_pcm_to_duration(
        sample_pcm,
        source_duration_ms=1000,
        target_duration_ms=500,
        sample_rate=24000,
    )
    assert len(fitted) == 24000
    assert isinstance(fitted, bytes)
    assert len(fitted) > 0

    # Empty input returns empty bytes
    assert fit_pcm_to_duration(b"", 1000, 500) == b""
    assert fit_pcm_to_duration(sample_pcm, 1000, 0) == b""

@pytest.mark.asyncio
async def test_tts_fit_loop_converts_provider_exception_to_failed_segment_without_escaping_gather():
    synthesizer = StudioVoiceSynthesizer()

    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        if text == "This provider call fails.":
            raise RuntimeError("provider unavailable")
        return 500, b"\x01\x00" * 12_000

    rewrite_fn = AsyncMock()
    failed_result, accepted_result = await asyncio.gather(
        synthesizer.fit_narration_segment_with_audio(
            segment_id="seg_provider_failure",
            production_id="prod_test",
            source_start_ms=0,
            source_end_ms=1000,
            available_duration_ms=1000,
            original_text="This provider call fails.",
            voice_id="Puck",
            tts_fn=mock_tts,
            rewrite_fn=rewrite_fn,
        ),
        synthesizer.fit_narration_segment_with_audio(
            segment_id="seg_provider_success",
            production_id="prod_test",
            source_start_ms=1000,
            source_end_ms=2000,
            available_duration_ms=1000,
            original_text="This provider call succeeds.",
            voice_id="Puck",
            tts_fn=mock_tts,
            rewrite_fn=rewrite_fn,
        ),
    )

    failed_segment, failed_audio = failed_result
    accepted_segment, accepted_audio = accepted_result
    assert failed_segment.status == NarrationSegmentStatus.FAILED
    assert failed_segment.attempts == 1
    assert failed_segment.generated_duration_ms == 0
    assert failed_segment.model_dump(include={"error_code", "error_message"}) == {
        "error_code": "TTS_PROVIDER_ERROR",
        "error_message": "RuntimeError: provider unavailable",
    }
    assert failed_audio == b""
    assert accepted_segment.status == NarrationSegmentStatus.ACCEPTED
    assert accepted_audio == b"\x01\x00" * 12_000
    rewrite_fn.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("narration_text", ["", " \t\n", "...?! —"])
async def test_tts_fit_loop_rejects_empty_or_punctuation_only_narration_without_provider_call(
    narration_text: str,
):
    synthesizer = StudioVoiceSynthesizer()
    tts_fn = AsyncMock(return_value=(500, b"\x01\x00" * 12_000))
    rewrite_fn = AsyncMock()

    segment, audio = await synthesizer.fit_narration_segment_with_audio(
        segment_id="seg_empty_narration",
        production_id="prod_test",
        source_start_ms=0,
        source_end_ms=1000,
        available_duration_ms=1000,
        original_text=narration_text,
        voice_id="Puck",
        tts_fn=tts_fn,
        rewrite_fn=rewrite_fn,
    )

    assert segment.status == NarrationSegmentStatus.FAILED
    assert segment.attempts == 0
    assert segment.generated_duration_ms == 0
    assert segment.model_dump(include={"error_code", "error_message"}) == {
        "error_code": "EMPTY_NARRATION_TEXT",
        "error_message": "Narration text contains no speakable characters",
    }
    assert audio == b""
    tts_fn.assert_not_awaited()
    rewrite_fn.assert_not_awaited()

@pytest.mark.asyncio
async def test_tts_fit_loop_with_audio_returns_pcm_bytes():
    synthesizer = StudioVoiceSynthesizer()
    expected_pcm = b"\x01\x02\x03\x04" * 100

    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        return 3500, expected_pcm

    async def mock_rewrite(text: str, max_dur_s: float, attempt: int) -> str:
        return text

    segment, pcm_bytes = await synthesizer.fit_narration_segment_with_audio(
        segment_id="seg_test_audio",
        production_id="prod_test",
        source_start_ms=0,
        source_end_ms=4000,
        available_duration_ms=4000,
        original_text="Testing audio byte persistence across the fit loop.",
        voice_id="Charon",
        tts_fn=mock_tts,
        rewrite_fn=mock_rewrite,
    )
    assert segment.status == NarrationSegmentStatus.ACCEPTED
    assert segment.generated_duration_ms == 3500
    assert pcm_bytes == expected_pcm


@pytest.mark.asyncio
async def test_fake_genai_client_synthesizes_studio_voice():
    client = FakeGenAIClient()
    dur_ms, pcm_bytes = await client.synthesize_studio_voice(
        text="Welcome back to Croviq studio voice narration test.",
        voice_id="Puck",
        production_id="prod_fake_1",
    )
    assert dur_ms > 0
    assert len(pcm_bytes) == dur_ms * 48
    assert len(client.call_history) == 1
    assert client.call_history[0]["method"] == "synthesize_studio_voice"
    assert client.call_history[0]["voice_id"] == "Puck"


@pytest.mark.asyncio
async def test_google_genai_client_synthesize_studio_voice_targets_gemini_31_tts():
    google_client = GoogleGenAIClient(project_id="test-proj", location="global")
    mock_raw_client = MagicMock()
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    # 24000 samples * 2 bytes * 2 seconds = 96000 bytes
    fake_audio_pcm = b"\x00" * 96000
    mock_part.inline_data.data = fake_audio_pcm
    mock_candidate.content.parts = [mock_part]
    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    mock_raw_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    google_client._client = mock_raw_client

    with patch("croviq_agents.client.log_ai_event") as mock_log:
        dur_ms, pcm_bytes = await google_client.synthesize_studio_voice(
            text="Narration test",
            voice_id="Aoede",
            production_id="prod_live_test",
            request_id="req_123",
        )
        assert dur_ms == 2000
        assert pcm_bytes == fake_audio_pcm

        # Verify direct call parameters to generate_content
        mock_raw_client.aio.models.generate_content.assert_awaited_once()
        call_kwargs = mock_raw_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-3.1-flash-tts-preview"
        assert call_kwargs["contents"] == "Narration test"
        config = call_kwargs["config"]
        assert config.response_modalities == ["AUDIO"]
        assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == "Aoede"

        # Verify first-party telemetry events logged
        assert mock_log.call_count == 2
        start_call = mock_log.call_args_list[0].kwargs
        assert start_call["model"] == "gemini-3.1-flash-tts-preview"
        assert start_call["status"] == "started"
        completed_call = mock_log.call_args_list[1].kwargs
        assert completed_call["model"] == "gemini-3.1-flash-tts-preview"
        assert completed_call["status"] == "success"
        assert completed_call["audio_duration_ms"] == 2000


def _google_tts_response(audio_data: bytes | str) -> MagicMock:
    part = MagicMock()
    part.inline_data.data = audio_data
    candidate = MagicMock()
    candidate.content.parts = [part]
    response = MagicMock()
    response.candidates = [candidate]
    return response


@pytest.mark.asyncio
async def test_google_genai_client_synthesize_studio_voice_decodes_base64_inline_data():
    google_client = GoogleGenAIClient(project_id="test-proj", location="global")
    expected_pcm = b"\x01\x00" * 24_000
    mock_raw_client = MagicMock()
    mock_raw_client.aio.models.generate_content = AsyncMock(
        return_value=_google_tts_response(base64.b64encode(expected_pcm).decode("ascii"))
    )
    google_client._client = mock_raw_client

    with patch("croviq_agents.client.log_ai_event"):
        duration_ms, pcm_bytes = await google_client.synthesize_studio_voice(
            text="Base64 narration",
            voice_id="Aoede",
            production_id="prod_base64",
        )

    assert pcm_bytes == expected_pcm
    assert duration_ms == 1000


@pytest.mark.asyncio
async def test_google_genai_client_synthesize_studio_voice_strips_riff_wav_container_to_pcm():
    google_client = GoogleGenAIClient(project_id="test-proj", location="global")
    expected_pcm = b"\x01\x00" * 24_000
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24_000)
        wav_file.writeframes(expected_pcm)

    mock_raw_client = MagicMock()
    mock_raw_client.aio.models.generate_content = AsyncMock(
        return_value=_google_tts_response(wav_buffer.getvalue())
    )
    google_client._client = mock_raw_client

    with patch("croviq_agents.client.log_ai_event"):
        duration_ms, pcm_bytes = await google_client.synthesize_studio_voice(
            text="WAV narration",
            voice_id="Aoede",
            production_id="prod_wav",
        )

    assert pcm_bytes == expected_pcm
    assert not pcm_bytes.startswith(b"RIFF")
    assert len(pcm_bytes) == 24_000 * 2
    assert duration_ms == 1000
def test_voice_replication_capability_blocked_when_not_allowlisted():
    service = VoiceReplicationService(allowlist_enabled=False)
    config = service.check_replication_capability()
    assert config.status == VoiceReplicationStatus.BLOCKED
    assert config.blocked_reason == "Google allowlist access required"
    assert "Request Gemini-TTS Voice Replication allowlist" in (config.suggested_action or "")


def test_voice_replication_consent_verification():
    service = VoiceReplicationService(allowlist_enabled=True)
    assert service.verify_consent_phrase(GOOGLE_VOICE_CONSENT_PHRASE_EN) is True
    assert service.verify_consent_phrase("I am the owner of this voice and have consented to synthetic model.") is True
    assert service.verify_consent_phrase("Random speech without consent") is False


def test_voice_replication_key_expiry_handling():
    service = VoiceReplicationService(allowlist_enabled=True)
    config, key_id = service.create_replicated_voice_key(b"sample_wav", b"consent_wav")
    assert config.status == VoiceReplicationStatus.AVAILABLE
    assert key_id is not None
    assert config.key_expires_at is not None
    assert service.is_key_expired(config) is False


def test_find_candidate_voice_sample_interval():
    words = [
        TranscriptWord(index=i, text=f"word{i}", start_ms=i * 500, end_ms=(i * 500) + 400, confidence=0.99)
        for i in range(40) # 0 to 20,000ms
    ]
    tr = Transcript(
        transcript_id="tr_01",
        production_id="prod_01",
        language_code="en",
        duration_ms=20000,
        created_at=datetime.now(timezone.utc),
        segments=[
            TranscriptSegment(
                segment_id="seg_01",
                start_ms=0,
                end_ms=20000,
                text=" ".join(w.text for w in words),
                word_start_index=0,
                word_end_index=len(words) - 1,
            )
        ],
        words=words,
    )
    start_ms, end_ms = find_candidate_voice_sample_interval(tr, min_duration_ms=10000, max_duration_ms=20000)
    assert end_ms - start_ms >= 10000
    assert end_ms - start_ms <= 20000
