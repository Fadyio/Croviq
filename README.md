# Croviq

> **DevOps for YouTube creators**: an autonomous, visible production team that learns the channel, transforms raw footage into a release, validates the work, learns from performance, and feeds those lessons into the next production.

Croviq operates like a professional media production company at the creator's workstation:
- **Maya (Director)**: Senior production lead who inspects footage, reads Channel Memory, guides editorial strategy, reviews edit batches, and approves masters.
- **Leo (Editor)**: Dialogue editor who performs semantic passes, eliminates filler/redundancy, applies natural cut safety, and renders masters and vertical Shorts.
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

- **Multimodal AI Reasoning**: Gemini 3.7 Flash via Google GenAI SDK (`google-genai`) on Vertex AI / Gemini API.
- **Shared Long-Term Memory**: Google Agent Platform Memory Bank (`ChannelProfile`, `ChannelLesson`).
- **Operational Data & State**: Google Cloud Firestore Native Mode (`us-central1`).
- **Media Storage**: Google Cloud Storage (GCS) private buckets.
- **Deterministic Rendering**: FFmpeg on Google Cloud Run executing typed Edit Decision Lists (EDLs).
- **Frontend Workstation**: React, Vite, TypeScript, Tailwind CSS, Twick timeline adapter, Motion for React, Lucide.
- **Backend API**: Python 3.12, FastAPI, Pydantic v2, `uv`.
- **Infrastructure as Code**: 100% Terraform-managed GCP and Cloudflare DNS resources.

---

## Sample Channel Disclosure

Croviq includes a deterministic sample AI engineering channel (~50,000 subscribers, 100 historical videos, ~18 months history) for evaluation and judging. Public-style metadata and synthetic private analytics (retention curves, impressions, CTR, traffic sources) are shaped to the exact contracts used by the real YouTube adapter. Real creator-owned YouTube channels connect via the YouTube Channel Data Provider with incremental OAuth permissions.

---

## Local Development

### Prerequisites
- Docker & Docker Compose
- pnpm (Node.js 20+)
- Python 3.12 & uv
- Terraform 1.5+

### Quick Start
```bash
# Start local development environment
docker compose up --build

# Frontend: http://localhost:5173
# API:      http://localhost:8080/api/health
```

### Testing & Verification
```bash
# Backend pytest suite
cd apps/api && uv run pytest

# Domain package tests
cd packages/domain && uv run pytest

# Observability package tests
cd packages/observability && uv run pytest

# Frontend typechecking & linting
pnpm -r typecheck
pnpm -r lint
pnpm format:check

# End-to-end browser tests
pnpm e2e
```

### Terraform Validation
```bash
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```

---

## Documentation

- [Engineering Principles & Guidelines](docs/ENGINEERING.md)
- [Design System & Workspace Layout](docs/design/DESIGN-SYSTEM.md)
- [Director & Editor Hero Slice Spec](docs/specs/DIRECTOR-EDITOR-VERTICAL-SLICE.md)
- [Domain Glossary](CONTEXT.md)
- [Architectural Decision Records (ADRs)](docs/adr/)
