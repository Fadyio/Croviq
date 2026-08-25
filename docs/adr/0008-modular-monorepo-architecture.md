# 0008: Modular Monorepo Architecture and Package Boundaries

## Context
Croviq encompasses client-side video editing interfaces, deterministic workflow state machines, multimodal LLM agent coordinators, heavy FFmpeg media processing, and Google Cloud observability. Bundling all logic into a single monolithic web application creates brittle dependencies and bloated builds. Conversely, microservices introduce excessive deployment and networking overhead for a rapid development cycle.

## Decision
We adopt a modular monorepo structure with explicit boundaries:
```text
apps/
  web/              # React + Vite + TypeScript frontend containerized for Cloud Run (pnpm)
  api/              # Python 3.12 + FastAPI backend Cloud Run service (uv)

packages/
  domain/           # Python / Pydantic models (canonical backend/domain contracts)
  engine/           # Python (deterministic workflow engine state machine and approval gate)
  agents/           # Python (department agents via Google GenAI SDK / Gemini 3.7 Flash)
  media/            # Python (deterministic FFmpeg execution, word alignment, and EDL processing)
  observability/   # Python (Cloud Logging structured loggers and request correlation)
```

Each package has strict dependencies:
- `packages/domain` has zero internal dependencies and is consumed by all backend packages; frontend TypeScript types/client are generated from FastAPI's OpenAPI schema.
- `packages/engine` depends only on `domain` and `observability`.
- `packages/agents` depends on `domain`, `observability`, and the Google GenAI SDK (`google-genai`).
- `packages/media` depends on `domain`, `observability`, and local FFmpeg/GCS utilities.
- `apps/web` consumes generated OpenAPI types/client and client-side UI libraries.
- `apps/api` orchestrates `engine`, `agents`, and `media`.

## Consequences
- Clean separation between client UI (TypeScript/pnpm), agent reasoning (Python/uv), and media rendering.
- Pydantic domain models serve as the single source of truth, producing OpenAPI contracts that guarantee type safety without manual synchronization.
- Independent testability for the engine, agents, and FFmpeg media processors using pytest.
