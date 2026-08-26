import os
import subprocess
from functools import lru_cache

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


def parse_allowed_emails(raw_value: str | None) -> list[str]:
    """Parse and normalize comma-separated allowed emails configuration.

    Returns empty list if unset, failing closed unless explicitly configured.
    """
    if not raw_value or not raw_value.strip():
        return []
    emails: list[str] = []
    for item in raw_value.split(","):
        cleaned = item.strip().lower()
        if cleaned and cleaned not in emails:
            emails.append(cleaned)
    return emails


class Settings:
    def __init__(self) -> None:
        self.service_name: str = "croviq-api"
        self.environment: str = os.getenv("CROVIQ_ENV") or os.getenv("ENVIRONMENT", "development")
        self.git_sha: str = resolve_git_sha()
        self.gcp_project_id: str | None = (
            os.getenv("GCP_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
            or os.getenv("PROJECT_ID")
        )
        self.memory_bank_location: str = os.getenv("MEMORY_BANK_LOCATION") or os.getenv("GCP_REGION", "us-central1")
        self.memory_bank_id: str = os.getenv("MEMORY_BANK_ID", "croviq-channel-memory")
        self.memory_store_provider: str = os.getenv("MEMORY_STORE_PROVIDER", "google" if (os.getenv("CROVIQ_ENV") == "production" or os.getenv("ENVIRONMENT") == "production") else "fake")
        self.allowed_emails: list[str] = parse_allowed_emails(os.getenv("CROVIQ_ALLOWED_EMAILS"))
        self.media_bucket_name: str = os.getenv("MEDIA_BUCKET_NAME") or (
            f"{self.gcp_project_id}-croviq-media-raw" if self.gcp_project_id else "croviq-media-raw"
        )
        self.media_storage_provider: str = os.getenv(
            "MEDIA_STORAGE_PROVIDER",
            "google" if (os.getenv("CROVIQ_ENV") == "production" or os.getenv("ENVIRONMENT") == "production") else "fake",
        )
        self.signed_url_expiry_seconds: int = int(os.getenv("SIGNED_URL_EXPIRY_SECONDS", str(DEFAULT_SIGNED_URL_EXPIRY_SECONDS)))
        self.max_upload_size_bytes: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(MAX_UPLOAD_SIZE_BYTES)))
        self.api_runtime_service_account: str | None = os.getenv("API_RUNTIME_SERVICE_ACCOUNT") or (
            f"croviq-api-runtime@{self.gcp_project_id}.iam.gserviceaccount.com" if self.gcp_project_id else None
        )
        self.speech_service_provider: str = os.getenv(
            "SPEECH_SERVICE_PROVIDER",
            "groq" if (os.getenv("CROVIQ_ENV") == "production" or os.getenv("ENVIRONMENT") == "production") else "fake",
        )
        self.groq_api_key: str | None = os.getenv("GROQ_API_KEY")
        self.groq_transcription_endpoint: str = os.getenv(
            "GROQ_TRANSCRIPTION_ENDPOINT",
            "https://api.groq.com/openai/v1/audio/transcriptions",
        )
        self.groq_transcription_model: str = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3")
        self.groq_transcription_prompt: str | None = os.getenv(
            "GROQ_TRANSCRIPTION_PROMPT",
            "Croviq, GitHub Actions, GitHub, YAML, workflow, runner, CI/CD, Cloud Run, Terraform, Docker, Google Cloud, repository, commit, deployment",
        )
        self.groq_timeout_seconds: float = float(os.getenv("GROQ_TIMEOUT_SECONDS", "120"))
        self.genai_backend_provider: str = os.getenv(
            "GENAI_BACKEND_PROVIDER",
            "google" if (os.getenv("CROVIQ_ENV") == "production" or os.getenv("ENVIRONMENT") == "production") else "fake",
        )
        self.gemini_model_id: str = os.getenv("GEMINI_MODEL_ID", "gemini-3.7-flash")
        self.vertexai_location: str = os.getenv("VERTEXAI_LOCATION") or os.getenv("GCP_REGION", "us-central1")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
