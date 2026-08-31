import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, "apps/api/src")
sys.path.insert(0, "packages/domain/src")
sys.path.insert(0, "packages/observability/src")
sys.path.insert(0, "packages/media/src")
sys.path.insert(0, "packages/agents/src")

import firebase_admin
from croviq_api.productions.edl_repository import FirestoreEDLRepository
from croviq_api.productions.editorial_repository import FirestoreEditorialRepository
from croviq_api.productions.render_repository import FirestoreRenderRepository
from croviq_api.productions.repository import FirestoreProductionRepository
from croviq_api.productions.studio_voice_repository import FirestoreStudioVoiceRepository
from croviq_api.productions.transcript_repository import FirestoreTranscriptRepository

PROJECT_ID = "croviq-506602"
PRODUCTION_ID = "prod_473209137802"

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": PROJECT_ID})

async def inspect():
    edl_repo = FirestoreEDLRepository()
    editorial_repo = FirestoreEditorialRepository()
    render_repo = FirestoreRenderRepository()
    studio_voice_repo = FirestoreStudioVoiceRepository()
    transcript_repo = FirestoreTranscriptRepository()

    # List all EDLs from subcollection
    coll = edl_repo._edls_subcollection(PRODUCTION_ID)
    docs = [d async for d in coll.order_by("created_at").stream()]
    print(f"=== ALL EDLs in Firestore ({len(docs)} total) ===")
    for doc in docs:
        data = doc.to_dict()
        cuts = data.get("cuts", [])
        v = data.get("version")
        ca = data.get("created_at")
        rem = sum(c.get("removed_duration_ms", 0) for c in cuts)
        dur = data.get("source_duration_ms", 0) - rem
        print(f"EDL {doc.id} v{v} cuts={len(cuts)} target_dur={dur/1000.0:.2f}s removed={rem/1000.0:.2f}s created={ca}")
        if doc.id in ("edl_85c7d62ec82f", "edl_a1c96e964109") or v in (1, 2, 31, 32, 33, 34):
            print(f"  --- Details for {doc.id} v{v} ---")
            for i, c in enumerate(cuts):
                cid = c.get("cut_id")
                s = c.get("safe_start_ms")
                e = c.get("safe_end_ms")
                d = c.get("removed_duration_ms")
                dt = c.get("decision_type")
                cat = c.get("category")
                txt = c.get("removed_text")
                r = c.get("concise_reason") or c.get("safety_reason")
                print(f"    Cut {i+1}: {cid} [{s}-{e}ms ({d}ms)] type={dt} cat={cat} text='{txt}'")
                print(f"      reason: {r}")

    # Transcript
    tr = await transcript_repo.get_transcript_by_production_id(PRODUCTION_ID)
    if tr:
        print(f"\n=== TRANSCRIPT: {len(tr.words)} words, duration={tr.duration_ms/1000.0:.2f}s ===")
        print("All words:")
        for idx, w in enumerate(tr.words):
            print(f"  [{idx}] {w.start_ms}-{w.end_ms}ms: '{w.text}'")

    # Proposal
    run = await editorial_repo.get_latest_editorial_run(PRODUCTION_ID)
    if run and run.editor_proposal_id:
        prop = await editorial_repo.get_editor_proposal(PRODUCTION_ID, run.editor_proposal_id)
        print(f"\n=== LATEST PROPOSAL: {run.editor_proposal_id} ({len(prop.decisions)} decisions) ===")
        for i, d in enumerate(prop.decisions):
            cat = getattr(d, "category", None)
            subcat = getattr(d, "subcategory", None)
            print(f"  Dec {i+1}: {d.decision_id} [{d.source_start_ms}-{d.source_end_ms}ms ({d.source_end_ms-d.source_start_ms}ms)] type={d.decision_type} act={d.action} text='{d.original_text}'")
            print(f"    cat={cat} subcat={subcat}")
            print(f"    reason: {d.concise_reason}")
    # Studio Voice & Music
    sv = await studio_voice_repo.get_by_production_id(PRODUCTION_ID)
    print("\n=== STUDIO VOICE ===")
    if sv:
        print(f"  edl_id: {sv.edl_id}, voice_id: {getattr(sv, 'voice_id', None)}, status: {sv.status}")
        print(f"  segments: {len(sv.segments)}")

    # Render artifacts
    artifacts = await render_repo.list_render_artifacts(PRODUCTION_ID)
    print(f"\n=== RENDER ARTIFACTS ({len(artifacts)} total) ===")
    for a in artifacts:
        print(f"  Artifact {a.artifact_id}: type={a.artifact_type} edl_id={a.edl_id} status={a.status} dur={a.duration_ms}ms gcs={a.gcs_object}")

if __name__ == "__main__":
    asyncio.run(inspect())
