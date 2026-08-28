import os
from pathlib import Path
import subprocess
from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from croviq_domain.production import (
    DEFAULT_SIGNED_URL_EXPIRY_SECONDS,
    MAX_UPLOAD_SIZE_BYTES,
)


def resolve_git_sha() -> str:
    """Resolve git SHA from environment or git repository fallback."""
    if sha := os.getenv("GIT_SHA"):
        return sha.strip()
    if sha := os.getenv("COMMIT_SHA"):
        return sha.strip()
    if sha := os.getenv("REVISION"):
        return sha.strip()
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
    except Exception:
        return "local"


def parse_allowed_emails(raw_value: str | list[str] | None) -> list[str]:
    """Parse and normalize comma-separated allowed emails configuration.

    Returns empty list if unset, failing closed unless explicitly configured.
    """
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [item.strip().lower() for item in raw_value if isinstance(item, str) and item.strip()]
    if not isinstance(raw_value, str) or not raw_value.strip():
        return []
    emails: list[str] = []
    for item in raw_value.split(","):
        cleaned = item.strip().lower()
        if cleaned and cleaned not in emails:
            emails.append(cleaned)
    return emails


class Settings(BaseSettings):
    """Canonical application settings loaded from environment or .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "croviq-api"
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("CROVIQ_ENV", "ENVIRONMENT"),
    )
    git_sha: str = Field(
        default_factory=resolve_git_sha,
        validation_alias=AliasChoices("GIT_SHA", "COMMIT_SHA", "REVISION"),
    )
    gcp_project_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "GCP_PROJECT_ID",
            "GOOGLE_CLOUD_PROJECT",
            "GCLOUD_PROJECT",
            "PROJECT_ID",
        ),
    )
    memory_bank_location: str = Field(
        default="us-central1",
        validation_alias=AliasChoices("MEMORY_BANK_LOCATION", "GCP_REGION"),
    )
    memory_bank_id: str = Field(
        default="croviq-channel-memory",
        validation_alias=AliasChoices("MEMORY_BANK_ID"),
    )
    memory_store_provider: str = Field(
        default="",
        validation_alias=AliasChoices("MEMORY_STORE_PROVIDER"),
    )
    allowed_emails: str | list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("CROVIQ_ALLOWED_EMAILS"),
    )
    media_bucket_name: str = Field(
        default="",
        validation_alias=AliasChoices("MEDIA_BUCKET_NAME"),
    )
    media_storage_provider: str = Field(
        default="",
        validation_alias=AliasChoices("MEDIA_STORAGE_PROVIDER"),
    )
    signed_url_expiry_seconds: int = Field(
        default=DEFAULT_SIGNED_URL_EXPIRY_SECONDS,
        validation_alias=AliasChoices("SIGNED_URL_EXPIRY_SECONDS"),
    )
    max_upload_size_bytes: int = Field(
        default=MAX_UPLOAD_SIZE_BYTES,
        validation_alias=AliasChoices("MAX_UPLOAD_SIZE_BYTES"),
    )
    api_runtime_service_account: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_RUNTIME_SERVICE_ACCOUNT"),
    )
    speech_service_provider: str = Field(
        default="",
        validation_alias=AliasChoices("SPEECH_SERVICE_PROVIDER"),
    )
    gemini_transcription_model: str = Field(
        default="gemini-3.5-transcribe-preview",
        validation_alias=AliasChoices("GEMINI_TRANSCRIPTION_MODEL"),
    )
    gemini_transcription_location: str = Field(
        default="global",
        validation_alias=AliasChoices(
            "GEMINI_TRANSCRIPTION_LOCATION",
            "VERTEXAI_LOCATION",
        ),
    )
    genai_backend_provider: str = Field(
        default="",
        validation_alias=AliasChoices("GENAI_BACKEND_PROVIDER"),
    )
    gemini_model_id: str = Field(
        default="gemini-3.7-flash",
        validation_alias=AliasChoices("GEMINI_MODEL_ID"),
    )
    vertexai_location: str = Field(
        default="global",
        validation_alias=AliasChoices("VERTEXAI_LOCATION"),
    )
    google_oauth_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_ID", "YOUTUBE_OAUTH_CLIENT_ID"),
    )
    google_oauth_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_SECRET", "YOUTUBE_OAUTH_CLIENT_SECRET"),
    )
    google_oauth_redirect_uri: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_OAUTH_REDIRECT_URI", "YOUTUBE_OAUTH_REDIRECT_URI"),
    )
    scheduler_auth_token: str = Field(
        default="",
        validation_alias=AliasChoices("SCHEDULER_AUTH_TOKEN", "CROVIQ_SCHEDULER_SECRET"),
    )

    @field_validator("allowed_emails", mode="after")
    @classmethod
    def _validate_allowed_emails(cls, value: Any) -> list[str]:
        return parse_allowed_emails(value)

    @model_validator(mode="after")
    def _apply_dynamic_defaults(self) -> "Settings":
        is_prod = self.environment == "production"

        if not self.memory_store_provider:
            self.memory_store_provider = "google" if is_prod else "fake"

        if not self.media_storage_provider:
            self.media_storage_provider = "google" if is_prod else "fake"

        if not self.speech_service_provider:
            self.speech_service_provider = "google" if is_prod else "fake"

        if not self.genai_backend_provider:
            self.genai_backend_provider = "google" if is_prod else "fake"

        if not self.media_bucket_name:
            self.media_bucket_name = (
                f"{self.gcp_project_id}-croviq-media-raw"
                if self.gcp_project_id
                else "croviq-media-raw"
            )

        if not self.api_runtime_service_account and self.gcp_project_id:
            self.api_runtime_service_account = (
                f"croviq-api-runtime@{self.gcp_project_id}.iam.gserviceaccount.com"
            )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
