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

async def main():
    prods = list(db.collection("productions").stream())
    print("=" * 80)
    print(f"ALL PRODUCTIONS IN FIRESTORE ({len(prods)}):")
    print("=" * 80)
    for p in prods:
        data = p.to_dict()
        pid = p.id
        title = data.get("title", "")
        src = data.get("source_media", {})
        filename = src.get("original_filename", "") if src else ""
        size = src.get("size_bytes", 0) if src else 0
        gcs_obj = src.get("gcs_object", "") if src else ""
        print(f"\n==================================================")
        print(f"PRODUCTION: {pid}")
        print(f"  Title: {title}")
        print(f"  Source File: {filename} ({size} bytes)")
        print(f"  Source GCS: {gcs_obj}")
        print(f"  Created: {data.get('created_at')}")

        # Transcripts (top level collection)
        transcripts = list(db.collection("transcripts").where("production_id", "==", pid).stream())
        print(f"  Transcripts ({len(transcripts)}): {[t.id for t in transcripts]}")
        for t in transcripts:
            tdata = t.to_dict()
            print(f"    - Transcript {t.id}: duration_ms={tdata.get('duration_ms')}, words={len(tdata.get('words', []))}")

        # Subcollection: editorial_runs
        runs = list(db.collection("productions").document(pid).collection("editorial_runs").stream())
        print(f"  Editorial Runs ({len(runs)}): {[r.id for r in runs]}")
        for r in runs:
            rdata = r.to_dict()
            print(f"    - Run {r.id}: status={rdata.get('status')}, proposal={rdata.get('editor_proposal_id')}, review={rdata.get('director_review_id')}")

        # Subcollection: editor_proposals
        proposals = list(db.collection("productions").document(pid).collection("editor_proposals").stream())
        print(f"  Editor Proposals ({len(proposals)}): {[pr.id for pr in proposals]}")
        for pr in proposals:
            prdata = pr.to_dict()
            print(f"    - Proposal {pr.id}: decisions={len(prdata.get('decisions', []))}, chapters={len(prdata.get('chapters', []))}")

        # Subcollection: director_reviews
        d_reviews = list(db.collection("productions").document(pid).collection("director_reviews").stream())
        print(f"  Director Reviews ({len(d_reviews)}): {[dr.id for dr in d_reviews]}")
        for dr in d_reviews:
            drdata = dr.to_dict()
            print(f"    - DirectorReview {dr.id}: approved_for_edl={drdata.get('approved_for_edl')}, reviews={len(drdata.get('decisions', []))}")

        # Subcollection: edls
        edls = list(db.collection("productions").document(pid).collection("edls").stream())
        print(f"  EDLs ({len(edls)}): {[e.id for e in edls]}")
        for e in edls:
            edata = e.to_dict()
            print(f"    - EDL {e.id}: ver={edata.get('version')}, src_dur={edata.get('source_duration_ms')}, removed_dur={edata.get('total_removed_duration_ms')}, cuts={len(edata.get('cuts', []))}, active_cuts={edata.get('active_cuts_count')}, target_dur={edata.get('estimated_target_duration_ms')}")
            for cut in edata.get('cuts', []):
                print(f"        Cut {cut.get('cut_id')}: type={cut.get('decision_type')}, status={cut.get('safety_status')}, safe=[{cut.get('safe_start_ms')}, {cut.get('safe_end_ms')}], removed={cut.get('removed_duration_ms')}ms")

        # Subcollection: renders
        renders = list(db.collection("productions").document(pid).collection("renders").stream())
        print(f"  Render Artifacts ({len(renders)}): {[rd.id for rd in renders]}")
        for rd in renders:
            rdata = rd.to_dict()
            print(f"    - Artifact {rd.id}: type={rdata.get('artifact_type')}, edl_id={rdata.get('edl_id')}, status={rdata.get('status')}, duration_ms={rdata.get('duration_ms')}, size={rdata.get('size_bytes')}, sha256={rdata.get('sha256')}, gcs={rdata.get('gcs_object')}")

        # Subcollection: render_reviews
        r_reviews = list(db.collection("productions").document(pid).collection("render_reviews").stream())
        print(f"  Render Reviews ({len(r_reviews)}): {[rr.id for rr in r_reviews]}")
        for rr in r_reviews:
            rrdata = rr.to_dict()
            print(f"    - RenderReview {rr.id}: verdict={rrdata.get('verdict')}, edl_id={rrdata.get('edl_id')}, preview_id={rrdata.get('preview_artifact_id')}")

        # Subcollection: packaging_proposals
        pkgs = list(db.collection("productions").document(pid).collection("packaging_proposals").stream())
        print(f"  Packaging Proposals ({len(pkgs)}): {[pkg.id for pkg in pkgs]}")
        for pkg in pkgs:
            pkgdata = pkg.to_dict()
            print(f"    - Package {pkg.id}: title='{pkgdata.get('primary_title')}', chapters={len(pkgdata.get('chapters', []))}")
            for ch in pkgdata.get('chapters', []):
                print(f"        Chapter: title='{ch.get('title')}', start={ch.get('start_ms')}ms ({ch.get('timestamp')})")

        # Subcollection: release_reviews
        reviews = list(db.collection("productions").document(pid).collection("release_reviews").stream())
        print(f"  Release Reviews ({len(reviews)}): {[rv.id for rv in reviews]}")
        for rv in reviews:
            rvdata = rv.to_dict()
            print(f"    - ReleaseReview {rv.id}: verdict={rvdata.get('verdict')}, master_id={rvdata.get('master_artifact_id')}, short_id={rvdata.get('short_artifact_id')}, pkg_id={rvdata.get('packaging_proposal_id')}")

        # Top-level: youtube_publish_jobs
        jobs = list(db.collection("youtube_publish_jobs").where("production_id", "==", pid).stream())
        print(f"  Publish Jobs ({len(jobs)}): {[j.id for j in jobs]}")
        for j in jobs:
            jdata = j.to_dict()
            print(f"    - PublishJob {j.id}: status={jdata.get('status')}, art_id={jdata.get('artifact_id')}, yt_id={jdata.get('youtube_video_id')}, privacy={jdata.get('requested_privacy')}, remote_privacy={jdata.get('remote_privacy_status')}, created={jdata.get('created_at')}")

if __name__ == "__main__":
    asyncio.run(main())
