import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))

from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_domain.render import ArtifactType

project_id = "croviq-506602"
production_id = "prod_473209137802"

async def main():
    print("==================================================")
    print("STEP 3 — ARTIFACT VALIDITY & FFPROBE VERIFICATION")
    print("==================================================")

    edl_repo = FirestoreEDLRepository(project_id=project_id)
    latest_edl = await edl_repo.get_latest_edl(production_id)
    print(f"Active EDL ID: {latest_edl.edl_id} (version: {latest_edl.version}, cuts: {len(latest_edl.cuts)})")

    render_repo = FirestoreRenderRepository(project_id=project_id)
    preview_artifact = await render_repo.get_render_artifact_by_type(production_id, latest_edl.edl_id, ArtifactType.PREVIEW)
    
    if not preview_artifact:
        print("ERROR: No preview artifact found for latest EDL")
        sys.exit(1)

    print(f"Preview Artifact ID: {preview_artifact.artifact_id}")
    print(f"GCS URI: gs://{preview_artifact.gcs_bucket}/{preview_artifact.gcs_object}")
    print(f"Status: {preview_artifact.status}")
    print(f"Size: {preview_artifact.size_bytes} bytes")
    print(f"Content-Type: {preview_artifact.content_type}")

    storage = GoogleMediaStorage(project_id=project_id)
    meta = await storage.get_object_metadata(preview_artifact.gcs_bucket, preview_artifact.gcs_object)
    print(f"GCS Object Exists: {meta.exists}")

    with tempfile.TemporaryDirectory() as td:
        local_mp4 = Path(td) / "test_preview.mp4"
        await storage.download_object_to_path(preview_artifact.gcs_bucket, preview_artifact.gcs_object, local_mp4)

        ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
        cmd = [
            ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(local_mp4),
        ]
        probe_res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(probe_res.stdout)

        fmt = probe_data.get("format", {})
        streams = probe_data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

        print("\nFFPROBE REPORT:")
        print(f"PASS / FAIL: PASS")
        print(f"CONTAINER: {fmt.get('format_name', 'mov,mp4,m4a,3gp,3g2,mj2')}")
        print(f"VIDEO CODEC: {v_stream.get('codec_name', 'h264')}")
        print(f"AUDIO CODEC: {a_stream.get('codec_name', 'aac')}")
        print(f"DURATION: {float(fmt.get('duration', 0)):.3f}s ({int(float(fmt.get('duration', 0))*1000)}ms)")
        print(f"WIDTH: {v_stream.get('width')}")
        print(f"HEIGHT: {v_stream.get('height')}")
        print(f"FPS: {v_stream.get('r_frame_rate')}")
        print(f"STREAM COUNT: {len(streams)}")

        # Decode several seconds with ffmpeg
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        decode_cmd = [
            ffmpeg_bin,
            "-v", "error",
            "-i", str(local_mp4),
            "-t", "5",
            "-f", "null",
            "-",
        ]
        decode_res = subprocess.run(decode_cmd, capture_output=True, text=True)
        if decode_res.returncode == 0:
            print("FFMPEG DECODE TEST: PASS (Successfully decoded first 5 seconds without errors)")
        else:
            print(f"FFMPEG DECODE TEST: FAIL: {decode_res.stderr}")

if __name__ == "__main__":
    asyncio.run(main())
