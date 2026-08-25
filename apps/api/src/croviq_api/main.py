from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from croviq_api.auth import auth_router
from croviq_api.config import get_settings
from croviq_api.logging import StructuredLoggingMiddleware
from croviq_api.schemas import HealthResponse

# In production (ADR-0013), all traffic is routed under single-origin app.croviq.app
# via Google Cloud Load Balancer, eliminating cross-origin browser CORS dependencies.
# Local development origins are retained for local developer tooling and API test harnesses.
LOCAL_DEVELOPMENT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Croviq API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_DEVELOPMENT_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
    )

    api_router = APIRouter(prefix="/api")

    @api_router.get(
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

    api_router.include_router(auth_router)

    app.include_router(api_router)
    return app


app = create_app()
