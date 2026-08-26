from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from croviq_api.auth import DemoAccessRestrictedError, auth_router
from croviq_api.auth.logging import log_auth_event
from croviq_api.config import get_settings
from croviq_api.logging import StructuredLoggingMiddleware
from croviq_observability import register_error_handlers
from croviq_api.schemas import ClientAuthEvent, HealthResponse
from croviq_api.memory import memory_router
from croviq_api.workspaces import workspace_router
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

    @app.exception_handler(DemoAccessRestrictedError)
    async def demo_access_restricted_handler(
        request: Request, exc: DemoAccessRestrictedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
            },
        )
    register_error_handlers(app)


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

    @api_router.post(
        "/client-events",
        status_code=status.HTTP_200_OK,
        summary="Record Sanitized Client Authentication Event",
        tags=["Auth"],
    )
    async def record_client_auth_event(event: ClientAuthEvent, request: Request) -> dict[str, str]:
        """Record a constrained client auth event without accepting sensitive payloads."""
        log_auth_event(
            event_type=event.event_type,
            status=status.HTTP_200_OK,
            request_id=getattr(request.state, "request_id", "unknown"),
            error_code=getattr(event, "error_code", None),
            include_error_code=True,
        )
        return {"status": "ok"}

    api_router.include_router(auth_router)
    api_router.include_router(workspace_router)
    api_router.include_router(memory_router)

    app.include_router(api_router)
    return app


app = create_app()
