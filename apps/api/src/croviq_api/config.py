import os
import subprocess
from functools import lru_cache


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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
