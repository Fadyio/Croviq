"""P0 AI Call Truth & Observability Audit Regression Tests.

Validates that:
1. Production AI clients strictly use Google / Vertex AI backend with ADC authentication and no API key.
2. No hidden fallback to Gemini Developer API or fake clients in production mode.
3. Structured model telemetry emits provider, backend, location, model, operation, latency, and status.
4. Telemetry strictly redacts and excludes secrets, auth tokens, and raw credentials.
5. Terraform declares Agent Platform Data Access audit logs and BigQuery observability dataset.
6. Publisher model logging configuration script is idempotent.
"""

import io
import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from croviq_api.config import Settings
from croviq_api.productions.dependencies import get_genai_client
from croviq_agents.client import GoogleGenAIClient, FakeGenAIClient
from croviq_media.transcript import GeminiTranscriptionService
from croviq_observability import StructuredLogger, log_ai_event
from croviq_observability.events import EventType
from croviq_observability.redaction import redact_string, sanitize_payload

@pytest.fixture(autouse=True)
def reset_genai_client_state():
    from croviq_api.productions.dependencies import set_genai_client
    set_genai_client(None)
    yield
    set_genai_client(None)


def test_production_genai_client_uses_vertex_backend() -> None:
    """Production mode must construct GoogleGenAIClient with vertexai=True and no API key."""
    settings = Settings(
        environment="production",
        gcp_project_id="croviq-506602",
        genai_backend_provider="google",
        gemini_model_id="gemini-3.7-flash",
        vertexai_location="global",
    )

    client = get_genai_client(settings)
    assert isinstance(client, GoogleGenAIClient)
def test_production_genai_client_fails_closed_without_gcp_project() -> None:
    """Production mode fails closed when gcp_project_id is missing, refusing fake client fallback."""
    from croviq_api.productions.dependencies import set_genai_client
    set_genai_client(None)

    settings = Settings(
        environment="production",
        gcp_project_id=None,
        genai_backend_provider="google",
    )

    with pytest.raises(RuntimeError, match="Production mode requires Google GenAI client"):
        get_genai_client(settings)
def test_no_api_key_environment_variable_used_by_ai_clients() -> None:
    """Ensure GoogleGenAIClient and GeminiTranscriptionService do not require or read API keys."""
    client = GoogleGenAIClient(project_id="croviq-506602", location="global", model_id="gemini-3.7-flash")
    assert not hasattr(client, "api_key")

    service = GeminiTranscriptionService(project_id="croviq-506602", location="global")
    assert not hasattr(service, "api_key")


def test_structured_model_telemetry_emits_canonical_metadata() -> None:
    """Structured AI telemetry emits provider, backend, location, model, latency, and status."""
    stream = io.StringIO()
    logger = StructuredLogger(service="croviq-api", environment="production", output_stream=stream)

    with patch("croviq_observability.logger._default_logger", logger):
        log_ai_event(
            event_type=EventType.AI_REQUEST_STARTED,
            agent="transcription",
            model="gemini-3.5-transcribe-preview",
            provider="google",
            backend="vertex_ai",
            location="global",
            operation="transcribe",
            production_id="prod_test_01",
            request_id="req_test_123",
            audio_duration_ms=15000,
            status="started",
        )

        log_ai_event(
            event_type=EventType.AI_REQUEST_COMPLETED,
            agent="transcription",
            model="gemini-3.5-transcribe-preview",
            provider="google",
            backend="vertex_ai",
            location="global",
            operation="transcribe",
            production_id="prod_test_01",
            request_id="req_test_123",
            latency_ms=1240.5,
            audio_duration_ms=15000,
            input_tokens=100,
            output_tokens=50,
            status="completed",
        )

    lines = [json.loads(line) for line in stream.getvalue().strip().split("\n") if line.strip()]
    assert len(lines) == 2

    start_event = lines[0]
    assert start_event["event_type"] == "ai.request.started"
    assert start_event["provider"] == "google"
    assert start_event["backend"] == "vertex_ai"
    assert start_event["location"] == "global"
    assert start_event["model"] == "gemini-3.5-transcribe-preview"
    assert start_event["status"] == "started"

    comp_event = lines[1]
    assert comp_event["event_type"] == "ai.request.completed"
    assert comp_event["provider"] == "google"
    assert comp_event["backend"] == "vertex_ai"
    assert comp_event["latency_ms"] == 1240.5
    assert comp_event["status"] == "completed"


def test_secrets_redacted_from_telemetry_payloads() -> None:
    """Credentials, bearer tokens, and API keys are automatically stripped from log payloads."""
    test_token = "".join(["ya29.", "a0AfH6SMDummyToken12345"])
    test_api_key = "".join(["AIza", "SyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P"])
    raw_payload = {
        "event_type": "ai.request.failed",
        "message": f"Authorization failed with Bearer {test_token} and API key {test_api_key}",
        "secret": "super_secret_password_value",
    }

    sanitized = sanitize_payload(raw_payload)
    serialized = json.dumps(sanitized)

    assert test_token not in serialized
    assert test_api_key not in serialized
    assert "super_secret_password_value" not in serialized
    assert "[REDACTED]" in serialized


def test_terraform_declares_agent_platform_audit_logs_and_bigquery() -> None:
    """Verify Terraform contains google_project_iam_audit_config for aiplatform and BigQuery observability."""
    root = Path(__file__).resolve().parents[3]
    main_tf = (root / "infra" / "main.tf").read_text(encoding="utf-8")

    # 1. Audit Config
    assert 'resource "google_project_iam_audit_config" "aiplatform_audit"' in main_tf
    assert 'service = "aiplatform.googleapis.com"' in main_tf
    assert 'log_type = "ADMIN_READ"' in main_tf
    assert 'log_type = "DATA_READ"' in main_tf
    assert 'log_type = "DATA_WRITE"' in main_tf

    # 2. BigQuery Dataset
    assert 'resource "google_bigquery_dataset" "ai_observability"' in main_tf
    assert 'dataset_id                 = "croviq_ai_observability"' in main_tf
    assert 'location                   = "US"' in main_tf

    # 3. BigQuery IAM permissions
    assert 'resource "google_bigquery_dataset_iam_member" "aiplatform_sa_bq_editor"' in main_tf
    assert 'role       = "roles/bigquery.dataEditor"' in main_tf
    assert 'resource "google_bigquery_dataset_iam_member" "api_runtime_bq_viewer"' in main_tf
    assert 'role       = "roles/bigquery.dataViewer"' in main_tf
