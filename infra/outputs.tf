output "project_id" {
  value       = var.project_id
  description = "The configured Google Cloud project ID."
}

output "region" {
  value       = var.region
  description = "The configured Google Cloud region."
}

output "environment" {
  value       = var.environment
  description = "The deployment environment."
}

output "app_domain" {
  value       = var.app_domain
  description = "The application domain."
}

output "artifact_registry_repository" {
  value       = google_artifact_registry_repository.api_repo.name
  description = "The fully qualified Artifact Registry repository resource name."
}

output "artifact_registry_location" {
  value       = google_artifact_registry_repository.api_repo.location
  description = "The Artifact Registry repository location."
}

output "runtime_service_account_email" {
  value       = google_service_account.api_runtime.email
  description = "The email address of the Cloud Run API runtime service account."
}

output "deploy_service_account_email" {
  value       = google_service_account.github_deployer.email
  description = "The email address of the GitHub Actions deployment service account."
}

output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github_provider.name
  description = "The full identifier of the Workload Identity Provider for GitHub Actions OIDC."
}

output "cloud_run_service_name" {
  value       = google_cloud_run_v2_service.api.name
  description = "The name of the Cloud Run API service."
}

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.api.uri
  description = "The live HTTPS URL of the deployed Cloud Run API service."
}

output "cloud_run_latest_revision" {
  value       = google_cloud_run_v2_service.api.latest_created_revision
  description = "The latest created revision identifier of the Cloud Run API service."
}

output "firestore_database_name" {
  value       = google_firestore_database.default.name
  description = "The database ID of the default Firestore database instance."
}

output "firestore_database_location" {
  value       = google_firestore_database.default.location_id
  description = "The location ID of the default Firestore database instance."
}

output "identity_platform_config_name" {
  value       = google_identity_platform_config.default.name
  description = "The resource name of the Identity Platform configuration."
}
