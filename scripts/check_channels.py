import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))

import firebase_admin
from firebase_admin import firestore

project_id = "croviq-506602"
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": project_id})

db = firestore.client()

async def main():
    channels = list(db.collection("channels").stream())
    print(f"Total channels in Firestore: {len(channels)}")
    for ch in channels:
        data = ch.to_dict()
        print(f"Channel ID: {ch.id}")
        print(f"  Title: {data.get('title')}")
        print(f"  Provider: {data.get('provider')}")
        print(f"  External ID: {data.get('external_id') or data.get('youtube_channel_id')}")
        print(f"  Has Token: {bool(data.get('encrypted_refresh_token') or data.get('access_token'))}")
        print(f"  Scopes: {data.get('granted_scopes') or data.get('scopes')}")

    yt_channels = list(db.collection("youtube_channels").stream())
    print(f"\nTotal youtube_channels in Firestore: {len(yt_channels)}")
    for ch in yt_channels:
        data = ch.to_dict()
        print(f"Doc ID: {ch.id}")
        print(f"  Data: {data}")

if __name__ == "__main__":
    asyncio.run(main())
