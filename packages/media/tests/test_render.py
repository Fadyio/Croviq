"""Unit and synthetic media tests for RenderService and FFmpegRenderService."""

from array import array
from datetime import datetime, timezone
import math
from pathlib import Path
import subprocess

import pytest

from croviq_domain.editorial import EditorDecisionType
from croviq_domain.edl import (
    CoverageMarker,
    CoverageType,
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
)
from croviq_domain.render import ArtifactType
from croviq_domain.transcript import Transcript, TranscriptWord
from croviq_media.render import (
    FakeRenderService,
    FFmpegRenderService,
    RenderError,
    RenderExecutionResult,
)


def _create_synthetic_video(target_path: Path, duration_sec: int = 5, size: str = "640x360") -> Path:
    """Helper to generate a synthetic test video (H.264/AAC) with visual test patterns and audio tone."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_sec}:size={size}:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_sec}",
        "-shortest",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(target_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        pytest.skip(f"ffmpeg not available for synthetic video creation: {res.stderr}")
    return target_path


def _create_sine_audio(
    target_path: Path,
    *,
    frequency_hz: int,
    duration_sec: float,
) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency_hz}:duration={duration_sec}",
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(target_path),
        ],
        check=True,
    )
    return target_path


def _decode_mono_audio(media_path: Path, sample_rate: int = 48000) -> array:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(media_path),
            "-vn",
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    samples = array("h")
    samples.frombytes(result.stdout)
    return samples


def _tone_amplitude(
    samples: array,
    frequency_hz: int,
    sample_rate: int = 48000,
) -> float:
    """Measure a steady tone in 100ms windows without depending on AAC phase."""
    window_size = sample_rate // 10
    coefficient = 2.0 * math.cos(2.0 * math.pi * frequency_hz / sample_rate)
    amplitudes: list[float] = []

    for start in range(0, len(samples) - window_size + 1, window_size):
        previous = 0.0
        previous_previous = 0.0
        for index in range(start, start + window_size):
            current = samples[index] + coefficient * previous - previous_previous
            previous_previous = previous
            previous = current
        power = max(
            0.0,
            previous_previous**2 + previous**2 - coefficient * previous * previous_previous,
        )
        amplitudes.append(2.0 * math.sqrt(power) / window_size / 32768.0)

    assert amplitudes, "decoded audio is too short to analyze"
    return sum(amplitudes) / len(amplitudes)


def _rms_amplitude(
    samples: array,
    start_sec: float,
    end_sec: float,
    sample_rate: int = 48000,
) -> float:
    start = int(start_sec * sample_rate)
    end = min(int(end_sec * sample_rate), len(samples))
    assert end > start, "requested audio interval is unavailable"
    mean_square = sum(samples[index] ** 2 for index in range(start, end)) / (end - start)
    return math.sqrt(mean_square) / 32768.0


@pytest.fixture
def synthetic_5s_video(tmp_path: Path) -> Path:
    video_path = tmp_path / "source_5s.mp4"
    return _create_synthetic_video(video_path, duration_sec=5)

@pytest.fixture
def synthetic_vertical_5s_video(tmp_path: Path) -> Path:
    video_path = tmp_path / "source_vert_5s.mp4"
    return _create_synthetic_video(video_path, duration_sec=5, size="360x640")



def test_zero_cut_preview_render(synthetic_5s_video: Path, tmp_path: Path):
    renderer = FFmpegRenderService()
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_zero",
        production_id="prod_test",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[
            CoverageMarker(
                marker_id="cov_001",
                decision_id="dec_001",
                source_start_ms=1000,
                source_end_ms=2000,
                coverage_type=CoverageType.SOURCE_SCREEN,
                reason="Screen coverage over test",
            )
        ],
        created_at=now,
    )

    out_path = tmp_path / "preview.mp4"
    result = renderer.render_preview(source_path=synthetic_5s_video, edl=edl, output_path=out_path)

    assert result.output_path.exists()
    assert result.output_path == out_path
    assert result.size_bytes > 0
    assert abs(result.duration_ms - 5000) <= 200  # Within 200ms tolerance
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
    assert result.width == 640
    assert result.height == 360
    assert result.frame_rate == pytest.approx(30.0, abs=1.0)
    assert result.render_time_ms > 0


def test_zero_cut_master_render(synthetic_5s_video: Path, tmp_path: Path):
    renderer = FFmpegRenderService()
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_zero_master",
        production_id="prod_test",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )

    out_path = tmp_path / "master.mp4"
    result = renderer.render_master(source_path=synthetic_5s_video, edl=edl, output_path=out_path)

    assert result.output_path.exists()
    assert result.size_bytes > 0
    assert abs(result.duration_ms - 5000) <= 200
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"


def test_single_cut_render(synthetic_5s_video: Path, tmp_path: Path):
    renderer = FFmpegRenderService()
    now = datetime.now(timezone.utc)
    # Cut 1.5s to 3.0s (1500ms removed) -> target duration 3500ms
    cut = CutInstruction(
        cut_id="cut_001",
        decision_id="dec_001",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=5,
        transcript_end_word=8,
        requested_start_ms=1500,
        requested_end_ms=3000,
        safe_start_ms=1500,
        safe_end_ms=3000,
        left_anchor="word1",
        right_anchor="word2",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Clean pause",
        confidence=1.0,
    )
    edl = EditDecisionList(
        edl_id="edl_single_cut",
        production_id="prod_test",
        source_duration_ms=5000,
        cuts=[cut],
        coverage_markers=[],
        created_at=now,
    )

    out_path = tmp_path / "single_cut_preview.mp4"
    result = renderer.render_preview(source_path=synthetic_5s_video, edl=edl, output_path=out_path)

    assert result.output_path.exists()
    assert abs(result.duration_ms - 3500) <= 200  # Expected ~3500ms
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"


def test_multi_cut_render_with_coverage_and_rejected_cuts(synthetic_5s_video: Path, tmp_path: Path):
    renderer = FFmpegRenderService()
    now = datetime.now(timezone.utc)
    # Cut 1: 1000 - 2000 (1000ms SAFE)
    cut1 = CutInstruction(
        cut_id="cut_001",
        decision_id="dec_001",
        decision_type=EditorDecisionType.REMOVE_FILLER,
        transcript_start_word=2,
        transcript_end_word=4,
        requested_start_ms=1000,
        requested_end_ms=2000,
        safe_start_ms=1000,
        safe_end_ms=2000,
        left_anchor="hello",
        right_anchor="world",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="Clean boundary",
        confidence=0.95,
    )
    # Cut 2: 3000 - 4000 (1000ms NEEDS_COVERAGE)
    cut2 = CutInstruction(
        cut_id="cut_002",
        decision_id="dec_002",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=8,
        transcript_end_word=10,
        requested_start_ms=3000,
        requested_end_ms=4000,
        safe_start_ms=3000,
        safe_end_ms=4000,
        left_anchor="pause_left",
        right_anchor="pause_right",
        transition_ms=20,
        safety_status=CutSafetyStatus.NEEDS_COVERAGE,
        safety_reason="Jump cut requires visual coverage",
        confidence=0.90,
    )
    # Cut 3: 4200 - 4800 (REJECTED_UNSAFE -> MUST BE IGNORED)
    cut3 = CutInstruction(
        cut_id="cut_003",
        decision_id="dec_003",
        decision_type=EditorDecisionType.REMOVE_REPETITION,
        transcript_start_word=12,
        transcript_end_word=14,
        requested_start_ms=4200,
        requested_end_ms=4800,
        safe_start_ms=4200,
        safe_end_ms=4800,
        left_anchor="unsafe_left",
        right_anchor="unsafe_right",
        transition_ms=20,
        safety_status=CutSafetyStatus.REJECTED_UNSAFE,
        safety_reason="Boundary clips syllable",
        confidence=0.20,
    )
    # Active cuts remove 2000ms total -> expected 3000ms
    edl = EditDecisionList(
        edl_id="edl_multi_cut",
        production_id="prod_test",
        source_duration_ms=5000,
        cuts=[cut1, cut2, cut3],
        coverage_markers=[],
        created_at=now,
    )

    out_path = tmp_path / "multi_cut_master.mp4"
    result = renderer.render_master(source_path=synthetic_5s_video, edl=edl, output_path=out_path)

    assert result.output_path.exists()
    assert abs(result.duration_ms - 3000) <= 200
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"


def test_render_missing_source_raises(tmp_path: Path):
    renderer = FFmpegRenderService()
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_err",
        production_id="prod_test",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    non_existent = tmp_path / "does_not_exist.mp4"
    with pytest.raises(RenderError, match="Source video not found"):
        renderer.render_preview(source_path=non_existent, edl=edl)


def test_render_cleanup_on_failure(synthetic_5s_video: Path, tmp_path: Path):
    # Pass an invalid binary name to trigger failure
    renderer = FFmpegRenderService(ffmpeg_binary="invalid_ffmpeg_binary_xyz")
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_err",
        production_id="prod_test",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    out_target = tmp_path / "should_not_exist.mp4"
    with pytest.raises(RenderError):
        renderer.render_preview(source_path=synthetic_5s_video, edl=edl, output_path=out_target)
    assert not out_target.exists()


def test_fake_render_service(synthetic_5s_video: Path, tmp_path: Path):
    fake = FakeRenderService()
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_fake",
        production_id="prod_test",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    out_path = tmp_path / "fake_out.mp4"
    res = fake.render_preview(source_path=synthetic_5s_video, edl=edl, output_path=out_path)
    assert res.output_path.exists()
    assert res.duration_ms == 5000
    assert res.video_codec == "h264"
    assert res.audio_codec == "aac"


def test_voiceover_preview_zero_cut_replaces_source_audio(
    synthetic_5s_video: Path,
    tmp_path: Path,
):
    renderer = FFmpegRenderService()
    edl = EditDecisionList(
        edl_id="edl_voiceover_zero_cut",
        production_id="prod_voiceover_zero_cut",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[],
        created_at=datetime.now(timezone.utc),
    )
    narration_path = _create_sine_audio(
        tmp_path / "zero_cut_narration.wav",
        frequency_hz=880,
        duration_sec=5,
    )

    result = renderer.render_voiceover_preview(
        source_path=synthetic_5s_video,
        edl=edl,
        narration_audio_path=narration_path,
        output_path=tmp_path / "voiceover_zero_cut.mp4",
    )

    samples = _decode_mono_audio(result.output_path)
    assert result.artifact_type == ArtifactType.VOICEOVER_PREVIEW
    assert _tone_amplitude(samples, 880) > 0.05
    assert _tone_amplitude(samples, 440) < 0.005


def test_voiceover_preview_multi_cut_replaces_source_audio_through_concat(
    synthetic_5s_video: Path,
    tmp_path: Path,
):
    renderer = FFmpegRenderService()
    cuts = [
        CutInstruction(
            cut_id="cut_voiceover_1",
            decision_id="decision_voiceover_1",
            decision_type=EditorDecisionType.REMOVE_FILLER,
            transcript_start_word=2,
            transcript_end_word=4,
            requested_start_ms=1000,
            requested_end_ms=2000,
            safe_start_ms=1000,
            safe_end_ms=2000,
            left_anchor="before-one",
            right_anchor="after-one",
            transition_ms=20,
            safety_status=CutSafetyStatus.SAFE,
            safety_reason="synthetic test boundary",
            confidence=1.0,
        ),
        CutInstruction(
            cut_id="cut_voiceover_2",
            decision_id="decision_voiceover_2",
            decision_type=EditorDecisionType.TRIM_PAUSE,
            transcript_start_word=8,
            transcript_end_word=10,
            requested_start_ms=3000,
            requested_end_ms=4000,
            safe_start_ms=3000,
            safe_end_ms=4000,
            left_anchor="before-two",
            right_anchor="after-two",
            transition_ms=20,
            safety_status=CutSafetyStatus.SAFE,
            safety_reason="synthetic test boundary",
            confidence=1.0,
        ),
    ]
    edl = EditDecisionList(
        edl_id="edl_voiceover_multi_cut",
        production_id="prod_voiceover_multi_cut",
        source_duration_ms=5000,
        cuts=cuts,
        coverage_markers=[],
        created_at=datetime.now(timezone.utc),
    )
    narration_path = _create_sine_audio(
        tmp_path / "multi_cut_narration.wav",
        frequency_hz=880,
        duration_sec=3,
    )

    result = renderer.render_voiceover_preview(
        source_path=synthetic_5s_video,
        edl=edl,
        narration_audio_path=narration_path,
        output_path=tmp_path / "voiceover_multi_cut.mp4",
    )

    samples = _decode_mono_audio(result.output_path)
    assert abs(result.duration_ms - 3000) <= 250
    assert _tone_amplitude(samples, 880) > 0.05
    assert _tone_amplitude(samples, 440) < 0.005


def test_voiceover_preview_missing_narration_raises_instead_of_using_source_audio(
    synthetic_5s_video: Path,
    tmp_path: Path,
):
    renderer = FFmpegRenderService()
    edl = EditDecisionList(
        edl_id="edl_voiceover_missing_narration",
        production_id="prod_voiceover_missing_narration",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[],
        created_at=datetime.now(timezone.utc),
    )

    with pytest.raises(RenderError):
        renderer.render_voiceover_preview(
            source_path=synthetic_5s_video,
            edl=edl,
            narration_audio_path=tmp_path / "missing-narration.wav",
            output_path=tmp_path / "must-not-fall-back.mp4",
        )


def test_voiceover_preview_pads_short_narration_with_silence_to_edl_duration(
    synthetic_5s_video: Path,
    tmp_path: Path,
):
    renderer = FFmpegRenderService()
    edl = EditDecisionList(
        edl_id="edl_voiceover_short_narration",
        production_id="prod_voiceover_short_narration",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[],
        created_at=datetime.now(timezone.utc),
    )
    narration_path = _create_sine_audio(
        tmp_path / "short_narration.wav",
        frequency_hz=880,
        duration_sec=1,
    )

    result = renderer.render_voiceover_preview(
        source_path=synthetic_5s_video,
        edl=edl,
        narration_audio_path=narration_path,
        output_path=tmp_path / "voiceover_short_narration.mp4",
    )

    samples = _decode_mono_audio(result.output_path)
    assert abs(result.duration_ms - 5000) <= 250
    assert len(samples) >= int(4.8 * 48000)
    assert _rms_amplitude(samples, 0.25, 0.75) > 0.03
    assert _rms_amplitude(samples, 4.0, 4.5) < 0.005


def test_render_studio_voice_preview(synthetic_5s_video: Path, tmp_path: Path):
    renderer = FFmpegRenderService()
    now = datetime.now(timezone.utc)
    edl = EditDecisionList(
        edl_id="edl_sv_test",
        production_id="prod_sv",
        source_duration_ms=5000,
        cuts=[],
        coverage_markers=[],
        created_at=now,
    )
    # Generate 5s synthetic narration wav
    narr_path = tmp_path / "narr.wav"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=5",
        "-c:a", "pcm_s16le", str(narr_path)
    ]
    subprocess.run(cmd, check=True)

    out_path = tmp_path / "studio_voice_preview.mp4"
    res = renderer.render_studio_voice_preview(
        source_path=synthetic_5s_video,
        edl=edl,
        narration_audio_path=narr_path,
        speech_intervals_ms=[(1000, 3000)],
        output_path=out_path,
    )

    assert res.output_path.exists()
    assert res.artifact_type == ArtifactType.STUDIO_VOICE_PREVIEW
    assert res.duration_ms >= 4800
    assert res.video_codec == "h264"
    assert res.audio_codec == "aac"


def test_render_final_mix_with_cuts_preserves_edited_timeline_duration(synthetic_5s_video: Path, tmp_path: Path):
    """Verify Final Mix strictly preserves EDL cut duration (~3s) despite 10s music track."""
    renderer = FFmpegRenderService()
    now = datetime.now(timezone.utc)
    cut = CutInstruction(
        cut_id="cut_01",
        decision_id="dec_01",
        decision_type=EditorDecisionType.TRIM_PAUSE,
        transcript_start_word=1,
        transcript_end_word=2,
        requested_start_ms=1000,
        requested_end_ms=3000,
        safe_start_ms=1000,
        safe_end_ms=3000,
        removed_duration_ms=2000,
        left_anchor="hello",
        right_anchor="world",
        transition_ms=20,
        safety_status=CutSafetyStatus.SAFE,
        safety_reason="clean silence boundary",
        confidence=0.98,
    )
    edl = EditDecisionList(
        edl_id="edl_final_mix_cut_test",
        production_id="prod_fm_cut",
        source_duration_ms=5000,
        cuts=[cut],
        created_at=now,
    )

    # Create 10s synthetic music WAV file
    music_path = tmp_path / "music_10s.wav"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        "-ar", "24000", "-ac", "1",
        str(music_path),
    ]
    subprocess.run(cmd, check=True)

    # Create 3s synthetic voiceover WAV file (matching 3000ms edited target duration)
    narr_path = tmp_path / "voiceover_3s.wav"
    cmd_narr = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=3",
        "-ar", "24000", "-ac", "1",
        str(narr_path),
    ]
    subprocess.run(cmd_narr, check=True)

    out_path = tmp_path / "final_mix_cut.mp4"
    res = renderer.render_final_mix(
        source_path=synthetic_5s_video,
        edl=edl,
        music_audio_path=music_path,
        narration_audio_path=narr_path,
        speech_intervals_ms=[(500, 1500)],
        output_path=out_path,
        music_volume_db=-24.0,
        music_ducking_db=-14.0,
    )

    assert res.output_path.exists()
    assert res.artifact_type == ArtifactType.FINAL_MIX
    # Duration MUST match EDL target duration (3000ms = 5000ms - 2000ms cut), not 5000ms source or 10000ms music!
    assert abs(res.duration_ms - 3000) <= 200
    assert res.video_codec == "h264"
    assert res.audio_codec == "aac"

    # Verify with FakeRenderService as well
    fake = FakeRenderService()
    fake_res = fake.render_final_mix(
        source_path=synthetic_5s_video,
        edl=edl,
        music_audio_path=music_path,
        narration_audio_path=narr_path,
        speech_intervals_ms=[(500, 1500)],
    )
    assert fake_res.artifact_type == ArtifactType.FINAL_MIX
    assert fake_res.duration_ms == 3000

def test_single_segment_narration_audio_is_not_dropped(synthetic_5s_video: Path, tmp_path: Path):
    """Verify single keep segment with narration produces audio mix including narration, not dropping it."""
    renderer = FFmpegRenderService()
    now = datetime.now(timezone.utc)
    # Single keep segment (trimmed from 1000ms to 4000ms)
    edl = EditDecisionList(
        edl_id="edl_single_narr",
        production_id="prod_narr",
        source_duration_ms=5000,
        cuts=[
            CutInstruction(
                cut_id="cut_0",
                decision_id="dec_0",
                decision_type=EditorDecisionType.TRIM_PAUSE,
                transcript_start_word=1,
                transcript_end_word=2,
                requested_start_ms=0,
                requested_end_ms=1000,
                safe_start_ms=0,
                safe_end_ms=1000,
                removed_duration_ms=1000,
                left_anchor="start",
                right_anchor="mid",
                transition_ms=20,
                safety_status=CutSafetyStatus.SAFE,
                safety_reason="clean",
                confidence=0.99,
            ),
            CutInstruction(
                cut_id="cut_1",
                decision_id="dec_1",
                decision_type=EditorDecisionType.TRIM_PAUSE,
                transcript_start_word=3,
                transcript_end_word=4,
                requested_start_ms=4000,
                requested_end_ms=5000,
                safe_start_ms=4000,
                safe_end_ms=5000,
                removed_duration_ms=1000,
                left_anchor="mid",
                right_anchor="end",
                transition_ms=20,
                safety_status=CutSafetyStatus.SAFE,
                safety_reason="clean",
                confidence=0.99,
            ),
        ],
        created_at=now,
    )
    from croviq_media.render import derive_keep_segments
    assert len(derive_keep_segments(edl)) == 1

    narr_path = tmp_path / "narr_3s.wav"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=3",
        "-ar", "24000", "-ac", "1",
        str(narr_path),
    ], check=True)

    out_path = tmp_path / "single_narr.mp4"
    res = renderer.render_studio_voice_master(
        source_path=synthetic_5s_video,
        edl=edl,
        narration_audio_path=narr_path,
        speech_intervals_ms=[(1000, 3000)],
        output_path=out_path,
    )
    assert res.output_path.exists()
    assert abs(res.duration_ms - 3000) <= 250



def test_render_service_abstract_interface_contract_parity():
    """Verify RenderService, FakeRenderService, and FFmpegRenderService share identical method signatures."""
    import inspect
    from croviq_media.render import RenderService, FakeRenderService, FFmpegRenderService

    abc_sig = inspect.signature(RenderService.render_final_mix)
    fake_sig = inspect.signature(FakeRenderService.render_final_mix)
    ffmpeg_sig = inspect.signature(FFmpegRenderService.render_final_mix)

    assert list(abc_sig.parameters.keys()) == list(fake_sig.parameters.keys())
    assert list(abc_sig.parameters.keys()) == list(ffmpeg_sig.parameters.keys())
