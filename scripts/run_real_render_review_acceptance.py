"""Execute real Issue #30 Maya post-render review acceptance against real Fairphone Preview fixture."""

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

from croviq_agents.client import GoogleGenAIClient
from croviq_agents.director import MayaDirector
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.render_review_repository import FirestoreRenderReviewRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.edl import EditDecisionList
from croviq_domain.editorial import DirectorReview, EditorProposal
from croviq_domain.memory import ChannelProfileBuilder
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
    build_render_artifact_gcs_object_path,
)
from croviq_domain.render_review import (
    RenderReview,
    RenderReviewIssue,
    RenderReviewVerdict,
)
from croviq_media.render import FFmpegRenderService


async def main() -> None:
    project_id = "croviq-506602"
    location = "global"
    model_id = "gemini-3.7-flash"
    production_id = "prod_0b7657f515ae"

    print("=" * 60)
    print("RUNNING REAL ACCEPTANCE: DIRECTOR POST-RENDER REVIEW (#30)")
    print(f"Project: {project_id} | Location: {location} | Model: {model_id}")
    print(f"Production: {production_id}")
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
    genai_client = GoogleGenAIClient(
        project_id=project_id,
        location=location,
        model_id=model_id,
    )
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

    # 4. Load real Preview RenderArtifact
    preview_artifact = await render_repo.get_render_artifact_by_type(
        production_id=production_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.PREVIEW,
    )
    if not preview_artifact or preview_artifact.status != ArtifactStatus.completed:
        print(f"ERROR: Completed PREVIEW artifact not found for EDL {edl.edl_id}")
        sys.exit(1)
    print(f"Loaded Preview Artifact: {preview_artifact.artifact_id} (gs://{preview_artifact.gcs_bucket}/{preview_artifact.gcs_object})")

    # 5. Load memory profile and lessons
    provider = SampleChannelDataProvider()
    channel = await provider.get_channel()
    channel_profile = ChannelProfileBuilder.build_profile(channel)
    lessons = ChannelProfileBuilder.build_lessons(channel)
    print(f"Loaded Channel Profile: {channel_profile.channel_name} ({len(lessons)} lessons)")

    # 6. Load latest proposal and review
    latest_run = await editorial_repo.get_latest_editorial_run(production_id)
    proposal = None
    director_review = None
    if latest_run and latest_run.editor_proposal_id:
        proposal = await editorial_repo.get_editor_proposal(production_id, latest_run.editor_proposal_id)
    if latest_run and latest_run.director_review_id:
        director_review = await editorial_repo.get_director_review(production_id, latest_run.director_review_id)

    if not proposal:
        proposal = EditorProposal(
            production_id=production_id,
            model=model_id,
            summary="Initial dialogue pass",
            decisions=[],
            short_candidate=None,
            overall_confidence=0.95,
        )

    # 7. Check idempotency: if RenderReview already exists in Firestore
    existing_review = await render_review_repo.get_render_review_by_preview(
        production_id=production_id,
        edl_id=edl.edl_id,
        preview_artifact_id=preview_artifact.artifact_id,
    )

    if existing_review:
        print(f"Idempotent: Found existing RenderReview: {existing_review.review_id}")
        render_review = existing_review
        usage_info = {"cached": True}
    else:
        print("Invoking REAL Gemini 3.7 Flash for Maya Director post-render review...")
        start_t = time.perf_counter()
        maya = MayaDirector(client=genai_client)
        render_review, usage, activities = await maya.review_render(
            preview_gcs_bucket=preview_artifact.gcs_bucket,
            preview_gcs_object=preview_artifact.gcs_object,
            preview_artifact_id=preview_artifact.artifact_id,
            edl=edl,
            proposal=proposal,
            director_review=director_review,
            transcript=transcript,
            production_id=production_id,
            preview_mime_type=preview_artifact.content_type or "video/mp4",
            channel_profile=channel_profile,
            lessons=lessons,
        )
        elapsed_sec = time.perf_counter() - start_t
        print(f"Maya Review Complete in {elapsed_sec:.2f}s!")
        print(f"Tokens: In={usage.input_tokens}, Out={usage.output_tokens}, Latency={usage.latency_ms}ms")

        # Persist review to Firestore
        await render_review_repo.save_render_review(render_review)
        print(f"Persisted RenderReview {render_review.review_id} to Firestore")
        usage_info = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "latency_ms": usage.latency_ms,
        }

    print("\n" + "=" * 60)
    print(f"POST-RENDER MAYA VERDICT: {render_review.verdict}")
    print(f"APPROVED FOR MASTER: {render_review.approved_for_master}")
    print(f"SUMMARY: {render_review.summary}")
    print(f"CONFIDENCE: {render_review.confidence}")
    print(f"ISSUES COUNT: {len(render_review.issues)}")
    for iss in render_review.issues:
        print(f"  - [{iss.issue_type}] ({iss.source_start_ms}ms-{iss.source_end_ms}ms): {iss.message} -> {iss.suggested_action}")
    print("=" * 60)

    # 8. If approved, verify Master render exists or render it
    master_art = await render_repo.get_render_artifact_by_type(
        production_id=production_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.MASTER,
    )
    if render_review.approved_for_master:
        if not master_art or master_art.status != ArtifactStatus.completed:
            print("Rendering Master video from approved EDL...")
            # Render master locally and upload
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                local_src = tmp_path / "source.mp4"
                local_out = tmp_path / "master.mp4"

                await media_storage.download_object_to_path(
                    bucket=prod.source_media.gcs_bucket,
                    object_name=prod.source_media.gcs_object,
                    target_path=local_src,
                )

                render_res = renderer.render_master(
                    source_path=local_src,
                    edl=edl,
                    output_path=local_out,
                )

                master_object = build_render_artifact_gcs_object_path(
                    workspace_id=prod.workspace_id,
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_type=ArtifactType.MASTER,
                )

                await media_storage.upload_object_from_path(
                    bucket=prod.source_media.gcs_bucket,
                    object_name=master_object,
                    source_path=local_out,
                    content_type="video/mp4",
                )

                master_art = RenderArtifact(
                    artifact_id=f"art_master_{int(time.time())}",
                    production_id=prod.production_id,
                    edl_id=edl.edl_id,
                    artifact_type=ArtifactType.MASTER,
                    status=ArtifactStatus.completed,
                    gcs_bucket=prod.source_media.gcs_bucket,
                    gcs_object=master_object,
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
                await render_repo.save_render_artifact(master_art)
                print(f"Master render completed and saved: {master_art.artifact_id}")
        else:
            print(f"Master render already exists and completed: {master_art.artifact_id}")

    # 9. Output report
    output_data = {
        "production_id": production_id,
        "edl_id": edl.edl_id,
        "preview_artifact_id": preview_artifact.artifact_id,
        "preview_gcs_uri": f"gs://{preview_artifact.gcs_bucket}/{preview_artifact.gcs_object}",
        "maya_verdict": render_review.verdict.value,
        "approved_for_master": render_review.approved_for_master,
        "summary": render_review.summary,
        "confidence": render_review.confidence,
        "issues": [i.model_dump() for i in render_review.issues],
        "master_artifact_id": master_art.artifact_id if master_art else None,
        "master_gcs_uri": f"gs://{master_art.gcs_bucket}/{master_art.gcs_object}" if master_art else None,
        "usage": usage_info,
    }

    result_path = Path("real_render_review_acceptance_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, default=str)
    print(f"\nSaved results to {result_path}")


if __name__ == "__main__":
    asyncio.run(main())
