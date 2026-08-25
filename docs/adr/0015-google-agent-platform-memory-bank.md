# 0015: Google Agent Platform Memory Bank for Long-Term Channel Intelligence

## Context
Croviq agents require persistent long-term memory across video productions to retain learned audience preferences, recurring retention drop-off points, successful packaging styles, and editorial guidelines. Introducing external vector databases (Pinecone, Weaviate, pgvector) adds separate vendor dependencies, operational fragility, and latency.

## Decision
1. **Google Agent Platform Memory Bank**: We integrate Google Agent Platform Memory Bank directly from `croviq-api` in FastAPI as the shared long-term memory store.
2. **Memory Data Models**:
   - `ChannelProfile`: Channel niche, primary topics, audience demographics, content pillars, baseline performance metrics.
   - `ChannelLesson`: Structured, evidence-backed rules (`directive`, `target_agent`, `evidence_summary`, `confidence`, `status`).
   - `ChannelExperiment`: Falsifiable hypothesis testing records created and evaluated by Alex (Data Scientist).
3. **Operational Separation**:
   - Firestore Native Mode stores operational application documents (Workspaces, Productions, Runs, Jobs, Artifacts).
   - Memory Bank stores semantic, long-term cross-production channel context.
   - GCS stores media bytes.
   - No external vector database is used.

## Consequences
- Native Google Cloud ecosystem integration on Cloud Run without extra database provisioning.
- Unified semantic memory layer accessible across all agent roles.
- Clean separation between transactional operational state and long-term channel intelligence.
