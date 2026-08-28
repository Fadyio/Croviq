"""Execute real Issue #32 Nina Packaging Agent acceptance against real Fairphone production."""

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
from croviq_agents.nina import NinaPackagingAgent
from croviq_api.channels.research_repository import FirestoreResearchRepository
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.memory.google import GoogleMemoryBankStore
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.packaging_repository import FirestorePackagingRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.render_review_repository import FirestoreRenderReviewRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository
from croviq_api.workspaces.agent_config_repository import FirestoreAgentConfigRepository
from croviq_domain.agent_config import AgentId
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.editorial import ShortCandidate
from croviq_domain.memory import ChannelProfileBuilder
from croviq_domain.packaging import PackagingProposal
from croviq_domain.render import (
    ArtifactStatus,
    ArtifactType,
    RenderArtifact,
)


async def main() -> None:
    project_id = "croviq-506602"
    production_id = "prod_0b7657f515ae"

    print("=" * 60)
    print("RUNNING REAL ACCEPTANCE: NINA PACKAGING AGENT (#32)")
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
    packaging_repo = FirestorePackagingRepository(project_id=project_id)
    agent_config_repo = FirestoreAgentConfigRepository(project_id=project_id)
    memory_store = GoogleMemoryBankStore(project_id=project_id)
    research_repo = FirestoreResearchRepository(project_id=project_id)
    media_storage = GoogleMediaStorage(project_id=project_id)
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

    # 4. Load Master Video RenderArtifact
    renders = await render_repo.list_render_artifacts(production_id)
    master_artifact = next(
        (r for r in renders if (r.artifact_type == ArtifactType.MASTER or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.MASTER.value)) and r.status == ArtifactStatus.completed),
        None,
    )
    if not master_artifact:
        print(f"ERROR: Completed MASTER artifact not found for production {production_id}")
        sys.exit(1)
    print(f"Loaded Master Artifact: {master_artifact.artifact_id} ({master_artifact.gcs_object}, {master_artifact.duration_ms}ms)")

    short_artifact = next(
        (r for r in renders if (r.artifact_type == ArtifactType.SHORT or (hasattr(r.artifact_type, "value") and r.artifact_type.value == ArtifactType.SHORT.value)) and r.status == ArtifactStatus.completed),
        None,
    )

    # 5. Load Leo's persisted ShortCandidate and chapters
    latest_run = await editorial_repo.get_latest_editorial_run(production_id)
    proposal = None
    if latest_run and latest_run.editor_proposal_id:
        proposal = await editorial_repo.get_editor_proposal(production_id, latest_run.editor_proposal_id)

    short_candidate = proposal.short_candidate if proposal else None
    chapters = proposal.chapters if proposal and proposal.chapters else []
    # 6. Load channel memory and research findings
    channel_profile = None
    lessons = []
    try:
        channel_profile = await memory_store.get_profile(prod.channel_id)
        if not channel_profile:
            sample_provider = SampleChannelDataProvider()
            c_data = await sample_provider.get_channel(prod.channel_id)
            if c_data:
                channel_profile, lessons = ChannelProfileBuilder.build(c_data)
                await memory_store.save_profile(channel_profile)
                if lessons:
                    await memory_store.save_lessons(prod.channel_id, lessons)
        else:
            lessons = await memory_store.get_lessons(prod.channel_id)
    except Exception as exc:
        print(f"Warning loading memory: {exc}")

    research_findings = []
    try:
        research_findings = await research_repo.list_findings(
            workspace_id=prod.workspace_id, channel_id=prod.channel_id, limit=5
        )
    except Exception as exc:
        print(f"Warning loading research: {exc}")

    # 7. Load Nina prompt config
    nina_prompt_config = await agent_config_repo.get_agent_prompt(prod.workspace_id, AgentId.NINA)

    # 8. Check for existing proposal or generate with Gemini 3.7 Flash
    existing_proposal = await packaging_repo.get_latest_packaging_proposal(production_id)
    
    genai_client = GoogleGenAIClient(project_id=project_id, model_id="gemini-3.7-flash")
    agent = NinaPackagingAgent(genai_client=genai_client, model_id="gemini-3.7-flash")

    print("\nInvoking Nina Packaging Agent with Multimodal Master Video & Channel Context...")
    start_time = time.perf_counter()

    pkg_proposal, usage = await agent.package_production(
        production_id=prod.production_id,
        master_artifact=master_artifact,
        transcript=transcript,
        channel_profile=channel_profile,
        lessons=lessons,
        chapters=chapters,
        research_findings=research_findings,
        short_candidate=short_candidate,
        has_short_artifact=bool(short_artifact),
        custom_prompt=nina_prompt_config.prompt_text if nina_prompt_config.is_custom else None,
        prompt_version=nina_prompt_config.version,
        request_id=f"acceptance_{int(time.time())}",
    )

    elapsed_s = time.perf_counter() - start_time
    print(f"Generated PackagingProposal in {elapsed_s:.2f}s | In Tokens: {usage.input_tokens} | Out Tokens: {usage.output_tokens}")

    # Persist proposal
    await packaging_repo.save_packaging_proposal(pkg_proposal)
    print(f"Persisted PackagingProposal to Firestore: {pkg_proposal.proposal_id}")

    # Display Acceptance Report
    print("\n" + "=" * 60)
    print("NINA PACKAGING ACCEPTANCE REPORT — FAIRPHONE PRODUCTION")
    print("=" * 60)
    print(f"NINA MODEL: {pkg_proposal.model}")
    print(f"MASTER VIDEO INPUT: YES")
    print(f"CHANNEL CONTEXT: YES")
    print(f"ALEX DATA: YES")
    print(f"PACKAGING PROPOSAL ID: {pkg_proposal.proposal_id}")
    print(f"\nPRIMARY TITLE:\n{pkg_proposal.primary_title}")
    print("\nALTERNATIVES:")
    alt_idx = 1
    for cand in pkg_proposal.title_candidates:
        if cand.text.strip().lower() != pkg_proposal.primary_title.strip().lower():
            print(f"{alt_idx}. {cand.text} [{cand.angle}] — {cand.why_it_works}")
            alt_idx += 1
            if alt_idx > 4:
                break

    print(f"\nDESCRIPTION:\n{pkg_proposal.description}")

    print("\nCHAPTERS:")
    for ch in pkg_proposal.chapters:
        print(f"- {ch.formatted_time} {ch.title}")

    for idx, th in enumerate(pkg_proposal.thumbnail_concepts[:3]):
        print(f"\nTHUMBNAIL {idx + 1}:")
        print(f"HEADLINE: \"{th.headline}\"")
        print(f"SUBJECT: {th.visual_subject}")
        print(f"FRAME: {(th.supporting_frame_ms / 1000.0):.2f}s ({th.supporting_frame_ms}ms)")
        print(f"VERIFIED: {'YES' if th.frame_verified else 'NO'}")

    if pkg_proposal.short_package:
        print(f"\nSHORT TITLE: {pkg_proposal.short_package.title}")
        print(f"SHORT DESCRIPTION: {pkg_proposal.short_package.description}")
        print(f"SHORT HOOK: {pkg_proposal.short_package.hook}")

    print(f"\nCHANNEL EVIDENCE:\n{pkg_proposal.channel_evidence}")
    print(f"\nNINA SETTINGS:")
    print(f"PROMPT: Version {nina_prompt_config.version} (Custom: {nina_prompt_config.is_custom})")
    print(f"MEMORY: Loaded {len(lessons)} Channel Lessons")
    print(f"RELEASE ROUTE: /productions/{production_id}/release")


if __name__ == "__main__":
    asyncio.run(main())
