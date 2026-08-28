import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))

import firebase_admin
from firebase_admin import firestore

project_id = "croviq-506602"
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": project_id})

db = firestore.client()

async def inspect_prod(pid):
    print(f"================== DETAILS FOR {pid} ==================")
    # Proposals
    proposals = list(db.collection("productions").document(pid).collection("editor_proposals").stream())
    for pr in proposals:
        d = pr.to_dict()
        print(f"\nPROPOSAL: {pr.id}")
        print(f"  Summary: {d.get('summary')}")
        print(f"  Short Candidate: {d.get('short_candidate')}")
        print(f"  Chapters: {json.dumps(d.get('chapters'), indent=2)}")
        print(f"  Decisions ({len(d.get('decisions', []))}):")
        for dec in d.get("decisions", []):
            print(f"    - ID: {dec.get('decision_id')} | Type: {dec.get('decision_type')} | Range: [{dec.get('start_ms')}, {dec.get('end_ms')}] | Reason: {dec.get('reason')}")

    # Reviews
    reviews = list(db.collection("productions").document(pid).collection("director_reviews").stream())
    for r in reviews:
        d = r.to_dict()
        print(f"\nDIRECTOR REVIEW: {r.id}")
        print(f"  Approved for EDL: {d.get('approved_for_edl')}")
        print(f"  Decisions ({len(d.get('decisions', []))}):")
        for dec in d.get("decisions", []):
            print(f"    - EditorDec: {dec.get('editor_decision_id')} | Verdict: {dec.get('verdict')} | Notes: {dec.get('director_notes')}")

    # EDLs
    edls = list(db.collection("productions").document(pid).collection("edls").stream())
    for e in edls:
        d = e.to_dict()
        print(f"\nEDL: {e.id} (ver {d.get('version')})")
        print(f"  Source Dur: {d.get('source_duration_ms')}ms")
        print(f"  Removed Dur: {d.get('total_removed_duration_ms')}ms")
        print(f"  Active Cuts Count: {d.get('active_cuts_count')}")
        print(f"  Target Dur: {d.get('estimated_target_duration_ms')}ms")
        print(f"  Cuts ({len(d.get('cuts', []))}):")
        for c in d.get("cuts", []):
            print(f"    - Cut {c.get('cut_id')}: decision={c.get('decision_id')} | type={c.get('decision_type')} | status={c.get('safety_status')} | safe=[{c.get('safe_start_ms')}, {c.get('safe_end_ms')}] | removed={c.get('removed_duration_ms')}ms")
        print(f"  Coverage Markers ({len(d.get('coverage_markers', []))}):")
        for cm in d.get("coverage_markers", []):
            print(f"    - Marker {cm.get('marker_id')}: type={cm.get('coverage_type')} | range=[{cm.get('source_start_ms')}, {cm.get('source_end_ms')}] | reason={cm.get('reason')}")

async def main():
    await inspect_prod("prod_f0b41bfd429e")
    await inspect_prod("prod_0b7657f515ae")

if __name__ == "__main__":
    asyncio.run(main())
