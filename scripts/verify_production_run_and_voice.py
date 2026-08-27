import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

PRODUCTION_ID = os.getenv("CROVIQ_PRODUCTION_ID", "prod_473209137802")
BASE_URL = os.getenv("CROVIQ_BASE_URL", "https://app.croviq.app")


def get_auth_token() -> str:
    """Retrieve authentication token from environment or Identity Platform."""
    custom_token = os.getenv("CROVIQ_AUTH_TOKEN")
    if custom_token:
        return custom_token

    api_key = os.getenv("VITE_FIREBASE_API_KEY") or os.getenv("FIREBASE_API_KEY")
    email = os.getenv("CROVIQ_DEMO_EMAIL", "demo@croviq.app")
    password = os.getenv("CROVIQ_DEMO_PASSWORD")

    if api_key and password:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        payload = json.dumps({"email": email, "password": password, "returnSecureToken": True}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data["idToken"]

    # Fallback to local gcloud identity token
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-identity-token"], text=True).strip()
        if token:
            return token
    except Exception:
        pass

    raise ValueError("No authentication method available. Set CROVIQ_AUTH_TOKEN or VITE_FIREBASE_API_KEY + CROVIQ_DEMO_PASSWORD.")
def api_request(path, method="GET", body=None, token=None, timeout=180):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())

def main():
    print("1. Authenticating with Identity Platform...")
    token = get_auth_token()
    print("Authentication successful.")

    print(f"2. Fetching production metadata for {PRODUCTION_ID}...")
    prod = api_request(f"/api/productions/{PRODUCTION_ID}", token=token)
    print("Production Source:", prod.get("source_media", {}).get("gcs_object"))

    print("3. Fetching existing transcript...")
    transcript = api_request(f"/api/productions/{PRODUCTION_ID}/transcript", token=token)
    print(f"Transcript words count: {len(transcript.get('words', []))}, duration_ms: {transcript.get('duration_ms')}")

    print("4. Triggering fresh Editorial Run (Leo analyze + tool use + self review)...")
    analyze_resp = api_request(f"/api/productions/{PRODUCTION_ID}/analyze?force=true", method="POST", token=token)
    print("Analyze response status:", analyze_resp.get("status"))

    # Poll for editorial run completion
    print("Waiting for editorial run to complete...")
    run_detail = None
    for attempt in range(60):
        time.sleep(3)
        run_detail = api_request(f"/api/productions/{PRODUCTION_ID}/editorial-run", token=token)
        status = run_detail.get("run", {}).get("status")
        print(f"  Attempt {attempt+1}: status = {status}")
        if status in ("completed", "failed"):
            break

    run = run_detail.get("run", {})
    print("Editorial Run Completed with status:", run.get("status"))
    print("Run ID:", run.get("run_id"))

    # 5. Assemble EDL
    print("5. Assembling EDL...")
    edl_resp = api_request(f"/api/productions/{PRODUCTION_ID}/edl", method="POST", token=token)
    print(f"EDL Assembled with {len(edl_resp.get('cuts', []))} cuts, output duration: {edl_resp.get('output_duration_ms')}ms")

    # 6. Render Edited Preview
    print("6. Rendering Edited Preview Video...")
    preview_resp = api_request(f"/api/productions/{PRODUCTION_ID}/renders/preview", method="POST", token=token)
    print("Edited Preview Render Status:", preview_resp.get("status"), "Playback URL:", preview_resp.get("playback_url"))

    # 7. Generate Real Studio Voice & Render Studio Voice Preview
    print("7. Generating Real Studio Voice & Studio Voice Preview...")
    sv_resp = api_request(f"/api/productions/{PRODUCTION_ID}/studio-voice", method="POST", token=token)
    print("Studio Voice generation status:", sv_resp.get("result", {}).get("status"), "Playback URL:", sv_resp.get("studio_voice_preview_url"))

    # 8. Fetch Production Playback URLs
    print("8. Fetching Production Playback URLs...")
    playback_resp = api_request(f"/api/productions/{PRODUCTION_ID}/playback", token=token)
    print("Playback URLs:", json.dumps(playback_resp, indent=2))

    # Save complete proof dump
    proof_data = {
        "production": prod,
        "transcript": transcript,
        "editorial_run_detail": run_detail,
        "edl": edl_resp,
        "preview_render": preview_resp,
        "studio_voice": sv_resp,
        "playback": playback_resp,
    }

    with open("/tmp/croviq_production_run_proof.json", "w") as f:
        json.dump(proof_data, f, indent=2)

    print("Saved production proof data to /tmp/croviq_production_run_proof.json")
if __name__ == "__main__":
    main()
