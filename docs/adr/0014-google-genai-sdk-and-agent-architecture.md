# 0014: Google GenAI SDK and Visible Production Team Architecture

*Status: Historical Context (Agent roster refined to canonical 3: Alex Data Scientist, Leo Video Editor, Iris Quality Control)*

## Context
Croviq requires an AI agent architecture to power specialized creative agents: Maya (Director), Leo (Editor), Alex (Data Scientist), Nina (Packaging), and Iris (QA). Hackathon compliance mandates at least one approved Google Agent Framework, Gemini 3.5 or newer, and Google Cloud infrastructure. Using excessive abstraction frameworks (such as full ADK when direct GenAI SDK suffices) adds unnecessary complexity, configuration overhead, and debugging latency to a tight 5-day delivery schedule.

## Decision
1. **Agent Framework Compliance**: We standardize on the official **Google GenAI SDK (`google-genai`)** in Python 3.12 running against Vertex AI / Gemini API.
2. **Model Target**: Gemini 3.7 Flash is the primary reasoning model for all department agents, configured via a centralized configuration variable (`GEMINI_MODEL_ID`) rather than hardcoded strings.
3. **Structured Outputs**: All agent invocations enforce typed Pydantic output schemas (e.g. `DialoguePassReport`, `DirectorReviewDecision`, `EditDecisionList`). Raw unstructured text scraping is strictly prohibited.
4. **Static Visible Identities**:
   - Maya (Director): Senior production lead, strategic coordination, batch review.
   - Leo (Editor): Dialogue pass, filler removal, pacing, Short extraction.
   - Alex (Data Scientist): Statistical analysis, baseline estimation, retention diagnostics.
   - Nina (Packaging): Title rankings, descriptions, chapters, thumbnail concepts.
   - Iris (QA): Factual verification, timestamp integrity, caption sync.
5. **Concise Summary Visibility**: The UI exposes concise action/reason summaries (e.g. "Removing repeated explanation at 02:14–02:27") rather than raw chain-of-thought dumps or verbose internal prompts.
6. **Structured AI Telemetry**: Every model call emits structured logs to stdout capturing `agent`, `model`, `run_id`, `job_id`, `input_tokens`, `output_tokens`, `latency_ms`, and `status`.

## Consequences
- 100% compliant with hackathon Google Agent Framework and Gemini requirements.
- Zero extra runtime dependencies; lightweight, high-performance execution on Cloud Run.
- Type-safe, verifiable agent reasoning with complete operational auditability.
