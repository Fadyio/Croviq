from fastapi import FastAPI

from croviq_api.config import get_settings
from croviq_api.logging import StructuredLoggingMiddleware
from croviq_api.schemas import HealthResponse


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Croviq API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(StructuredLoggingMiddleware)

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Service Health Check",
        tags=["Health"],
    )
    async def health_check() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.service_name,
            git_sha=settings.git_sha,
        )

    return app


app = create_app()
