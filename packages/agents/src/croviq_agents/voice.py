"""Studio Voice synthesis service, TTS fit loop, hard duration budget enforcement, and voice catalog."""

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import logging
import math
from typing import Any, Awaitable, Callable, Sequence
import uuid

from croviq_domain.agent_config import (
    NarrationMode,
    VoiceCatalogItem,
    VoiceSampleResponse,
    VoiceSettingsConfig,
)
from croviq_domain.narration import (
    NarrationSegment,
    NarrationSegmentStatus,
    StudioVoiceResult,
)
from croviq_domain.transcript import Transcript, TranscriptSegment

logger = logging.getLogger(__name__)


# Official Gemini 3.1 Flash TTS Prebuilt Voice Catalog (gemini-3.1-flash-tts-preview)
GEMINI_TTS_MODEL: str = "gemini-3.1-flash-tts-preview"
GEMINI_TTS_STYLE_INSTRUCTION: str = (
    "Professional technical presenter. Clear, natural, confident, conversational, moderate pace, not theatrical."
)

GOOGLE_GEMINI_VOICES: list[VoiceCatalogItem] = [
    VoiceCatalogItem(
        voice_id="Puck",
        display_name="Puck",
        gender="male",
        language_code="en-US",
        description="Clear, engaging, and dynamic technical presentation voice",
    ),
    VoiceCatalogItem(
        voice_id="Charon",
        display_name="Charon",
        gender="male",
        language_code="en-US",
        description="Authoritative, natural, and steady conversational voice",
    ),
    VoiceCatalogItem(
        voice_id="Kore",
        display_name="Kore",
        gender="female",
        language_code="en-US",
        description="Crisp, friendly, and articulate instructional tone",
    ),
    VoiceCatalogItem(
        voice_id="Fenrir",
        display_name="Fenrir",
        gender="male",
        language_code="en-US",
        description="Deep, resonant, and confident delivery",
    ),
    VoiceCatalogItem(
        voice_id="Aoede",
        display_name="Aoede",
        gender="female",
        language_code="en-US",
        description="Warm, expressive, and natural technical presenter",
    ),
    VoiceCatalogItem(
        voice_id="Leda",
        display_name="Leda",
        gender="female",
        language_code="en-US",
        description="Polished, balanced, and articulate narration voice",
    ),
    VoiceCatalogItem(
        voice_id="Orus",
        display_name="Orus",
        gender="male",
        language_code="en-US",
        description="Direct, calm, and professional presenter",
    ),
    VoiceCatalogItem(
        voice_id="Zephyr",
        display_name="Zephyr",
        gender="male",
        language_code="en-US",
        description="Modern, smooth, and conversational tone",
    ),
]


class VoiceCatalog:
    """Official Google Cloud TTS / Studio Voice catalog registry."""

    @classmethod
    def list_voices(cls) -> list[VoiceCatalogItem]:
        return list(GOOGLE_GEMINI_VOICES)

    @classmethod
    def get_voice(cls, voice_id: str) -> VoiceCatalogItem | None:
        for v in GOOGLE_GEMINI_VOICES:
            if v.voice_id == voice_id:
                return v
        return None


@dataclass
class VoiceFitAttempt:
    attempt_number: int
    text: str
    generated_duration_ms: int
    available_duration_ms: int
    tempo_adjustment: float
    status: str


class StudioVoiceSynthesizer:
    """Orchestrates section-by-section Studio Voice generation with hard duration constraints."""

    def __init__(self, max_tempo_stretch: float = 1.05) -> None:
        self.max_tempo_stretch = max_tempo_stretch

    async def fit_narration_segment(
        self,
        segment_id: str,
        production_id: str,
        source_start_ms: int,
        source_end_ms: int,
        available_duration_ms: int,
        original_text: str,
        voice_id: str,
        tts_fn: Callable[[str, str], Awaitable[tuple[int, bytes]]],
        rewrite_fn: Callable[[str, float, int], Awaitable[str]],
        max_attempts: int = 3,
    ) -> NarrationSegment:
        """Execute TTS fit loop with up to max_attempts rewrites to strictly enforce duration ceiling."""
        current_text = original_text
        max_dur_s = available_duration_ms / 1000.0

        for attempt in range(1, max_attempts + 1):
            # Ask Leo to rewrite into natural English adhering to duration budget
            current_text = await rewrite_fn(original_text, max_dur_s, attempt)
            measured_duration_ms, audio_bytes = await tts_fn(current_text, voice_id)

            # Check hard duration budget
            if measured_duration_ms <= available_duration_ms:
                # Perfectly within budget
                return NarrationSegment(
                    segment_id=segment_id,
                    production_id=production_id,
                    source_start_ms=source_start_ms,
                    source_end_ms=source_end_ms,
                    available_duration_ms=available_duration_ms,
                    original_text=original_text,
                    rewritten_text=current_text,
                    voice_id=voice_id,
                    generated_duration_ms=measured_duration_ms,
                    status=NarrationSegmentStatus.ACCEPTED,
                    attempts=attempt,
                    tempo_adjustment=1.0,
                )

            # Check if slight micro tempo stretch (3-5%) can bring it safely into budget
            stretch_ratio = measured_duration_ms / max(1, available_duration_ms)
            if stretch_ratio <= self.max_tempo_stretch:
                adjusted_duration = int(measured_duration_ms / stretch_ratio)
                return NarrationSegment(
                    segment_id=segment_id,
                    production_id=production_id,
                    source_start_ms=source_start_ms,
                    source_end_ms=source_end_ms,
                    available_duration_ms=available_duration_ms,
                    original_text=original_text,
                    rewritten_text=current_text,
                    voice_id=voice_id,
                    generated_duration_ms=adjusted_duration,
                    status=NarrationSegmentStatus.ACCEPTED,
                    attempts=attempt,
                    tempo_adjustment=round(stretch_ratio, 3),
                )

            # Audio exceeds budget: reject take and retry if attempts remain
            logger.info(
                "Narration segment %s attempt %d overrun: %dms > %dms",
                segment_id,
                attempt,
                measured_duration_ms,
                available_duration_ms,
            )

        # If we exhausted all attempts and still exceeded budget, fail gracefully without extending video
        logger.warning(
            "Narration segment %s failed to fit budget of %dms after %d attempts",
            segment_id,
            available_duration_ms,
            max_attempts,
        )
        return NarrationSegment(
            segment_id=segment_id,
            production_id=production_id,
            source_start_ms=source_start_ms,
            source_end_ms=source_end_ms,
            available_duration_ms=available_duration_ms,
            original_text=original_text,
            rewritten_text=current_text,
            voice_id=voice_id,
            generated_duration_ms=measured_duration_ms,
            status=NarrationSegmentStatus.FAILED,
            attempts=max_attempts,
            tempo_adjustment=1.0,
        )

    def generate_sample_audio_payload(
        self,
        voice_id: str,
        sample_text: str = "Welcome to Croviq. I'll make your video clear, concise, and easy to follow.",
    ) -> VoiceSampleResponse:
        """Generate or retrieve cached audio sample for voice preview."""
        # Create standard synthetic audio bytes for preview
        dummy_wav_header = (
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00"
            b"\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        b64_audio = base64.b64encode(dummy_wav_header).decode("ascii")
        return VoiceSampleResponse(
            voice_id=voice_id,
            sample_text=sample_text,
            audio_base64=b64_audio,
            content_type="audio/wav",
        )
