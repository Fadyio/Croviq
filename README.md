# Croviq

> **Autonomous Multi-Agent Production Studio & Channel Intelligence for YouTube Creators**

Croviq is an autonomous, visible multi-agent production team that learns a creator's channel, transforms raw video footage into polished releases with natural dialogue editing, generates Studio Voice audio and generative B-roll, executes continuous grounded channel research, and distills performance lessons into long-term Channel Memory.

---

## Implemented Autonomous Production Team

- **Alex (Data Scientist)**: Channel intelligence and research agent. Alex analyzes channel performance trends, executes automated Google Search-grounded research on configurable cadences with verifiable citations, runs Python code execution for statistical correlations, and distills falsifiable lessons into the persistent Channel Memory Bank.
- **Leo (Video Editor)**: Full-timeline dialogue and narrative editing agent. Leo inspects raw footage, demuxes multi-track audio, detects speech boundaries, eliminates filler/redundancy, generates candidates for vertical Shorts (9:16), rewrites Studio Voice voiceover scripts, and generates context-aware B-roll coverage.
- **Iris (Quality Control)**: Independent verification and release gatekeeper agent. Iris inspects the actual rendered video artifact for editing continuity, bad cuts, dead air, audio loudness (~ -16 LUFS target), caption sync, vertical Short framing, and factual consistency.
- **Maya (Director — Internal Review)**: Production quality director reviewing candidate cut decisions against multimodal footage and channel guidelines before deterministic Edit Decision List (EDL) compilation.
---

## Current AI Stack (Vertex AI & Google GenAI SDK)

- **Multimodal AI Reasoning**: Gemini 3.7 Flash (`gemini-3.7-flash`) on Vertex AI for agent decision-making, dialogue pass generation, and director review.
- **Speech Transcription**: Gemini 3.5 Transcribe Preview (`gemini-3.5-transcribe-preview`) on Vertex AI for word-level timestamped speech recognition with natural casing and punctuation.
- **Studio Voice Synthesis**: Gemini 3.1 Flash TTS Preview (`gemini-3.1-flash-tts-preview`) with prebuilt voice catalog (Puck, Charon, Aoede, Kore, Fenrir, Leda, Orus, Zephyr) and a bounded duration-fit loop.
- **B-Roll Visual Coverage Planning**: Visual continuity and B-roll recommendation planning (prompts, timing, framing, and keyframe transition specifications) planned by Leo.
- **Grounded Research & Execution**: Google Search grounding for live web knowledge retrieval + Python Code Execution for deterministic numeric analysis.
- **Channel Memory Bank**: Google Agent Platform Memory Bank (`ChannelProfile`, `ChannelLesson`, `ChannelExperiment`) for cross-production knowledge persistence.

---

## Authentication & Security Architecture

- **Creator Authentication**: Built with Firebase JS SDK (`12.18.0`) on the frontend client and Google Cloud Identity Platform on the backend. Creators authenticate via Email/Password. FastAPI verifies Firebase ID tokens on every request.
- **YouTube Channel Integration**: A separate Google OAuth 2.0 channel connection for read-only YouTube Data API and YouTube Analytics API authorization.
- **Application OAuth Secret Protection**: The Google OAuth client secret is securely stored in **Google Secret Manager** (`youtube-oauth-client-secret`) and injected into Cloud Run via native container `value_source.secret_key_ref` (never stored in Terraform state or repository code).
- **User YouTube Token Envelope Encryption**: User-authorized YouTube OAuth access and refresh tokens are encrypted at rest using **Tink + Google Cloud KMS** symmetric key encryption (`youtube-oauth-kek`) with Additional Authenticated Data (AAD binding `workspace_id`, `channel_id`, `user_id`) before storage in Firestore. **Zero plaintext tokens are ever stored in Firestore or emitted in logs.**
---

## Data & Storage Architecture

- **Google Cloud Storage (GCS)** (`croviq-media-raw`): Private, uniform-access bucket storing raw source footage, extracted 16kHz WAV audio, rendered Master MP4s, vertical Short MP4s, Studio Voice synthesis audio, and generative B-roll clips. Client uploads use short-lived V4 signed URLs with zero API server proxying.
- **Google Cloud Firestore (Native Mode)**: Native document database managing workspaces, productions, transcripts, editorial runs, assembled EDLs, render metadata, research runs, findings, and KMS-encrypted OAuth connection payloads.
- **Deterministic Rendering**: FFmpeg running in Cloud Run container worker threads executing typed Edit Decision Lists (EDLs) with natural cut-safety micro-crossfades and audio envelope padding.

---

## Production Topology & Single Origin (ADR-0013)

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

- **Production URL**: `https://app.croviq.app`
- **Root Domain**: `https://croviq.app` → HTTP 308 permanent redirect to `https://app.croviq.app`
- **GCP Project**: `croviq-506602` (Primary Region: `us-central1`)
- **Infrastructure as Code**: 100% Terraform-managed GCP infrastructure (`infra/`) and Cloudflare DNS (`infra/cloudflare-dns/`).

---

## Sample Data vs Connected Channel Truth

- **Sample Channel**: By default, Croviq provides a rich synthetic AI engineering YouTube channel (`SampleChannelDataProvider`) modeled strictly after real YouTube Data API and YouTube Analytics API schemas.
- **Research Findings**: Grounded research queries execute live via Gemini 3.7 Flash + Google Search grounding when the Google backend provider is active.
- **Connected Channel**: When a creator connects a real YouTube channel via OAuth, Croviq invokes the live YouTube Data API and YouTube Analytics API for authentic analytics and historical metrics.

---

## Local Development & Quickstart

The root `Makefile` is the canonical developer interface for Croviq.

### 1. Prerequisites
- **Python**: `>= 3.12`
- **uv**: `>= 0.1.0`
- **Node.js**: `>= 22.0.0`
- **pnpm**: `>= 9.0.0`
- **FFmpeg & FFprobe**: in system PATH
- **Terraform**: `>= 1.5.0, < 2.0.0`

Check your environment:
```bash
make doctor
```

### 2. Setup & Bootstrap
Bootstrap dependencies and initialize local `.env` files:
```bash
make setup
```

### 3. Development Paths

#### Path 1: Deterministic Local Mode (Zero Cloud Credentials Required)
All AI agents, transcription, speech synthesis, media storage, Firestore persistence, and memory banks run against deterministic in-memory implementations. No Google Cloud credentials or network connection required.
```bash
make dev
```
- **Frontend SPA**: `http://localhost:5173`
- **Backend API Health**: `http://localhost:8080/api/health`

#### Path 2: Full Verification Suite
Execute the complete clean-room verification pipeline (typechecks, linters, format checks, backend tests, OpenAPI contract sync, Terraform validation, security audits):
```bash
make verify
```

#### Path 3: Google-Backed Integration Mode
Test against live Google Cloud services (Vertex AI Gemini, Gemini Transcribe, Gemini TTS, GCS, Memory Bank) using Application Default Credentials (ADC):
```bash
# 1. Login with developer ADC
gcloud auth application-default login

# 2. Configure .env with Google provider flags:
#    GCP_PROJECT_ID=croviq-506602
#    GENAI_BACKEND_PROVIDER=google
#    SPEECH_SERVICE_PROVIDER=google
#    MEDIA_STORAGE_PROVIDER=google
#    MEMORY_STORE_PROVIDER=google

# 3. Start local development
make dev
```
*(Note: Real YouTube channel OAuth requires creator-provided Google OAuth Client ID and Secret in `.env`; ADC does not replace creator OAuth credentials.)*

---

## Developer Command Reference

| Command | Description |
| :--- | :--- |
| `make doctor` | Verify local developer tool installations and versions |
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
| `make openapi` | Synchronize OpenAPI 3.1 schema and TypeScript contract types |
| `make infra-validate` | Validate Terraform configurations across all Terraform roots |
| `make security` | Run repository secret scans, git history audits, and sandbox checks |
| `make verify` | **Canonical verification pipeline** (runs all checks and test suites) |

---

## Documentation Links

- [Engineering Principles & Guidelines](docs/ENGINEERING.md)
- [Design System & Workspace Layout](docs/design/DESIGN-SYSTEM.md)
- [Director & Editor Hero Slice Spec](docs/specs/DIRECTOR-EDITOR-VERTICAL-SLICE.md)
- [Domain Glossary](CONTEXT.md)
- [Architectural Decision Records (ADRs)](docs/adr/)
