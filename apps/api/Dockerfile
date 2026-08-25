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
COPY pyproject.toml uv.lock ./

# Install production dependencies only using frozen lockfile
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY src/ ./src/

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
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment and application code from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Create non-root user
RUN useradd -u 1000 -U -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# Production Uvicorn entrypoint: non-development (no --reload), listens on $PORT
CMD ["sh", "-c", "exec uvicorn croviq_api.main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log --workers 1"]
