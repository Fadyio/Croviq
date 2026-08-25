# 0013: Google Cloud Application Load Balancer and Single-Origin Routing

## Context
Croviq previously utilized Cloudflare Workers/Pages for frontend hosting alongside Google Cloud Run for the backend API. While this provided quick initial edge static file serving, it introduced multiple operational and architectural frictions:
1. **Dual-Cloud Deployment Complexity**: Requiring Cloudflare deployment credentials and account tokens in GitHub Actions alongside Google Cloud Workload Identity Federation (WIF) introduced brittle multi-cloud failure points and API credential invalidations.
2. **Cross-Origin Complexity (CORS)**: Separate hostnames for frontend (`app.croviq.app`) and backend (direct Cloud Run URL `*.run.app`) required cross-origin CORS negotiation, complicated browser authentication token propagation, and forced build-time injection of ephemeral backend URLs (`VITE_API_BASE_URL`).
3. **Fragmented Observability**: Splitting runtime telemetry across Cloudflare and Google Cloud Logging degraded unified trace correlation and audit trails.

## Decision
We establish Google Cloud as the sole application runtime platform for both frontend and backend services, reducing Cloudflare's role strictly to authoritative DNS.

```
Cloudflare DNS (app.croviq.app)
              ↓
Google Global External Application Load Balancer
              ↓
      Google Managed TLS
              ↓
           URL Map
       ├── /*
       │     ↓
       │   Serverless NEG (croviq-web-neg)
       │     ↓
       │   croviq-web (Cloud Run / Containerized React + Vite)
       │
       └── /api/*
             ↓
           Serverless NEG (croviq-api-neg)
             ↓
           croviq-api (Cloud Run / Python 3.12 + FastAPI)
```

1. **Cloudflare Role**: DNS provider only. Cloudflare does not host, execute, or proxy application logic (no Cloudflare Workers, Pages, KV, R2, or runtime compute).
2. **Google Cloud Run Services**:
   - `croviq-web`: Containerized Nginx / lightweight web server hosting the compiled React/Vite single-page application.
   - `croviq-api`: Containerized Python 3.12 / FastAPI backend serving API endpoints and deterministic engine workloads.
3. **Global External Application Load Balancer & Serverless NEGs**:
   - A single Google Cloud Global External Application Load Balancer serves the production entrypoint `https://app.croviq.app`.
   - Serverless Network Endpoint Groups (NEGs) connect the Load Balancer backend services to the respective Cloud Run services in `us-central1`.
   - Google-managed SSL certificates provide automated HTTPS encryption.
4. **Single-Origin Path-Based Routing**:
   - `app.croviq.app/*` routes to `croviq-web`.
   - `app.croviq.app/api/*` routes to `croviq-api`.
   - **Native Prefix Ownership**: FastAPI natively owns and registers routes under the `/api` prefix (e.g. `/api/health`, `/api/auth/me`, `/api/workspaces`). The Load Balancer forwards requests without stripping or rewriting `/api`.
   - **Relative Frontend API Calls**: The frontend web client strictly uses relative `/api/...` endpoints for all data fetching and WebSocket connections. Build-time injection of direct Cloud Run hostnames is eliminated.
5. **Infrastructure as Code**: All Load Balancer components (forwarding rules, target HTTPS proxies, URL maps, backend services, and serverless NEGs) are managed authoritatively via Terraform in `infra/`.
6. **CI/CD Promotion**: GitHub Actions builds and pushes both `croviq-web` and `croviq-api` container images to Google Artifact Registry, authenticating keylessly via Google Cloud Workload Identity Federation.

## Consequences
- **Single Origin**: Complete elimination of cross-origin CORS complexity, preflight latency, and cross-site cookie/header restrictions in production.
- **Unified Observability**: End-to-end request tracing, load balancer latency, and application stdout logs reside entirely within Google Cloud Logging and Cloud Trace.
- **Simplified CI/CD**: Deployments rely solely on Google Cloud Workload Identity Federation; external Cloudflare deployment tokens and CLI tooling are eliminated.
- **Portable & Reproducible**: Evaluators and developers can deploy the entire production stack (load balancer, web, API, database, storage) into any Google Cloud project using Terraform alone.
