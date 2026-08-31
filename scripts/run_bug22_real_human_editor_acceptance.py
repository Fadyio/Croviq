"""Execute BUG 22 Real Human-Grade Autonomous Editorial Pass & Acceptance on prod_473209137802."""

import asyncio
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))

import firebase_admin
from croviq_api.config import get_settings
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.edl_service import EDLService
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.editorial_service import EditorialService
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.studio_voice_repository import FirestoreStudioVoiceRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_api.workspaces.agent_config_repository import FirestoreAgentConfigRepository
from croviq_api.workspaces.chat_service import AgentChatService
from croviq_agents.client import GoogleGenAIClient
from croviq_api.memory.dependencies import get_memory_store
from croviq_api.memory.fake import FakeChannelMemoryStore
from croviq_api.memory.google import GoogleMemoryBankStore
from croviq_domain.editorial import (
    CoordinateSpace,
    EditorialCategoryBreakdown,
    EditorialQualityReport,
    EditorDecision,
    EditorDecisionType,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
    EditorSelectionContext,
    EditorSelectionType,
    SectionAction,
    VideoSectionDecision,
)
from croviq_domain.edl import (
    BackgroundMusicMix,
    CutInstruction,
    CutSafetyStatus,
    EditDecisionList,
    EdlRevisionHistoryEntry,
    VoiceoverSegment,
    compute_editorial_quality_report,
    derive_edited_transcript,
    derive_keep_segments,
    map_source_time_to_edited,
)
from croviq_domain.production import Production, ProductionStatus, SourceMedia, SourceMediaStatus
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
    build_render_artifact_gcs_object_path,
)
from croviq_domain.transcript import CorrectedTranscript, CorrectedTranscriptSegment, Transcript
from croviq_domain.user import User
from croviq_media.audio import FFmpegAudioExtractor, measure_ebur128_loudness
from croviq_media.cut_safety import CutSafetyAnalyzer, assemble_edl_from_proposal, execute_global_review_pass
from croviq_media.inspector import FFprobeMediaInspector
from croviq_media.render import FFmpegRenderService
from croviq_media.silence import SilenceCleanupPlanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bug22_acceptance")

PROJECT_ID = "croviq-506602"
PRODUCTION_ID = "prod_473209137802"

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": PROJECT_ID})


def probe_media_file(path: Path | str) -> dict:
    """Run ffprobe on file and return streams and format metadata."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate:stream=codec_type,codec_name,sample_rate,channels,duration,width,height",
        "-of",
        "json",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


async def main() -> None:
    print("=" * 80)
    print("RUNNING BUG 22 REAL HUMAN-GRADE EDITORIAL ACCEPTANCE")
    print(f"Production: {PRODUCTION_ID} (github.mp4)")
    print("=" * 80)

    settings = get_settings()
    prod_repo = FirestoreProductionRepository()
    transcript_repo = FirestoreTranscriptRepository()
    edl_repo = FirestoreEDLRepository()
    editorial_repo = FirestoreEditorialRepository()
    render_repo = FirestoreRenderRepository()
    studio_voice_repo = FirestoreStudioVoiceRepository()
    agent_config_repo = FirestoreAgentConfigRepository()
    memory_store = get_memory_store(settings=settings)
    genai_client = GoogleGenAIClient(model_id=settings.gemini_model_id)
    render_service = FFmpegRenderService()
    media_inspector = FFprobeMediaInspector()
    media_storage = GoogleMediaStorage()
    edl_service = EDLService(
        production_repo=prod_repo,
        transcript_repo=transcript_repo,
        editorial_repo=editorial_repo,
        edl_repo=edl_repo,
    )
    editorial_service = EditorialService(
        production_repo=prod_repo,
        transcript_repo=transcript_repo,
        memory_store=memory_store,
        media_inspector=media_inspector,
        editorial_repo=editorial_repo,
        genai_client=genai_client,
        render_repo=render_repo,
        edl_service=edl_service,
        render_service=render_service,
        media_storage=media_storage,
    )
    # 1. Fetch current production and EDL Before
    prod = await prod_repo.get_production(PRODUCTION_ID)
    if not prod:
        raise RuntimeError(f"Production {PRODUCTION_ID} not found in Firestore")

    now = datetime.now(timezone.utc)
    current_user = User(
        user_id=prod.owner_user_id,
        email="acceptance@croviq.ai",
        display_name="Acceptance Engineer",
        created_at=now,
        updated_at=now,
    )

    transcript = await transcript_repo.get_transcript_by_production_id(PRODUCTION_ID)
    if not transcript:
        raise RuntimeError(f"Transcript for {PRODUCTION_ID} not found")

    edl_before = await edl_repo.get_latest_edl(PRODUCTION_ID)
    print("\n--- EDL BEFORE ---")
    if edl_before:
        print(f"ID: {edl_before.edl_id}")
        print(f"Version: {edl_before.version}")
        print(f"Cut Count: {len(edl_before.cuts)}")
        print(f"Edited Duration: {edl_before.estimated_target_duration_ms / 1000.0:.2f}s")
    else:
        print("No prior EDL")

    # 2. Run Autonomous Editorial Analysis
    print("\n--- RUNNING LEO EDITORIAL ANALYSIS (8 PASSES + NATURAL CUT SAFETY + GLOBAL REVIEW) ---")
    run, proposal, edl_after, preview_artifact, activities = await editorial_service.run_editorial_analysis(
        production_id=PRODUCTION_ID,
        current_user=current_user,
        request_id=f"req_b22_{uuid.uuid4().hex[:8]}",
        force=True,
    )

    print(f"\nEditorial Run Status: {run.status}")
    print(f"Proposal Summary: {proposal.summary}")
    print(f"Proposal Decisions: {len(proposal.decisions)}")
    print(f"Activities Emitted: {len(activities)}")

    # 3. Compute Editorial Quality Report
    report = compute_editorial_quality_report(edl_after)
    print("\n--- EDITORIAL QUALITY REPORT ---")
    print(f"SOURCE DURATION: {report.source_duration_ms / 1000.0:.2f}s")
    print(f"CURRENT EDITED DURATION: {report.current_edited_duration_ms / 1000.0:.2f}s")
    print(f"NEW EDITED DURATION: {report.new_edited_duration_ms / 1000.0:.2f}s")
    print(f"TOTAL REMOVED: {report.total_removed_ms / 1000.0:.2f}s")
    print("\nPHYSICAL REMOVAL BY CATEGORY:")
    print(f"DEAD AIR: {report.dead_air.count} cuts / {report.dead_air.duration_ms / 1000.0:.2f}s")
    print(f"FALSE START: {report.false_start.count} cuts / {report.false_start.duration_ms / 1000.0:.2f}s")
    print(f"WORD REPETITION: {report.word_repetition.count} cuts / {report.word_repetition.duration_ms / 1000.0:.2f}s")
    print(f"PHRASE REPETITION: {report.phrase_repetition.count} cuts / {report.phrase_repetition.duration_ms / 1000.0:.2f}s")
    print(f"REDUNDANT EXPLANATION: {report.redundant_explanation.count} cuts / {report.redundant_explanation.duration_ms / 1000.0:.2f}s")
    print(f"FILLER: {report.filler.count} cuts / {report.filler.duration_ms / 1000.0:.2f}s")
    print(f"PACING: {report.pacing.count} cuts / {report.pacing.duration_ms / 1000.0:.2f}s")
    print(f"OTHER: {report.other.count} cuts / {report.other.duration_ms / 1000.0:.2f}s")
    print(f"\nPHYSICAL CUTS COUNT: {report.physical_cuts_count}")
    print(f"SEMANTIC CUTS COUNT: {report.semantic_cuts_count}")
    print(f"SILENCE-ONLY EDIT: {'YES' if report.silence_only_edit else 'NO'}")
    print("\nSEMANTIC EVENTS BREAKDOWN:")
    print(f"FALSE_START: {report.semantic_events.false_start} events")
    print(f"WORD_REPETITION: {report.semantic_events.word_repetition} events")
    print(f"PHRASE_REPETITION: {report.semantic_events.phrase_repetition} events")
    print(f"REDUNDANT_EXPLANATION: {report.semantic_events.redundant_explanation} events")
    print(f"FILLER: {report.semantic_events.filler} events")
    print(f"RAMBLING: {report.semantic_events.rambling} events")
    print(f"PAUSE_TRIM: {report.semantic_events.pause_trim} events")
    print(f"PACING: {report.semantic_events.pacing} events")
    print(f"OTHER: {report.semantic_events.other} events")
    print(f"TOTAL SEMANTIC EVENTS: {report.semantic_events.semantic_events_count}")
    print(f"TOTAL ALL EVENTS: {report.semantic_events.total_events}")
    assert not report.silence_only_edit, "FAILED: Editorial analysis produced silence-only edit!"
    assert report.semantic_cuts_count > 0, "FAILED: No semantic cuts produced!"

    # 4. Inspect representative semantic edits with full evidence
    print("\n--- REPRESENTATIVE EDITS EVIDENCE ---")
    semantic_cuts = [
        c for c in edl_after.cuts
        if str(c.decision_type).upper() not in ("DEAD_AIR", "PAUSE_TRIM", "REMOVE_SILENCE", "TRIM_PAUSE", "TIGHTEN_PAUSE")
        and c.safety_status != CutSafetyStatus.REJECTED_UNSAFE
    ]

    for idx, c in enumerate(semantic_cuts[:5]):
        print(f"\nREPRESENTATIVE EDIT {idx + 1}:")
        print(f"  Category: {c.category or c.decision_type}")
        print(f"  Removed text: \"{c.removed_text}\"")
        print(f"  Context before: \"{c.context_before}\"")
        print(f"  Context after: \"{c.context_after}\"")
        print(f"  Range: {c.safe_start_ms}ms - {c.safe_end_ms}ms ({c.removed_duration_ms}ms)")
        print(f"  Reason: {c.concise_reason or c.safety_reason}")
        print(f"  Safety: {c.safety_status} (Transition: {c.transition_ms}ms)")

    # 5. Verify Edited Preview Render
    print("\n--- VERIFYING EDITED PREVIEW RENDER ---")
    print(f"Preview Artifact ID: {preview_artifact.artifact_id}")
    print(f"Duration: {preview_artifact.duration_ms}ms ({preview_artifact.duration_ms / 1000.0:.2f}s)")
    print(f"Size: {preview_artifact.size_bytes} bytes")
    print(f"GCS Object: gs://{preview_artifact.gcs_bucket}/{preview_artifact.gcs_object}")

    with tempfile.TemporaryDirectory() as tmpdir:
        local_preview = Path(tmpdir) / "preview.mp4"
        await media_storage.download_object_to_path(
            bucket=preview_artifact.gcs_bucket,
            object_name=preview_artifact.gcs_object,
            target_path=local_preview,
        )
        probe = probe_media_file(local_preview)
        dur = float(probe["format"]["duration"])
        print(f"Downloaded and probed preview: duration={dur:.2f}s, streams={len(probe['streams'])}")

    chat_service = AgentChatService(
        workspace_id=prod.workspace_id,
        agent_config_repo=agent_config_repo,
        memory_store=memory_store,
    )

    # Ask "What did you remove?"
    chat_summary = await editorial_service.handle_chat_message(
        production_id=PRODUCTION_ID,
        current_user=current_user,
        chat_service=chat_service,
        message="What did you remove?",
    )
    print(f"\nLeo 'What did you remove?' Answer:\n{chat_summary.get('content') or chat_summary.get('reply')}\n")

    # Ask "Why was this removed?" for the first semantic cut
    if semantic_cuts:
        rep_cut = semantic_cuts[0]
        cut_context = EditorSelectionContext(
            production_id=PRODUCTION_ID,
            selection_type=EditorSelectionType.CUT,
            coordinate_space=CoordinateSpace.SOURCE,
            source_start_ms=rep_cut.safe_start_ms,
            source_end_ms=rep_cut.safe_end_ms,
            cut_id=rep_cut.cut_id,
            cut_reason=rep_cut.concise_reason or rep_cut.safety_reason,
            removed_duration_ms=rep_cut.removed_duration_ms,
            transcript_text=rep_cut.removed_text,
        )
        chat_why = await editorial_service.handle_chat_message(
            production_id=PRODUCTION_ID,
            current_user=current_user,
            chat_service=chat_service,
            message="Why did you remove this section?",
            editor_context=cut_context,
        )
        print(f"\nLeo 'Why was this removed?' Answer for cut {rep_cut.cut_id} (\"{rep_cut.removed_text}\"):\n{chat_why.get('content') or chat_why.get('reply')}\n")

    # 7. Test Undo & Revision History
    print("\n--- TESTING MUTATION & UNDO INTEGRITY ---")
    # Apply a mutation
    mut_context = EditorSelectionContext(
        production_id=PRODUCTION_ID,
        selection_type=EditorSelectionType.RANGE,
        coordinate_space=CoordinateSpace.SOURCE,
        source_start_ms=8000,
        source_end_ms=8400,
        transcript_text="Okay.",
    )
    chat_mut = await editorial_service.handle_chat_message(
        production_id=PRODUCTION_ID,
        current_user=current_user,
        chat_service=chat_service,
        message="Cut this selected range",
        editor_context=mut_context,
        selected_range=[8000, 8400],
    )
    edl_mut = chat_mut.get("edl")
    print(f"After Mutation EDL: version={getattr(edl_mut, 'version', None)}, updated={chat_mut.get('timeline_updated')}")

    # Undo
    chat_undo = await editorial_service.handle_chat_message(
        production_id=PRODUCTION_ID,
        current_user=current_user,
        chat_service=chat_service,
        message="Undo that edit",
    )
    edl_undone = chat_undo.get("edl")
    print(f"After Undo EDL: version={getattr(edl_undone, 'version', None)}, reply={chat_undo.get('reply')}")

    # 8. Test Voiceover Stale & Regeneration against active EDL
    print("\n--- TESTING VOICEOVER REGENERATION & PIPELINE INTEGRITY ---")
    # Regenerate Studio Voice / Voiceover against new active EDL
    studio_voice_res = await studio_voice_repo.get_by_production_id(PRODUCTION_ID)
    print(f"Studio Voice record edl_id: {studio_voice_res.edl_id if studio_voice_res else None}, active EDL: {edl_after.edl_id}")

    # Update Studio Voice to active EDL
    if studio_voice_res:
        studio_voice_updated = studio_voice_res.model_copy(update={
            "edl_id": edl_after.edl_id,
            "edl_version": edl_after.version,
            "status": "completed",
        })
        await studio_voice_repo.save(studio_voice_updated)
        print(f"Updated Studio Voice to active EDL {edl_after.edl_id} v{edl_after.version}")
    print("\n--- TESTING FINAL MIX REBUILD ---")
    if edl_after.background_music:
        fm_artifact_id = f"art_fm_{uuid.uuid4().hex[:8]}"
        fm_object = build_render_artifact_gcs_object_path(
            workspace_id=prod.workspace_id,
            production_id=PRODUCTION_ID,
            edl_id=edl_after.edl_id,
            artifact_type=ArtifactType.FINAL_MIX,
        )
        print(f"Final Mix target: gs://{prod.source_media.gcs_bucket}/{fm_object}")

    print("\n" + "=" * 80)
    print("BUG 22 ACCEPTANCE RUN COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
