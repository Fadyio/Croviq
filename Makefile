# =============================================================================
# Croviq Canonical Root Makefile
# =============================================================================
# Single canonical entrypoint for local development, verification, and CI.
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: help doctor setup dev dev-api dev-web test e2e typecheck lint format format-check openapi infra-validate security verify

# -----------------------------------------------------------------------------
# 1. HELP & DISCOVERY
# -----------------------------------------------------------------------------
help:
	@echo "================================================================="
	@echo " Croviq Developer Workflow Targets"
	@echo "================================================================="
	@echo "  make doctor         Verify required local development tools & versions"
	@echo "  make setup          Bootstrap repo: install deps & create missing .env"
	@echo "  make dev            Start both Backend API and Frontend Web concurrently"
	@echo "  make dev-api        Start Backend API server only (:8080)"
	@echo "  make dev-web        Start Frontend Web Vite dev server only (:5173)"
	@echo "  make test           Run all Python backend & domain package test suites"
	@echo "  make e2e            Run Playwright end-to-end browser tests"
	@echo "  make typecheck      Run workspace TypeScript typechecking"
	@echo "  make lint           Run configured linters"
	@echo "  make format         Apply repository code formatters (Prettier)"
	@echo "  make format-check   Check code formatting without modifying files"
	@echo "  make openapi        Export FastAPI OpenAPI 3.1 & generate TypeScript contracts"
	@echo "  make infra-validate Terraform format check and validation across all roots"
	@echo "  make security       Run reproducible local security and secret scans"
	@echo "  make verify         Canonical pre-commit / CI verification suite"
	@echo "================================================================="

# -----------------------------------------------------------------------------
# 2. ENVIRONMENT & BOOTSTRAP
# -----------------------------------------------------------------------------
doctor:
	@python3 scripts/doctor.py

setup: doctor
	@echo "==> Setting up local environment and dependencies..."
	@if [ ! -f .env ]; then \
		echo "Creating .env from .env.example..."; \
		cp .env.example .env; \
	fi
	@if [ ! -f apps/web/.env.local ]; then \
		echo "Creating apps/web/.env.local from apps/web/.env.example..."; \
		cp apps/web/.env.example apps/web/.env.local; \
	fi
	@echo "==> Installing Node/Frontend dependencies with pnpm..."
	@pnpm install --frozen-lockfile
	@echo "==> Installing Python dependencies with uv..."
	@uv sync --directory packages/domain
	@uv sync --directory packages/observability
	@uv sync --directory packages/media
	@uv sync --directory packages/agents
	@uv sync --directory apps/api
	@echo "✓ Setup complete! Edit .env and apps/web/.env.local if custom settings are needed."

# -----------------------------------------------------------------------------
# 3. LOCAL DEVELOPMENT SERVERS
# -----------------------------------------------------------------------------
dev:
	@echo "==> Starting Croviq full-stack development environment..."
	@echo "    Backend API:  http://localhost:8080 (Health: http://localhost:8080/api/health)"
	@echo "    Frontend Web: http://localhost:5173"
	@echo "    Press Ctrl+C to terminate both servers."
	@trap 'kill 0' SIGINT SIGTERM EXIT; \
		(uv run --directory apps/api uvicorn croviq_api.main:app --host 0.0.0.0 --port 8080 --reload) & \
		(pnpm --filter @croviq/web dev) & \
		wait

dev-api:
	@echo "==> Starting Croviq Backend API on port 8080..."
	@uv run --directory apps/api uvicorn croviq_api.main:app --host 0.0.0.0 --port 8080 --reload

dev-web:
	@echo "==> Starting Croviq Frontend Web on port 5173..."
	@pnpm --filter @croviq/web dev

# -----------------------------------------------------------------------------
# 4. TESTING & VALIDATION
# -----------------------------------------------------------------------------
test:
	@echo "==> Running Python domain package tests..."
	@uv run --directory packages/domain pytest
	@echo "==> Running Python observability package tests..."
	@uv run --directory packages/observability pytest
	@echo "==> Running Python media package tests..."
	@uv run --directory packages/media pytest
	@echo "==> Running Python agents package tests..."
	@uv run --directory packages/agents pytest
	@echo "==> Running Python API tests..."
	@uv run --directory apps/api pytest
	@echo "✓ All backend and package test suites passed."

e2e:
	@echo "==> Running Playwright E2E browser tests..."
	@pnpm --filter @croviq/web e2e

typecheck:
	@echo "==> Running TypeScript workspace typecheck..."
	@pnpm -r run typecheck
	@echo "✓ TypeScript typecheck passed."

lint:
	@echo "==> Running workspace linters..."
	@pnpm -r --if-present run lint
	@echo "✓ Lint checks passed."

format:
	@echo "==> Applying repository formatters..."
	@pnpm format

format-check:
	@echo "==> Checking repository formatting..."
	@pnpm format:check

openapi:
	@echo "==> Exporting OpenAPI specification & generating TypeScript contracts..."
	@uv run --directory apps/api python ../../scripts/export_openapi.py
	@pnpm prettier --write openapi.json apps/web/src/api/generated.ts > /dev/null
infra-validate:
	@echo "==> Checking Terraform formatting..."
	@terraform fmt -check -recursive infra/
	@echo "==> Validating infra/..."
	@(cd infra && terraform init -backend=false -upgrade=false > /dev/null && terraform validate)
	@echo "==> Validating infra/bootstrap/..."
	@(cd infra/bootstrap && terraform init -backend=false -upgrade=false > /dev/null && terraform validate)
	@echo "==> Validating infra/cloudflare-dns/..."
	@(cd infra/cloudflare-dns && terraform init -backend=false -upgrade=false > /dev/null && terraform validate)
	@echo "✓ Infrastructure configurations validated."

security:
	@python3 scripts/security_audit.py
	@if command -v gitleaks > /dev/null 2>&1; then \
		echo "==> Running Gitleaks independent secret scan..."; \
		gitleaks dir --verbose . && echo "✓ Gitleaks scan passed with 0 findings."; \
	fi
# -----------------------------------------------------------------------------
# 5. CANONICAL VERIFICATION (Local & CI)
# -----------------------------------------------------------------------------
verify: doctor format-check lint typecheck test openapi infra-validate security
	@echo "==> Checking for OpenAPI contract drift..."
	@git diff --exit-code openapi.json apps/web/src/api/generated.ts || (echo "✗ OpenAPI contract drift detected! Run 'make openapi' and commit changes." && exit 1)
	@echo "================================================================="
	@echo "✓ VERIFICATION PASSED: All tests, checks, and audits succeeded!"
	@echo "================================================================="
