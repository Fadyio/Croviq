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


def determine_severity(status_code: Any = None, default: LogSeverity = "INFO") -> LogSeverity:
    """Map status code (int or string) to canonical Cloud Logging severity."""
    if status_code is None:
        return default
    if isinstance(status_code, str):
        status_lower = status_code.lower()
        if status_lower in ("failed", "error"):
            return "ERROR"
        if status_lower in ("warning", "warn"):
            return "WARNING"
        if status_lower in ("success", "ok", "completed"):
            return "INFO"
        try:
            status_code = int(status_code)
        except ValueError:
            return default
    if isinstance(status_code, (int, float)):
        if status_code >= 500:
            return "ERROR"
        if status_code >= 400:
            return "WARNING"
        return "INFO"
    return default


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
        status: int | str | None = None,
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


def log_agent_tool_event(
    event_type: str | EventType,
    tool_name: str,
    production_id: str,
    run_id: str | None = None,
    latency_ms: float | None = None,
    status: str | int = "completed",
    error_code: str | None = None,
    message: str | None = None,
    request_id: str | None = None,
    git_sha: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Emit a canonical structured log event for internal agent tool execution."""
    ev_str = event_type.value if isinstance(event_type, EventType) else str(event_type)
    severity: LogSeverity = "ERROR" if str(status).lower() in ("failed", "error") else "INFO"
    return _default_logger.log(
        event_type=ev_str,
        severity=severity,
        tool_name=tool_name,
        production_id=production_id,
        run_id=run_id,
        latency_ms=latency_ms,
        status=status,
        error_code=error_code,
        message=message or f"Agent tool {tool_name} {status}",
        request_id=request_id,
        git_sha=git_sha,
        **kwargs,
    )


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
    **kwargs: Any,
) -> dict[str, Any]:
    severity: LogSeverity = "ERROR" if (str(status).startswith("5") or status == "failed" or exception is not None) else "INFO"
    return _default_logger.log(
        event_type=event_type,
        severity=severity,
        channel_id=channel_id,
        status=status,
        request_id=request_id,
        latency_ms=latency_ms,
        memory_schema_id=memory_schema_id,
        memory_bank_resource=memory_bank_resource,
        message=message,
        error_code=error_code,
        exception=exception,
        **kwargs,
    )

def log_upload_event(
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
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured media upload event for Google Cloud Logging ingestion.

    Guarantees:
    - Never logs signed URLs, authorization tokens, or GCP credentials.
    """
    severity: LogSeverity = "ERROR" if (str(status).startswith("4") or str(status).startswith("5") or status == "failed" or exception is not None) else "INFO"
    extra: dict[str, Any] = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "production_id": production_id,
        "upload_id": upload_id,
    }
    if filename is not None:
        extra["filename"] = filename
    if size_bytes is not None:
        extra["size_bytes"] = size_bytes
    if content_type is not None:
        extra["content_type"] = content_type
    if latency_ms is not None:
        extra["latency_ms"] = latency_ms

    return _default_logger.log(
        event_type=event_type,
        severity=severity,
        status=status,
        request_id=request_id,
        message=message,
        error_code=error_code,
        exception=exception,
        **extra,
        **kwargs,
    )


def log_transcription_event(
    event_type: str,
    status: int | str,
    request_id: str,
    production_id: str,
    transcript_id: str | None = None,
    duration_ms: int | None = None,
    word_count: int | None = None,
    segment_count: int | None = None,
    language_code: str | None = None,
    latency_ms: float | None = None,
    message: str | None = None,
    error_code: str | None = None,
    exception: BaseException | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured speech transcription event for Google Cloud Logging ingestion.

    Guarantees:
    - Never logs full transcript, signed URLs, authorization tokens, or GCP credentials.
    """
    severity: LogSeverity = "ERROR" if (str(status).startswith("4") or str(status).startswith("5") or status == "failed" or exception is not None) else "INFO"
    status_code: int | None = None
    if isinstance(status, int):
        status_code = status
    elif isinstance(status, str) and status.isdigit():
        status_code = int(status)

    extra: dict[str, Any] = {
        "production_id": production_id,
    }
    if not isinstance(status, int):
        extra["execution_status"] = str(status)
    if transcript_id is not None:
        extra["transcript_id"] = transcript_id
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    if word_count is not None:
        extra["word_count"] = word_count
    if segment_count is not None:
        extra["segment_count"] = segment_count
    if language_code is not None:
        extra["language_code"] = language_code
    if latency_ms is not None:
        extra["latency_ms"] = latency_ms

    return _default_logger.log(
        event_type=event_type,
        severity=severity,
        status=status_code,
        request_id=request_id,
        message=message,
        error_code=error_code,
        exception=exception,
        **extra,
        **kwargs,
    )


def log_media_inspect_event(
    event_type: str,
    status: int | str,
    request_id: str,
    production_id: str,
    duration_ms: int | None = None,
    width: int | None = None,
    height: int | None = None,
    video_codec: str | None = None,
    audio_codec: str | None = None,
    latency_ms: float | None = None,
    message: str | None = None,
    error_code: str | None = None,
    exception: BaseException | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured media inspection event for Google Cloud Logging ingestion."""
    severity: LogSeverity = "ERROR" if (str(status).startswith("4") or str(status).startswith("5") or status == "failed" or exception is not None) else "INFO"
    status_code: int | None = None
    if isinstance(status, int):
        status_code = status
    elif isinstance(status, str) and status.isdigit():
        status_code = int(status)

    extra: dict[str, Any] = {
        "production_id": production_id,
    }
    if not isinstance(status, int):
        extra["execution_status"] = str(status)
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    if width is not None:
        extra["width"] = width
    if height is not None:
        extra["height"] = height
    if video_codec is not None:
        extra["video_codec"] = video_codec
    if audio_codec is not None:
        extra["audio_codec"] = audio_codec
    if latency_ms is not None:
        extra["latency_ms"] = latency_ms

    return _default_logger.log(
        event_type=event_type,
        severity=severity,
        status=status_code,
        request_id=request_id,
        message=message,
        error_code=error_code,
        exception=exception,
        **extra,
        **kwargs,
    )


def log_edl_event(
    event_type: str,
    production_id: str,
    edl_id: str | None = None,
    run_id: str | None = None,
    status: int | str = "success",
    request_id: str | None = None,
    cut_count: int | None = None,
    coverage_marker_count: int | None = None,
    removed_duration_ms: int | None = None,
    latency_ms: float | None = None,
    message: str | None = None,
    error_code: str | None = None,
    exception: BaseException | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured EDL assembly lifecycle event for Google Cloud Logging ingestion."""
    severity: LogSeverity = "ERROR" if (str(status).startswith("4") or str(status).startswith("5") or status == "failed" or exception is not None) else "INFO"
    status_code: int | None = None
    if isinstance(status, int):
        status_code = status
    elif isinstance(status, str) and status.isdigit():
        status_code = int(status)

    extra: dict[str, Any] = {
        "production_id": production_id,
    }
    if edl_id:
        extra["edl_id"] = edl_id
    if run_id:
        extra["run_id"] = run_id
    if not isinstance(status, int):
        extra["execution_status"] = str(status)
    if cut_count is not None:
        extra["cut_count"] = cut_count
    if coverage_marker_count is not None:
        extra["coverage_marker_count"] = coverage_marker_count
    if removed_duration_ms is not None:
        extra["removed_duration_ms"] = removed_duration_ms
    if latency_ms is not None:
        extra["latency_ms"] = latency_ms

    return _default_logger.log(
        event_type=event_type,
        severity=severity,
        status=status_code,
        request_id=request_id,
        message=message,
        error_code=error_code,
        exception=exception,
        **extra,
        **kwargs,
    )


def log_cut_safety_event(
    production_id: str,
    decision_id: str,
    safety_status: str,
    safety_reason: str,
    requested_start_ms: int,
    requested_end_ms: int,
    safe_start_ms: int,
    safe_end_ms: int,
    removed_duration_ms: int,
    request_id: str | None = None,
    confidence: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured individual cut safety evaluation."""
    return _default_logger.log(
        event_type=EventType.CUT_SAFETY_EVALUATED,
        severity="INFO",
        request_id=request_id,
        production_id=production_id,
        decision_id=decision_id,
        safety_status=safety_status,
        safety_reason=safety_reason,
        requested_start_ms=requested_start_ms,
        requested_end_ms=requested_end_ms,
        safe_start_ms=safe_start_ms,
        safe_end_ms=safe_end_ms,
        removed_duration_ms=removed_duration_ms,
        confidence=confidence,
        **kwargs,
    )


def log_render_event(
    event_type: str | EventType,
    production_id: str,
    edl_id: str,
    artifact_id: str,
    artifact_type: str,
    status: str,
    source_duration_ms: int | None = None,
    target_duration_ms: int | None = None,
    rendered_duration_ms: int | None = None,
    render_time_ms: float | None = None,
    size_bytes: int | None = None,
    request_id: str | None = None,
    git_sha: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured media rendering event for Google Cloud Logging ingestion."""
    normalized_type = event_type.value if isinstance(event_type, EventType) else str(event_type)
    severity: LogSeverity = "ERROR" if (normalized_type == EventType.RENDER_FAILED.value or status == "failed") else "INFO"

    status_code: int | None = None
    if isinstance(status, int):
        status_code = status
    elif isinstance(status, str) and status.isdigit():
        status_code = int(status)
    else:
        status_code = 500 if (status == "failed" or normalized_type == EventType.RENDER_FAILED.value) else 200

    extra: dict[str, Any] = {
        "production_id": production_id,
        "edl_id": edl_id,
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "render_status": str(status),
    }
    if source_duration_ms is not None:
        extra["source_duration_ms"] = source_duration_ms
    if target_duration_ms is not None:
        extra["target_duration_ms"] = target_duration_ms
    if rendered_duration_ms is not None:
        extra["rendered_duration_ms"] = rendered_duration_ms
    if render_time_ms is not None:
        extra["render_time_ms"] = round(render_time_ms, 2)
    if size_bytes is not None:
        extra["size_bytes"] = size_bytes
    if git_sha is not None:
        extra["git_sha"] = git_sha

    return _default_logger.log(
        event_type=normalized_type,
        severity=severity,
        status=status_code,
        request_id=request_id,
        message=message or f"Render {artifact_type} {status}",
        error_code=error_code,
        **extra,
        **kwargs,
    )


def log_render_review_event(
    event_type: str | EventType,
    production_id: str,
    edl_id: str,
    preview_artifact_id: str,
    review_id: str | None = None,
    run_id: str | None = None,
    agent: str = "maya",
    model: str | None = None,
    verdict: str | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    request_id: str | None = None,
    git_sha: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured post-render review lifecycle event."""
    normalized_type = event_type.value if isinstance(event_type, EventType) else str(event_type)
    severity: LogSeverity = "ERROR" if (normalized_type == EventType.DIRECTOR_RENDER_REVIEW_FAILED.value or error_code) else "INFO"

    extra: dict[str, Any] = {
        "production_id": production_id,
        "edl_id": edl_id,
        "preview_artifact_id": preview_artifact_id,
        "agent": agent,
    }
    if review_id is not None:
        extra["review_id"] = review_id
    if run_id is not None:
        extra["run_id"] = run_id
    if model is not None:
        extra["model"] = model
    if verdict is not None:
        extra["verdict"] = verdict
    if latency_ms is not None:
        extra["latency_ms"] = latency_ms
    if input_tokens is not None:
        extra["input_tokens"] = input_tokens
    if output_tokens is not None:
        extra["output_tokens"] = output_tokens
    if git_sha is not None:
        extra["git_sha"] = git_sha

    return _default_logger.log(
        event_type=normalized_type,
        severity=severity,
        status=500 if severity == "ERROR" else 200,
        request_id=request_id,
        message=message or f"Director render review {verdict or 'event'}",
        error_code=error_code,
        **extra,
        **kwargs,
    )


def log_editor_correction_event(
    event_type: str | EventType,
    production_id: str,
    edl_id: str,
    run_id: str | None = None,
    agent: str = "leo",
    model: str | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    request_id: str | None = None,
    git_sha: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured editor correction lifecycle event."""
    normalized_type = event_type.value if isinstance(event_type, EventType) else str(event_type)
    severity: LogSeverity = "ERROR" if (normalized_type == EventType.EDITOR_CORRECTION_FAILED.value or error_code) else "INFO"

    extra: dict[str, Any] = {
        "production_id": production_id,
        "edl_id": edl_id,
        "agent": agent,
    }
    if run_id is not None:
        extra["run_id"] = run_id
    if model is not None:
        extra["model"] = model
    if latency_ms is not None:
        extra["latency_ms"] = latency_ms
    if input_tokens is not None:
        extra["input_tokens"] = input_tokens
    if output_tokens is not None:
        extra["output_tokens"] = output_tokens
    if git_sha is not None:
        extra["git_sha"] = git_sha

    return _default_logger.log(
        event_type=normalized_type,
        severity=severity,
        status=500 if severity == "ERROR" else 200,
        request_id=request_id,
        message=message or f"Editor correction {normalized_type}",
        error_code=error_code,
        **extra,
        **kwargs,
    )


def log_master_approved_event(
    production_id: str,
    edl_id: str,
    preview_artifact_id: str,
    review_id: str,
    run_id: str | None = None,
    request_id: str | None = None,
    git_sha: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured Master render approval event."""
    extra: dict[str, Any] = {
        "production_id": production_id,
        "edl_id": edl_id,
        "preview_artifact_id": preview_artifact_id,
        "review_id": review_id,
    }
    if run_id is not None:
        extra["run_id"] = run_id
    if git_sha is not None:
        extra["git_sha"] = git_sha

    return _default_logger.log(
        event_type=EventType.MASTER_APPROVED.value,
        severity="INFO",
        status=200,
        request_id=request_id,
        message="Master render approved by Director post-render review",
        **extra,
        **kwargs,
    )


def log_short_render_event(
    event_type: str | EventType,
    production_id: str,
    edl_id: str,
    artifact_id: str | None = None,
    short_start_ms: int | None = None,
    short_end_ms: int | None = None,
    duration_ms: int | None = None,
    render_time_ms: float | None = None,
    size_bytes: int | None = None,
    request_id: str | None = None,
    git_sha: str | None = None,
    status: str = "success",
    error_code: str | None = None,
    message: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Log structured vertical Short render event for Google Cloud Logging ingestion."""
    normalized_type = event_type.value if isinstance(event_type, EventType) else str(event_type)
    severity: LogSeverity = "ERROR" if (normalized_type == EventType.SHORT_RENDER_FAILED.value or status == "failed") else "INFO"

    status_code: int = 500 if (status == "failed" or normalized_type == EventType.SHORT_RENDER_FAILED.value) else 200

    extra: dict[str, Any] = {
        "production_id": production_id,
        "edl_id": edl_id,
        "artifact_id": artifact_id,
        "render_status": str(status),
    }
    if short_start_ms is not None:
        extra["short_start_ms"] = short_start_ms
    if short_end_ms is not None:
        extra["short_end_ms"] = short_end_ms
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    if render_time_ms is not None:
        extra["render_time_ms"] = round(render_time_ms, 2)
    if size_bytes is not None:
        extra["size_bytes"] = size_bytes
    if git_sha is not None:
        extra["git_sha"] = git_sha

    return _default_logger.log(
        event_type=normalized_type,
        severity=severity,
        status=status_code,
        request_id=request_id,
        message=message or f"Short render {status}",
        error_code=error_code,
        **extra,
        **kwargs,
    )
