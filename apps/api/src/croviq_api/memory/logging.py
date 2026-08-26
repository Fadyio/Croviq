"""Structured logging for Channel Memory operations."""

from typing import Any
from croviq_observability import log_memory_event as obs_log_memory_event


def log_memory_event(
    event_type: str,
    channel_id: str,
    status: int | str = 200,
    request_id: str = "unknown",
    latency_ms: float | None = None,
    memory_schema_id: str = "channel-profile",
    memory_bank_resource: str | None = None,
    message: str | None = None,
    error_code: str | None = None,
    exception: BaseException | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Log structured memory bank operation event for Google Cloud Logging ingestion.

    Guarantees:
    - Never logs credentials, tokens, or raw sensitive memory content.
    - Captures channel_id, request_id, status, latency_ms, schema_id, and resource name.
    """
    return obs_log_memory_event(
        event_type=event_type,
        channel_id=channel_id,
        status=status,
        request_id=request_id,
        latency_ms=latency_ms,
        memory_schema_id=memory_schema_id,
        memory_bank_resource=memory_bank_resource,
        message=message,
        error_code=error_code,
        exception=exception,
        **extra,
    )
