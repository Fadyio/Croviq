# 0012: Python 3.12 / FastAPI Backend and Generated API Contracts

## Context
Croviq requires an autonomous production backend capable of heavy multimodal AI orchestration, deep integration with Google Agent Development Kit (ADK) and Gemini 3.7 Flash, deterministic media manipulation with FFmpeg, word-level audio alignment, and auditable workflow execution. 

Earlier architectural drafts assumed a unified TypeScript stack across both frontend and backend. However:
1. Google's Agent Development Kit (ADK), Gemini SDKs, and multimodal reasoning tooling offer first-class, idiomatic support in Python.
2. Media processing, audio analysis, phonetic alignment, and numerical operations have a significantly richer and more mature ecosystem in Python.
3. Maintaining hand-written duplicate domain models in both TypeScript and Python creates unnecessary overhead, divergence risks, and synchronization friction.
4. There is no architectural requirement or operational benefit in forcing the frontend and backend to share a single runtime language.

## Decision
We adopt a Python 3.12 + FastAPI backend architecture with OpenAPI-generated client contracts:

1. **Backend Runtime & Framework**: Python 3.12 and FastAPI power the API server, Deterministic Workflow Engine, agent coordinators, and media processing services (`apps/api`).
2. **Python Package & Toolchain Management**: `uv` is the standardized package and project manager for all Python workspaces and virtual environments.
3. **Canonical Domain Schemas**: `packages/domain` contains canonical Pydantic v2 models defining all domain entities (`Mission`, `Run`, `Job`, `Artifact`, `EDL`, `QAReport`, `Lesson`, `Event`). Pydantic models are the single source of truth for all backend contracts.
4. **Contract-First API Interface (OpenAPI)**: FastAPI automatically generates the OpenAPI specification from the canonical Pydantic models and route signatures.
5. **Generated Frontend Contracts**: TypeScript types and API client code for `apps/web` will be generated directly from the OpenAPI schema. We strictly prohibit maintaining hand-written duplicate TypeScript domain schemas.
6. **Frontend Runtime & Toolchain**: The frontend (`apps/web`) remains React + Vite + TypeScript, managed with `pnpm`.
7. **Modular Python Packages**:
   - `packages/domain`: Python / Pydantic models (canonical backend/domain contracts).
   - `packages/engine`: Python (deterministic workflow engine state machine and approval gate).
   - `packages/agents`: Python (Google ADK / Gemini integrations and department reasoning).
   - `packages/media`: Python (FFmpeg execution, word-level alignment, and EDL processing).
   - `packages/observability`: Python (structured logging for Google Cloud Logging, OpenTelemetry tracing for Cloud Trace).
8. **Testing Toolchain**: Backend unit and integration testing is executed via `pytest`. Frontend unit and component testing is executed via `vitest` / Playwright.

## Consequences
- **First-Class AI/ML Ecosystem**: Direct, native access to Google ADK, Vertex AI / Gemini SDKs, and Python audio/video processing libraries without subprocess or IPC shims.
- **Single Source of Truth**: Backend Pydantic models authoritatively define domain schemas, automatically producing OpenAPI specifications consumed by the frontend.
- **Zero Schema Drift**: Client TypeScript types are generated from OpenAPI rather than manually synchronized.
- **High Performance & Developer Velocity**: `uv` provides sub-second package resolution and installation; FastAPI provides high-throughput asynchronous request handling on Google Cloud Run.
- **Clean Toolchain Isolation**: `pnpm` exclusively manages the JavaScript/TypeScript frontend workspaces (`apps/web`), while `uv` manages the Python backend services and packages.
