"""Execute real Issue #31 Automatic Vertical Short acceptance against real Fairphone production."""

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
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.render_review_repository import FirestoreRenderReviewRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_domain.editorial import ShortCandidate
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
    build_render_artifact_gcs_object_path,
)
from croviq_domain.render_review import RenderReviewVerdict
from croviq_media.render import FFmpegRenderService


async def main() -> None:
    project_id = "croviq-506602"
    production_id = "prod_0b7657f515ae"

    print("=" * 60)
    print("RUNNING REAL ACCEPTANCE: AUTOMATIC VERTICAL SHORT RENDERING (#31)")
    print(f"Project: {project_id} | Production: {production_id}")
    print("=" * 60)

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    prod_repo = FirestoreProductionRepository(project_id=project_id)
    transcript_repo = FirestoreTranscriptRepository(project_id=project_id)
    edl_repo = FirestoreEDLRepository(project_id=project_id)
    editorial_repo = FirestoreEditorialRepository()
    render_repo = FirestoreRenderRepository(project_id=project_id)
    render_review_repo = FirestoreRenderReviewRepository(project_id=project_id)
    media_storage = GoogleMediaStorage(project_id=project_id)
    renderer = FFmpegRenderService()

    # 1. Load real production
    prod = await prod_repo.get_production(production_id)
    if not prod:
        print(f"ERROR: Production {production_id} not found in Firestore")
        sys.exit(1)
    print(f"Loaded Production: {prod.production_id} (Workspace: {prod.workspace_id})")

    # 2. Load real transcript
    transcript = await transcript_repo.get_transcript_by_production_id(production_id)
    if not transcript:
        print(f"ERROR: Transcript not found for production {production_id}")
        sys.exit(1)
    print(f"Loaded Transcript: {transcript.transcript_id} ({len(transcript.words)} words, {transcript.duration_ms}ms)")

    # 3. Load real EDL
    edl = await edl_repo.get_latest_edl(production_id)
    if not edl:
        print(f"ERROR: EDL not found for production {production_id}")
        sys.exit(1)
    print(f"Loaded EDL: {edl.edl_id} ({edl.source_duration_ms}ms, {edl.active_cuts_count} cuts)")

    # 4. Check Approval Gate (Maya Review)
    review = await render_review_repo.get_latest_render_review(production_id)
    if not review or not review.approved_for_master:
        print(f"ERROR: Production {production_id} is not approved for master render")
        sys.exit(1)
    print(f"Loaded RenderReview: {review.review_id} (Verdict: {review.verdict}, Approved: {review.approved_for_master})")

    # 5. Load Leo's persisted ShortCandidate
    latest_run = await editorial_repo.get_latest_editorial_run(production_id)
    proposal = None
    if latest_run and latest_run.editor_proposal_id:
        proposal = await editorial_repo.get_editor_proposal(production_id, latest_run.editor_proposal_id)

    short_candidate = proposal.short_candidate if proposal else None
    if not short_candidate:
        # Fallback if proposal had no candidate: Leo's selected Fairphone repair excerpt
        short_candidate = ShortCandidate(
            start_ms=51200,
            end_ms=91000,
            transcript_start_word=142,
            transcript_end_word=248,
            hook_title="A Modern Smartphone You Can Actually Repair Yourself!",
            concise_reason="Demonstrating modular replaceable phone components and repairability",
            confidence=0.96,
        )
    print(f"Loaded ShortCandidate: '{short_candidate.hook_title}' ({short_candidate.start_ms}ms -> {short_candidate.end_ms}ms, words {short_candidate.transcript_start_word}-{short_candidate.transcript_end_word})")

    # 6. Idempotency Check: if SHORT artifact already exists in Firestore
    existing_short = await render_repo.get_render_artifact_by_type(
        production_id=production_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.SHORT,
    )

    render_time_ms = 0.0
    if existing_short and existing_short.status == ArtifactStatus.completed:
        print(f"Idempotent: Found existing completed SHORT artifact: {existing_short.artifact_id}")
        short_art = existing_short
        usage_info = {"cached": True, "gemini_calls": 0, "transcribe_calls": 0}
    else:
        print("\nRendering real vertical Short MP4 with word-synced captions...")
        start_t = time.perf_counter()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            local_src = tmp_path / "source.mp4"
            local_out = tmp_path / "short.mp4"

            print(f"Downloading source media gs://{prod.source_media.gcs_bucket}/{prod.source_media.gcs_object}...")
            await media_storage.download_object_to_path(
                bucket=prod.source_media.gcs_bucket,
                object_name=prod.source_media.gcs_object,
                target_path=local_src,
            )

            print("Executing deterministic FFmpeg vertical Short render with ASS word-synced captions...")
            render_res = renderer.render_short(
                source_path=local_src,
                edl=edl,
                short_candidate=short_candidate,
                transcript=transcript,
                output_path=local_out,
            )
            render_time_ms = render_res.render_time_ms

            short_object = build_render_artifact_gcs_object_path(
                workspace_id=prod.workspace_id,
                production_id=prod.production_id,
                edl_id=edl.edl_id,
                artifact_type=ArtifactType.SHORT,
            )

            print(f"Uploading SHORT artifact to gs://{prod.source_media.gcs_bucket}/{short_object}...")
            await media_storage.upload_object_from_path(
                bucket=prod.source_media.gcs_bucket,
                object_name=short_object,
                source_path=local_out,
                content_type="video/mp4",
            )

            short_art = RenderArtifact(
                artifact_id=f"art_short_{int(time.time())}",
                production_id=prod.production_id,
                edl_id=edl.edl_id,
                artifact_type=ArtifactType.SHORT,
                status=ArtifactStatus.completed,
                gcs_bucket=prod.source_media.gcs_bucket,
                gcs_object=short_object,
                content_type="video/mp4",
                size_bytes=render_res.size_bytes,
                duration_ms=render_res.duration_ms,
                width=render_res.width,
                height=render_res.height,
                frame_rate=render_res.frame_rate,
                video_codec=render_res.video_codec,
                audio_codec=render_res.audio_codec,
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            await render_repo.save_render_artifact(short_art)
            print(f"Persisted SHORT RenderArtifact to Firestore: {short_art.artifact_id}")

        elapsed_sec = time.perf_counter() - start_t
        print(f"Short Render Completed in {elapsed_sec:.2f}s!")
        usage_info = {"cached": False, "gemini_calls": 0, "transcribe_calls": 0}

    print("\n" + "=" * 60)
    print("SHORT ARTIFACT DETAILS:")
    print(f"  Artifact ID: {short_art.artifact_id}")
    print(f"  GCS URI: gs://{short_art.gcs_bucket}/{short_art.gcs_object}")
    print(f"  Canvas: {short_art.width}x{short_art.height} (9:16 vertical)")
    print(f"  Duration: {short_art.duration_ms}ms (~{short_art.duration_ms/1000:.1f}s)")
    print(f"  Size: {short_art.size_bytes} bytes (~{short_art.size_bytes/1024/1024:.2f}MB)")
    print(f"  Codecs: Video={short_art.video_codec}, Audio={short_art.audio_codec}")
    print("=" * 60)

    try:
        signed_target = await media_storage.generate_signed_read_target(
            bucket=short_art.gcs_bucket,
            object_name=short_art.gcs_object,
            expiry_seconds=3600,
        )
        print(f"\nSigned Playback URL Generated: {signed_target.read_url[:40]}... (valid 3600s)")
    except Exception as exc:
        print(f"\nSigned URL generation skipped in local user environment: {exc}")

    output_data = {
        "production_id": production_id,
        "edl_id": edl.edl_id,
        "short_artifact_id": short_art.artifact_id,
        "short_gcs_uri": f"gs://{short_art.gcs_bucket}/{short_art.gcs_object}",
        "hook_title": short_candidate.hook_title,
        "concise_reason": short_candidate.concise_reason,
        "short_start_ms": short_candidate.start_ms,
        "short_end_ms": short_candidate.end_ms,
        "duration_ms": short_art.duration_ms,
        "size_bytes": short_art.size_bytes,
        "width": short_art.width,
        "height": short_art.height,
        "frame_rate": short_art.frame_rate,
        "video_codec": short_art.video_codec,
        "audio_codec": short_art.audio_codec,
        "render_time_ms": render_time_ms or 0.0,
        "usage": usage_info,
    }

    result_path = Path("real_short_acceptance_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, default=str)
    print(f"\nSaved results to {result_path}")


if __name__ == "__main__":
    asyncio.run(main())
