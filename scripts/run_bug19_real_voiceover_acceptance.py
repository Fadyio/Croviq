"""Execute BUG 19 Real Voiceover Preview Generation and Acceptance for prod_473209137802."""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))

import firebase_admin
from croviq_api.config import get_settings
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.studio_voice_repository import FirestoreStudioVoiceRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_api.workspaces.agent_config_repository import FirestoreAgentConfigRepository
from croviq_api.workspaces.repository import FirestoreWorkspaceRepository
from croviq_agents.client import GoogleGenAIClient, generate_fallback_narration_rewrite
from croviq_agents.voice import StudioVoiceSynthesizer, VoiceCatalog
from croviq_domain.agent_config import NarrationMode, VoiceSettingsConfig
from croviq_domain.edl import EditDecisionList, VoiceoverSegment, derive_keep_segments, map_source_time_to_edited
from croviq_domain.narration import NarrationSegment, NarrationSegmentStatus, StudioVoiceResult
from croviq_domain.render import ArtifactStatus, ArtifactType, RenderArtifact, build_render_artifact_gcs_object_path
from croviq_domain.transcript import CorrectedTranscript, CorrectedTranscriptSegment, EntailmentVerdict, ScriptCorrectionChangeType
from croviq_media.render import FFmpegRenderService

PROJECT_ID = "croviq-506602"
PRODUCTION_ID = "prod_473209137802"

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": PROJECT_ID})


async def main():
    print("=" * 80)
    print("CROVIQ BUG 19 — ACTIVE EDL VOICEOVER PREVIEW ACCEPTANCE")
    print(f"Production ID: {PRODUCTION_ID}")
    print("=" * 80)

    prod_repo = FirestoreProductionRepository(project_id=PROJECT_ID)
    tr_repo = FirestoreTranscriptRepository(project_id=PROJECT_ID)
    edl_repo = FirestoreEDLRepository(project_id=PROJECT_ID)
    render_repo = FirestoreRenderRepository(project_id=PROJECT_ID)
    sv_repo = FirestoreStudioVoiceRepository(project_id=PROJECT_ID)
    workspace_repo = FirestoreWorkspaceRepository(project_id=PROJECT_ID)
    agent_cfg_repo = FirestoreAgentConfigRepository(project_id=PROJECT_ID)
    storage = GoogleMediaStorage(project_id=PROJECT_ID)
    genai_client = GoogleGenAIClient(project_id=PROJECT_ID)
    render_service = FFmpegRenderService()

    prod = await prod_repo.get_production(PRODUCTION_ID)
    if not prod:
        print("ERROR: Production not found")
        sys.exit(1)

    transcript = await tr_repo.get_transcript_by_production_id(PRODUCTION_ID)
    if not transcript:
        print("ERROR: Transcript not found")
        sys.exit(1)

    active_edl = await edl_repo.get_latest_edl(PRODUCTION_ID)
    if not active_edl:
        print("ERROR: Active EDL not found")
        sys.exit(1)

    print(f"Source duration: {active_edl.source_duration_ms} ms")
    print(f"Active EDL ID: {active_edl.edl_id}")
    print(f"EDL version: {active_edl.version}")
    print(f"Active cut count: {len(active_edl.active_cuts)}")
    print(f"Target edited duration: {active_edl.estimated_target_duration_ms} ms")

    # Voice selection from config
    voice_cfg = await agent_cfg_repo.get_voice_settings(prod.workspace_id) if prod.workspace_id else None
    selected_voice = voice_cfg.selected_voice if voice_cfg else "Aoede"
    voice_item = VoiceCatalog.get_voice(selected_voice)
    print(f"Studio Voice: {selected_voice} ({voice_item.description if voice_item else 'Prebuilt Voice'})")

    # Step 1: Fetch or derive source-grounded corrected script under active EDL
    cached_script = await tr_repo.get_corrected_transcript_by_production_id(
        PRODUCTION_ID, edl_id=active_edl.edl_id
    )
    if cached_script and cached_script.segments:
        corrected_script = cached_script
        print(f"\nLoaded persisted canonical corrected script {corrected_script.transcript_id} ({len(corrected_script.segments)} segments)")
    else:
        video_uri = f"gs://{prod.source_media.gcs_bucket}/{prod.source_media.gcs_object}"
        corrected_script, usage = await genai_client.correct_transcript_with_video_grounding(
            video_uri=video_uri,
            mime_type="video/mp4",
            transcript=transcript,
            edl=active_edl,
            production_id=PRODUCTION_ID,
        )
        await tr_repo.save_corrected_transcript(corrected_script, edl_id=active_edl.edl_id)
        print(f"\nGenerated and persisted new canonical corrected script {corrected_script.transcript_id}")

    print(f"Total canonical segments: {len(corrected_script.segments)}")
    print(f"Corrections count: {corrected_script.corrections_count}")
    print(f"Meaning preserved: {corrected_script.meaning_preserved}")

    # Prepare segments with positive edited duration
    prepared_segments = []
    for seg in corrected_script.segments:
        ed_start = seg.edited_start_ms if seg.edited_start_ms is not None else map_source_time_to_edited(seg.source_start_ms, active_edl)
        ed_end = seg.edited_end_ms if seg.edited_end_ms is not None else map_source_time_to_edited(seg.source_end_ms, active_edl)
        avail_ms = ed_end - ed_start
        if avail_ms <= 0:
            continue
        text_to_synthesize = seg.corrected_text or seg.original_text
        prepared_segments.append({
            "segment_id": seg.segment_id,
            "source_start_ms": seg.source_start_ms,
            "source_end_ms": seg.source_end_ms,
            "edited_start_ms": ed_start,
            "edited_end_ms": ed_end,
            "available_duration_ms": avail_ms,
            "text": text_to_synthesize,
            "original_text": seg.original_text,
            "change_type": seg.change_type.value if hasattr(seg.change_type, "value") else str(seg.change_type),
        })

    def _needs_merge(s_dict: dict) -> bool:
        avail = s_dict["available_duration_ms"]
        word_count = len(s_dict["text"].split())
        return avail < 1000 or (avail < 2000 and word_count * 310 > avail)

    # Merge tight segments with adjacent segments so natural TTS cadence fits comfortably
    merged_segments = []
    i = 0
    while i < len(prepared_segments):
        curr = dict(prepared_segments[i])
        if _needs_merge(curr) and i + 1 < len(prepared_segments):
            nxt = prepared_segments[i + 1]
            curr["segment_id"] = f"{curr['segment_id']}_{nxt['segment_id']}"
            curr["source_end_ms"] = nxt["source_end_ms"]
            curr["edited_end_ms"] = nxt["edited_end_ms"]
            curr["available_duration_ms"] = curr["edited_end_ms"] - curr["edited_start_ms"]
            curr["text"] = f"{curr['text']} {nxt['text']}".strip()
            curr["original_text"] = f"{curr['original_text']} {nxt['original_text']}".strip()
            merged_segments.append(curr)
            i += 2
        elif _needs_merge(curr) and merged_segments:
            prev = merged_segments[-1]
            prev["segment_id"] = f"{prev['segment_id']}_{curr['segment_id']}"
            prev["source_end_ms"] = curr["source_end_ms"]
            prev["edited_end_ms"] = curr["edited_end_ms"]
            prev["available_duration_ms"] = prev["edited_end_ms"] - prev["edited_start_ms"]
            prev["text"] = f"{prev['text']} {curr['text']}".strip()
            prev["original_text"] = f"{prev['original_text']} {curr['original_text']}".strip()
            i += 1
        else:
            merged_segments.append(curr)
            i += 1

    synthesizer = StudioVoiceSynthesizer()

    async def tts_fn(text: str, voice_id: str) -> tuple[int, bytes]:
        # Real Google Gemini TTS synthesis
        return await genai_client.synthesize_studio_voice(
            text=text,
            voice_id=voice_id,
            production_id=PRODUCTION_ID,
        )

    async def leo_rewrite_fn(orig_text: str, max_dur_s: float, attempt: int) -> str:
        return await genai_client.generate_narration_rewrite(
            original_text=orig_text,
            available_duration_s=max_dur_s,
            attempt=attempt,
            production_id=PRODUCTION_ID,
        )

    fit_tasks = []
    for item in merged_segments:
        fit_tasks.append(
            synthesizer.fit_narration_segment_with_audio(
                segment_id=item["segment_id"],
                production_id=PRODUCTION_ID,
                source_start_ms=item["source_start_ms"],
                source_end_ms=item["source_end_ms"],
                available_duration_ms=item["available_duration_ms"],
                original_text=item["text"],
                voice_id=selected_voice,
                tts_fn=tts_fn,
                rewrite_fn=leo_rewrite_fn,
                edited_start_ms=item["edited_start_ms"],
                edited_end_ms=item["edited_end_ms"],
                change_type=item["change_type"],
            )
        )

    results = list(await asyncio.gather(*fit_tasks))
    narration_segments = [r[0] for r in results]
    accepted_segments = [
        (seg, pcm_bytes)
        for seg, pcm_bytes in results
        if seg.status == NarrationSegmentStatus.ACCEPTED and pcm_bytes and len(pcm_bytes) > 0 and seg.generated_duration_ms <= seg.available_duration_ms
    ]

    print("\n" + "=" * 110)
    print(f"{'SEG ID':<16} | {'EDITED TIME':<16} | {'BUDGET':<8} | {'TTS DUR':<8} | {'STATUS':<9} | {'TEXT'}")
    print("-" * 110)
    for s in narration_segments:
        ed_t = f"{(s.edited_start_ms or 0)/1000:.2f}s-{(s.edited_end_ms or 0)/1000:.2f}s"
        print(f"{s.segment_id:<16} | {ed_t:<16} | {s.available_duration_ms:<8} | {s.generated_duration_ms:<8} | {s.status.value:<9} | {s.rewritten_text}")
    print("=" * 110)

    if len(accepted_segments) != len(merged_segments):
        print(f"ERROR: Not all segments fit! ({len(accepted_segments)}/{len(merged_segments)})")
        sys.exit(1)

    # Render Voiceover Preview video
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        local_src = tmp_path / "source.mp4"
        local_narr = tmp_path / "narration.wav"
        local_out = tmp_path / "voiceover_preview.mp4"

        print("\nDownloading source media from GCS...")
        await storage.download_object_to_path(
            bucket=prod.source_media.gcs_bucket,
            object_name=prod.source_media.gcs_object,
            target_path=local_src,
        )

        sample_rate = 24000
        total_dur_ms = active_edl.estimated_target_duration_ms
        num_samples = int(sample_rate * total_dur_ms / 1000)
        audio_buffer = bytearray(num_samples * 2)
        speech_intervals = []

        for seg, pcm_bytes in accepted_segments:
            ed_start = seg.edited_start_ms
            ed_end = seg.edited_end_ms
            avail_ms = ed_end - ed_start
            if avail_ms <= 0:
                continue
            speech_intervals.append((ed_start, min(total_dur_ms, ed_start + seg.generated_duration_ms)))
            start_sample = int(sample_rate * ed_start / 1000)
            start_byte = start_sample * 2
            copy_len = min(len(pcm_bytes), avail_ms * 48, len(audio_buffer) - start_byte)
            if copy_len > 0 and start_byte < len(audio_buffer):
                audio_buffer[start_byte : start_byte + copy_len] = pcm_bytes[:copy_len]

        with wave.open(str(local_narr), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(bytes(audio_buffer))

        narration_gcs_obj = f"workspaces/{prod.workspace_id}/productions/{prod.production_id}/narration/studio_voice_narration.wav"
        await storage.upload_object_from_path(
            bucket=prod.source_media.gcs_bucket,
            object_name=narration_gcs_obj,
            source_path=local_narr,
            content_type="audio/wav",
        )

        print(f"Rendering Voiceover Preview with FFmpeg ({len(speech_intervals)} replacement intervals)...")
        render_res = render_service.render_voiceover_preview(
            source_path=local_src,
            edl=active_edl,
            narration_audio_path=local_narr,
            speech_intervals_ms=speech_intervals,
            output_path=local_out,
        )

        print(f"Render complete: duration={render_res.duration_ms}ms, size={render_res.size_bytes} bytes, video_codec={render_res.video_codec}, audio_codec={render_res.audio_codec}")

        # Run ffprobe verification on the output MP4
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration:stream=codec_name,width,height",
            "-of", "json",
            str(local_out),
        ]
        probe_out = subprocess.check_output(probe_cmd, text=True)
        probe_data = json.loads(probe_out)
        ffprobe_dur_s = float(probe_data["format"]["duration"])
        ffprobe_dur_ms = int(ffprobe_dur_s * 1000)
        print(f"FFprobe verified duration: {ffprobe_dur_ms}ms (target: {total_dur_ms}ms, diff: {abs(ffprobe_dur_ms - total_dur_ms)}ms)")

        # Upload artifacts
        now = datetime.now(timezone.utc)
        gcs_obj = build_render_artifact_gcs_object_path(
            workspace_id=prod.workspace_id,
            production_id=prod.production_id,
            edl_id=active_edl.edl_id,
            artifact_type=ArtifactType.VOICEOVER_PREVIEW,
        )
        await storage.upload_object_from_path(
            bucket=prod.source_media.gcs_bucket,
            object_name=gcs_obj,
            source_path=local_out,
            content_type="video/mp4",
        )

        art_id = f"art_vo_{active_edl.edl_id[:8]}"
        art = RenderArtifact(
            artifact_id=art_id,
            production_id=prod.production_id,
            edl_id=active_edl.edl_id,
            artifact_type=ArtifactType.VOICEOVER_PREVIEW,
            status=ArtifactStatus.completed,
            gcs_bucket=prod.source_media.gcs_bucket,
            gcs_object=gcs_obj,
            content_type="video/mp4",
            size_bytes=render_res.size_bytes,
            duration_ms=render_res.duration_ms,
            width=render_res.width,
            height=render_res.height,
            frame_rate=render_res.frame_rate,
            video_codec=render_res.video_codec,
            audio_codec=render_res.audio_codec,
            created_at=now,
            completed_at=now,
        )
        await render_repo.save_render_artifact(art)

        # Save StudioVoiceResult in repository
        sv_result = StudioVoiceResult(
            production_id=prod.production_id,
            voice_id=selected_voice,
            narration_mode="studio_voice",
            edl_id=active_edl.edl_id,
            edl_version=active_edl.version,
            corrected_script_version=corrected_script.transcript_id,
            segments=narration_segments,
            total_segments=len(merged_segments),
            accepted_segments=len(accepted_segments),
            all_within_budget=True,
            gcs_bucket=prod.source_media.gcs_bucket,
            gcs_object=narration_gcs_obj,
            preview_artifact_id=art.artifact_id,
            status="completed",
            created_at=now,
            updated_at=now,
        )
        await sv_repo.save(sv_result)

        # Update active EDL voiceover segments
        active_edl.voiceover_segments = [
            VoiceoverSegment(
                segment_id=s.segment_id,
                source_start_ms=s.source_start_ms,
                source_end_ms=s.source_end_ms,
                text=s.rewritten_text or s.original_text,
                original_text=s.original_text,
                voice_mode="PREBUILT_STUDIO_VOICE",
                voice_id=selected_voice,
                generated_duration_ms=s.generated_duration_ms,
                preview_artifact_id=art.artifact_id,
            )
            for s, _ in accepted_segments
        ]
        await edl_repo.save_edl(active_edl)

        print("\nSUCCESS: Voiceover Preview generated and saved to Firestore + GCS!")
        print(f"Artifact ID: {art.artifact_id}")
        print(f"Artifact URI: gs://{art.gcs_bucket}/{art.gcs_object}")
        print(f"Studio Voice Result: {sv_result.status} ({sv_result.accepted_segments}/{sv_result.total_segments} segments, voice={sv_result.voice_id})")
if __name__ == "__main__":
    asyncio.run(main())
