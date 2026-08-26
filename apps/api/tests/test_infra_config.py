"""Regression tests for Terraform infrastructure configuration."""

from pathlib import Path
import re
import pytest


def get_infra_main_content() -> str:
    """Find and read infra/main.tf from repo root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "infra" / "main.tf"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError("Could not find infra/main.tf")


def extract_api_cloud_run_env_vars(main_tf_content: str) -> dict[str, str]:
    """Extract environment variables configured in google_cloud_run_v2_service.api container."""
    # Locate the google_cloud_run_v2_service "api" block
    api_match = re.search(
        r'resource\s+"google_cloud_run_v2_service"\s+"api"\s*{(.*?)\nresource\s+',
        main_tf_content,
        re.DOTALL,
    )
    assert api_match is not None, "google_cloud_run_v2_service.api resource block not found in infra/main.tf"
    api_block = api_match.group(1)

    # Find all env blocks
    env_blocks = re.findall(
        r'env\s*{\s*name\s*=\s*"([^"]+)"\s*value\s*=\s*([^\s}]+)\s*}',
        api_block,
    )
    return {name: val.strip('"') for name, val in env_blocks}


def test_api_cloud_run_has_required_production_env_vars() -> None:
    """Assert presence of required production environment variables on Cloud Run API service."""
    content = get_infra_main_content()
    env_vars = extract_api_cloud_run_env_vars(content)

    # Core required environment variables
    assert "CROVIQ_ALLOWED_EMAILS" in env_vars, "CROVIQ_ALLOWED_EMAILS missing from Cloud Run API service in infra/main.tf"
    assert env_vars["CROVIQ_ALLOWED_EMAILS"] == "var.allowed_emails"

    assert "MEMORY_STORE_PROVIDER" in env_vars, "MEMORY_STORE_PROVIDER missing from Cloud Run API service in infra/main.tf"
    assert env_vars["MEMORY_STORE_PROVIDER"] == "google"

    assert "MEDIA_STORAGE_PROVIDER" in env_vars, "MEDIA_STORAGE_PROVIDER missing from Cloud Run API service in infra/main.tf"
    assert env_vars["MEDIA_STORAGE_PROVIDER"] == "google"

    assert "CROVIQ_ENV" in env_vars, "CROVIQ_ENV missing from Cloud Run API service in infra/main.tf"
    assert env_vars["CROVIQ_ENV"] == "production"

    assert "ENVIRONMENT" in env_vars, "ENVIRONMENT missing from Cloud Run API service in infra/main.tf"
    assert env_vars["ENVIRONMENT"] == "production"

    assert "GIT_SHA" in env_vars, "GIT_SHA missing from Cloud Run API service in infra/main.tf"
    assert env_vars["GIT_SHA"] == "var.git_sha"

    assert "MEMORY_BANK_LOCATION" in env_vars, "MEMORY_BANK_LOCATION missing from Cloud Run API service in infra/main.tf"
    assert env_vars["MEMORY_BANK_LOCATION"] == "var.region"

    assert "MEMORY_BANK_ID" in env_vars, "MEMORY_BANK_ID missing from Cloud Run API service in infra/main.tf"
    assert env_vars["MEMORY_BANK_ID"] == "var.memory_bank_id"

    assert "MEDIA_BUCKET_NAME" in env_vars, "MEDIA_BUCKET_NAME missing from Cloud Run API service in infra/main.tf"
    assert env_vars["MEDIA_BUCKET_NAME"] == "google_storage_bucket.media_raw.name"


def test_deployer_has_serviceusage_consumer_role() -> None:
    """Assert presence of roles/serviceusage.serviceUsageConsumer IAM role for deployment service account."""
    content = get_infra_main_content()
    assert (
        'role    = "roles/serviceusage.serviceUsageConsumer"' in content
    ), "roles/serviceusage.serviceUsageConsumer missing from infra/main.tf"
