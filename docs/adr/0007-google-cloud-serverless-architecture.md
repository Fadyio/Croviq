# 0007: Google Cloud Serverless Architecture and State Partitioning

## Context
Croviq requires an infrastructure stack on Google Cloud (`us-central1`) that supports heavy multimodal video processing, real-time agent workflow updates in the browser, shared long-term memory, and structured observability, while avoiding unnecessary operational complexity, idle server costs, or external database vendors.

## Decision
We adopt a serverless, decoupled Google Cloud architecture:

1. **Multimodal AI Reasoning (Google GenAI SDK on Vertex AI / Gemini API)**:
   - Gemini 3.7 Flash powers native video and audio understanding, dialogue editing proposals, metadata generation, and QA verification via the Google GenAI SDK (`google-genai`).

2. **Shared Long-Term Memory (Google Agent Platform Memory Bank)**:
   - Memory Bank serves as the long-term memory store for `ChannelProfile`, `ChannelLesson`, and `ChannelExperiment` records.
   - Zero external vector databases (no Pinecone, Weaviate, or pgvector).

3. **Operational State & Tenancy (Firestore Native Mode)**:
   - Firestore in `us-central1` stores operational application state: Workspaces, Productions, Runs, Jobs, and Artifacts.
   - Client reactivity is provided via standard FastAPI REST endpoints and Firestore listeners.

4. **Media Storage (Google Cloud Storage)**:
   - Dedicated private GCS buckets store raw uploaded video footage, extracted audio tracks, intermediate render segments, rendered masters, captions, and thumbnails.
   - Public access prevention is enforced; client uploads use signed URLs.

5. **Compute & Web (Google Cloud Run)**:
   - `croviq-web`: Containerized React/Vite SPA on Cloud Run.
   - `croviq-api`: Containerized Python 3.12 / FastAPI backend on Cloud Run executing API routes, agent logic, and deterministic FFmpeg rendering.
   - Both services are locked to `internal-and-cloud-load-balancing` ingress.

6. **Single-Origin Public Ingress (Google Global External Load Balancer)**:
   - Public origin at `https://app.croviq.app` routes `/*` to `croviq-web` and `/api/*` to `croviq-api` via Serverless NEGs (ADR-0013).
   - Root domain `https://croviq.app` redirects permanently (HTTP 308) to `https://app.croviq.app`.
   - Cloudflare is restricted strictly to authoritative DNS.

7. **Observability (Google Cloud Logging)**:
   - Python structured logger outputs single-line JSON to stdout.
   - Cloud Run ingests logs directly into Google Cloud Logging with unified correlation fields (`request_id`, `user_id`, `run_id`, `job_id`, `model`, `latency_ms`).
   - No OpenTelemetry, Prometheus, or Grafana infrastructure required.

## Consequences
- Total operational simplicity: 100% serverless Google Cloud architecture managed via Terraform.
- Clean state partitioning: media bytes in GCS, operational state in Firestore, long-term memory in Memory Bank, logs in Cloud Logging.
- Low latency and zero cross-origin CORS overhead in production.
