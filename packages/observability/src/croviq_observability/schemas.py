"""Pydantic schemas and type definitions for structured log payloads."""

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

LogSeverity = Literal[
    "DEFAULT",
    "DEBUG",
    "INFO",
    "NOTICE",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "ALERT",
    "EMERGENCY",
]


class StandardLogEvent(BaseModel):
    """Canonical structured log entry schema for Google Cloud Logging ingestion.

    Guarantees:
    - Every required standard field is structured as top-level jsonPayload.
    - Cloud Logging trace correlation is embedded when project and trace_id exist.
    - AI agent & model fields are explicitly typed for future execution graphs.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Standard core fields
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    severity: LogSeverity = Field(default="INFO", description="Cloud Logging standard severity")
    service: str = Field(default="croviq-api", description="Service identifier")
    environment: str = Field(default="development", description="Deployment environment")
    event_type: str = Field(description="Normalized taxonomy event type")
    request_id: str = Field(description="Correlation request identifier")
    trace_id: str = Field(description="Distributed OpenTelemetry / Cloud Trace identifier")
    user_id: str | None = Field(default=None, description="Authenticated creator user ID")
    route: str | None = Field(default=None, description="HTTP route or execution handler")
    status: int | str | None = Field(default=None, description="HTTP or execution status code")
    latency_ms: float | None = Field(default=None, description="Execution duration in milliseconds")
    git_sha: str | None = Field(default=None, description="Git commit SHA or image digest")
    error_code: str | None = Field(default=None, description="Machine-readable error classification")
    message: str | None = Field(default=None, description="Human-readable summary message")

    # Error diagnostics (kept server-side in logs only)
    exception_type: str | None = Field(
        default=None, description="Exception class name if an error occurred"
    )
    exception_message: str | None = Field(
        default=None, description="Sanitized exception message"
    )

    # Future AI / Agent fields (Defined now, consumed in future agent department jobs)
    agent: str | None = Field(default=None, description="Department agent name (e.g. Director, Editor, Packaging, QA)")
    model: str | None = Field(default=None, description="Multimodal LLM model identifier (e.g. gemini-3.7-flash)")
    run_id: str | None = Field(default=None, description="Immutable workflow Run ID")
    job_id: str | None = Field(default=None, description="Bounded execution Job ID within Run")
    input_tokens: int | None = Field(default=None, description="Prompt token count consumed")
    output_tokens: int | None = Field(default=None, description="Candidate token count produced")

    # Google Cloud Logging special fields for native indexing
    gcp_trace: str | None = Field(
        default=None,
        alias="logging.googleapis.com/trace",
        description="Google Cloud Trace resource link for log correlation",
    )


class ClientEventPayload(BaseModel):
    """Sanitized client event ingested from browser UI at /api/client-events."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["client.error", "auth.login_attempt", "auth.login_failed"]
    error_code: str | None = None
    message: str | None = None
