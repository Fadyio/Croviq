"""Structured logging for Workspace lifecycle events."""

from typing import Any
from croviq_observability import log_workspace_event as obs_log_workspace_event


def log_workspace_event(
    event_type: str,
    status: int,
    request_id: str,
    user_id: str,
    workspace_id: str | None = None,
    message: str | None = None,
    error_code: str | None = None,
    exception: BaseException | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Log structured workspace event for Google Cloud Logging ingestion.

    Guarantees:
    - Never logs ID tokens, Authorization headers, or credentials.
    - Always includes request_id, user_id, workspace_id, event_type, status, service, and environment.
    """
    return obs_log_workspace_event(
        event_type=event_type,
        status=status,
        request_id=request_id,
        user_id=user_id,
        workspace_id=workspace_id,
        message=message,
        error_code=error_code,
        exception=exception,
        **extra,
    )
