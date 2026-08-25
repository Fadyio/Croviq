import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from croviq_api.config import get_settings


def determine_severity(status_code: int) -> str:
    if status_code >= 500:
        return "ERROR"
    if status_code >= 400:
        return "WARNING"
    return "INFO"


def log_json_entry(payload: dict[str, Any]) -> None:
    """Write structured JSON log entry to stdout for Cloud Logging ingestion."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        start_time = time.perf_counter()
        settings = get_settings()

        # Extract or generate x-request-id
        request_id = request.headers.get("x-request-id")
        if not request_id or not request_id.strip():
            request_id = str(uuid.uuid4())
        else:
            request_id = request_id.strip()

        request.state.request_id = request_id

        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            timestamp = datetime.now(timezone.utc).isoformat()
            severity = determine_severity(status_code)

            log_entry = {
                "timestamp": timestamp,
                "severity": severity,
                "service": settings.service_name,
                "environment": settings.environment,
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": latency_ms,
                "git_sha": settings.git_sha,
                "message": f"{request.method} {request.url.path} {status_code} - {latency_ms:.2f}ms",
            }
            log_json_entry(log_entry)
