# Croviq

> **DevOps for YouTube creators**: an autonomous, visible production team that learns the channel, transforms raw footage into a release, validates the work, learns from performance, and feeds those lessons into the next production.

### Implemented Autonomous Agents
- **Leo (Video Editor)**: Video Editor responsible for full-video inspection, full-timeline editorial planning, real media tool use, test rendering, self-review, semantic cuts, Short candidate selection, Studio Voice narration rewriting, and B-roll decisions when useful.
- **Maya (Director)**: Director who reviews Leo's edit plan, reviews rendered Preview, requests at most one correction, and approves final output.

### Planned Agents
- **Alex (Data Scientist)**: Statistical intelligence agent who detects retention patterns, baseline shifts, and feeds falsifiable lessons into long-term Channel Memory.
- **Nina (Packaging)**: Metadata, chapters, title rankings, and thumbnail concept generation.
- **Iris (Quality Assurance)**: Independent verification of factual claims, captions, timestamps, and publishing readiness.
---

## Production Topology & Single Origin

```text
Cloudflare (Authoritative DNS Only)
                 │
                 ▼
Google Global External Application Load Balancer
                 │
                 ├── app.croviq.app/*
                 │      -> Serverless NEG
                 │      -> croviq-web (Cloud Run / React + Vite SPA)
                 │
                 └── app.croviq.app/api/*
                        -> Serverless NEG
                        -> croviq-api (Cloud Run / Python 3.12 + FastAPI)
```

- **Production App**: `https://app.croviq.app`
- **Root Domain**: `https://croviq.app` → HTTP 308 permanent redirect to `https://app.croviq.app`
- **GCP Project**: `croviq-506602`
- **Primary Region**: `us-central1`

---

## Technology Stack

- **Multimodal AI Reasoning**: Gemini 3.7 Flash (`gemini-3.7-flash`) via Google GenAI SDK (`google-genai`) on Vertex AI.
- **Speech Transcription**: Gemini 3.5 Transcribe Preview (`gemini-3.5-transcribe-preview`) on Vertex AI.
- **Studio Voice**: Gemini 3.1 Flash TTS (`gemini-3.1-flash-tts-preview`) with prebuilt voice catalog (Puck, Charon, Aoede, Kore, Fenrir, Leda, Orus, Zephyr) via Google GenAI SDK.
- **Generative Video / B-Roll**: Gemini Omni 1.1 Flash (`gemini-omni-1.1-flash`) on Vertex AI with scene extension (up to 10s), keyframe control, and 360p drafting mode.
- **Agent Tool Runtime**: Deterministic `ToolRegistry` with 13 internal sandboxed tools for media inspection, audio demuxing, waveform analysis, and EDL candidate generation.
- **Silence / Pause Processing**: Deterministic silence/pause cleanup with cut-safety validation.
- **Authentication**: Firebase JS SDK (`12.18.0`) on client + Google Cloud Identity Platform + Firebase Admin token verification on FastAPI backend.
- **Shared Long-Term Memory**: Google Agent Platform Memory Bank (`ChannelProfile`, `ChannelLesson`).
- **Storage Separation**:
  - **Google Cloud Storage (GCS)**: Stores source footage, rendered Preview, Master, Short, Studio Voice audio, and generated B-roll media artifacts.
  - **Google Cloud Firestore**: Stores workspaces, productions, transcripts, editorial runs, agent activity, EDLs, render metadata, reviews, and operational state.
- **DNS & Routing**: Cloudflare (Authoritative DNS Only) + Google Global External Application Load Balancer (single-origin routing to Cloud Run).
- **Timeline Component**: `@twick/timeline` (https://github.com/ncounterspecialist/twick).
- **Deterministic Rendering**: FFmpeg on Google Cloud Run executing typed Edit Decision Lists (EDLs).
- **Frontend Workstation**: React 19.2.8, Vite 8.2.2 (Rolldown unified bundler), TypeScript 5.9.3, Tailwind CSS 4.3.3 (`@tailwindcss/vite`), Firebase JS SDK 12.18.0, Motion 13.1.1, Lucide-react 1.34.0, `@twick/timeline` 0.15.31, Playwright 1.62.1.
- **Backend API**: Python 3.12, FastAPI, Pydantic v2, `google-genai` 2.20.0, `uvicorn`, `uv`.
- **Infrastructure as Code**: 100% Terraform-managed GCP and Cloudflare DNS resources.
## Local Development

The root `Makefile` is the canonical developer interface for Croviq.

### 1. Prerequisites
- **Python**: `>= 3.12`
- **uv**: `>= 0.1.0` (Fast Python package manager)
- **Node.js**: `>= 20.0.0` (LTS recommended)
- **pnpm**: `>= 9.0.0` (Package manager)
- **FFmpeg & FFprobe**: available in PATH (for media inspect, extract, and render)
- **Terraform**: `>= 1.5.0, < 2.0.0` (for infrastructure validation)

Check your environment at any time:
```bash
make doctor
```

### 2. Setup & Bootstrap
Bootstrap all workspace dependencies and create local `.env` files from templates:
```bash
make setup
```
This safely creates `.env` and `apps/web/.env.local` if missing without overwriting existing configurations or populating secrets.

### 3. Local Development Modes

#### Mode A: Deterministic Local / Test Mode (Default — Zero Cloud Cost)
All integrations (GenAI, Speech Transcription, GCS Media Storage, Firestore, Memory Bank) run against deterministic in-memory providers. No Google credentials or cloud connectivity required.
```bash
# Start full-stack local development (API + Web)
make dev

# Or start services individually:
make dev-api   # Backend API on http://localhost:8080
make dev-web   # Frontend Web on http://localhost:5173
```
- **Frontend**: `http://localhost:5173`
- **Backend Health**: `http://localhost:8080/api/health`

#### Mode B: Google-Backed Integration Mode
To test against real Google Cloud services (Vertex AI Gemini, Gemini Transcribe, GCS, Memory Bank) using Application Default Credentials (ADC):
```bash
# 1. Authenticate local workstation ADC
gcloud auth application-default login

# 2. Update .env:
#    GCP_PROJECT_ID=croviq-506602
#    GENAI_BACKEND_PROVIDER=google
#    SPEECH_SERVICE_PROVIDER=google
#    MEDIA_STORAGE_PROVIDER=google
#    MEMORY_STORE_PROVIDER=google

# 3. Start local development
make dev
```
*Note: Service-account JSON keys are never used for local development. Production uses Cloud Run service account ADC, and CI/CD uses GitHub Workload Identity Federation (WIF).*

---

## Developer Commands & Verification

| Target | Description |
| :--- | :--- |
| `make help` | Display all available Makefile targets |
| `make doctor` | Verify local tool installations and versions |
| `make setup` | Install Node + Python dependencies and initialize `.env` files |
| `make dev` | Start full-stack development environment (API + Web concurrently) |
| `make dev-api` | Run FastAPI backend server on `:8080` with hot reload |
| `make dev-web` | Run Vite frontend development server on `:5173` |
| `make test` | Run complete Python backend and domain package test suites |
| `make e2e` | Run Playwright end-to-end browser test suite |
| `make typecheck` | Run workspace TypeScript typechecking (`tsc --noEmit`) |
| `make lint` | Run workspace linters |
| `make format` | Apply Prettier code formatters across the repository |
| `make format-check` | Check code formatting without modifying files |
| `make openapi` | Export OpenAPI 3.1 schema and generate TypeScript contract types |
| `make infra-validate` | Validate Terraform configurations across all Terraform roots |
| `make security` | Run repository secret scans, git history audits, and sandbox checks |
| `make verify` | **Canonical verification pipeline** (runs all tests, checks, and audits) |

---

## Pre-Commit & CI Verification

Before submitting changes, run the canonical verification target:
```bash
make verify
```
This executes:
1. `make doctor` (dependency verification)
2. `make format-check` (Prettier code style)
3. `make lint` (workspace linters)
4. `make typecheck` (TypeScript validation)
5. `make test` (350+ unit and integration tests across 5 packages)
6. `make openapi` (contract synchronization and drift check)
7. `make infra-validate` (Terraform syntax and schema validation)
8. `make security` (secret scans, git history audit, terminal sandbox verification)

---

## Documentation

- [Engineering Principles & Guidelines](docs/ENGINEERING.md)
- [Design System & Workspace Layout](docs/design/DESIGN-SYSTEM.md)
- [Director & Editor Hero Slice Spec](docs/specs/DIRECTOR-EDITOR-VERTICAL-SLICE.md)
- [Domain Glossary](CONTEXT.md)
- [Architectural Decision Records (ADRs)](docs/adr/)
