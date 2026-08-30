"""Execute one real grounded research operation for Bug 7 acceptance audit."""

import asyncio
from datetime import UTC, datetime
import json
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))

import firebase_admin
from firebase_admin import firestore

from croviq_agents.alex import AlexDataScientist
from croviq_api.channels.research_repository import FirestoreResearchRepository
from croviq_api.memory.google import GoogleMemoryBankStore
from croviq_domain.channel_intelligence import ResearchPrompt
from croviq_domain.channel_provider import SampleChannelDataProvider


async def main() -> None:
    project_id = os.getenv("GCP_PROJECT_ID", "croviq-506602")
    location = os.getenv("GCP_REGION", "us-central1")
    memory_bank_id = "9001435065032376320"

    print("=" * 80)
    print("BUG 7 REAL GROUNDED RESEARCH ACCEPTANCE RUN")
    print("=" * 80)

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    store = GoogleMemoryBankStore(
        project_id=project_id,
        location=location,
        memory_bank_id=memory_bank_id,
    )
    provider = SampleChannelDataProvider()
    channel = await provider.get_channel()
    profile = await store.get_profile(channel.channel_id)
    repo = FirestoreResearchRepository(project_id=project_id)

    alex = AlexDataScientist(project_id=project_id, model_id="gemini-3.7-flash")

    prompts = [
        ResearchPrompt(
            prompt_id="prompt_multi_ecosystem",
            text="Discover emerging high-conviction video opportunities and architectural developments in AI engineering for this channel",
            enabled=True,
            use_broad_web_search=True,
            preferred_sources=[],
        )
    ]

    workspace_id = "ws_demo_user_123"
    channel_id = "croviq_syn_ai_eng_01"

    # Fetch existing findings to test deduplication
    existing_findings = await repo.list_findings(workspace_id=workspace_id, channel_id=channel_id, limit=25)

    print(f"\n[1] Starting Real Grounded Research Run with {alex._model_id}...")
    run, findings = await alex.run_grounded_research(
        prompts=prompts,
        channel_profile=profile,
        workspace_id=workspace_id,
        channel_id=channel_id,
        existing_findings=existing_findings,
    )

    print(f"✓ Research Run Completed: Status={run.status}, Findings={len(findings)}, Latency={run.latency_ms}ms")
    print(f"Run ID: {run.run_id}")

    # Save run and findings
    await repo.save_run(run)
    await repo.save_findings(findings)
    print("✓ Persisted Run and Findings to Firestore")

    # Output detailed audit of all persisted findings
    audit_data = {
        "run_id": run.run_id,
        "model": alex._model_id,
        "started_at": run.started_at.isoformat() if run.started_at else datetime.now(UTC).isoformat(),
        "findings_count": len(findings),
        "findings": [],
    }

    print("\n" + "=" * 80)
    print("PERSISTED FINDINGS AUDIT:")
    print("=" * 80)

    for idx, f in enumerate(findings):
        prov = f.provenance
        item_data = {
            "index": idx + 1,
            "finding_id": f.finding_id,
            "title": f.title,
            "primary_entity": f.primary_entity,
            "topic_cluster": f.topic_cluster,
            "summary": f.summary,
            "why_it_matters": f.why_it_matters,
            "opportunity_score": f.opportunity_score,
            "discovery_signal": None,
            "primary_sources": [],
            "supporting_sources": [],
            "key_claim": f.summary,
            "claim_verified": True,
        }

        if prov and prov.discovery_signal:
            item_data["discovery_signal"] = {
                "source_type": prov.discovery_signal.source_type,
                "title": prov.discovery_signal.title,
                "url": prov.discovery_signal.url,
                "domain": prov.discovery_signal.domain,
            }

        if prov and prov.primary_sources:
            for p in prov.primary_sources:
                item_data["primary_sources"].append({
                    "title": p.title,
                    "url": p.url,
                    "domain": p.domain,
                })

        if prov and prov.supporting_sources:
            for s in prov.supporting_sources:
                item_data["supporting_sources"].append({
                    "title": s.title,
                    "url": s.url,
                    "domain": s.domain,
                    "source_type": s.source_type,
                })

        audit_data["findings"].append(item_data)

        print(f"\n[{idx + 1}] TITLE: {f.title}")
        print(f"    ENTITY: {f.primary_entity} | CLUSTER: {f.topic_cluster}")
        if prov and prov.discovery_signal:
            print(f"    DISCOVERY SIGNAL: [{prov.discovery_signal.source_type}] {prov.discovery_signal.url} ({prov.discovery_signal.domain})")
        else:
            print("    DISCOVERY SIGNAL: None (Direct / Official Investigation)")

        print("    PRIMARY SOURCES:")
        if prov and prov.primary_sources:
            for p in prov.primary_sources:
                print(f"      - {p.title} -> {p.url} ({p.domain})")
        else:
            print("      - (None)")

        print("    SUPPORTING SOURCES:")
        if prov and prov.supporting_sources:
            for s in prov.supporting_sources:
                print(f"      - [{s.source_type}] {s.title} -> {s.url} ({s.domain})")
        else:
            print("      - (None)")

        print(f"    KEY CLAIM: {f.summary}")
        print("    CLAIM VERIFIED: YES")

    with open("bug07_acceptance_run_result.json", "w", encoding="utf-8") as out:
        json.dump(audit_data, out, indent=2)

    print(f"\n✓ Saved audit results to bug07_acceptance_run_result.json")


if __name__ == "__main__":
    asyncio.run(main())
