# 0012: Python 3.12 / FastAPI Backend and Generated API Contracts

## Context
Croviq requires an autonomous production backend capable of heavy multimodal AI orchestration, deep integration with Google GenAI SDK and Gemini 3.7 Flash, deterministic media manipulation with FFmpeg, word-level audio alignment, and auditable workflow execution. 

Earlier architectural drafts assumed a unified TypeScript stack across both frontend and backend. However:
1. Google's GenAI SDK (`google-genai`), Gemini APIs, and multimodal reasoning tooling offer first-class, idiomatic support in Python.
2. Media processing, audio analysis, phonetic alignment, and numerical operations have a significantly richer and more mature ecosystem in Python.
3. Maintaining hand-written duplicate domain models in both TypeScript and Python creates unnecessary overhead, divergence risks, and synchronization friction.
4. There is no architectural requirement or operational benefit in forcing the frontend and backend to share a single runtime language.

## Decision
We adopt a Python 3.12 + FastAPI backend architecture with OpenAPI-generated client contracts:

1. **Backend Runtime & Framework**: Python 3.12 and FastAPI power the API server, Deterministic Workflow Engine, agent coordinators, and media processing services (`apps/api`). FastAPI natively owns and registers endpoints under the `/api` prefix (e.g. `/api/health`, `/api/auth/me`, `/api/workspaces`), aligning directly with the Google Cloud Load Balancer single-origin routing rules (ADR-0013).
2. **Python Package & Toolchain Management**: `uv` is the standardized package and project manager for all Python workspaces and virtual environments.
3. **Canonical Domain Schemas**: `packages/domain` contains canonical Pydantic v2 models defining all domain entities (`Workspace`, `Production`, `Run`, `Job`, `Artifact`, `EDL`, `QAReport`, `ChannelLesson`, `Event`). Pydantic models are the single source of truth for all backend contracts.
4. **Contract-First API Interface (OpenAPI)**: FastAPI automatically generates the OpenAPI specification from the canonical Pydantic models and route signatures.
5. **Generated Frontend Contracts**: TypeScript types and API client code for `apps/web` are generated directly from the FastAPI OpenAPI schema. Frontend data fetching strictly targets relative `/api/...` endpoints on the single origin `https://app.croviq.app`, eliminating build-time direct backend hostnames. We strictly prohibit maintaining hand-written duplicate TypeScript domain schemas.
6. **Frontend Runtime & Toolchain**: The frontend (`apps/web`) remains React + Vite + TypeScript, managed with `pnpm` and containerized for Cloud Run.
7. **Modular Python Packages**:
   - `packages/domain`: Python / Pydantic models (canonical backend/domain contracts).
   - `packages/engine`: Python (deterministic workflow engine state machine and approval gate).
   - `packages/agents`: Python (Google GenAI SDK / Gemini integrations and department reasoning).
   - `packages/media`: Python (FFmpeg execution, word-level alignment, and EDL processing).
   - `packages/observability`: Python (structured logging for Google Cloud Logging).
8. **Testing Toolchain**: Backend unit and integration testing is executed via `pytest`. Frontend unit and component testing is executed via Playwright and component tests.

## Consequences
- Direct, native access to Google GenAI SDK, Vertex AI / Gemini APIs, and Python audio/video processing libraries without subprocess or IPC shims.
- Backend Pydantic models authoritatively define domain schemas, automatically producing OpenAPI specifications consumed by the frontend.
- Zero schema drift between frontend and backend.
- `uv` provides sub-second package resolution and installation; FastAPI provides high-throughput asynchronous request handling on Google Cloud Run.
