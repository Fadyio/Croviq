"""Canonical structured JSON logger for Google Cloud Logging."""

from datetime import datetime, timezone
import json
import os
import sys
from typing import Any, TextIO

from croviq_observability.context import (
    get_environment,
    get_git_sha,
    get_request_id,
    get_route,
    get_service,
    get_trace_id,
    get_user_id,
)
from croviq_observability.events import EventType
from croviq_observability.redaction import sanitize_payload
from croviq_observability.schemas import LogSeverity, StandardLogEvent


def determine_severity(status_code: int | None = None, default: LogSeverity = "INFO") -> LogSeverity:
    """Map HTTP status code to canonical Cloud Logging severity."""
    if status_code is None:
        return default
    if status_code >= 500:
        return "ERROR"
    if status_code >= 400:
        return "WARNING"
    return "INFO"


class StructuredLogger:
    """Canonical structured JSON logger writing to stdout for Cloud Logging jsonPayload parsing."""

    def __init__(
        self,
        service: str | None = None,
        environment: str | None = None,
        git_sha: str | None = None,
        gcp_project_id: str | None = None,
        output_stream: TextIO | None = None,
    ) -> None:
        self._service = service or os.getenv("SERVICE_NAME", "croviq-api")
        self._environment = (
            environment or os.getenv("CROVIQ_ENV") or os.getenv("ENVIRONMENT", "development")
        )
        self._git_sha = git_sha or os.getenv("GIT_SHA") or os.getenv("COMMIT_SHA") or "local"
        self._gcp_project_id = (
            gcp_project_id
            or os.getenv("GCP_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
            or os.getenv("PROJECT_ID")
        )
        self._stream = output_stream

    def log(
        self,
        event_type: str,
        *,
        severity: LogSeverity | None = None,
        status: int | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        user_id: str | None = None,
        route: str | None = None,
        latency_ms: float | None = None,
        error_code: str | None = None,
        include_error_code: bool = False,
        message: str | None = None,
        exception: BaseException | None = None,
        agent: str | None = None,
        model: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Emit a canonical structured log event."""
        # 1. Resolve context defaults
        req_id = request_id or get_request_id()
        tr_id = trace_id or get_trace_id()
        uid = user_id or get_user_id()
        rt = route or get_route()
        svc = self._service or get_service() or "croviq-api"
        env = self._environment or get_environment() or "development"
        sha = self._git_sha or get_git_sha() or "local"

        # 2. Determine severity
        if severity is None:
            severity = determine_severity(status, default="INFO")
            if exception is not None:
                severity = "ERROR"

        # 3. Handle exceptions
        exc_type: str | None = None
        exc_msg: str | None = None
        if exception is not None:
            exc_type = type(exception).__name__
            exc_msg = str(exception)
            if not message:
                message = f"{exc_type}: {exc_msg}"

        # 4. Construct Cloud Trace link if project id available
        gcp_trace: str | None = None
        if self._gcp_project_id and tr_id:
            gcp_trace = f"projects/{self._gcp_project_id}/traces/{tr_id}"

        # 5. Build base event payload
        event = StandardLogEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            severity=severity,
            service=svc,
            environment=env,
            event_type=event_type,
            request_id=req_id,
            trace_id=tr_id,
            user_id=uid,
            route=rt,
            status=status,
            latency_ms=round(latency_ms, 2) if latency_ms is not None else None,
            git_sha=sha,
            error_code=error_code,
            message=message,
            exception_type=exc_type,
            exception_message=exc_msg,
            agent=agent,
            model=model,
            run_id=run_id,
            job_id=job_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            gcp_trace=gcp_trace,
        )

        # 6. Convert to dict, incorporate extra fields, and sanitize all secrets
        raw_dict = event.model_dump(by_alias=True, exclude_none=True)
        if include_error_code and error_code is None:
            raw_dict["error_code"] = None
        elif error_code is not None:
            raw_dict["error_code"] = error_code

        if extra:
            for k, v in extra.items():
                raw_dict[k] = v

        sanitized = sanitize_payload(raw_dict)

        # 7. Write single-line JSON to dynamic stdout stream
        stream = self._stream if self._stream is not None else sys.stdout
        json_line = json.dumps(sanitized, ensure_ascii=False)
        stream.write(json_line + "\n")
        stream.flush()
        return sanitized


# Global default logger instance
_default_logger = StructuredLogger()


def get_logger() -> StructuredLogger:
    return _default_logger


def set_logger(logger: StructuredLogger) -> None:
    global _default_logger
    _default_logger = logger


def log_event(event_type: str, **kwargs: Any) -> dict[str, Any]:
    return _default_logger.log(event_type, **kwargs)


def log_auth_event(
    event_type: str,
    status: int,
    request_id: str | None = None,
    user_id: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    include_error_code: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    return _default_logger.log(
        event_type=event_type,
        status=status,
        request_id=request_id,
        user_id=user_id,
        error_code=error_code,
        include_error_code=include_error_code,
        message=message,
        **kwargs,
    )


def log_workspace_event(
    event_type: str,
    status: int,
    workspace_id: str | None = None,
    request_id: str | None = None,
    user_id: str | None = None,
    message: str | None = None,
    error_code: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    extra = {}
    if workspace_id:
        extra["workspace_id"] = workspace_id
    return _default_logger.log(
        event_type=event_type,
        status=status,
        request_id=request_id,
        user_id=user_id,
        message=message,
        error_code=error_code,
        **extra,
        **kwargs,
    )


def log_firestore_event(
    event_type: str,
    collection: str,
    operation: str,
    status: int = 200,
    document_id: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    exception: BaseException | None = None,
    latency_ms: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    extra = {
        "collection": collection,
        "operation": operation,
    }
    if document_id:
        extra["document_id"] = document_id
    return _default_logger.log(
        event_type=event_type,
        status=status,
        latency_ms=latency_ms,
        error_code=error_code,
        message=message,
        exception=exception,
        **extra,
        **kwargs,
    )


def log_error(
    event_type: str,
    exception: BaseException,
    status: int = 500,
    route: str | None = None,
    request_id: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return _default_logger.log(
        event_type=event_type,
        severity="ERROR",
        status=status,
        route=route,
        request_id=request_id,
        error_code=error_code,
        message=message or f"Unhandled error: {type(exception).__name__}",
        exception=exception,
        **kwargs,
    )


def log_ai_event(
    event_type: str,
    agent: str,
    model: str,
    status: str = "success",
    run_id: str | None = None,
    job_id: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: float | None = None,
    error_code: str | None = None,
    message: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    severity: LogSeverity = "ERROR" if status == "failed" else "INFO"
    return _default_logger.log(
        event_type=event_type,
        severity=severity,
        agent=agent,
        model=model,
        run_id=run_id,
        job_id=job_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        error_code=error_code,
        message=message,
        **kwargs,
    )
