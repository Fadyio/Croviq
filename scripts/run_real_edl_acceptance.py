"""Execute real Issue #27 EDL assembly acceptance against prod_f0b41bfd429e."""

import asyncio
from datetime import datetime, timezone
import json
import os
import sys
import time

# Ensure packages and apps are in path
sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))

import firebase_admin
from firebase_admin import firestore

from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_domain.editorial import (
    DirectorDecision,
    DirectorReview,
    EditorDecision,
    EditorProposal,
    EditorialRun,
)
from croviq_domain.edl import EditDecisionList, derive_keep_segments
from croviq_domain.media_metadata import MediaMetadata
from croviq_media.cut_safety import CutSafetyAnalyzer, assemble_edl_from_review


async def main() -> None:
    project_id = "croviq-506602"
    production_id = "prod_f0b41bfd429e"
    transcript_id = "tr_b9ab6b65d13e"

    print("=" * 60)
    print("RUNNING REAL ACCEPTANCE: CANONICAL EDL & CUT SAFETY (#27)")
    print(f"Project: {project_id}")
    print(f"Production: {production_id} | Transcript: {transcript_id}")
    print("=" * 60)

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    prod_repo = FirestoreProductionRepository(project_id=project_id)
    transcript_repo = FirestoreTranscriptRepository(project_id=project_id)
    editorial_repo = FirestoreEditorialRepository()
    edl_repo = FirestoreEDLRepository()

    # 1. Load real production
    prod = await prod_repo.get_production(production_id)
    if not prod:
        print(f"ERROR: Production {production_id} not found in Firestore")
        sys.exit(1)
    print(f"Loaded Production: {prod.production_id} (Channel: {prod.channel_id})")

    # 2. Load real transcript
    transcript = await transcript_repo.get_transcript_by_production_id(production_id)
    if not transcript:
        transcript = await transcript_repo.get_transcript(transcript_id)
    if not transcript:
        print(f"ERROR: Transcript {transcript_id} not found in Firestore")
        sys.exit(1)
    print(f"Loaded Transcript: {transcript.transcript_id} ({len(transcript.words)} words, {transcript.duration_ms}ms)")

    # 3. Load latest completed EditorialRun
    run = await editorial_repo.get_latest_editorial_run(production_id)
    if not run:
        print(f"ERROR: No EditorialRun found for {production_id}")
        sys.exit(1)
    print(f"Loaded EditorialRun: {run.run_id} (Status: {run.status})")

    # 4. Load real EditorProposal and DirectorReview
    proposal = await editorial_repo.get_editor_proposal(production_id, run.editor_proposal_id)
    review = await editorial_repo.get_director_review(production_id, run.director_review_id)
    if not proposal or not review:
        print(f"ERROR: Proposal or Review missing for run {run.run_id}")
        sys.exit(1)

    print(f"Loaded EditorProposal: {len(proposal.decisions)} decisions")
    print(f"Loaded DirectorReview: approved_for_edl={review.approved_for_edl}, {len(review.decisions)} reviews")

    # 5. Media Metadata
    media_metadata = MediaMetadata(
        duration_ms=transcript.duration_ms,
        width=1080,
        height=1920,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=44100,
        audio_channels=2,
        rotation=0,
        size_bytes=prod.source_media.size_bytes if prod.source_media else 20000000,
    )

    # 6. Assemble Canonical EDL (Zero Model Calls)
    t0 = time.monotonic()
    analyzer = CutSafetyAnalyzer()
    edl = assemble_edl_from_review(
        production_id=production_id,
        proposal=proposal,
        review=review,
        transcript=transcript,
        media_metadata=media_metadata,
        version=1,
        analyzer=analyzer,
    )
    latency_ms = (time.monotonic() - t0) * 1000

    # 7. Persist to Firestore
    await edl_repo.save_edl(edl)
    print(f"Persisted EDL {edl.edl_id} to Firestore (Latency: {latency_ms:.2f}ms)")

    # 8. Derive Keep Segments
    keep_segments = derive_keep_segments(edl)

    # 9. Output report
    print("\n" + "=" * 60)
    print("REAL EDL ASSEMBLY SUMMARY")
    print("=" * 60)
    print(f"EDL ID:                   {edl.edl_id}")
    print(f"Version:                  {edl.version}")
    print(f"Source Duration:          {edl.source_duration_ms} ms ({edl.source_duration_ms / 1000:.2f}s)")
    print(f"Active Cut Count:         {edl.active_cuts_count}")
    print(f"Coverage Marker Count:    {len(edl.coverage_markers)}")
    print(f"Total Removed Duration:   {edl.total_removed_duration_ms} ms")
    print(f"Estimated Target Duration:{edl.estimated_target_duration_ms} ms ({edl.estimated_target_duration_ms / 1000:.2f}s)")
    print(f"Keep Segments Count:      {len(keep_segments)}")
    print(f"Derived Keep Segments:    {keep_segments}")

    print("\n" + "-" * 60)
    print("COVERAGE MARKERS:")
    for marker in edl.coverage_markers:
        print(f"  • [{marker.coverage_type}] {marker.source_start_ms}ms -> {marker.source_end_ms}ms | Decision: {marker.decision_id} | Reason: {marker.reason}")

    print("\n" + "-" * 60)
    print("DECISION TO CUT BREAKDOWN:")
    for d in proposal.decisions:
        rev_dec = next((r for r in review.decisions if r.editor_decision_id == d.decision_id), None)
        verdict = rev_dec.verdict if rev_dec else "APPROVE"
        matching_cut = next((c for c in edl.cuts if c.decision_id == d.decision_id), None)
        if matching_cut:
            print(f"  • {d.decision_id} ({d.decision_type}) -> CUT [{matching_cut.safety_status}] safe=[{matching_cut.safe_start_ms}, {matching_cut.safe_end_ms}] removed={matching_cut.removed_duration_ms}ms")
        else:
            print(f"  • {d.decision_id} ({d.decision_type}) [Verdict: {verdict}] -> NO DESTRUCTIVE CUT (preserves speech)")

    print("=" * 60)

    # Save summary artifact
    output_result = {
        "edl_id": edl.edl_id,
        "production_id": production_id,
        "transcript_id": transcript_id,
        "run_id": run.run_id,
        "source_duration_ms": edl.source_duration_ms,
        "active_cut_count": edl.active_cuts_count,
        "coverage_marker_count": len(edl.coverage_markers),
        "total_removed_duration_ms": edl.total_removed_duration_ms,
        "estimated_target_duration_ms": edl.estimated_target_duration_ms,
        "keep_segments": keep_segments,
        "coverage_markers": [m.model_dump(mode="json") for m in edl.coverage_markers],
        "cuts": [c.model_dump(mode="json") for c in edl.cuts],
        "latency_ms": latency_ms,
    }
    with open("real_edl_acceptance_result.json", "w") as f:
        json.dump(output_result, f, indent=2, default=str)
    print("\nSaved full result to real_edl_acceptance_result.json")


if __name__ == "__main__":
    asyncio.run(main())
