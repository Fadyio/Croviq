# Production Dockerfile for Croviq API
# Stage 1: Build virtual environment using uv
FROM python:3.12-slim AS builder

# Install uv from official binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy dependency specifications first for layer caching
COPY packages/domain/ /app/packages/domain/
COPY packages/observability/ /app/packages/observability/
COPY apps/api/pyproject.toml apps/api/uv.lock /app/apps/api/

WORKDIR /app/apps/api

# Install production dependencies only using frozen lockfile
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY apps/api/src/ /app/apps/api/src/

# Install the application package into the virtual environment
RUN uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# Stage 2: Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runner

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV CROVIQ_ENV=production
ENV ENVIRONMENT=production
ENV PATH="/app/apps/api/.venv/bin:$PATH"

WORKDIR /app/apps/api

# Copy virtual environment and application code from builder
COPY --from=builder /app/apps/api/.venv /app/apps/api/.venv
COPY --from=builder /app/apps/api/src /app/apps/api/src
COPY --from=builder /app/packages/domain /app/packages/domain
COPY --from=builder /app/packages/observability /app/packages/observability
# Create non-root user
RUN useradd -u 1000 -U -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# Production Uvicorn entrypoint: non-development (no --reload), listens on $PORT
CMD ["sh", "-c", "exec uvicorn croviq_api.main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log --workers 1"]
