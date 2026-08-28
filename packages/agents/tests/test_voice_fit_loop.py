"""Tests for Studio Voice TTS fit loop, hard duration budgets, and retry logic."""

from datetime import datetime, timezone
import pytest

from croviq_agents.voice import (
    StudioVoiceSynthesizer,
    VoiceCatalog,
    VoiceFitAttempt,
    VoiceReplicationService,
    find_candidate_voice_sample_interval,
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
async def test_tts_fit_loop_fails_gracefully_after_max_attempts():
    synthesizer = StudioVoiceSynthesizer()

    # Mock TTS always returning over-budget audio (e.g. 8000ms for 4000ms window)
    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        return 8000, b"too_long_audio"

    async def mock_rewrite(text: str, max_dur_s: float, attempt: int) -> str:
        return f"Attempt {attempt} text"

    segment = await synthesizer.fit_narration_segment(
        segment_id="seg_03",
        production_id="prod_test",
        source_start_ms=0,
        source_end_ms=4000,
        available_duration_ms=4000,
        original_text="A very long sentence that never fits in the window.",
        voice_id="Puck",
        tts_fn=mock_tts,
        rewrite_fn=mock_rewrite,
        max_attempts=3,
    )

    assert segment.status == NarrationSegmentStatus.FAILED
    assert segment.attempts == 3
    # Hard timing rule: Never lengthen video!
    assert segment.available_duration_ms == 4000
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
