"""Structured logging for authentication events."""

from typing import Any
from croviq_observability import log_auth_event as obs_log_auth_event


def log_auth_event(
    event_type: str,
    status: int,
    request_id: str,
    user_id: str | None = None,
    authenticated_user_id: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    include_error_code: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Log structured authentication event for Google Cloud Logging ingestion.

    Guarantees:
    - Never logs ID tokens, Authorization headers, or credentials.
    - Always includes request_id, event_type, status, service, and environment.
    - Includes user_id / authenticated_user_id when available.
    """
    uid = user_id or authenticated_user_id
    extra_fields = dict(extra)
    if uid is not None:
        extra_fields["authenticated_user_id"] = uid

    return obs_log_auth_event(
        event_type=event_type,
        status=status,
        request_id=request_id,
        user_id=uid,
        error_code=error_code,
        message=message,
        include_error_code=include_error_code,
        **extra_fields,
    )
