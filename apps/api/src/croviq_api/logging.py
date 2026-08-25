"""Structured logging adapter integrating croviq-observability with API configuration."""

from typing import Any
from croviq_api.config import get_settings
from croviq_observability import (
    StructuredLogger,
    StructuredLoggingMiddleware,
    determine_severity,
    get_logger,
    log_ai_event,
    log_auth_event,
    log_error,
    log_event,
    log_firestore_event,
    log_workspace_event,
    set_logger,
)


def configure_api_logging() -> StructuredLogger:
    """Initialize canonical StructuredLogger with croviq-api settings."""
    settings = get_settings()
    logger = StructuredLogger(
        service=settings.service_name,
        environment=settings.environment,
        git_sha=settings.git_sha,
        gcp_project_id=settings.gcp_project_id,
    )
    set_logger(logger)
    return logger


# Configure on import
_api_logger = configure_api_logging()


def log_json_entry(payload: dict[str, Any]) -> None:
    """Compatibility shim for existing tests/modules directly logging dicts."""
    event_type = payload.get("event_type", "http.response")
    get_logger().log(event_type=event_type, **payload)


__all__ = [
    "StructuredLogger",
    "StructuredLoggingMiddleware",
    "configure_api_logging",
    "determine_severity",
    "get_logger",
    "log_ai_event",
    "log_auth_event",
    "log_error",
    "log_event",
    "log_firestore_event",
    "log_json_entry",
    "log_workspace_event",
]
