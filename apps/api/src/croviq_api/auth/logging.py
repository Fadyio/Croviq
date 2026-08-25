"""Structured logging for authentication events."""

from datetime import datetime, timezone
from typing import Any

from croviq_api.config import get_settings
from croviq_api.logging import determine_severity, log_json_entry


def log_auth_event(
    event_type: str,
    status: int,
    request_id: str,
    user_id: str | None = None,
    authenticated_user_id: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    include_error_code: bool = False,
) -> None:
    """Log structured authentication event for Google Cloud Logging ingestion.

    Guarantees:
    - Never logs ID tokens, Authorization headers, or credentials.
    - Always includes request_id, event_type, status, service, and environment.
    - Includes user_id / authenticated_user_id when available.
    """
    settings = get_settings()
    timestamp = datetime.now(timezone.utc).isoformat()
    severity = determine_severity(status)

    uid = user_id or authenticated_user_id

    payload: dict[str, Any] = {
        "timestamp": timestamp,
        "severity": severity,
        "service": settings.service_name,
        "environment": settings.environment,
        "event_type": event_type,
        "status": status,
        "request_id": request_id,
        "git_sha": settings.git_sha,
    }

    if uid is not None:
        payload["user_id"] = uid
        payload["authenticated_user_id"] = uid

    if error_code is not None or include_error_code:
        payload["error_code"] = error_code

    if message is not None:
        payload["message"] = message

    log_json_entry(payload)
