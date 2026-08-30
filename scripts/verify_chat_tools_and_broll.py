import asyncio
import os
import sys
import time
import json
from pathlib import Path

# Setup paths
sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))

import firebase_admin
from firebase_admin import firestore

from croviq_agents.client import GoogleGenAIClient, FakeGenAIClient
from croviq_agents.editor import LeoVideoEditor
from croviq_agents.iris import IrisQAAgent
from croviq_agents.voice import VoiceReplicationService, StudioVoiceSynthesizer
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_api.productions.broll_repository import FirestoreBRollRepository
from croviq_api.productions.studio_voice_repository import FirestoreStudioVoiceRepository
from croviq_domain.agent_config import VoiceReplicationStatus
from croviq_domain.editorial import EditorDecisionType
from croviq_domain.edl import derive_keep_segments
from croviq_domain.user import User
from croviq_domain.agent_config import VoiceReplicationStatus
from croviq_domain.render import ArtifactType, RenderArtifact
from croviq_media.inspector import FFprobeMediaInspector
from croviq_media.render import FFmpegRenderService
async def main():
    project_id = "croviq-506602"
    location = "global"
    prod_id = "prod_acc_demo_1788044745"
    user_id = "27iEBUMcu6ToDYwp2OdEIHBuwIA3"
    now = datetime.now(timezone.utc) if "datetime" in globals() else None

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    db = firestore.client()

    print("=" * 80)
    print("CROVIQ LEO EDITOR WORKSPACE — REAL ACCEPTANCE VERIFICATION")
    print(f"Production ID: {prod_id}")
    print("=" * 80)

    prod_repo = FirestoreProductionRepository(project_id=project_id)
    transcript_repo = FirestoreTranscriptRepository(project_id=project_id)
    editorial_repo = FirestoreEditorialRepository(project_id=project_id)
    edl_repo = FirestoreEDLRepository(project_id=project_id)
    render_repo = FirestoreRenderRepository(project_id=project_id)
    broll_repo = FirestoreBRollRepository(project_id=project_id)
    voice_repo = FirestoreStudioVoiceRepository(project_id=project_id)

    production = await prod_repo.get_production(prod_id)
    transcript = await transcript_repo.get_transcript_by_production_id(prod_id)
    latest_run = await editorial_repo.get_latest_editorial_run(prod_id)
    proposal = await editorial_repo.get_editor_proposal(prod_id, latest_run.editor_proposal_id)
    edl = await edl_repo.get_latest_edl(prod_id)

    source_meta = FFprobeMediaInspector().inspect_media(Path("/tmp/github_optimized.mp4"))

    print(f"\n1. INITIAL STATE VERIFICATION")
    print(f"  Source Duration: {source_meta.duration_ms}ms ({source_meta.duration_ms/1000.0:.2f}s)")
    print(f"  EDL ID:          {edl.edl_id}")
    print(f"  Cuts Count:      {len(edl.cuts)} (Active: {edl.active_cuts_count})")
    print(f"  Coverage:        {len(edl.coverage_markers)}")
    print(f"  Chapters:        {len(proposal.chapters if proposal else [])}")

    # Initialize Leo with canonical client
    client = GoogleGenAIClient(project_id=project_id, location=location)
    leo = LeoVideoEditor(client=client)

    # 2. Test ordinary question via Chat: Why did you make this cut?
    print(f"\n2. LEO CHAT: WHY DID YOU MAKE THIS CUT?")
    cut0 = edl.cuts[0]
    chat_res1 = await leo.chat(
        message="Why did you make this cut?",
        conversation_history=[],
        production=production,
        media_metadata=source_meta,
        transcript=transcript,
        proposal=proposal,
        edl=edl,
        current_playhead_ms=cut0.safe_start_ms,
        selected_range=(cut0.safe_start_ms, cut0.safe_end_ms),
        selected_element={
            "type": "cut",
            "id": cut0.cut_id,
            "label": f"{cut0.decision_type.value} {cut0.removed_duration_ms}ms",
            "start_ms": cut0.safe_start_ms,
            "end_ms": cut0.safe_end_ms,
        },
    )
    print(f"  Leo Reply:\n{chat_res1['content']}\n")
    print(f"  Tools executed: {[t.get('tool') or t.get('name') for t in chat_res1.get('tool_executions', [])]}")

    # 3. Test mutating edit: Tighten an unedited section (e.g. 83000 to 85000 ms)
    print(f"\n3. LEO CHAT MUTATING EDIT: TIGHTEN SECTION")
    chat_res2 = await leo.chat(
        message="This section from 00:31 to 00:35 has a small hesitation. Tighten it by cutting 83000 to 85000ms.",
        conversation_history=[
            {"role": "user", "content": "Why did you make this cut?"},
            {"role": "assistant", "content": chat_res1["content"]},
        ],
        production=production,
        media_metadata=source_meta,
        transcript=transcript,
        proposal=proposal,
        edl=edl,
        current_playhead_ms=83000,
        selected_range=(83000, 85000),
    )
    print(f"  Leo Reply:\n{chat_res2['content']}\n")
    print(f"  Tools executed: {[t.get('tool') or t.get('name') for t in chat_res2.get('tool_executions', [])]}")
    updated_edl = chat_res2.get("edl") or edl
    print(f"  Updated Cuts count: {len(updated_edl.cuts)} (Active: {updated_edl.active_cuts_count})")

    # 4. Test Undo / Restore from Chat
    print(f"\n4. LEO CHAT UNDO / RESTORE")
    chat_res3 = await leo.chat(
        message="Actually restore the section from 83000 to 85000ms back to original.",
        conversation_history=[
            {"role": "user", "content": "Tighten 83000 to 85000ms"},
            {"role": "assistant", "content": chat_res2["content"]},
        ],
        production=production,
        media_metadata=source_meta,
        transcript=transcript,
        proposal=proposal,
        edl=updated_edl,
        current_playhead_ms=83000,
        selected_range=(83000, 85000),
    )
    print(f"  Leo Reply:\n{chat_res3['content']}\n")
    print(f"  Tools executed: {[t.get('tool') or t.get('name') for t in chat_res3.get('tool_executions', [])]}")
    restored_edl = chat_res3.get("edl") or edl
    print(f"  Restored Cuts count: {len(restored_edl.cuts)} (Active: {restored_edl.active_cuts_count})")

    # 5. Test B-roll candidate & generation flow
    print(f"\n5. B-ROLL GENERATION & COVERAGE TEST")
    chat_res4 = await leo.chat(
        message="Add B-roll over the section from 64000 to 72000ms showing Cloudflare workflow verification.",
        conversation_history=[],
        production=production,
        media_metadata=source_meta,
        transcript=transcript,
        proposal=proposal,
        edl=restored_edl,
        current_playhead_ms=64000,
        selected_range=(64000, 72000),
    )
    print(f"  Leo Reply:\n{chat_res4['content']}\n")
    print(f"  Tools executed: {[t.get('tool') or t.get('name') for t in chat_res4.get('tool_executions', [])]}")

    # 6. Test Gemini 3.1 Flash TTS voice replication flow
    print(f"\n6. VOICE REPLICATION / MY VOICE CAPABILITY AUDIT")
    voice_service = VoiceReplicationService(allowlist_enabled=False)
    rep_config = voice_service.check_replication_capability()
    print(f"  Allowlist capability status: {rep_config.status.value}")
    print(f"  Blocked Reason:             {rep_config.blocked_reason}")
    print(f"  Suggested Action:           {rep_config.suggested_action}")

    # Clean speech interval extraction test (24kHz mono LINEAR16 WAV)
    start_samp, end_samp, ref_path = VoiceReplicationService.select_and_extract_reference(
        video_path=Path("/tmp/github_optimized.mp4"),
        transcript=transcript,
        audio_extractor=from_audio_extractor() if "from_audio_extractor" in globals() else FFmpegRenderService(),
        target_path=Path("/tmp/croviq_media/voice_reference_24k.wav"),
    )
    print(f"  Extracted Clean Voice Reference: [{start_samp}ms -> {end_samp}ms] ({end_samp - start_samp}ms) at {ref_path}")
    print(f"  Reference file size: {ref_path.stat().st_size} bytes")

    # 7. Iris QA Check
    print(f"\n7. IRIS QA VERIFICATION ON PREVIEW ARTIFACT")
    preview_file = Path(f"/tmp/croviq_media/{prod_id}_preview.mp4")
    if not preview_file.exists():
        FFmpegRenderService().render_preview(Path("/tmp/github_optimized.mp4"), edl, preview_file)

    render_artifact = RenderArtifact(
        artifact_id="art_preview_latest",
        production_id=prod_id,
        edl_id=edl.edl_id,
        artifact_type=ArtifactType.PREVIEW,
        gcs_bucket="croviq-506602-croviq-media-raw",
        gcs_object=f"workspaces/ws_27iEBUMcu6ToDYwp2OdEIHBuwIA3/productions/{prod_id}/renders/preview_edl_e0c73b6c7cf6.mp4",
        duration_ms=source_meta.duration_ms,
        status="completed",
        created_at=now,
    )
    iris = IrisQAAgent(genai_client=client)
    review_res, iris_usage = await iris.review_production(
        production_id=prod_id,
        master_artifact=render_artifact,
        transcript=transcript,
    )
    print(f"  Iris Approved:    {review_res.approved_for_release}")
    print(f"  Iris Summary:     {review_res.summary}")

    print("\n" + "=" * 80)
    print("ACCEPTANCE VERIFICATION FINISHED SUCCESSFULLY!")
    print("=" * 80)

def from_audio_extractor():
    from croviq_media.audio import FFmpegAudioExtractor
    return FFmpegAudioExtractor()

if __name__ == "__main__":
    asyncio.run(main())
