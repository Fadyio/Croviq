import asyncio
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))

import firebase_admin
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_domain.edl import (
    CoverageMarker,
    CoverageType,
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
    derive_keep_segments,
)
from croviq_domain.editorial import EditorDecisionType
from croviq_media.render import FFmpegRenderService

project_id = "croviq-506602"
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": project_id})

async def main():
    prod_repo = FirestoreProductionRepository(project_id=project_id)
    storage = GoogleMediaStorage(project_id=project_id)
    renderer = FFmpegRenderService()

    pid = "prod_f0b41bfd429e"
    prod = await prod_repo.get_production(pid)
    bucket = prod.source_media.gcs_bucket
    obj = prod.source_media.gcs_object

    with tempfile.TemporaryDirectory() as tmpdir:
        local_src = Path(tmpdir) / "source.mp4"
        print(f"Downloading gs://{bucket}/{obj}...")
        await storage.download_object_to_path(bucket, obj, local_src)

        now = datetime.now(timezone.utc)
        edl = EditDecisionList(
            edl_id="edl_2cut_acceptance",
            production_id=pid,
            source_duration_ms=113824,
            editor_proposal_id="prop_run_1787894922_fd429e",
            director_review_id="rev_run_1787894922_fd429e",
            version=1,
            cuts=[
                CutInstruction(
                    cut_id="cut_acc_01",
                    decision_id="dec_01_tighten_pause",
                    decision_type=EditorDecisionType.TRIM_PAUSE,
                    transcript_start_word=27,
                    transcript_end_word=28,
                    requested_start_ms=12540,
                    requested_end_ms=15000,
                    safe_start_ms=12540,
                    safe_end_ms=15000,
                    removed_duration_ms=2460,
                    left_anchor="out.",
                    right_anchor="Now",
                    safety_status=CutSafetyStatus.SAFE,
                    safety_reason="Clean pause boundary between sentences",
                    confidence=0.96,
                ),
                CutInstruction(
                    cut_id="cut_acc_02",
                    decision_id="dec_02_tighten_battery",
                    decision_type=EditorDecisionType.REMOVE_FALSE_START,
                    transcript_start_word=121,
                    transcript_end_word=125,
                    requested_start_ms=42340,
                    requested_end_ms=44400,
                    safe_start_ms=42340,
                    safe_end_ms=44400,
                    removed_duration_ms=2060,
                    left_anchor="fingers.",
                    right_anchor="And",
                    safety_status=CutSafetyStatus.SAFE,
                    safety_reason="Stumbled phrase restart cleanly excised",
                    confidence=0.94,
                ),
            ],
            coverage_markers=[
                CoverageMarker(
                    marker_id="cov_acc_01",
                    decision_id="dec_002",
                    source_start_ms=26160,
                    source_end_ms=42340,
                    coverage_type=CoverageType.BROLL_CANDIDATE,
                    reason="Close-up macro teardown insert",
                ),
            ],
            created_at=now,
        )

        keep_segments = derive_keep_segments(edl)
        print(f"Keep segments: {keep_segments}")
        print(f"Expected duration: {edl.estimated_target_duration_ms}ms")

        # 1. Render Preview
        preview_path = Path(tmpdir) / "preview.mp4"
        prev_res = renderer.render_preview(local_src, edl, preview_path)
        print(f"\nPreview rendered:")
        print(f"  Duration: {prev_res.duration_ms}ms ({prev_res.duration_ms / 1000.0:.3f}s)")
        print(f"  Size: {prev_res.size_bytes} bytes")
        print(f"  Codec: video={prev_res.video_codec}, audio={prev_res.audio_codec}")
        print(f"  Resolution: {prev_res.width}x{prev_res.height} @ {prev_res.frame_rate}fps")
        prev_sha = hashlib.sha256(preview_path.read_bytes()).hexdigest()
        print(f"  SHA256: {prev_sha}")

        # 2. Render Master
        master_path = Path(tmpdir) / "master.mp4"
        mast_res = renderer.render_master(local_src, edl, master_path)
        print(f"\nMaster rendered:")
        print(f"  Duration: {mast_res.duration_ms}ms ({mast_res.duration_ms / 1000.0:.3f}s)")
        print(f"  Size: {mast_res.size_bytes} bytes")
        print(f"  Codec: video={mast_res.video_codec}, audio={mast_res.audio_codec}")
        print(f"  Resolution: {mast_res.width}x{mast_res.height} @ {mast_res.frame_rate}fps")
        mast_sha = hashlib.sha256(master_path.read_bytes()).hexdigest()
        print(f"  SHA256: {mast_sha}")

        # FFprobe verification
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-show_entries", "stream=width,height,codec_name,r_frame_rate",
            "-of", "json",
            str(master_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("\nFFprobe Master:")
        print(res.stdout)

if __name__ == "__main__":
    asyncio.run(main())
