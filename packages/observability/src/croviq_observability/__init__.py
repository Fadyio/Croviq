"""Croviq canonical structured observability package."""

from croviq_observability.context import (
    clear_request_context,
    extract_request_id,
    extract_trace_id,
    get_environment,
    get_git_sha,
    get_request_id,
    get_route,
    get_service,
    get_trace_id,
    get_user_id,
    set_request_context,
)
from croviq_observability.events import (
    CLIENT_ALLOWED_EVENT_TYPES,
    NORMALIZED_EVENT_TYPES,
    EventType,
)
from croviq_observability.logger import (
    StructuredLogger,
    determine_severity,
    get_logger,
    log_ai_event,
    log_auth_event,
    log_error,
    log_event,
    log_firestore_event,
    log_workspace_event,
    log_memory_event,
    set_logger,
    log_upload_event,
    log_transcription_event,
    log_media_inspect_event,
    log_edl_event,
    log_cut_safety_event,
)
try:
    from croviq_observability.middleware import (
        StructuredLoggingMiddleware,
        register_error_handlers,
    )
except ImportError:
    StructuredLoggingMiddleware = None  # type: ignore[assignment, misc]
    register_error_handlers = None  # type: ignore[assignment]
from croviq_observability.redaction import redact_string, sanitize_payload
from croviq_observability.schemas import ClientEventPayload, LogSeverity, StandardLogEvent

__all__ = [
    "CLIENT_ALLOWED_EVENT_TYPES",
    "NORMALIZED_EVENT_TYPES",
    "ClientEventPayload",
    "EventType",
    "LogSeverity",
    "StandardLogEvent",
    "StructuredLogger",
    "clear_request_context",
    "determine_severity",
    "extract_request_id",
    "extract_trace_id",
    "get_environment",
    "get_git_sha",
    "get_logger",
    "get_request_id",
    "get_route",
    "get_service",
    "get_trace_id",
    "get_user_id",
    "log_ai_event",
    "log_auth_event",
    "log_error",
    "log_event",
    "log_firestore_event",
    "log_memory_event",
    "log_workspace_event",
    "log_upload_event",
    "log_transcription_event",
    "log_media_inspect_event",
    "log_edl_event",
    "log_cut_safety_event",
    "register_error_handlers",
    "sanitize_payload",
    "set_logger",
    "set_request_context",
    "StructuredLoggingMiddleware",
]
