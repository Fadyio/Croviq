"""Unit and synthetic media tests for RenderService and FFmpegRenderService."""

from datetime import datetime, timezone
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
from croviq_media.render import (
    FakeRenderService,
    FFmpegRenderService,
    RenderError,
    RenderExecutionResult,
)


def _create_synthetic_video(target_path: Path, duration_sec: int = 5) -> Path:
    """Helper to generate a synthetic test video (H.264/AAC) with visual test patterns and audio tone."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_sec}:size=640x360:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_sec}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(target_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        pytest.skip(f"ffmpeg not available for synthetic video creation: {res.stderr}")
    return target_path


@pytest.fixture
def synthetic_5s_video(tmp_path: Path) -> Path:
    video_path = tmp_path / "source_5s.mp4"
    return _create_synthetic_video(video_path, duration_sec=5)


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
                coverage_type=CoverageType.BROLL_CANDIDATE,
                reason="Insert b-roll over test",
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
        safety_reason="Jump cut requires B-roll",
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
