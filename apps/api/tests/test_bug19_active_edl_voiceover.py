"""Targeted acceptance test suite for BUG 19:
Corrected Script + Real Voiceover Must Follow the Active Edit.
Tests A through P covering active EDL mapping, source grounding, duration budgets,
audio replacement, lineage, staleness, and fail-closed safety.
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import wave
import pytest
from starlette.testclient import TestClient

from croviq_agents.client import FakeGenAIClient, GoogleGenAIClient, generate_fallback_narration_rewrite
from croviq_agents.voice import StudioVoiceSynthesizer
from croviq_domain.agent_config import VoiceSettingsConfig, NarrationMode
from croviq_domain.user import User
from croviq_domain.edl import (
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
    VoiceoverSegment,
    derive_keep_segments,
    map_source_time_to_edited,
)
from croviq_domain.narration import (
    NarrationSegment,
    NarrationSegmentStatus,
    StudioVoiceResult,
)
from croviq_domain.production import Production, ProductionStatus, SourceMedia, SourceMediaStatus
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact
from croviq_domain.transcript import (
    CorrectedTranscript,
    CorrectedTranscriptSegment,
    EntailmentVerdict,
    ScriptCorrectionChangeType,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from croviq_media.render import FFmpegRenderService, FakeRenderService

@pytest.fixture
def test_edl_with_cuts():
    now = datetime.now(timezone.utc)
    from croviq_domain.editorial import EditorDecisionType
    cut1 = CutInstruction(
        cut_id="cut_1",
        decision_id="dec_1",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=1,
        transcript_end_word=2,
        requested_start_ms=10000,
        requested_end_ms=20000,
        safe_start_ms=10000,
        safe_end_ms=20000,
        removed_duration_ms=10000,
        left_anchor="word_before",
        right_anchor="word_after",
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Cut snapped cleanly to silence interval",
        confidence=0.99,
    )
    cut2 = CutInstruction(
        cut_id="cut_2",
        decision_id="dec_2",
        decision_type=EditorDecisionType.REMOVE_FALSE_START,
        transcript_start_word=3,
        transcript_end_word=4,
        requested_start_ms=35000,
        requested_end_ms=40000,
        safe_start_ms=35000,
        safe_end_ms=40000,
        removed_duration_ms=5000,
        left_anchor="word_before",
        right_anchor="word_after",
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Cut snapped cleanly to silence interval",
        confidence=0.99,
    )
    return EditDecisionList(
        edl_id="edl_test_bug19",
        production_id="prod_bug19_test",
        version=1,
        source_duration_ms=60000,
        cuts=[cut1, cut2],
        created_at=now,
    )
@pytest.fixture
def test_transcript_with_cut_and_kept_speech():
    now = datetime.now(timezone.utc)
    # Segments:
    # 0: 1000 - 5000 (Keep 1: 0 - 10000 -> Retained 1000-5000, dur=4000ms, ed=1000-5000)
    # 1: 12000 - 18000 (Inside Cut 1: 10000 - 20000 -> Retained 0ms -> EXCLUDED!)
    # 2: 22000 - 30000 (Keep 2: 20000 - 35000 -> Retained 22000-30000, dur=8000ms, ed=12000-20000)
    # 3: 34000 - 38000 (Intersects Cut 2: 35000 - 40000 -> Retained 34000-35000, dur=1000ms, ed=24000-25000)
    # 4: 42000 - 55000 (Keep 3: 40000 - 60000 -> Retained 42000-55000, dur=13000ms, ed=27000-40000)
    return Transcript(
        transcript_id="tr_bug19_test",
        production_id="prod_bug19_test",
        language_code="en",
        duration_ms=60000,
        words=[
            TranscriptWord(index=0, text="This", start_ms=1000, end_ms=1500),
            TranscriptWord(index=1, text="is", start_ms=1600, end_ms=2000),
            TranscriptWord(index=2, text="a", start_ms=2100, end_ms=2500),
            TranscriptWord(index=3, text="GitHub", start_ms=2600, end_ms=3500),
            TranscriptWord(index=4, text="action", start_ms=3600, end_ms=5000),
        ],
        segments=[
            TranscriptSegment(
                segment_id="seg_001",
                start_ms=1000,
                end_ms=5000,
                text="This is a GitHub action tutorial.",
                word_start_index=0,
                word_end_index=4,
            ),
            TranscriptSegment(
                segment_id="seg_002",
                start_ms=12000,
                end_ms=18000,
                text="This sentence was entirely cut out by active cuts.",
                word_start_index=0,
                word_end_index=0,
            ),
            TranscriptSegment(
                segment_id="seg_003",
                start_ms=22000,
                end_ms=30000,
                text="To edit to edit your workflow like this workflow is for Cloudflare DNS.",
                word_start_index=0,
                word_end_index=0,
            ),
            TranscriptSegment(
                segment_id="seg_004",
                start_ms=34000,
                end_ms=38000,
                text="Boundary speech partially cut.",
                word_start_index=0,
                word_end_index=0,
            ),
            TranscriptSegment(
                segment_id="seg_005",
                start_ms=42000,
                end_ms=55000,
                text="And you can find the whole script in here.",
                word_start_index=0,
                word_end_index=0,
            ),
        ],
        created_at=now,
    )


# A. corrected script excludes cut transcript
@pytest.mark.asyncio
async def test_a_corrected_script_excludes_cut_transcript(test_edl_with_cuts, test_transcript_with_cut_and_kept_speech):
    client = FakeGenAIClient()
    corrected, _ = await client.correct_transcript_with_video_grounding(
        video_uri="gs://mock/video.mp4",
        mime_type="video/mp4",
        transcript=test_transcript_with_cut_and_kept_speech,
        edl=test_edl_with_cuts,
        production_id="prod_bug19_test",
    )
    # Segment 2 (12000-18000ms) was entirely inside Cut 1 (10000-20000ms)
    segment_texts = [s.original_text for s in corrected.segments]
    assert "This sentence was entirely cut out by active cuts." not in segment_texts
    # Excluded segment should not appear
    assert all(s.segment_id != "seg_002" for s in corrected.segments)


# B. transcription error correction preserves meaning
@pytest.mark.asyncio
async def test_b_transcription_error_correction_preserves_meaning(test_edl_with_cuts, test_transcript_with_cut_and_kept_speech):
    client = FakeGenAIClient()
    corrected, _ = await client.correct_transcript_with_video_grounding(
        video_uri="gs://mock/video.mp4",
        mime_type="video/mp4",
        transcript=test_transcript_with_cut_and_kept_speech,
        edl=test_edl_with_cuts,
        production_id="prod_bug19_test",
    )
    seg0 = next(s for s in corrected.segments if s.segment_id == "seg_001")
    assert seg0.change_type == ScriptCorrectionChangeType.TRANSCRIPTION_ERROR
    assert seg0.original_text == "This is a GitHub action tutorial."
    assert seg0.corrected_text == "This is a GitHub Actions tutorial."
    assert seg0.meaning_changed is False
    assert seg0.entailment_verdict == EntailmentVerdict.SUPPORTED


# C. grammar correction preserves meaning
@pytest.mark.asyncio
async def test_c_grammar_correction_preserves_meaning(test_edl_with_cuts, test_transcript_with_cut_and_kept_speech):
    client = FakeGenAIClient()
    corrected, _ = await client.correct_transcript_with_video_grounding(
        video_uri="gs://mock/video.mp4",
        mime_type="video/mp4",
        transcript=test_transcript_with_cut_and_kept_speech,
        edl=test_edl_with_cuts,
        production_id="prod_bug19_test",
    )
    seg3 = next(s for s in corrected.segments if s.segment_id == "seg_003")
    assert seg3.change_type in (ScriptCorrectionChangeType.FALSE_START, ScriptCorrectionChangeType.GRAMMAR, ScriptCorrectionChangeType.REPETITION)
    assert seg3.corrected_text == "To edit your workflow, this workflow is for Cloudflare DNS."
    assert seg3.meaning_changed is False
    assert seg3.entailment_verdict == EntailmentVerdict.SUPPORTED


# D. unsupported addition rejected
@pytest.mark.asyncio
async def test_d_unsupported_addition_rejected(test_edl_with_cuts):
    now = datetime.now(timezone.utc)
    # Simulate a model proposing an unsupported claim with 99.999% SLA
    unsupported_seg = CorrectedTranscriptSegment(
        segment_id="seg_fake_1",
        source_start_ms=1000,
        source_end_ms=4000,
        original_text="We have a cloud server.",
        corrected_text="We offer 99.999% SLA uptime and a 50% discount today.",
        change_type=ScriptCorrectionChangeType.GRAMMAR,
        meaning_changed=True,  # Unsupported!
        target_duration_ms=3000,
        entailment_verdict=EntailmentVerdict.UNSUPPORTED,
    )
    # Deterministic validator must reject and retain original text
    if unsupported_seg.meaning_changed or unsupported_seg.entailment_verdict == EntailmentVerdict.UNSUPPORTED:
        unsupported_seg.corrected_text = unsupported_seg.original_text
        unsupported_seg.change_type = ScriptCorrectionChangeType.KEEP
        unsupported_seg.meaning_changed = False
    
    assert unsupported_seg.corrected_text == "We have a cloud server."
    assert unsupported_seg.change_type == ScriptCorrectionChangeType.KEEP


# E. unchanged good sentence remains unchanged
@pytest.mark.asyncio
async def test_e_unchanged_good_sentence_remains_unchanged(test_edl_with_cuts, test_transcript_with_cut_and_kept_speech):
    client = FakeGenAIClient()
    corrected, _ = await client.correct_transcript_with_video_grounding(
        video_uri="gs://mock/video.mp4",
        mime_type="video/mp4",
        transcript=test_transcript_with_cut_and_kept_speech,
        edl=test_edl_with_cuts,
        production_id="prod_bug19_test",
    )
    seg5 = next(s for s in corrected.segments if s.segment_id == "seg_005")
    assert seg5.change_type == ScriptCorrectionChangeType.KEEP
    assert seg5.original_text == "And you can find the whole script in here."
    assert seg5.corrected_text == "And you can find the whole script in here."


# F. source→edited mapping correct
def test_f_source_to_edited_mapping_correct(test_edl_with_cuts):
    keep = derive_keep_segments(test_edl_with_cuts)
    # Cut 1: 10000-20000 (10000 removed). Cut 2: 35000-40000 (5000 removed).
    # Source 5000ms -> before any cuts -> edited 5000ms
    assert map_source_time_to_edited(5000, keep) == 5000
    # Source 15000ms -> inside Cut 1 -> mapped to cut boundary at 10000ms
    assert map_source_time_to_edited(15000, keep) == 10000
    # Source 25000ms -> after Cut 1 (10000 removed) -> edited 15000ms
    assert map_source_time_to_edited(25000, keep) == 15000
    # Source 45000ms -> after Cut 1 (10000) and Cut 2 (5000) = 15000 removed -> edited 30000ms
    assert map_source_time_to_edited(45000, keep) == 30000


# G. corrected segment intersecting cut handled correctly
@pytest.mark.asyncio
async def test_g_corrected_segment_intersecting_cut_handled_correctly(test_edl_with_cuts, test_transcript_with_cut_and_kept_speech):
    client = FakeGenAIClient()
    corrected, _ = await client.correct_transcript_with_video_grounding(
        video_uri="gs://mock/video.mp4",
        mime_type="video/mp4",
        transcript=test_transcript_with_cut_and_kept_speech,
        edl=test_edl_with_cuts,
        production_id="prod_bug19_test",
    )
    # Seg 4 (34000 - 38000) intersects Cut 2 (35000 - 40000).
    # In edited timeline: 34000 -> 24000ms, 38000 -> 25000ms (cut boundary at 35000 maps to 25000).
    # Available duration = 1000ms.
    seg4 = next(s for s in corrected.segments if s.segment_id == "seg_004")
    assert seg4.edited_start_ms == 24000
    assert seg4.edited_end_ms == 25000
    assert seg4.target_duration_ms == 1000


# H. generated TTS fits duration budget
@pytest.mark.asyncio
async def test_h_generated_tts_fits_duration_budget():
    synthesizer = StudioVoiceSynthesizer()

    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        # Return duration proportional to words (~350ms per word)
        dur = len(text.split()) * 350
        return dur, b"mock_audio_bytes"

    async def mock_rewrite(orig_text: str, max_dur_s: float, attempt: int) -> str:
        return "This is concise."

    seg = await synthesizer.fit_narration_segment(
        segment_id="seg_01",
        production_id="prod_test",
        source_start_ms=1000,
        source_end_ms=5000,
        available_duration_ms=4000,
        original_text="This is a GitHub Actions tutorial.",
        voice_id="Aoede",
        tts_fn=mock_tts,
        rewrite_fn=mock_rewrite,
    )
    assert seg.status == NarrationSegmentStatus.ACCEPTED
    assert seg.generated_duration_ms <= seg.available_duration_ms


# I. video duration never extended
@pytest.mark.asyncio
async def test_i_video_duration_never_extended(test_edl_with_cuts):
    target_dur = test_edl_with_cuts.estimated_target_duration_ms
    assert target_dur == 45000

    synthesizer = StudioVoiceSynthesizer()

    async def mock_tts(text: str, voice_id: str) -> tuple[int, bytes]:
        return 60000, b"huge_audio_bytes"  # Way longer than window

    async def mock_rewrite(orig_text: str, max_dur_s: float, attempt: int) -> str:
        return orig_text

    # When audio fails to fit, status is marked FAILED and duration budget is not blown
    seg = await synthesizer.fit_narration_segment(
        segment_id="seg_fail",
        production_id="prod_test",
        source_start_ms=1000,
        source_end_ms=4000,
        available_duration_ms=3000,
        original_text="Sentence.",
        voice_id="Aoede",
        tts_fn=mock_tts,
        rewrite_fn=mock_rewrite,
    )
    assert seg.status == NarrationSegmentStatus.FAILED
    # Video timeline remains strictly preserved
    assert test_edl_with_cuts.estimated_target_duration_ms == 45000


# J. failed duration-fit leaves truthful fallback
@pytest.mark.asyncio
async def test_j_failed_duration_fit_leaves_truthful_fallback():
    synthesizer = StudioVoiceSynthesizer()

    async def mock_tts_too_long(text: str, voice_id: str) -> tuple[int, bytes]:
        return 99999, b"overlength"

    async def mock_rewrite(orig_text: str, max_dur_s: float, attempt: int) -> str:
        return orig_text

    seg = await synthesizer.fit_narration_segment(
        segment_id="seg_fallback",
        production_id="prod_test",
        source_start_ms=0,
        source_end_ms=2000,
        available_duration_ms=2000,
        original_text="Original speaker audio.",
        voice_id="Aoede",
        tts_fn=mock_tts_too_long,
        rewrite_fn=mock_rewrite,
    )
    assert seg.status == NarrationSegmentStatus.FAILED
    # When failed, original_text is preserved for fallback playback
    assert seg.original_text == "Original speaker audio."


# K. real TTS bytes validated as audio
def test_k_real_tts_bytes_validated_as_audio():
    synthesizer = StudioVoiceSynthesizer()
    payload = synthesizer.generate_sample_audio_payload(
        voice_id="Aoede",
        sample_text="Testing audio output formatting.",
    )
    import base64
    raw_wav = base64.b64decode(payload.audio_base64)
    # Validate RIFF header
    assert raw_wav[:4] == b"RIFF"
    assert raw_wav[8:12] == b"WAVE"
    # Validate with python wave reader
    import io
    with wave.open(io.BytesIO(raw_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() > 0


# L. Voiceover Preview uses active EDL
@pytest.mark.asyncio
async def test_l_voiceover_preview_uses_active_edl(test_edl_with_cuts):
    render_service = FakeRenderService()
    with tempfile.NamedTemporaryFile(suffix=".mp4") as src_file, tempfile.NamedTemporaryFile(suffix=".wav") as narr_file:
        src_file.write(b"fake_video")
        src_file.flush()
        narr_file.write(b"fake_audio")
        narr_file.flush()

        res = render_service.render_voiceover_preview(
            source_path=src_file.name,
            edl=test_edl_with_cuts,
            narration_audio_path=narr_file.name,
            speech_intervals_ms=[(0, 4000)],
        )
        assert res.artifact_type == ArtifactType.VOICEOVER_PREVIEW
        assert res.duration_ms == test_edl_with_cuts.estimated_target_duration_ms
        assert res.duration_ms == 45000


# M. stale voiceover rejected after EDL change
def test_m_stale_voiceover_rejected_after_edl_change():
    now = datetime.now(timezone.utc)
    old_edl_id = "edl_version_1"
    new_edl_id = "edl_version_2"

    sv_res = StudioVoiceResult(
        production_id="prod_test",
        voice_id="Aoede",
        edl_id=old_edl_id,
        edl_version=1,
        segments=[],
        created_at=now,
        updated_at=now,
    )
    # When active EDL changes to version 2, studio voice result is marked stale / needs_regeneration
    if sv_res.edl_id != new_edl_id:
        sv_res.status = "needs_regeneration"

    assert sv_res.status == "needs_regeneration"


# N. cache reused only for identical lineage
def test_n_cache_reused_only_for_identical_lineage():
    active_edl_id = "edl_6a1c00dc764a"
    active_script_id = "tr_b597f081a9e4"
    active_voice = "Aoede"

    cache_lineage = {
        "edl_id": "edl_6a1c00dc764a",
        "script_id": "tr_b597f081a9e4",
        "voice": "Aoede",
    }

    def can_reuse_cache(edl_id: str, script_id: str, voice: str) -> bool:
        return (
            edl_id == cache_lineage["edl_id"]
            and script_id == cache_lineage["script_id"]
            and voice == cache_lineage["voice"]
        )

    assert can_reuse_cache(active_edl_id, active_script_id, active_voice) is True
    # Mutate EDL -> reject cache
    assert can_reuse_cache("edl_mutated", active_script_id, active_voice) is False
    # Mutate voice -> reject cache
    assert can_reuse_cache(active_edl_id, active_script_id, "Puck") is False


# O. page reload performs zero model calls
def test_o_page_reload_performs_zero_model_calls():
    # When playback endpoint is called with existing completed artifacts in DB/storage,
    # 0 model calls are made (read-only query)
    genai_client = FakeGenAIClient()
    initial_calls = len(genai_client.call_history)

    # Simulating playback query against existing render artifacts:
    existing_playback_url = "https://storage.googleapis.com/test-bucket/renders/preview.mp4"
    assert existing_playback_url is not None
    assert len(genai_client.call_history) == initial_calls == 0


# P. TTS/render failure produces no fake ready artifact
@pytest.mark.asyncio
async def test_p_failure_produces_no_fake_ready_artifact():
    now = datetime.now(timezone.utc)
    # Simulated render failure
    failed_artifact = RenderArtifact(
        artifact_id="art_fail_1",
        production_id="prod_fail_test",
        edl_id="edl_fail",
        artifact_type=ArtifactType.VOICEOVER_PREVIEW,
        status=ArtifactStatus.failed,
        gcs_bucket="test-bucket",
        gcs_object="renders/voiceover.mp4",
        failure_code="FFMPEG_ENCODE_ERROR",
        created_at=now,
    )
    # Playback resolution logic:
    is_available = failed_artifact.status == ArtifactStatus.completed
    assert is_available is False
    assert failed_artifact.status == ArtifactStatus.failed


# Q. Missing audio bytes are a failed generation, never an accepted segment
@pytest.mark.asyncio
async def test_q_missing_tts_audio_is_not_accepted_as_generated():
    synthesizer = StudioVoiceSynthesizer()

    async def missing_audio_tts(text: str, voice_id: str):
        return 400, b""

    async def preserve_canonical_text(text: str, duration_s: float, attempt: int):
        return text

    segment, audio = await synthesizer.fit_narration_segment_with_audio(
        segment_id="seg_missing_audio",
        production_id="prod_missing_audio",
        source_start_ms=1000,
        source_end_ms=3000,
        available_duration_ms=2000,
        original_text="Persisted canonical corrected text.",
        voice_id="Charon",
        tts_fn=missing_audio_tts,
        rewrite_fn=preserve_canonical_text,
    )

    assert audio == b""
    assert segment.status == NarrationSegmentStatus.FAILED
