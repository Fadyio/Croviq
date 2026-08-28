import asyncio
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/media/src"))

import firebase_admin
from croviq_api.media.google import GoogleMediaStorage
from croviq_api.productions.repository import FirestoreProductionRepository

project_id = "croviq-506602"
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": project_id})

async def main():
    prod_repo = FirestoreProductionRepository(project_id=project_id)
    storage = GoogleMediaStorage(project_id=project_id)

    pid = "prod_f0b41bfd429e"
    prod = await prod_repo.get_production(pid)
    print(f"Production: {prod.production_id}")
    print(f"Source media: {prod.source_media}")

    bucket = prod.source_media.gcs_bucket
    obj = prod.source_media.gcs_object

    with tempfile.TemporaryDirectory() as tmpdir:
        local_src = Path(tmpdir) / "source.mp4"
        print(f"Downloading gs://{bucket}/{obj}...")
        await storage.download_object_to_path(bucket, obj, local_src)
        print(f"Downloaded source: {local_src.stat().st_size} bytes")

        # SHA256
        sha = hashlib.sha256(local_src.read_bytes()).hexdigest()
        print(f"Source SHA256: {sha}")

        # FFprobe
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-show_entries", "stream=width,height,codec_name,r_frame_rate",
            "-of", "json",
            str(local_src)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("FFprobe source:")
        print(res.stdout)

if __name__ == "__main__":
    asyncio.run(main())
