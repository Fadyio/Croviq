# 0006: Channel Memory via Google Agent Platform Memory Bank

*Status: Historical Context (Reflects early multi-agent team design; canonical active agents are Alex, Leo, Iris)*

## Context
Croviq's production team (Maya, Leo, Alex, Nina, Iris) requires persistent, shared long-term memory across productions to learn from past channel performance, audience retention curves, packaging CTRs, and editorial guidelines. Storing memory as unstructured conversational chat dumps leads to hallucinated, untestable advice. Conversely, deploying external vector databases (Pinecone, Weaviate, pgvector) introduces unnecessary operational complexity, separate infrastructure failure modes, and cost overhead.

## Decision
We implement Channel Memory using Google Agent Platform Memory Bank directly from FastAPI:

1. **Shared Long-Term Memory (Google Agent Platform Memory Bank)**:
   - Memory Bank is the centralized long-term memory store accessible to all production agents.
   - Eliminates all external vector databases, embedding infrastructure, and ADK runtime lock-in.
   - Operational application data remains in Google Cloud Firestore Native Mode; Memory Bank serves strictly as shared long-term agent memory.

2. **Core Memory Profiles**:
   - **`ChannelProfile`**: Structured profile capturing inferred channel niche, topics, primary audience geographies, content pillars, baseline performance metrics, and recurring retention patterns.
   - **`ChannelLesson`**: Actionable, evidence-backed rules (`lesson_id`, `observation`, `evidence`, `confidence`, `recommended_action`, `applies_to`, `source_runs`).
   - **`ChannelExperiment`**: Structured hypotheses, treatments, baselines, and evaluation metrics designed by Alex (Data Scientist) to validate production optimizations.

3. **Feedback Loop (DevOps for Creators)**:
   ```text
   Alex Analyzes Channel Analytics & Baselines
     -> Writes Falsifiable Lessons to Memory Bank
     -> Maya Reads Relevant Lessons on Raw Ingest
     -> Leo Applies Narrative Constraints
     -> Master Published & Measured
     -> Memory Bank Updated with New Evidence
   ```

## Consequences
- Shared, consistent channel intelligence without managing custom vector stores or embeddings.
- Production rules are falsifiable and grounded in measurable YouTube performance evidence.
- Seamless memory access directly from FastAPI via Google Cloud client libraries.
