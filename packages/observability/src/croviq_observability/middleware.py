"""FastAPI / Starlette middleware and error handling for structured observability."""

import time
from typing import Any, Callable
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from croviq_observability.context import (
    clear_request_context,
    extract_request_id,
    extract_trace_id,
    set_request_context,
)
from croviq_observability.events import EventType
from croviq_observability.logger import get_logger, log_error


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for request correlation, latency measurement, and structured HTTP logs."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        start_time = time.perf_counter()

        # 1. Extract or generate request_id and trace_id
        headers_dict = dict(request.headers)
        request_id = extract_request_id(headers_dict)
        trace_id = extract_trace_id(headers_dict)
        route = request.url.path

        # 2. Bind into contextvars and request.state
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        request.state.route = route

        set_request_context(
            request_id=request_id,
            trace_id=trace_id,
            route=route,
        )

        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code

            response.headers["x-request-id"] = request_id
            response.headers["x-trace-id"] = trace_id
            return response
        except Exception as exc:
            status_code = 500
            log_error(
                event_type=EventType.HTTP_RESPONSE.value,
                exception=exc,
                status=500,
                route=route,
                request_id=request_id,
                trace_id=trace_id,
                message=f"Unhandled exception on {request.method} {route}: {type(exc).__name__}",
            )
            raise
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000
            user_id = getattr(request.state, "user_id", None)

            get_logger().log(
                event_type=EventType.HTTP_RESPONSE.value,
                status=status_code,
                request_id=request_id,
                trace_id=trace_id,
                user_id=user_id,
                route=route,
                path=route,
                latency_ms=latency_ms,
                method=request.method,
                message=f"{request.method} {route} {status_code} - {latency_ms:.2f}ms",
            )
            clear_request_context()

def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers that prevent stack trace leaks to clients."""

    @app.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", extract_request_id(dict(request.headers)))
        trace_id = getattr(request.state, "trace_id", extract_trace_id(dict(request.headers)))

        log_error(
            event_type=EventType.HTTP_RESPONSE.value,
            exception=exc,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            route=request.url.path,
            request_id=request_id,
            trace_id=trace_id,
            message=f"Internal server error: {type(exc).__name__}",
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "internal_error",
                "message": "An internal server error occurred. Please try again later.",
            },
            headers={
                "x-request-id": request_id,
                "x-trace-id": trace_id,
            },
        )
