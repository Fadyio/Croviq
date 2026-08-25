# 0008: Modular Monorepo Architecture and Package Boundaries

## Context
Croviq encompasses client-side video editing interfaces, deterministic workflow state machines, multimodal LLM agent coordinators, heavy FFmpeg media processing, and Google Cloud observability. Bundling all logic into a single monolithic web application creates brittle dependencies and bloated builds. Conversely, microservices introduce excessive deployment and networking overhead for a rapid development cycle.

## Decision
We adopt a modular monorepo structure with explicit boundaries:
```
apps/
  web/              # React + Vite frontend (Twick timeline, transcript, mission UI)
  api/              # Cloud Run service (REST/WebSocket endpoints, workflow coordinator)

packages/
  domain/           # Canonical Zod schemas and TypeScript types (Mission, Run, Job, EDL, etc.)
  engine/           # Deterministic workflow engine state machine and approval gate
  agents/           # Department agents (Director, Editor, Packaging, QA, Data Science) via Vertex AI
  media/            # Deterministic FFmpeg execution, word alignment, and EDL processing
  observability/   # OpenTelemetry, Cloud Logging structured loggers, and Trace correlation
```

Each package has strict dependencies:
- `packages/domain` has zero internal dependencies and is consumed by all apps and packages.
- `packages/engine` depends only on `domain` and `observability`.
- `packages/agents` depends on `domain`, `observability`, and Vertex AI SDKs.
- `packages/media` depends on `domain`, `observability`, and local FFmpeg/GCS utilities.
- `apps/web` consumes `domain` and client-side UI libraries.
- `apps/api` orchestrates `engine`, `agents`, and `media`.

## Consequences
- Clean compile-time separation between client UI, agent reasoning, and media rendering.
- Shared domain contracts guarantee type safety between backend execution and frontend visualization.
- Independent testability for the engine, agents, and FFmpeg media processors.
