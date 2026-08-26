"""Execute real Issue #29 Render acceptance against prod_0b7657f515ae and edl_6cfe6b3bf3f2."""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time

# Ensure packages and apps are in path
sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))

import firebase_admin
from firebase_admin import firestore

from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_domain.edl import EditDecisionList, derive_keep_segments
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
    build_render_artifact_gcs_object_path,
)
from croviq_media.render import FFmpegRenderService


async def main() -> None:
    project_id = "croviq-506602"
    production_id = "prod_0b7657f515ae"
    edl_id = "edl_6cfe6b3bf3f2"

    print("=" * 60)
    print("RUNNING REAL ACCEPTANCE: DETERMINISTIC PREVIEW + MASTER RENDER (#29)")
    print(f"Project: {project_id}")
    print(f"Production: {production_id} | EDL: {edl_id}")
    print("=" * 60)

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    prod_repo = FirestoreProductionRepository(project_id=project_id)
    edl_repo = FirestoreEDLRepository(project_id=project_id)
    render_repo = FirestoreRenderRepository(project_id=project_id)
    media_storage = GoogleMediaStorage(project_id=project_id)
    renderer = FFmpegRenderService()

    # 1. Load real production
    prod = await prod_repo.get_production(production_id)
    if not prod:
        print(f"ERROR: Production {production_id} not found in Firestore")
        sys.exit(1)
    print(f"Loaded Production: {prod.production_id} (Workspace: {prod.workspace_id})")

    if not prod.source_media or not prod.source_media.gcs_object:
        print(f"ERROR: Production {production_id} has no source media")
        sys.exit(1)
    print(f"Source Media Object: gs://{prod.source_media.gcs_bucket}/{prod.source_media.gcs_object}")

    # 2. Load real EDL
    edl = await edl_repo.get_edl(production_id, edl_id)
    if not edl:
        # Fallback to get latest EDL if id differs
        edl = await edl_repo.get_latest_edl(production_id)
    if not edl:
        print(f"ERROR: EDL {edl_id} not found in Firestore for production {production_id}")
        sys.exit(1)

    print(f"Loaded EDL: {edl.edl_id} ({edl.source_duration_ms}ms, {edl.active_cuts_count} active cuts, {len(edl.coverage_markers)} coverage markers)")
    keep_segments = derive_keep_segments(edl)
    print(f"Keep Segments: {keep_segments}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        local_src = tmp_path / "source_media.mp4"
        local_preview = tmp_path / "preview.mp4"
        local_master = tmp_path / "master.mp4"

        # 3. Download source media from private GCS
        print("\nDownloading source media from GCS...")
        t_dl_start = time.perf_counter()
        await media_storage.download_object_to_path(
            bucket=prod.source_media.gcs_bucket,
            object_name=prod.source_media.gcs_object,
            target_path=local_src,
        )
        dl_ms = (time.perf_counter() - t_dl_start) * 1000
        print(f"Source downloaded in {dl_ms:.1f}ms ({local_src.stat().st_size:,} bytes)")

        # 4. Render PREVIEW
        print("\nRendering PREVIEW artifact via FFmpeg...")
        t_prev_start = time.perf_counter()
        preview_res = renderer.render_preview(source_path=local_src, edl=edl, output_path=local_preview)
        preview_render_time_ms = (time.perf_counter() - t_prev_start) * 1000
        print(f"Preview Render complete: {preview_render_time_ms:.1f}ms, size: {preview_res.size_bytes:,} bytes, duration: {preview_res.duration_ms}ms")

        # 5. Render MASTER
        print("\nRendering MASTER artifact via FFmpeg...")
        t_mast_start = time.perf_counter()
        master_res = renderer.render_master(source_path=local_src, edl=edl, output_path=local_master)
        master_render_time_ms = (time.perf_counter() - t_mast_start) * 1000
        print(f"Master Render complete: {master_render_time_ms:.1f}ms, size: {master_res.size_bytes:,} bytes, duration: {master_res.duration_ms}ms")

        # 6. Upload PREVIEW to GCS
        preview_obj = build_render_artifact_gcs_object_path(
            workspace_id=prod.workspace_id,
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_type=ArtifactType.PREVIEW,
        )
        print(f"\nUploading Preview to gs://{prod.source_media.gcs_bucket}/{preview_obj}...")
        await media_storage.upload_object_from_path(
            bucket=prod.source_media.gcs_bucket,
            object_name=preview_obj,
            source_path=local_preview,
            content_type="video/mp4",
        )

        # 7. Upload MASTER to GCS
        master_obj = build_render_artifact_gcs_object_path(
            workspace_id=prod.workspace_id,
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_type=ArtifactType.MASTER,
        )
        print(f"Uploading Master to gs://{prod.source_media.gcs_bucket}/{master_obj}...")
        await media_storage.upload_object_from_path(
            bucket=prod.source_media.gcs_bucket,
            object_name=master_obj,
            source_path=local_master,
            content_type="video/mp4",
        )

        now = datetime.now(timezone.utc)

        # 8. Create and persist RenderArtifact for PREVIEW
        preview_artifact = RenderArtifact(
            artifact_id=f"art_prev_{edl.edl_id[-8:]}",
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_type=ArtifactType.PREVIEW,
            status=ArtifactStatus.completed,
            gcs_bucket=prod.source_media.gcs_bucket,
            gcs_object=preview_obj,
            content_type="video/mp4",
            size_bytes=preview_res.size_bytes,
            duration_ms=preview_res.duration_ms,
            width=preview_res.width,
            height=preview_res.height,
            frame_rate=preview_res.frame_rate,
            video_codec=preview_res.video_codec,
            audio_codec=preview_res.audio_codec,
            created_at=now,
            completed_at=now,
        )
        await render_repo.save_render_artifact(preview_artifact)
        print(f"Persisted Preview RenderArtifact: {preview_artifact.artifact_id}")

        # 9. Create and persist RenderArtifact for MASTER
        master_artifact = RenderArtifact(
            artifact_id=f"art_mast_{edl.edl_id[-8:]}",
            production_id=prod.production_id,
            edl_id=edl.edl_id,
            artifact_type=ArtifactType.MASTER,
            status=ArtifactStatus.completed,
            gcs_bucket=prod.source_media.gcs_bucket,
            gcs_object=master_obj,
            content_type="video/mp4",
            size_bytes=master_res.size_bytes,
            duration_ms=master_res.duration_ms,
            width=master_res.width,
            height=master_res.height,
            frame_rate=master_res.frame_rate,
            video_codec=master_res.video_codec,
            audio_codec=master_res.audio_codec,
            created_at=now,
            completed_at=now,
        )
        await render_repo.save_render_artifact(master_artifact)
        print(f"Persisted Master RenderArtifact: {master_artifact.artifact_id}")

        # 10. Generate signed playback URLs to verify playback access
        signed_preview = await media_storage.generate_signed_read_target(
            bucket=preview_artifact.gcs_bucket,
            object_name=preview_artifact.gcs_object,
            expiry_seconds=3600,
        )
        signed_master = await media_storage.generate_signed_read_target(
            bucket=master_artifact.gcs_bucket,
            object_name=master_artifact.gcs_object,
            expiry_seconds=3600,
        )

        result_summary = {
            "production_id": prod.production_id,
            "edl_id": edl.edl_id,
            "source_duration_ms": edl.source_duration_ms,
            "cuts_count": len(edl.cuts),
            "active_cuts_count": edl.active_cuts_count,
            "coverage_markers_count": len(edl.coverage_markers),
            "keep_segments": keep_segments,
            "preview_artifact": {
                "artifact_id": preview_artifact.artifact_id,
                "gcs_bucket": preview_artifact.gcs_bucket,
                "gcs_object": preview_artifact.gcs_object,
                "size_bytes": preview_res.size_bytes,
                "duration_ms": preview_res.duration_ms,
                "width": preview_res.width,
                "height": preview_res.height,
                "frame_rate": preview_res.frame_rate,
                "video_codec": preview_res.video_codec,
                "audio_codec": preview_res.audio_codec,
                "render_time_ms": preview_render_time_ms,
                "signed_playback_available": bool(signed_preview.read_url),
            },
            "master_artifact": {
                "artifact_id": master_artifact.artifact_id,
                "gcs_bucket": master_artifact.gcs_bucket,
                "gcs_object": master_artifact.gcs_object,
                "size_bytes": master_res.size_bytes,
                "duration_ms": master_res.duration_ms,
                "width": master_res.width,
                "height": master_res.height,
                "frame_rate": master_res.frame_rate,
                "video_codec": master_res.video_codec,
                "audio_codec": master_res.audio_codec,
                "render_time_ms": master_render_time_ms,
                "signed_playback_available": bool(signed_master.read_url),
            },
            "model_calls": {
                "gemini_transcribe": 0,
                "gemini_leo": 0,
                "gemini_maya": 0,
                "groq": 0,
            },
        }

        output_json = Path(__file__).resolve().parent.parent / "apps" / "api" / "real_render_acceptance_result.json"
        output_json.write_text(json.dumps(result_summary, indent=2), encoding="utf-8")

        print("\n" + "=" * 60)
        print("REAL ACCEPTANCE COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"PREVIEW: {preview_res.width}x{preview_res.height} @ {preview_res.frame_rate}fps | {preview_res.duration_ms}ms | {preview_res.size_bytes:,} bytes | render time: {preview_render_time_ms:.1f}ms")
        print(f"MASTER:  {master_res.width}x{master_res.height} @ {master_res.frame_rate}fps | {master_res.duration_ms}ms | {master_res.size_bytes:,} bytes | render time: {master_render_time_ms:.1f}ms")
        print(f"Results saved to {output_json}")


if __name__ == "__main__":
    asyncio.run(main())
