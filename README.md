# Croviq

> **Autonomous Multi-Agent Production Studio & Channel Intelligence for YouTube Creators**

[![Live Production](https://img.shields.io/badge/Production-app.croviq.app-2563eb?style=flat-square)](https://app.croviq.app)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Cloud%20Run%20%7C%20Vertex%20AI%20%7C%20Firestore-4285f4?style=flat-square&logo=googlecloud&logoColor=white)](https://cloud.google.com)
[![Gemini Models](https://img.shields.io/badge/Gemini-3.7%20Flash%20%7C%203.5%20Transcribe%20%7C%203.1%20TTS-8e75ff?style=flat-square&logo=googlegemini&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Terraform](https://img.shields.io/badge/IaC-100%25%20Terraform-844fba?style=flat-square&logo=terraform&logoColor=white)](infra/)
[![TypeScript](https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite%20%7C%20Tailwind%20v4-3178c6?style=flat-square&logo=typescript&logoColor=white)](apps/web/)
[![Python](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12%20%7C%20uv-3776ab?style=flat-square&logo=python&logoColor=white)](apps/api/)

---

Croviq is an autonomous, visible multi-agent production team and channel intelligence platform built for YouTube creators. Croviq learns a creator's channel, transforms raw video footage into polished releases with natural dialogue editing, synthesizes Studio Voice voiceover audio, mixes background music, executes continuous grounded web research with verifiable citations, and distills performance lessons into a persistent Channel Memory Bank.

- **Live Production Application**: [https://app.croviq.app](https://app.croviq.app)
- **Backend API Docs (Swagger)**: `http://localhost:8080/docs` (or production `/api/docs`)
- **GCP Production Project**: `croviq-506602` (Primary Region: `us-central1`)

---

## ⚡ Quickstart: Zero-to-Running in 60 Seconds

Croviq is designed for **100% reproducible local execution**. By default, it runs in **Deterministic Local Mode**—all AI agents, speech transcription, voice synthesis, GCS media storage, and Firestore persistence run against deterministic local implementations with zero cloud credentials or billing required.

### Step 1: Check Local Prerequisites

Ensure your workstation has the required tools installed:
- **Node.js**: `>= 20.0.0` (LTS recommended)
- **pnpm**: `>= 9.0.0` (`corepack enable && corepack prepare pnpm@11.23.0 --activate`)
- **Python**: `>= 3.12`
- **uv**: `>= 0.1.0` (Fast Python package installer: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **FFmpeg & FFprobe**: in your system `$PATH` (e.g. `brew install ffmpeg` on macOS)
- **Terraform**: `>= 1.5.0, < 2.0.0` (for infrastructure validation)

Run the environment doctor to verify your setup:
```bash
make doctor
```

```text
==================================================
 Croviq Local Development Environment Doctor
==================================================
TOOL           | REQUIRED           | FOUND              | STATUS
-----------------------------------------------------------------
python         | >= 3.12            | 3.12+              | ✓ OK
uv             | >= 0.1.0           | 0.12+              | ✓ OK
node           | >= 20.0.0          | 20+ / 22+          | ✓ OK
pnpm           | >= 9.0.0           | 11.23+             | ✓ OK
ffmpeg         | available          | 7+ / 8+ / 9+       | ✓ OK
ffprobe        | available          | 7+ / 8+ / 9+       | ✓ OK
terraform      | >= 1.5.0, < 2.0.0  | v1.5 - v1.16       | ✓ OK
==================================================
✓ All required local development tools are installed and operational.
```

---

### Step 2: One-Command Bootstrap

Bootstrap all frontend and backend dependencies and initialize local environment files:
```bash
make setup
```

This automatically:
1. Copies `.env.example` → `.env`
2. Copies `apps/web/.env.example` → `apps/web/.env.local`
3. Installs frontend dependencies with `pnpm install --frozen-lockfile`
4. Resolves and synchronizes Python dependencies across all workspace packages (`packages/domain`, `packages/observability`, `packages/media`, `packages/agents`, and `apps/api`) via `uv sync`.

---

### Step 3: Start Full-Stack Development

Start both the FastAPI backend and the Vite frontend concurrently with hot reloading:
```bash
make dev
```

The terminal will display the active services:
```text
==> Starting Croviq full-stack development environment...
    Backend API:  http://localhost:8080 (Health: http://localhost:8080/api/health)
    Frontend Web: http://localhost:5173
    Press Ctrl+C to terminate both servers.
```

---

### Step 4: Open and Explore the Studio

1. Navigate to **`http://localhost:5173`** in your browser.
2. Sign in using the pre-configured demo creator account:
   - **Email**: `demo@croviq.app`
   - **Password**: any password (or leave blank in local dev mode)
3. **Explore Key Capabilities**:
   - **Channel Intelligence Overview** (`/`): Inspect channel retention trends, subscriber growth velocity, Alex's Google Search-grounded competitive research findings with citations, and Channel Memory Bank lessons.
   - **Video Timeline & Dialogue Editor** (`/productions` → select any production → **Editor**): Inspect the interactive Twick multi-track timeline, synchronized transcript with word-level strike-through cuts, Leo's semantic dialogue edit decisions, Studio Voice synthesis preview, and Iris's quality control report.
   - **Release Gate & Packaging** (`/productions/.../release`): Inspect publishing assets (title, description, tags, QA certificate), human approval gate, and private YouTube release dispatch.
4. **Backend OpenAPI Documentation**: Explore interactive FastAPI Swagger endpoints at **`http://localhost:8080/docs`**.

---

## 🐳 Alternative Spin-Up: Docker Compose

If you prefer running inside containers without installing Python or Node locally:

```bash
# Build and start web and api containers
docker compose up --build
```

- **Frontend Web**: `http://localhost:5173`
- **Backend API**: `http://localhost:8080`
- **API Health**: `http://localhost:8080/api/health`

To stop containers:
```bash
docker compose down
```

---

## ☁️ Live Google Cloud / Vertex AI Connected Mode

To connect your local instance to live Google Cloud services (Vertex AI Gemini 3.7 Flash, Gemini Transcribe, Gemini TTS, Google Cloud Storage, and Google Agent Platform Memory Bank):

```bash
# 1. Authenticate with Google Cloud Application Default Credentials (ADC)
gcloud auth application-default login

# 2. Update .env to enable Google providers:
#    GCP_PROJECT_ID=croviq-506602
#    GENAI_BACKEND_PROVIDER=google
#    SPEECH_SERVICE_PROVIDER=google
#    MEDIA_STORAGE_PROVIDER=google
#    MEMORY_STORE_PROVIDER=google

# 3. Start local development
make dev
```

*(Note: Real YouTube channel OAuth connection requires your Google OAuth Client ID and Secret in `.env`; developer ADC handles all Vertex AI reasoning, speech, storage, and memory APIs.)*

---

## 🤖 Implemented Autonomous Production Team

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             CROVIQ PRODUCTION STUDIO                             │
├───────────────────────┬──────────────────────────┬───────────────────────────────┤
│   ALEX (Data Science) │     LEO (Video Editor)   │    IRIS (Quality Control)     │
├───────────────────────┼──────────────────────────┼───────────────────────────────┤
│ • Channel intelligence│ • Dialogue boundary cuts │ • Rendered artifact inspection│
│ • Google Search ground│ • Filler/pause removal   │ • Jump cut & dead air checks  │
│ • Python code analysis│ • Studio Voice synthesis │ • Loudness audit (~ -16 LUFS) │
│ • Falsifiable lessons │ • Audio-safe cut plan    │ • Caption sync & fact check   │
│ • Channel Memory Bank │ • Twick timeline sync    │ • Failsafe release gatekeeper │
└───────────────────────┴──────────────────────────┴───────────────────────────────┘
```

1. **Alex (Data Scientist)**:
   - Analyzes channel performance baselines, subscriber velocity, and retention drop-offs.
   - Executes live Google Search-grounded competitive research with verifiable URL citations.
   - Runs deterministic Python code execution in sandboxed environments for statistical correlation.
   - Distills evidence-backed, falsifiable insights into the persistent **Channel Memory Bank**.

2. **Leo (Video Editor)**:
   - Performs full-timeline semantic dialogue editing, identifying filler words, false starts, and redundant explanations.
   - Generates Edit Decision Lists (EDLs) with natural cut-safety micro-crossfades and audio envelope padding.
   - Rewrites and synthesizes voiceover scripts via **Gemini 3.1 Flash TTS Preview** with prebuilt voice personas.
   - Generates background music and audio-safe speech ducking.

3. **Iris (Quality Control & Gatekeeper)**:
   - Evaluates the rendered master video against strict broadcast and YouTube standards.
   - Verifies dialogue continuity, missing audio frames, audio loudness target (~ -16 LUFS), caption sync, and factual claims.
   - Produces immutable structured QA reports (`PASS`, `REVISE`, `CREATOR_REQUIRED`, `FAIL`).
   - Enforces deterministic human approval gates before triggering YouTube release publishers.

---

## 🧠 AI Models & Media Engineering Stack

| Capability | Model / Engine | Provider / Implementation |
| :--- | :--- | :--- |
| **Multimodal Agent Reasoning** | `gemini-3.7-flash` | Google GenAI SDK / Vertex AI |
| **Speech Transcription** | `gemini-3.5-transcribe-preview` | Vertex AI (Word-level timestamps & natural casing) |
| **Studio Voice Synthesis** | `gemini-3.1-flash-tts-preview` | Vertex AI (Puck, Charon, Aoede, Kore, Fenrir, Leda, Orus, Zephyr) |
| **Grounded Web Research** | Google Search Grounding | Gemini 3.7 Flash Tool Integration + URL Citations |
| **Statistical Analysis** | Python Code Execution | Vertex AI Built-in Code Execution Tool |
| **Channel Memory Bank** | Google Agent Platform | `ChannelProfile`, `ChannelLesson`, `ChannelExperiment` |
| **Deterministic Video Render** | FFmpeg 7+ | Cloud Run Worker / Micro-crossfades & EDL Rendering |
| **Multi-Track Timeline** | Twick (`@twick/timeline`) | React 19 + TypeScript Interactive Canvas |
| **Analytics Visualization** | Apache ECharts (`echarts`) | Responsive retention curves & metric trend charts |

---

## 🔒 Security, Authentication & Data Architecture

```text
                                  ┌────────────────────────┐
                                  │ Creator Browser Client │
                                  └───────────┬────────────┘
                                              │ 1. Email/Password Login
                                              ▼
                               ┌───────────────────────────────┐
                               │ Google Cloud Identity Platform│
                               │        (Firebase Auth)        │
                               └──────────────┬────────────────┘
                                              │ 2. Verified JWT Bearer
                                              ▼
                               ┌───────────────────────────────┐
                               │    FastAPI API Server         │
                               └──────┬─────────────────┬──────┘
             3. Signed URL V4 Uploads │                 │ 4. Encrypted OAuth Tokens
                                      ▼                 ▼
                       ┌────────────────────┐   ┌───────────────────────────┐
                       │ Google Cloud       │   │ Google Cloud Firestore    │
                       │ Storage (GCS)      │   │ (Encrypted with Cloud KMS │
                       │ croviq-media-raw   │   │  + Tink Symmetric AEAD)   │
                       └────────────────────┘   └───────────────────────────┘
```

- **Creator Authentication**: Built with Google Cloud Identity Platform (Firebase JS SDK on frontend, FastAPI token verification on backend). Requests fail closed unless authenticated.
- **YouTube Channel Integration**: Incremental Google OAuth 2.0 authorization for read-only YouTube Analytics/Data API access and optional private video publishing.
- **Secret Manager Protection**: Google OAuth client secret is securely stored in **Google Secret Manager** (`youtube-oauth-client-secret`) and mounted directly into the Cloud Run container. Zero secrets exist in code or Terraform state.
- **Token Envelope Encryption (KMS + Tink)**: User YouTube OAuth tokens are encrypted at rest using **Google Cloud KMS** (`youtube-oauth-kek`) + **Tink** symmetric key AEAD with Additional Authenticated Data (AAD binding `workspace_id`, `channel_id`, `user_id`) before storage in Firestore. **Zero plaintext tokens are ever stored or logged.**
- **Zero-Proxy Direct Media Uploads**: Raw 4K footage and media assets are uploaded directly from the browser to private Google Cloud Storage buckets via short-lived V4 signed URLs (1GB max file upload limit).

---

## 🌐 Production Cloud Topology (ADR-0013)

Croviq uses a single-origin routing architecture to eliminate CORS overhead, optimize cookie/token transmission, and ensure low-latency global delivery:

```text
                       https://app.croviq.app
                                 │
                                 ▼
                     Cloudflare Authoritative DNS
                                 │
                                 ▼
           Google Global External Application Load Balancer
                 (Managed SSL Certificate / Anycast IP)
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
                 ▼ /*                            ▼ /api/*
      Serverless Network Endpoint     Serverless Network Endpoint
            Group (NEG)                     Group (NEG)
                 │                               │
                 ▼                               ▼
        croviq-web (Cloud Run)          croviq-api (Cloud Run)
        React 19 + Vite SPA             Python 3.12 + FastAPI
        Static Asset Container          Deterministic Agent Engine
```

- **Production URL**: `https://app.croviq.app`
- **Root Domain**: `https://croviq.app` → HTTP 308 permanent redirect to `https://app.croviq.app`
- **Infrastructure as Code**: 100% Terraform definitions in `infra/` (GCP resources) and `infra/cloudflare-dns/` (DNS routing).

---

## 🧪 Verification & Quality Gate Reference

Croviq maintains a strict zero-regression quality gate. All checks can be executed locally:

| Command | Target | Description |
| :--- | :--- | :--- |
| `make doctor` | System | Verify all required local developer tools and versions |
| `make setup` | Setup | Bootstrap dependencies and generate missing `.env` configurations |
| `make dev` | Runtime | Launch full-stack environment (FastAPI on `:8080` + Vite on `:5173`) |
| `make dev-api` | Runtime | Start FastAPI backend server only (`http://localhost:8080`) |
| `make dev-web` | Runtime | Start Vite frontend dev server only (`http://localhost:5173`) |
| `make test` | Testing | Run all Python test suites across all 4 domain packages and API |
| `make e2e` | Testing | Run Playwright end-to-end browser test suite |
| `make typecheck` | Typing | Run TypeScript typechecking across workspace (`tsc --noEmit`) |
| `make lint` | Quality | Run Biome linter across the frontend codebase |
| `make format` | Quality | Apply Prettier code formatting across the repository |
| `make format-check` | Quality | Check code formatting without modifying files |
| `make openapi` | Contract | Export FastAPI OpenAPI 3.1 schema and generate TypeScript client types |
| `make infra-validate` | DevOps | Validate Terraform configurations across all infrastructure roots |
| `make security` | Security | Run secret scanning, AST security audit, and sandbox checks |
| `make verify` | **Gate** | **Canonical clean-room verification pipeline (runs all checks)** |

Run the full verification pipeline:
```bash
make verify
```

---

## 📂 Repository Structure

```text
croviq/
├── apps/
│   ├── web/                        # React 19 + Vite + Tailwind v4 + Twick SPA
│   │   ├── src/
│   │   │   ├── api/                # Auto-generated TypeScript API client contracts
│   │   │   ├── auth/               # Identity Platform & Firebase Auth context
│   │   │   ├── components/         # Timeline, VideoStage, ECharts, DecisionInspector
│   │   │   ├── pages/              # Overview (Alex), Editor (Leo), Release (Iris), Login
│   │   │   └── lib/                # Provenance tracking, EDL adapters, Firebase setup
│   │   └── e2e/                    # Playwright end-to-end browser test specifications
│   └── api/                        # Python 3.12 + FastAPI backend application
│       ├── src/croviq_api/
│       │   ├── auth/               # JWT token verification & access control
│       │   ├── channels/           # YouTube OAuth, Data API & grounded research routes
│       │   ├── productions/        # Editorial engine, EDL service, Studio Voice, render
│       │   ├── workspaces/         # Multi-tenant workspace management & agent chat
│       │   └── memory/             # Google Agent Platform Memory Bank integration
│       └── tests/                  # API integration and contract test suites
├── packages/
│   ├── domain/                     # Pure Python domain models (Workspaces, EDLs, Channels)
│   ├── agents/                     # Alex (Data Science), Leo (Editor), Iris (QC) agents
│   ├── media/                      # FFmpeg deterministic render pipelines & audio tools
│   └── observability/              # Structured JSON logging, telemetry & audit trails
├── infra/                          # 100% Terraform Google Cloud infrastructure definitions
│   ├── bootstrap/                  # Terraform state storage bucket & initial IAM
│   └── cloudflare-dns/             # Cloudflare DNS records & HTTPS redirect rules
├── docs/
│   ├── adr/                        # 17 Architectural Decision Records (ADRs)
│   ├── design/                     # Design system & dark workspace styling guidelines
│   └── specs/                      # Feature specifications & hero slice documentation
├── scripts/                        # Verification, doctor, OpenAPI exporter & security tools
├── docker-compose.yml              # Local multi-container development environment
├── Makefile                        # Canonical developer interface
├── openapi.json                    # Exported OpenAPI 3.1 schema specification
└── CONTEXT.md                      # Ubiquitous domain language and architectural glossary
```

---

## 📚 Architectural Decision Records (ADRs)

Key architectural and engineering decisions are documented in [`docs/adr/`](docs/adr/):

- [ADR-0001: Deterministic Engine with Coordinator / Director](docs/adr/0001-deterministic-engine-with-coordinator-director.md)
- [ADR-0002: Human Approval Gate for External Publishing](docs/adr/0002-human-approval-gate-for-external-publishing.md)
- [ADR-0003: Decoupled Editor UI and FFmpeg Rendering](docs/adr/0003-decoupled-editor-ui-and-ffmpeg-rendering.md)
- [ADR-0004: AI Dialogue and Narrative Editing Architecture](docs/adr/0004-ai-dialogue-and-narrative-editing-architecture.md)
- [ADR-0005: QA Evaluation and Revision Routing](docs/adr/0005-qa-evaluation-and-revision-routing.md)
- [ADR-0006: Creator Memory Evidence and Lessons](docs/adr/0006-creator-memory-evidence-and-lessons.md)
- [ADR-0007: Google Cloud Serverless Architecture](docs/adr/0007-google-cloud-serverless-architecture.md)
- [ADR-0008: Modular Monorepo Architecture](docs/adr/0008-modular-monorepo-architecture.md)
- [ADR-0009: Frontend UI Stack and Design Direction](docs/adr/0009-frontend-ui-stack-and-design-direction.md)
- [ADR-0010: Authentication and Incremental YouTube OAuth](docs/adr/0010-authentication-and-incremental-youtube-oauth.md)
- [ADR-0011: Reproducible Infrastructure and CI/CD Promotion](docs/adr/0011-reproducible-infrastructure-and-cicd-promotion.md)
- [ADR-0012: Python FastAPI Backend and Generated API Contracts](docs/adr/0012-python-fastapi-backend-and-generated-api-contracts.md)
- [ADR-0013: Google Cloud Load Balancer Single Origin Routing](docs/adr/0013-google-cloud-load-balancer-single-origin-routing.md)
- [ADR-0014: Google GenAI SDK and Agent Architecture](docs/adr/0014-google-genai-sdk-and-agent-architecture.md)
- [ADR-0015: Google Agent Platform Memory Bank](docs/adr/0015-google-agent-platform-memory-bank.md)
- [ADR-0016: Channel Data Provider Abstraction](docs/adr/0016-channel-data-provider-abstraction.md)
- [ADR-0017: Natural Cut Safety and Deterministic Media Rendering](docs/adr/0017-natural-cut-safety-and-deterministic-media-rendering.md)
