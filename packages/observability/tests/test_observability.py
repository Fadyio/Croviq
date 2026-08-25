"""Unit and integration tests for croviq-observability package."""

import io
import json
from fastapi import FastAPI, Request, status
from fastapi.testclient import TestClient
import pytest

from croviq_observability import (
    CLIENT_ALLOWED_EVENT_TYPES,
    EventType,
    StructuredLogger,
    StructuredLoggingMiddleware,
    extract_request_id,
    extract_trace_id,
    get_request_id,
    get_trace_id,
    log_ai_event,
    log_auth_event,
    log_error,
    log_event,
    log_firestore_event,
    log_workspace_event,
    redact_string,
    register_error_handlers,
    sanitize_payload,
    set_logger,
    set_request_context,
)


@pytest.fixture
def log_stream() -> io.StringIO:
    return io.StringIO()


@pytest.fixture
def custom_logger(log_stream: io.StringIO) -> StructuredLogger:
    logger = StructuredLogger(
        service="croviq-test-api",
        environment="test",
        git_sha="test_sha_123",
        gcp_project_id="croviq-test-project",
        output_stream=log_stream,
    )
    set_logger(logger)
    return logger


def parse_single_log(stream: io.StringIO) -> dict:
    stream.seek(0)
    lines = [line.strip() for line in stream.getvalue().splitlines() if line.strip()]
    assert len(lines) >= 1
    return json.loads(lines[-1])


# -----------------------------------------------------------------------------
# 1. Standard Fields Verification
# -----------------------------------------------------------------------------


def test_standard_fields_emitted_on_event(custom_logger: StructuredLogger, log_stream: io.StringIO) -> None:
    set_request_context(
        request_id="req-12345",
        trace_id="0123456789abcdef0123456789abcdef",
        user_id="user-xyz",
        route="/api/workspace",
    )

    custom_logger.log(
        event_type=EventType.WORKSPACE_LOADED.value,
        status=200,
        latency_ms=12.34,
        message="Workspace loaded successfully",
    )

    log_entry = parse_single_log(log_stream)

    assert log_entry["service"] == "croviq-test-api"
    assert log_entry["environment"] == "test"
    assert log_entry["git_sha"] == "test_sha_123"
    assert log_entry["event_type"] == "workspace.loaded"
    assert log_entry["request_id"] == "req-12345"
    assert log_entry["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert log_entry["user_id"] == "user-xyz"
    assert log_entry["route"] == "/api/workspace"
    assert log_entry["status"] == 200
    assert log_entry["severity"] == "INFO"
    assert log_entry["latency_ms"] == 12.34
    assert log_entry["logging.googleapis.com/trace"] == "projects/croviq-test-project/traces/0123456789abcdef0123456789abcdef"


# -----------------------------------------------------------------------------
# 2. Secret Redaction
# -----------------------------------------------------------------------------


def test_secret_redaction_masks_sensitive_keys() -> None:
    payload = {
        "user_id": "usr-1",
        "password": "super-secret-password",
        "id_token": "eyJhbGciOi...",
        "authorization": "Bearer secret_bearer_token",
        "api_key": "AIzaSySecretApiKey12345678901234567",
        "nested": {
            "credentials": {"private_key": "-----BEGIN PRIVATE KEY-----..."},
            "safe_field": "visible_value",
        },
    }

    sanitized = sanitize_payload(payload)

    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["id_token"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["credentials"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "visible_value"


def test_secret_redaction_in_strings() -> None:
    assert redact_string("Bearer my_secret_token_123") == "Bearer [REDACTED]"
    assert redact_string("https://api.example.com?password=mysecret&safe=1") == "https://api.example.com?password=[REDACTED]&safe=1"


# -----------------------------------------------------------------------------
# 3. Context & Trace Extraction
# -----------------------------------------------------------------------------


def test_trace_extraction_from_cloud_trace_header() -> None:
    headers = {
        "x-cloud-trace-context": "105445aa7843bc8bf206b12000100000/1;o=1"
    }
    trace_id = extract_trace_id(headers)
    assert trace_id == "105445aa7843bc8bf206b12000100000"


def test_trace_extraction_from_traceparent_header() -> None:
    headers = {
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    }
    trace_id = extract_trace_id(headers)
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_request_id_extraction_and_fallback() -> None:
    headers = {"x-request-id": "custom-req-id-99"}
    assert extract_request_id(headers) == "custom-req-id-99"

    generated = extract_request_id({})
    assert len(generated) >= 32


# -----------------------------------------------------------------------------
# 4. Domain & Helper Logging
# -----------------------------------------------------------------------------


def test_auth_event_logging(custom_logger: StructuredLogger, log_stream: io.StringIO) -> None:
    log_auth_event(
        event_type=EventType.AUTH_LOGIN_VERIFIED.value,
        status=200,
        request_id="auth-req-1",
        user_id="creator_1",
    )
    entry = parse_single_log(log_stream)
    assert entry["event_type"] == "auth.login_verified"
    assert entry["status"] == 200
    assert entry["user_id"] == "creator_1"


def test_firestore_event_logging(custom_logger: StructuredLogger, log_stream: io.StringIO) -> None:
    log_firestore_event(
        event_type=EventType.FIRESTORE_WRITE.value,
        collection="workspaces",
        operation="set",
        document_id="ws-123",
        status=200,
    )
    entry = parse_single_log(log_stream)
    assert entry["event_type"] == "firestore.write"
    assert entry["collection"] == "workspaces"
    assert entry["operation"] == "set"
    assert entry["document_id"] == "ws-123"


def test_future_ai_event_logging(custom_logger: StructuredLogger, log_stream: io.StringIO) -> None:
    log_ai_event(
        event_type=EventType.AI_CALL_COMPLETED.value,
        agent="Director",
        model="gemini-3.7-flash",
        status="success",
        run_id="run-456",
        job_id="job-789",
        input_tokens=1200,
        output_tokens=350,
        latency_ms=842.1,
    )
    entry = parse_single_log(log_stream)
    assert entry["event_type"] == "ai.call.completed"
    assert entry["agent"] == "Director"
    assert entry["model"] == "gemini-3.7-flash"
    assert entry["run_id"] == "run-456"
    assert entry["job_id"] == "job-789"
    assert entry["input_tokens"] == 1200
    assert entry["output_tokens"] == 350
    assert entry["latency_ms"] == 842.1


# -----------------------------------------------------------------------------
# 5. FastAPI Middleware & Error Handling (No Stack Leaks to Client)
# -----------------------------------------------------------------------------


def test_middleware_and_error_handling(custom_logger: StructuredLogger, log_stream: io.StringIO) -> None:
    app = FastAPI()
    register_error_handlers(app)
    app.add_middleware(StructuredLoggingMiddleware)

    @app.get("/test-ok")
    async def ok_route() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/test-error")
    async def error_route() -> None:
        raise ValueError("Sensitive database internal exception message")

    client = TestClient(app, raise_server_exceptions=False)

    # 1. Successful request
    res_ok = client.get("/test-ok", headers={"x-request-id": "client-req-001"})
    assert res_ok.status_code == 200
    assert res_ok.headers["x-request-id"] == "client-req-001"
    assert "x-trace-id" in res_ok.headers

    # 2. Failing request (500 internal error)
    res_err = client.get("/test-error", headers={"x-request-id": "client-req-002"})
    assert res_err.status_code == 500
    assert res_err.headers["x-request-id"] == "client-req-002"

    body = res_err.json()
    assert body["error_code"] == "internal_error"
    # Never leak internal stack trace to browser / client!
    assert "Traceback" not in str(body)
    assert "Sensitive database internal" not in str(body)

    # But server-side structured error log contains diagnostic info
    err_entry = parse_single_log(log_stream)
    assert err_entry["severity"] == "ERROR"
    assert err_entry["status"] == 500
    assert err_entry["exception_type"] == "ValueError"
