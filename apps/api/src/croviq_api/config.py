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

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
