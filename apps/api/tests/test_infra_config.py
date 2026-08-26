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

    assert "GCP_PROJECT_ID" in env_vars, "GCP_PROJECT_ID missing from Cloud Run API service in infra/main.tf"
    assert env_vars["GCP_PROJECT_ID"] == "var.project_id"

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


def test_identity_platform_keeps_phone_auth_disabled() -> None:
    """Pin the deployed disabled phone-auth block so Terraform cannot remove it."""
    content = get_infra_main_content()

    identity_platform = re.search(
        r'resource\s+"google_identity_platform_config"\s+"default"\s*{(.*?)\n}\n\n# -+',
        content,
        re.DOTALL,
    )
    assert identity_platform is not None
    assert re.search(
        r"phone_number\s*{\s*enabled\s*=\s*false\s*}",
        identity_platform.group(1),
        re.DOTALL,
    )

def test_groq_secret_manager_phase_two_injects_scoped_runtime_secret() -> None:
    """Require the API Cloud Run service to reference Groq's latest secret version."""
    content = get_infra_main_content()

    assert '"secretmanager.googleapis.com"' in content
    assert '"speech.googleapis.com"' in content
    assert 'resource "google_project_iam_member" "deployer_secretmanager_admin"' in content
    assert 'role    = "roles/secretmanager.admin"' in content
    assert 'member  = "serviceAccount:${google_service_account.github_deployer.email}"' in content
    secret_resource = re.search(
        r'resource\s+"google_secret_manager_secret"\s+"groq_api_key"\s*{(.*?)\n}',
        content,
        re.DOTALL,
    )
    assert secret_resource is not None
    assert 'secret_id = "groq-api-key"' in secret_resource.group(1)
    assert "depends_on = [google_project_service.required_services]" in secret_resource.group(1)

    assert 'resource "google_secret_manager_secret_iam_member" "api_runtime_groq_accessor"' in content
    assert 'secret_id = google_secret_manager_secret.groq_api_key.id' in content
    assert 'role      = "roles/secretmanager.secretAccessor"' in content
    assert 'member    = "serviceAccount:${google_service_account.api_runtime.email}"' in content

    api_service = re.search(
        r'resource\s+"google_cloud_run_v2_service"\s+"api"\s*{(.*?)\n}\n\n# Public invoker',
        content,
        re.DOTALL,
    )
    assert api_service is not None
    assert 'name = "GROQ_API_KEY"' in api_service.group(1)
    assert 'secret  = google_secret_manager_secret.groq_api_key.secret_id' in api_service.group(1)
    assert 'version = "latest"' in api_service.group(1)
