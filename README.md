# Croviq

Production entrypoint:
https://app.croviq.app (Google Cloud Global External Application Load Balancer)

Architecture:
Cloudflare (DNS Only) → Google Global External Application Load Balancer → Serverless NEGs → Cloud Run (croviq-web: /*, croviq-api: /api/*)

Infrastructure:
Terraform (Google Cloud)
Production GCP project:
croviq-506602

Primary region:
us-central1

> **Portability Note**: Reusable Terraform configurations in `infra/` accept any standard Google Cloud `project_id` via variables, allowing judges and developers to deploy isolated Croviq environments into their own GCP projects.

## Local Development

### Prerequisites
- Docker
- pnpm
- Python 3.12
- uv
- Terraform

### Quick start
```bash
docker compose up --build
```

- **Frontend**: http://localhost:5173
- **API**: http://localhost:8080/api/health

### Logs
```bash
docker compose logs -f web
docker compose logs -f api
```

### Tests
```bash
pnpm e2e

cd apps/api && uv run pytest

pnpm -r build
pnpm -r typecheck
pnpm -r lint
pnpm format:check
```

### Terraform validation
```bash
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```

For fresh GCP project bootstrap, remote Terraform state, `project_id` configuration, and production infrastructure, see [infra/README.md](infra/README.md).

## Repository Structure

```
Croviq/
├── apps/
├── packages/
├── infra/
├── scripts/
├── docs/
├── .gitignore
└── README.md
```

## Documentation

- [Engineering Principles](docs/ENGINEERING.md)
- [Infrastructure & Deployment Guide](infra/README.md)
