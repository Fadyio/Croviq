# Engineering Principles

## Core Principles

- **Decoupled components**
- **Reusable modules**
- **Idempotent operations**
- **Explicit interfaces/contracts**
- **Structured observability**
- **Least-privilege security**
- **Configuration separated from code**
- **No hidden environment assumptions**
- **One feature at a time**
- **Local test before commit**
- **Push to main only after local verification**
- **Verify deployment/logs before declaring work complete**

## Production Topology (ADR-0013)

- **Authoritative DNS**: Cloudflare (DNS only; no Workers, Pages, KV, R2, or edge runtime execution).
- **Entrypoint & Routing**: Single public origin at `https://app.croviq.app` via Google Global External Application Load Balancer with Serverless NEGs.
  - `https://app.croviq.app/*` → `croviq-web` (Cloud Run containerized React/Vite SPA).
  - `https://app.croviq.app/api/*` → `croviq-api` (Cloud Run Python 3.12 / FastAPI backend).
- **Native Routing**: FastAPI natively owns `/api` route prefixes; frontend uses relative `/api/...` calls without cross-origin CORS overhead.
- **Infrastructure as Code**: 100% Google Cloud infrastructure managed via Terraform in `infra/`.

## Definition of Done

For all future features:

1. **CODED**
2. **TESTED LOCALLY**
3. **COMMITTED**
4. **PUSHED**
5. **DEPLOYED** (when applicable)
6. **LOGS VERIFIED** (when applicable)
7. **BROWSER VERIFIED** (when applicable)

## Promotion Workflow

```
LOCAL
→ COMMIT
→ PUSH
→ CI
→ DEPLOY
→ LOG VERIFY
→ BROWSER VERIFY
```

Production infrastructure changes are never applied manually from application code.

