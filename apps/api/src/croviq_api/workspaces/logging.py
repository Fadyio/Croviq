"""Structured logging for Workspace lifecycle events."""

from datetime import datetime, timezone
from typing import Any

from croviq_api.config import get_settings
from croviq_api.logging import determine_severity, log_json_entry


def log_workspace_event(
    event_type: str,
    status: int,
    request_id: str,
    user_id: str,
    workspace_id: str,
    message: str | None = None,
) -> None:
    """Log structured workspace event for Google Cloud Logging ingestion.

    Guarantees:
    - Never logs ID tokens, Authorization headers, or credentials.
    - Always includes request_id, user_id, workspace_id, event_type, status, service, and environment.
    """
    settings = get_settings()
    timestamp = datetime.now(timezone.utc).isoformat()
    severity = determine_severity(status)

    payload: dict[str, Any] = {
        "timestamp": timestamp,
        "severity": severity,
        "service": settings.service_name,
        "environment": settings.environment,
        "event_type": event_type,
        "status": status,
        "request_id": request_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "git_sha": settings.git_sha,
    }

    if message is not None:
        payload["message"] = message

    log_json_entry(payload)
