"""Request and trace context management using Python contextvars."""

from contextvars import ContextVar
import re
import uuid

_current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)
_current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)
_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)
_current_route: ContextVar[str | None] = ContextVar("current_route", default=None)
_current_service: ContextVar[str | None] = ContextVar("current_service", default=None)
_current_environment: ContextVar[str | None] = ContextVar("current_environment", default=None)
_current_git_sha: ContextVar[str | None] = ContextVar("current_git_sha", default=None)


def extract_trace_id(headers: dict[str, str] | None = None) -> str:
    """Extract trace_id from Cloud Trace or W3C traceparent headers, or generate a 32-hex ID."""
    if headers:
        # 1. Google Cloud Trace header: 'TRACE_ID/SPAN_ID;o=TRACE_TRUE'
        cloud_trace = headers.get("x-cloud-trace-context") or headers.get("X-Cloud-Trace-Context")
        if cloud_trace:
            match = re.match(r"^([a-fA-F0-9]{32})(?:/\d+)?(?:;o=\d+)?", cloud_trace.strip())
            if match:
                return match.group(1).lower()
            # Also support 16-32 char hex before slash
            parts = cloud_trace.split("/")
            if parts and len(parts[0].strip()) >= 16:
                return parts[0].strip().lower()

        # 2. W3C traceparent header: 'version-trace_id-parent_id-trace_flags'
        traceparent = headers.get("traceparent") or headers.get("Traceparent")
        if traceparent:
            parts = traceparent.strip().split("-")
            if len(parts) >= 4 and len(parts[1]) == 32:
                return parts[1].lower()

        # 3. Explicit x-trace-id header
        explicit_trace = headers.get("x-trace-id") or headers.get("X-Trace-Id")
        if explicit_trace and explicit_trace.strip():
            return explicit_trace.strip().lower()

    # Fallback: generate canonical 32-character hex trace ID
    return uuid.uuid4().hex


def extract_request_id(headers: dict[str, str] | None = None) -> str:
    """Extract x-request-id header or generate a new UUID4 string."""
    if headers:
        req_id = headers.get("x-request-id") or headers.get("X-Request-Id")
        if req_id and req_id.strip():
            return req_id.strip()
    return str(uuid.uuid4())


def set_request_context(
    request_id: str | None = None,
    trace_id: str | None = None,
    user_id: str | None = None,
    route: str | None = None,
    service: str | None = None,
    environment: str | None = None,
    git_sha: str | None = None,
) -> None:
    """Set the contextual values for the active coroutine/thread."""
    if request_id is not None:
        _current_request_id.set(request_id)
    if trace_id is not None:
        _current_trace_id.set(trace_id)
    if user_id is not None:
        _current_user_id.set(user_id)
    if route is not None:
        _current_route.set(route)
    if service is not None:
        _current_service.set(service)
    if environment is not None:
        _current_environment.set(environment)
    if git_sha is not None:
        _current_git_sha.set(git_sha)


def get_request_id() -> str:
    """Retrieve the current request_id or generate a fallback."""
    val = _current_request_id.get()
    return val if val else str(uuid.uuid4())


def get_trace_id() -> str:
    """Retrieve the current trace_id or generate a fallback."""
    val = _current_trace_id.get()
    return val if val else uuid.uuid4().hex


def get_user_id() -> str | None:
    """Retrieve the current user_id if authenticated."""
    return _current_user_id.get()


def get_route() -> str | None:
    """Retrieve the current route path."""
    return _current_route.get()


def get_service() -> str | None:
    return _current_service.get()


def get_environment() -> str | None:
    return _current_environment.get()


def get_git_sha() -> str | None:
    return _current_git_sha.get()


def clear_request_context() -> None:
    """Reset all request context variables."""
    _current_request_id.set(None)
    _current_trace_id.set(None)
    _current_user_id.set(None)
    _current_route.set(None)
