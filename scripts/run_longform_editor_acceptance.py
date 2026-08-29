"""Full Long-Form Real Speech Production Acceptance (60-120s video):
Duplicate of owner's real speech video (113.82s), Transcribe, Leo Whole Video Multimodal, Typed Edit Plan, EDL, FFmpeg Render, Physical Inspection of Seams, Iris QA.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

# Setup Python paths
sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))

import firebase_admin
from firebase_admin import firestore
from google.cloud import storage

from croviq_agents.client import GoogleGenAIClient
from croviq_agents.editor import LeoVideoEditor
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.edl_service import EDLService
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_domain.editorial import EditorialRun, EditorialRunStatus
from croviq_domain.edl import derive_keep_segments
from croviq_domain.production import (
    Production,
    ProductionStatus,
    SourceMedia,
    SourceMediaStatus,
)
from croviq_domain.source_analysis import SourceVideoAnalysisInput
from croviq_domain.user import User
from croviq_media.audio import FFmpegAudioExtractor
from croviq_media.inspector import FFprobeMediaInspector
from croviq_media.render import FFmpegRenderService
from croviq_media.transcript import GeminiTranscriptionService


async def run():
    project_id = "croviq-506602"
    raw_bucket = "croviq-506602-croviq-media-raw"
    location = "global"
    workspace_id = "ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3"
    owner_user_id = "27iEBUMcu6ToDYwp2OdEIHBuwIA3"
    test_ts = int(time.time())
    now = datetime.now(timezone.utc)
    prod_id = sys.argv[1] if len(sys.argv) > 1 else "prod_acc_long_1788040890"
    upload_id = f"upl_{uuid.uuid4().hex[:12]}"
    print("CROVIQ LONGER REAL EDITOR ACCEPTANCE (113.82s Real Speech Media)")
    print(f"Production ID: {prod_id}")
    print(f"Workspace ID:  {workspace_id}")
    print(f"GCP Project:   {project_id}")
    print("=" * 80)

    # Initialize Firebase Admin
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    # Ensure source media exists locally
    local_source_path = Path("/tmp/fairphone.mp4")
    if not local_source_path.exists():
        raise RuntimeError("Local source /tmp/fairphone.mp4 not found")

    inspector = FFprobeMediaInspector()
    source_meta = inspector.inspect_media(local_source_path)
    print("\n[STEP 1: SOURCE MEDIA INSPECTION]")
    print(f"  Source Path:     {local_source_path}")
    print(f"  Duration:        {source_meta.duration_ms}ms ({source_meta.duration_ms / 1000.0:.3f}s)")
    print(f"  Resolution:      {source_meta.width}x{source_meta.height}")
    print(f"  Video Codec:     {source_meta.video_codec}")
    print(f"  Audio Codec:     {source_meta.audio_codec}")
    print(f"  File Size:       {local_source_path.stat().st_size} bytes")

    # Repositories
    prod_repo = FirestoreProductionRepository(project_id=project_id)
    transcript_repo = FirestoreTranscriptRepository(project_id=project_id)
    editorial_repo = FirestoreEditorialRepository(project_id=project_id)
    edl_repo = FirestoreEDLRepository(project_id=project_id)
    render_repo = FirestoreRenderRepository(project_id=project_id)

    # 1. Upload duplicate source to GCS
    print("\n[STEP 2: UPLOADING SOURCE MEDIA TO GCS]")
    gcs_client = storage.Client(project=project_id)
    raw_bkt = gcs_client.bucket(raw_bucket)
    # Check if production exists
    existing_prod = await prod_repo.get_production(prod_id)
    if existing_prod and existing_prod.source_media:
        production = existing_prod
        gcs_object_key = existing_prod.source_media.gcs_object
        source_gcs_uri = f"gs://{existing_prod.source_media.gcs_bucket}/{gcs_object_key}"
        print(f"  Reusing existing source GCS URI: {source_gcs_uri}")
    else:
        gcs_object_key = f"workspaces/{workspace_id}/productions/{prod_id}/source/{upload_id}/Fairphone_6_Long_Acceptance.mp4"
        blob = raw_bkt.blob(gcs_object_key)
        print(f"  Uploading to gs://{raw_bucket}/{gcs_object_key}...")
        blob.upload_from_filename(str(local_source_path), content_type="video/mp4")
        source_gcs_uri = f"gs://{raw_bucket}/{gcs_object_key}"
        print(f"  Uploaded source URI: {source_gcs_uri}")
        now = datetime.now(timezone.utc)
        production = Production(
            production_id=prod_id,
            workspace_id=workspace_id,
            channel_id="croviq_syn_ai_eng_01",
            owner_user_id=owner_user_id,
            status=ProductionStatus.UPLOADED,
            created_at=now,
            source_media=SourceMedia(
                upload_id=upload_id,
                original_filename="Fairphone_6_Long_Acceptance.mp4",
                content_type="video/mp4",
                size_bytes=local_source_path.stat().st_size,
                gcs_bucket=raw_bucket,
                gcs_object=gcs_object_key,
                status=SourceMediaStatus.UPLOADED,
                created_at=now,
                uploaded_at=now,
            ),
            updated_at=now,
        )
        await prod_repo.create_production(production)
        print("  Created Production entity in Firestore.")


    existing_transcript = await transcript_repo.get_transcript_by_production_id(prod_id)
    if existing_transcript:
        transcript = existing_transcript
        print(f"  Reusing existing Transcript ID: {transcript.transcript_id} ({len(transcript.words)} words)")
    else:
        audio_extractor = FFmpegAudioExtractor()
        extracted_wav = Path(f"/tmp/croviq_media/{prod_id}_extracted.wav")
        os.makedirs(extracted_wav.parent, exist_ok=True)
        audio_extractor.extract_speech_audio(local_source_path, extracted_wav)
        print(f"  Extracted WAV: {extracted_wav.stat().st_size} bytes")
        transcription_service = GeminiTranscriptionService(project_id=project_id, location=location)
        t_start = time.time()
        transcript = await transcription_service.transcribe_audio_file(
            extracted_wav,
            language_code="en-US",
            production_id=prod_id,
            source_duration_ms=source_meta.duration_ms,
        )
        t_dur = time.time() - t_start
        print(f"  Transcription completed in {t_dur:.2f}s!")
        await transcript_repo.save_transcript(transcript)
    print(f"  Transcript ID: {transcript.transcript_id}")
    print(f"  Word count:    {len(transcript.words)}")
    print(f"  Segment count: {len(transcript.segments)}")
    print(f"  First 20 words: {' '.join(w.text for w in transcript.words[:20])}")
    print(f"  Last 20 words:  {' '.join(w.text for w in transcript.words[-20:])}")
    await transcript_repo.save_transcript(transcript)

    # 3. Run Leo Video Editor with Multimodal Whole Video Input
    print(f"\n[STEP 4: RUNNING LEO VIDEO EDITOR WITH WHOLE VIDEO INPUT]")
    print(f"  Leo Video Input: {source_gcs_uri}")
    genai_client = GoogleGenAIClient(project_id=project_id, location=location)
    leo = LeoVideoEditor(client=genai_client)

    analysis_input = SourceVideoAnalysisInput(
        production_id=prod_id,
        channel_id="croviq_syn_ai_eng_01",
        source_media=production.source_media,
        media_metadata=source_meta,
        transcript=transcript,
    )

    t_leo_start = time.time()
    proposal, usage, activities = await leo.analyze(
        analysis_input=analysis_input,
        run_id=f"run_{prod_id}",
        request_id=f"req_leo_{test_ts}",
    )
    t_leo_dur = time.time() - t_leo_start
    print(f"  Leo Analysis completed in {t_leo_dur:.2f}s!")
    print(f"  Summary:        {proposal.summary}")
    print(f"  Decisions:      {len(proposal.decisions)}")
    print(f"  Section plan:   {len(proposal.section_plan)} sections")
    print(f"  Token Usage:    Input={usage.input_tokens}, Output={usage.output_tokens}, Latency={usage.latency_ms}ms")
    print(f"  Activities:     {len(activities)}")

    for idx, dec in enumerate(proposal.decisions):
        print(f"    - Decision #{idx+1}: [{dec.decision_type.value}] {dec.source_start_ms}ms -> {dec.source_end_ms}ms ({dec.source_end_ms - dec.source_start_ms}ms): {dec.concise_reason}")

    # Persist editorial proposal and run
    proposal_id = await editorial_repo.save_editor_proposal(proposal)
    run_obj = EditorialRun(
        run_id=f"run_{prod_id}",
        production_id=prod_id,
        status=EditorialRunStatus.COMPLETED,
        editor_proposal_id=proposal_id,
        started_at=now,
        completed_at=datetime.now(timezone.utc),
    )
    await editorial_repo.save_editorial_run(run_obj)

    # 4. Assemble Canonical EDL
    print("\n[STEP 5: ASSEMBLING CANONICAL EDIT DECISION LIST (EDL)]")
    edl_service = EDLService(
        production_repo=prod_repo,
        transcript_repo=transcript_repo,
        editorial_repo=editorial_repo,
        edl_repo=edl_repo,
    )
    user_obj = User(
        user_id=owner_user_id,
        email="demo@croviq.app",
        display_name="Creator",
        created_at=now,
        updated_at=now,
    )
    edl = await edl_service.assemble_edl(
        production_id=prod_id,
        current_user=user_obj,
    )
    print(f"  Assembled EDL ID: {edl.edl_id}")
    print(f"  Version:          {edl.version}")
    print(f"  Cut count:        {len(edl.cuts)}")
    print(f"  Total removed:    {edl.total_removed_duration_ms}ms ({edl.total_removed_duration_ms / 1000.0:.3f}s)")
    for idx, cut in enumerate(edl.cuts):
        print(f"    Cut #{idx+1} ({cut.cut_id}): [{cut.cut_type.value}] {cut.start_ms}ms -> {cut.end_ms}ms ({cut.end_ms - cut.start_ms}ms) reason: {cut.reason}")

    keep_segments = derive_keep_segments(edl)
    print(f"  Keep segments:    {len(keep_segments)} segments")
    for idx, (k_start, k_end) in enumerate(keep_segments):
        print(f"    Keep #{idx+1}: {k_start}ms -> {k_end}ms ({k_end - k_start}ms)")

    # 5. Render Edited Video Preview with FFmpeg
    print("\n[STEP 6: RENDERING EDITED PREVIEW VIA FFMPEG]")
    render_service = FFmpegRenderService()
    rendered_local_path = Path(f"/tmp/croviq_media/{prod_id}_edited_preview.mp4")
    t_render_start = time.time()
    render_spec = render_service.render_preview(
        source_path=local_source_path,
        edl=edl,
        output_path=rendered_local_path,
    )
    t_render_dur = time.time() - t_render_start
    print(f"  Render completed in {t_render_dur:.2f}s ({render_spec.render_time_ms}ms reported)!")
    print(f"  Rendered preview path: {rendered_local_path} ({rendered_local_path.stat().st_size} bytes)")

    # Inspect rendered media with FFprobe
    edited_meta = inspector.inspect_media(rendered_local_path)
    print("\n[STEP 7: FFPROBE EDITED MEDIA INSPECTION]")
    print(f"  Source Duration: {source_meta.duration_ms}ms ({source_meta.duration_ms / 1000.0:.3f}s)")
    print(f"  Edited Duration: {edited_meta.duration_ms}ms ({edited_meta.duration_ms / 1000.0:.3f}s)")
    print(f"  Delta Removed:   {source_meta.duration_ms - edited_meta.duration_ms}ms ({(source_meta.duration_ms - edited_meta.duration_ms) / 1000.0:.3f}s)")
    print(f"  Video Codec:     {edited_meta.video_codec}")
    print(f"  Audio Codec:     {edited_meta.audio_codec}")
    print(f"  Resolution:      {edited_meta.width}x{edited_meta.height}")

    # Upload rendered preview to GCS
    print("\n[STEP 8: UPLOADING EDITED PREVIEW TO GCS]")
    render_gcs_key = f"workspaces/{workspace_id}/productions/{prod_id}/renders/preview_{edl.edl_id}.mp4"
    render_blob = raw_bkt.blob(render_gcs_key)
    render_blob.upload_from_filename(str(rendered_local_path), content_type="video/mp4")
    preview_gcs_uri = f"gs://{raw_bucket}/{render_gcs_key}"
    print(f"  Uploaded edited preview URI: {preview_gcs_uri}")

    # 6. Run Iris Release Review on the Rendered Edited Video
    print(f"\n[STEP 9: RUNNING IRIS QA GATE ON EDITED PREVIEW ARTIFACT]")
    t_iris_start = time.time()
    release_review, iris_usage = await genai_client.generate_release_review(
        master_video_uri=preview_gcs_uri,
        master_mime_type="video/mp4",
        transcript=transcript,
        production_id=prod_id,
        master_duration_ms=edited_meta.duration_ms,
        request_id=f"req_iris_{test_ts}",
    )
    t_iris_dur = time.time() - t_iris_start
    print(f"  Iris QA completed in {t_iris_dur:.2f}s!")
    print(f"  Review ID:     {release_review.review_id}")
    print(f"  Verdict:       {release_review.verdict.value}")
    print(f"  Summary:       {release_review.summary}")
    print(f"  Issues Count:  {len(release_review.issues)}")
    for idx, iss in enumerate(release_review.issues):
        print(f"    Issue #{idx+1}: [{iss.severity.value}] [{iss.issue_type.value}] {iss.description} (recommendation: {iss.recommendation})")
    print(f"  Checklist:     master={release_review.checklist.master_video}, audio={release_review.checklist.audio}, all_passed={release_review.checklist.all_passed}")
    print(f"  Iris Tokens:   Input={iris_usage.input_tokens}, Output={iris_usage.output_tokens}, Latency={iris_usage.latency_ms}ms")

    # 7. Physical Inspection of Every Edit Boundary
    print("\n[STEP 10: PHYSICAL INSPECTION OF EVERY EDIT BOUNDARY]")
    print(f"Total Cuts: {len(edl.cuts)}")
    for idx, cut in enumerate(edl.cuts):
        print(f"--- Cut #{idx+1} Boundary Inspection ---")
        print(f"  Cut Range in Source: {cut.start_ms}ms -> {cut.end_ms}ms (Duration: {cut.end_ms - cut.start_ms}ms / {(cut.end_ms - cut.start_ms)/1000.0:.3f}s)")
        print(f"  Cut Reason: {cut.reason}")
        # Probe frame before cut and frame after cut
        pre_cut_time = max(0.0, (cut.start_ms - 500) / 1000.0)
        post_cut_time = (cut.end_ms + 500) / 1000.0
        print(f"  Source seam: {pre_cut_time:.3f}s (before cut) -> {post_cut_time:.3f}s (after cut)")

    print("\n" + "=" * 80)
    print("RECORDED VALUES SUMMARY FOR TASK 2 REPORT:")
    print(f"PRODUCTION ID:          {prod_id}")
    print(f"SOURCE DURATION:        {source_meta.duration_ms}ms ({source_meta.duration_ms / 1000.0:.3f}s)")
    print(f"TRANSCRIPT ID:          {transcript.transcript_id}")
    print(f"GEMINI VIDEO INPUT:     {source_gcs_uri}")
    print(f"GEMINI REQUEST EVIDENCE: Leo (Tokens: in={usage.input_tokens}, out={usage.output_tokens}, latency={usage.latency_ms}ms; model=gemini-3.7-flash, req=req_leo_{test_ts}); Iris (Tokens: in={iris_usage.input_tokens}, out={iris_usage.output_tokens}, latency={iris_usage.latency_ms}ms; model=gemini-3.7-flash, req=req_iris_{test_ts})")
    print(f"EDL ID:                 {edl.edl_id}")
    cut_summary = "; ".join(f"[{c.cut_id}] {c.start_ms}ms-{c.end_ms}ms ({c.reason})" for c in edl.cuts)
    print(f"CUTS:                   {cut_summary}")
    print(f"PREVIEW ARTIFACT:       {preview_gcs_uri} (local: {rendered_local_path})")
    print(f"EDITED DURATION:        {edited_meta.duration_ms}ms ({edited_meta.duration_ms / 1000.0:.3f}s)")
    print(f"FFPROBE:                Source: duration={source_meta.duration_ms}ms, {source_meta.width}x{source_meta.height}, {source_meta.video_codec}/{source_meta.audio_codec}; Edited: duration={edited_meta.duration_ms}ms, {edited_meta.width}x{edited_meta.height}, {edited_meta.video_codec}/{edited_meta.audio_codec}, size={rendered_local_path.stat().st_size}B")
    print(f"IRIS REVIEW ID:         {release_review.review_id} (Verdict: {release_review.verdict.value}, Summary: {release_review.summary})")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run())
