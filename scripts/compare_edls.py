import asyncio
import os
import sys

sys.path.insert(0, "apps/api/src")
sys.path.insert(0, "packages/domain/src")
sys.path.insert(0, "packages/observability/src")
sys.path.insert(0, "packages/media/src")
sys.path.insert(0, "packages/agents/src")

import firebase_admin
from croviq_api.productions.edl_repository import FirestoreEDLRepository

PROJECT_ID = "croviq-506602"
PRODUCTION_ID = "prod_473209137802"

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": PROJECT_ID})

async def compare():
    edl_repo = FirestoreEDLRepository()
    coll = edl_repo._edls_subcollection(PRODUCTION_ID)
    docs = [d async for d in coll.order_by("created_at").stream()]
    
    for doc in docs:
        data = doc.to_dict()
        cuts = data.get("cuts", [])
        rem = sum(c.get("removed_duration_ms", 0) for c in cuts)
        dur = (data.get("source_duration_ms", 0) - rem) / 1000.0
        if abs(dur - 54.29) < 0.5 or doc.id in ("edl_85c7d62ec82f", "edl_a1c96e964109", "edl_6a1c00dc764a", "edl_84911034b8c2", "edl_9d8222692fa6"):
            v = data.get("version")
            print(f"\nEDL {doc.id} v{v}: target_dur={dur:.2f}s, cuts={len(cuts)}")
            for i, c in enumerate(cuts):
                s = c.get("safe_start_ms")
                e = c.get("safe_end_ms")
                d = c.get("removed_duration_ms")
                dt = c.get("decision_type")
                txt = c.get("removed_text")
                r = c.get("concise_reason") or c.get("safety_reason")
                print(f"  Cut {i+1}: [{s}-{e}ms ({d}ms)] type={dt} text='{txt}'")
                print(f"    reason: {r}")

if __name__ == "__main__":
    asyncio.run(compare())
