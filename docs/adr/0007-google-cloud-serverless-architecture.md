# 0007: Google Cloud Serverless Architecture and State Partitioning

## Context
Croviq requires an infrastructure stack on Google Cloud (`us-central1`) that supports heavy multimodal video processing, real-time agent workflow updates in the browser, structured operational state management, and end-to-end observability, while scaling to zero and avoiding unnecessary operational overhead during development and hackathon evaluation.

## Decision
We adopt a serverless, decoupled Google Cloud architecture:
1. **Operational State & Memory (Firestore Native Mode)**: Firestore stores all structured operational documents: Workspaces, Missions, Runs, Jobs, Artifacts metadata, QA Reports, and Creator Memory Lessons. Real-time document snapshot listeners provide low-latency UI synchronization as agents mutate workflow states.
2. **Media Storage (Google Cloud Storage)**: Dedicated GCS buckets store raw uploaded video footage, extracted audio tracks, intermediate render segments, rendered cut masters, captions, and thumbnail images.
3. **Compute, Web & Routing (Google Cloud Run & Global Load Balancer)**: Both the frontend (`croviq-web` containerized React/Vite SPA) and backend (`croviq-api` Python 3.12 / FastAPI) are hosted on Google Cloud Run in `us-central1`. A Google Global External Application Load Balancer with Serverless NEGs provides a single public HTTPS origin at `https://app.croviq.app`, routing `/*` to `croviq-web` and `/api/*` to `croviq-api` without cross-origin CORS overhead (ADR-0013).
4. **Multimodal AI (Vertex AI)**: Gemini 3.7 Flash powers native video and audio understanding, dialogue editing proposals, metadata generation, and QA verification via the Google Gen AI SDK.
5. **Observability (Cloud Logging & Cloud Trace)**: Every log entry and span carries unified correlation fields (`run_id`, `mission_id`, `job_id`, `department`, `agent_name`, `trace_id`) exported as structured `jsonPayload` for instant filtering and auditability.

## Consequences
- Total operational simplicity: no VPCs, managed relational instances, or idle server costs.
- Real-time client reactivity out of the box via Firestore listeners.
- Strict isolation between high-bandwidth media bytes (GCS) and low-latency operational metadata (Firestore).
