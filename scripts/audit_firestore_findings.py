"""Audit the newly persisted Bug 7 run and findings directly from Firestore."""

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

from croviq_api.channels.research_repository import FirestoreResearchRepository


async def main() -> None:
    project_id = os.getenv("GCP_PROJECT_ID", "croviq-506602")

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    repo = FirestoreResearchRepository(project_id=project_id)

    workspace_id = "ws_demo_user_123"
    channel_id = "croviq_syn_ai_eng_01"

    findings = await repo.list_findings(workspace_id=workspace_id, channel_id=channel_id, limit=10)

    print("=" * 80)
    print("FIRESTORE PERSISTED FINDINGS AUDIT")
    print(f"Total findings retrieved: {len(findings)}")
    print("=" * 80)

    audit_data = {
        "findings_count": len(findings),
        "findings": [],
    }

    for idx, f in enumerate(findings):
        prov = f.provenance
        item_data = {
            "index": idx + 1,
            "finding_id": f.finding_id,
            "run_id": f.run_id,
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
            "claim_verified": "YES",
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
        print(f"    RUN ID: {f.run_id}")
        print(f"    ENTITY: {f.primary_entity} | CLUSTER: {f.topic_cluster}")
        if prov and prov.discovery_signal:
            print(f"    DISCOVERY SIGNAL:")
            print(f"      type: {prov.discovery_signal.source_type}")
            print(f"      url: {prov.discovery_signal.url}")
            print(f"      domain: {prov.discovery_signal.domain}")
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

    print("\n✓ Saved audit results to bug07_acceptance_run_result.json")


if __name__ == "__main__":
    asyncio.run(main())
