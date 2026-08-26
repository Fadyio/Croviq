"""Structured logging for media upload events."""

from typing import Any
from croviq_observability import log_upload_event as obs_log_upload_event


def log_media_upload_event(
    event_type: str,
    status: int | str,
    request_id: str,
    user_id: str,
    workspace_id: str,
    channel_id: str,
    production_id: str,
    upload_id: str,
    filename: str | None = None,
    size_bytes: int | None = None,
    content_type: str | None = None,
    latency_ms: float | None = None,
    message: str | None = None,
    error_code: str | None = None,
    exception: BaseException | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Log structured media upload event for Google Cloud Logging ingestion.

    Guarantees:
    - Never logs signed URLs, authorization tokens, or GCP credentials.
    """
    return obs_log_upload_event(
        event_type=event_type,
        status=status,
        request_id=request_id,
        user_id=user_id,
        workspace_id=workspace_id,
        channel_id=channel_id,
        production_id=production_id,
        upload_id=upload_id,
        filename=filename,
        size_bytes=size_bytes,
        content_type=content_type,
        latency_ms=latency_ms,
        message=message,
        error_code=error_code,
        exception=exception,
        **extra,
    )
