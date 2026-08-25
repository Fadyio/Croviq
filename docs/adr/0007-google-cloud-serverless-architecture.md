# 0007: Google Cloud Serverless Architecture and State Partitioning

## Context
Croviq requires an infrastructure stack on Google Cloud (`us-central1`) that supports heavy multimodal video processing, real-time agent workflow updates in the browser, structured operational state management, and end-to-end observability, while scaling to zero and avoiding unnecessary operational overhead during development and hackathon evaluation.

## Decision
We adopt a serverless, decoupled Google Cloud architecture:
1. **Operational State & Memory (Firestore Native Mode)**: Firestore stores all structured operational documents: Workspaces, Missions, Runs, Jobs, Artifacts metadata, QA Reports, and Creator Memory Lessons. Real-time document snapshot listeners provide low-latency UI synchronization as agents mutate workflow states.
2. **Media Storage (Google Cloud Storage)**: Dedicated GCS buckets store raw uploaded video footage, extracted audio tracks, intermediate render segments, rendered cut masters, captions, and thumbnail images.
3. **Compute & Rendering (Google Cloud Run)**: A unified containerized Node.js/TypeScript backend hosts the API, the Deterministic Workflow Engine, and headless FFmpeg rendering workers.
4. **Multimodal AI (Vertex AI)**: Gemini 3.7 Flash powers native video and audio understanding, dialogue editing proposals, metadata generation, and QA verification via the Google Gen AI SDK.
5. **Observability (Cloud Logging & Cloud Trace)**: Every log entry and span carries unified correlation fields (`run_id`, `mission_id`, `job_id`, `department`, `agent_name`, `trace_id`) exported as structured `jsonPayload` for instant filtering and auditability.

## Consequences
- Total operational simplicity: no VPCs, managed relational instances, or idle server costs.
- Real-time client reactivity out of the box via Firestore listeners.
- Strict isolation between high-bandwidth media bytes (GCS) and low-latency operational metadata (Firestore).
