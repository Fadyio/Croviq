"""Tests for configuration truth, production parity, and startup logging invariants."""

import pytest
from croviq_domain.production import (
    DEFAULT_SIGNED_URL_EXPIRY_SECONDS,
    MAX_UPLOAD_SIZE_BYTES,
)
from croviq_api.config import Settings
from croviq_api.main import emit_startup_config_event


def test_canonical_domain_constants():
    """Verify domain constants match approved product specifications."""
    assert MAX_UPLOAD_SIZE_BYTES == 1_073_741_824  # 1 GB
    assert DEFAULT_SIGNED_URL_EXPIRY_SECONDS == 1800  # 30 minutes


def test_settings_default_limits():
    """Verify Settings defaults match canonical domain constants."""
    settings = Settings()
    assert settings.max_upload_size_bytes == 1_073_741_824
    assert settings.signed_url_expiry_seconds == 1800


def test_production_settings_resolution_no_fake_providers(monkeypatch):
    """Verify that in production mode, provider settings strictly resolve to 'google', never 'fake'."""
    monkeypatch.setenv("CROVIQ_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("MEMORY_STORE_PROVIDER", raising=False)
    monkeypatch.delenv("MEDIA_STORAGE_PROVIDER", raising=False)
    monkeypatch.delenv("SPEECH_SERVICE_PROVIDER", raising=False)
    monkeypatch.delenv("GENAI_BACKEND_PROVIDER", raising=False)

    prod_settings = Settings()
    assert prod_settings.environment == "production"
    assert prod_settings.memory_store_provider == "google"
    assert prod_settings.media_storage_provider == "google"
    assert prod_settings.speech_service_provider == "google"
    assert prod_settings.genai_backend_provider == "google"
    assert prod_settings.gemini_transcription_model == "gemini-3.5-transcribe-preview"
    assert prod_settings.vertexai_location == "global"


def test_google_backed_local_mode_parity(monkeypatch):
    """Verify Google-backed local mode mirrors production provider and model choices."""
    monkeypatch.setenv("CROVIQ_ENV", "development")
    monkeypatch.setenv("GCP_PROJECT_ID", "croviq-506602")
    monkeypatch.setenv("MEMORY_STORE_PROVIDER", "google")
    monkeypatch.setenv("MEDIA_STORAGE_PROVIDER", "google")
    monkeypatch.setenv("SPEECH_SERVICE_PROVIDER", "google")
    monkeypatch.setenv("GENAI_BACKEND_PROVIDER", "google")
    monkeypatch.setenv("VERTEXAI_LOCATION", "global")
    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-3.7-flash")
    monkeypatch.setenv("GEMINI_TRANSCRIPTION_MODEL", "gemini-3.5-transcribe-preview")
    monkeypatch.setenv("GEMINI_TRANSCRIPTION_LOCATION", "global")
    monkeypatch.setenv("MEMORY_BANK_LOCATION", "us-central1")

    google_local_settings = Settings()
    assert google_local_settings.environment == "development"
    assert google_local_settings.gcp_project_id == "croviq-506602"
    assert google_local_settings.memory_store_provider == "google"
    assert google_local_settings.media_storage_provider == "google"
    assert google_local_settings.speech_service_provider == "google"
    assert google_local_settings.genai_backend_provider == "google"
    assert google_local_settings.vertexai_location == "global"
    assert google_local_settings.gemini_model_id == "gemini-3.7-flash"
    assert google_local_settings.gemini_transcription_model == "gemini-3.5-transcribe-preview"
    assert google_local_settings.gemini_transcription_location == "global"
    assert google_local_settings.memory_bank_location == "us-central1"


def test_deterministic_fake_local_mode_defaults(monkeypatch):
    """Verify deterministic local fake mode defaults safely to 'fake'."""
    monkeypatch.setenv("CROVIQ_ENV", "development")
    monkeypatch.delenv("MEMORY_STORE_PROVIDER", raising=False)
    monkeypatch.delenv("MEDIA_STORAGE_PROVIDER", raising=False)
    monkeypatch.delenv("SPEECH_SERVICE_PROVIDER", raising=False)
    monkeypatch.delenv("GENAI_BACKEND_PROVIDER", raising=False)

    fake_settings = Settings()
    assert fake_settings.environment == "development"
    assert fake_settings.memory_store_provider == "fake"
    assert fake_settings.media_storage_provider == "fake"
    assert fake_settings.speech_service_provider == "fake"
    assert fake_settings.genai_backend_provider == "fake"


def test_startup_config_loaded_event_structure(monkeypatch):
    """Verify config.loaded event emits required fields and NEVER logs sensitive secrets."""
    monkeypatch.setenv("CROVIQ_ENV", "production")
    monkeypatch.setenv("GCP_PROJECT_ID", "croviq-506602")
    monkeypatch.setenv("CROVIQ_ALLOWED_EMAILS", "demo@croviq.app,secret_user@example.com")
    monkeypatch.setenv("GIT_SHA", "test_sha_12345")

    settings = Settings()
    event = emit_startup_config_event(settings)

    payload = event
    # Allowed fields
    assert payload["environment"] == "production"
    assert payload["gcp_project_id"] == "croviq-506602"
    assert payload["vertex_location"] == "global"
    assert payload["genai_provider"] == "google"
    assert payload["gemini_model"] == "gemini-3.7-flash"
    assert payload["transcription_provider"] == "google"
    assert payload["transcription_model"] == "gemini-3.5-transcribe-preview"
    assert payload["memory_provider"] == "google"
    assert payload["media_provider"] == "google"
    assert payload["tts_provider"] == "google"
    assert payload["max_upload_size_bytes"] == 1_073_741_824
    assert payload["signed_url_expiry_seconds"] == 1800
    assert payload["git_sha"] == "test_sha_12345"

    # Forbidden fields (must never be logged)
    assert "api_key" not in payload
    assert "apiKey" not in payload
    assert "token" not in payload
    assert "secret" not in payload
    assert "allowed_emails" not in payload
    assert "demo@croviq.app" not in str(payload)
    assert "secret_user@example.com" not in str(payload)
