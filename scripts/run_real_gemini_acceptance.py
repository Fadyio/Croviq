"""Execute real Gemini 3.7 Flash acceptance test on real production fixture."""

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

from croviq_agents.client import GoogleGenAIClient
from croviq_agents.director import MayaDirector
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.memory import ChannelProfileBuilder
from croviq_agents.editor import LeoVideoEditor
from croviq_api.config import get_settings
from croviq_api.memory.dependencies import initialize_sample_channel_memory
from croviq_api.memory.google import GoogleMemoryBankStore
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_domain.editorial import (
    AgentActivity,
    DirectorReview,
    EditorProposal,
    EditorialRun,
    EditorialRunStatus,
)
from croviq_domain.media_metadata import MediaMetadata
from croviq_domain.source_analysis import SourceVideoAnalysisInput


async def main() -> None:
    project_id = "croviq-506602"
    location = "global"
    model_id = "gemini-3.7-flash"
    production_id = "prod_f0b41bfd429e"
    transcript_id = "tr_b9ab6b65d13e"

    print("=" * 60)
    print("RUNNING REAL ACCEPTANCE: LEO & MAYA GENAI SDK VERTEX AI")
    print(f"Project: {project_id} | Location: {location} | Model: {model_id}")
    print(f"Production: {production_id} | Transcript: {transcript_id}")
    print("=" * 60)

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    prod_repo = FirestoreProductionRepository(project_id=project_id)
    transcript_repo = FirestoreTranscriptRepository(project_id=project_id)
    editorial_repo = FirestoreEditorialRepository()
    memory_store = GoogleMemoryBankStore(
        project_id=project_id,
        location=location,
        memory_bank_id="croviq-channel-memory",
    )

    # 1. Load real production
    prod = await prod_repo.get_production(production_id)
    if not prod:
        print(f"ERROR: Production {production_id} not found in Firestore")
        sys.exit(1)
    print(f"Loaded Production: {prod.production_id} (Channel: {prod.channel_id})")
    print(f"Source GCS: gs://{prod.source_media.gcs_bucket}/{prod.source_media.gcs_object}")

    # 2. Load real transcript
    transcript = await transcript_repo.get_transcript_by_production_id(production_id)
    if not transcript:
        # Fallback to direct transcript ID fetch if production_id index is building
        transcript = await transcript_repo.get_transcript(transcript_id)
    if not transcript:
        print(f"ERROR: Transcript {transcript_id} not found in Firestore")
        sys.exit(1)
    print(f"Loaded Transcript: {transcript.transcript_id} ({len(transcript.words)} words, {transcript.duration_ms}ms)")

    # 3. Load Channel Memory (Profile & Lessons)
    provider = SampleChannelDataProvider()
    channel = await provider.get_channel()
    channel_profile = ChannelProfileBuilder.build_profile(channel)
    lessons = ChannelProfileBuilder.build_lessons(channel)
    print(f"Loaded Channel Profile: {channel_profile.channel_name} ({len(lessons)} active lessons)")
    # 4. Construct SourceVideoAnalysisInput
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
        size_bytes=prod.source_media.size_bytes,
    )
    analysis_input = SourceVideoAnalysisInput(
        production_id=production_id,
        source_media=prod.source_media,
        media_metadata=media_metadata,
        transcript=transcript,
        channel_id=prod.channel_id,
    )

    # 5. Initialize GenAI client with Vertex AI backend
    genai_client = GoogleGenAIClient(
        project_id=project_id,
        location=location,
        model_id=model_id,
    )

    run_id = f"run_{int(time.time())}_{production_id[-6:]}"
    run = EditorialRun(
        run_id=run_id,
        production_id=production_id,
        status=EditorialRunStatus.ANALYZING,
        started_at=datetime.now(timezone.utc),
    )
    await editorial_repo.save_editorial_run(run)
    print(f"\nCreated EditorialRun: {run_id} (Status: ANALYZING)")

    # 6. Run Leo (Video Editor)
    print("\n--- Invoking Leo (Video Editor) on Gemini 3.7 Flash via Vertex AI ---")
    leo = LeoVideoEditor(client=genai_client)
    t0 = time.perf_counter()
    proposal, leo_usage, leo_activities = await leo.analyze(
        analysis_input=analysis_input,
        channel_profile=channel_profile,
        lessons=lessons,
        run_id=run_id,
        request_id=f"req_real_leo_{run_id}",
    )
    leo_duration_s = time.perf_counter() - t0
    print(f"Leo completed in {leo_duration_s:.2f}s | Latency: {leo_usage.latency_ms}ms | Input Tokens: {leo_usage.input_tokens} | Output Tokens: {leo_usage.output_tokens}")
    print(f"Summary: {proposal.summary}")
    print(f"Proposed Decisions: {len(proposal.decisions)}")
    if proposal.short_candidate:
        print(f"Short Candidate: \"{proposal.short_candidate.hook_title}\" ({proposal.short_candidate.start_ms}ms - {proposal.short_candidate.end_ms}ms)")

    # Persist proposal and Leo activities
    proposal_id = f"prop_{run_id}"
    await editorial_repo.save_editor_proposal(proposal, proposal_id=proposal_id)
    await editorial_repo.save_activities(leo_activities)

    run.status = EditorialRunStatus.REVIEWING
    run.editor_proposal_id = proposal_id
    await editorial_repo.save_editorial_run(run)

    # 7. Run Maya (Director)
    print("\n--- Invoking Maya (Director) on Gemini 3.7 Flash via Vertex AI ---")
    maya = MayaDirector(client=genai_client)
    t1 = time.perf_counter()
    review, maya_usage, maya_activities = await maya.review(
        analysis_input=analysis_input,
        proposal=proposal,
        channel_profile=channel_profile,
        lessons=lessons,
        run_id=run_id,
        request_id=f"req_real_maya_{run_id}",
    )
    maya_duration_s = time.perf_counter() - t1
    print(f"Maya completed in {maya_duration_s:.2f}s | Latency: {maya_usage.latency_ms}ms | Input Tokens: {maya_usage.input_tokens} | Output Tokens: {maya_usage.output_tokens}")
    print(f"Assessment: {review.overall_assessment}")
    print(f"Feedback: {review.editor_feedback}")
    print(f"Approved for EDL: {review.approved_for_edl}")

    # Persist review and Maya activities
    review_id = f"rev_{run_id}"
    await editorial_repo.save_director_review(review, review_id=review_id)
    await editorial_repo.save_activities(maya_activities)

    # 8. Complete run
    run.status = EditorialRunStatus.COMPLETED
    run.director_review_id = review_id
    run.completed_at = datetime.now(timezone.utc)
    await editorial_repo.save_editorial_run(run)

    total_tokens_in = leo_usage.input_tokens + maya_usage.input_tokens
    total_tokens_out = leo_usage.output_tokens + maya_usage.output_tokens
    total_latency_ms = leo_usage.latency_ms + maya_usage.latency_ms

    print("\n" + "=" * 60)
    print("REAL ACCEPTANCE SUMMARY RESULTS")
    print("=" * 60)
    print(f"RUN ID: {run_id}")
    print(f"TOTAL INPUT TOKENS: {total_tokens_in}")
    print(f"TOTAL OUTPUT TOKENS: {total_tokens_out}")
    print(f"TOTAL MODEL LATENCY: {total_latency_ms}ms ({total_latency_ms / 1000:.2f}s)")
    print(f"LEO DECISIONS COUNT: {len(proposal.decisions)}")

    approved_count = sum(1 for d in review.decisions if d.verdict.value == "APPROVE")
    rejected_count = sum(1 for d in review.decisions if d.verdict.value == "REJECT")
    modified_count = sum(1 for d in review.decisions if d.verdict.value == "MODIFY")
    print(f"MAYA APPROVED: {approved_count} | REJECTED: {rejected_count} | MODIFIED: {modified_count}")

    print("\nDECISIONS QUALITY TABLE:")
    print("-" * 100)
    print(f"{'TIME':<16} | {'LEO ACTION':<22} | {'ORIGINAL TEXT':<28} | {'MAYA VERDICT':<12} | {'MAYA REASON'}")
    print("-" * 100)

    # Build decision lookup
    review_map = {d.editor_decision_id: d for d in review.decisions}
    for dec in proposal.decisions:
        time_str = f"{dec.source_start_ms/1000:04.1f}s - {dec.source_end_ms/1000:04.1f}s"
        action_str = f"[{dec.decision_type.value}] {dec.action}"
        orig_text = (dec.original_text[:25] + "...") if len(dec.original_text) > 28 else dec.original_text
        rev_dec = review_map.get(dec.decision_id)
        verdict_str = rev_dec.verdict.value if rev_dec else "N/A"
        reason_str = rev_dec.concise_reason if rev_dec else dec.concise_reason
        print(f"{time_str:<16} | {action_str:<22} | {orig_text:<28} | {verdict_str:<12} | {reason_str}")
    print("-" * 100)

    # Save output summary to JSON for final evidence
    result_data = {
        "run_id": run_id,
        "production_id": production_id,
        "transcript_id": transcript_id,
        "model_id": model_id,
        "leo_usage": {
            "input_tokens": leo_usage.input_tokens,
            "output_tokens": leo_usage.output_tokens,
            "latency_ms": leo_usage.latency_ms,
        },
        "maya_usage": {
            "input_tokens": maya_usage.input_tokens,
            "output_tokens": maya_usage.output_tokens,
            "latency_ms": maya_usage.latency_ms,
        },
        "total_input_tokens": total_tokens_in,
        "total_output_tokens": total_tokens_out,
        "total_latency_ms": total_latency_ms,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "modified_count": modified_count,
        "proposal": proposal.model_dump(mode="json"),
        "review": review.model_dump(mode="json"),
        "activities_count": len(leo_activities) + len(maya_activities),
    }

    with open("real_gemini_acceptance_result.json", "w") as f:
        json.dump(result_data, f, indent=2)
    print("\nSaved full result to real_gemini_acceptance_result.json")


if __name__ == "__main__":
    asyncio.run(main())
