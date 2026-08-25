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

output "root_domain" {
  value       = var.root_domain
  description = "The root domain hostname."
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

output "web_cloud_run_service_name" {
  value       = google_cloud_run_v2_service.web.name
  description = "The name of the Cloud Run Web service."
}

output "web_cloud_run_url" {
  value       = google_cloud_run_v2_service.web.uri
  description = "The live HTTPS URL of the deployed Cloud Run Web service."
}

output "web_cloud_run_latest_revision" {
  value       = google_cloud_run_v2_service.web.latest_created_revision
  description = "The latest created revision identifier of the Cloud Run Web service."
}

output "web_artifact_registry_repository" {
  value       = google_artifact_registry_repository.web_repo.name
  description = "The fully qualified Artifact Registry web repository resource name."
}

output "web_runtime_service_account_email" {
  value       = google_service_account.web_runtime.email
  description = "The email address of the Cloud Run Web runtime service account."
}

output "load_balancer_ip" {
  value       = google_compute_global_address.app_ip.address
  description = "The static global external IPv4 address allocated for the Application Load Balancer."
}

output "dns_authorization_record_name" {
  value       = google_certificate_manager_dns_authorization.app_dns_auth.dns_resource_record[0].name
  description = "The DNS Resource Record Name for Google Certificate Manager DNS authorization."
}

output "dns_authorization_record_type" {
  value       = google_certificate_manager_dns_authorization.app_dns_auth.dns_resource_record[0].type
  description = "The DNS Resource Record Type for Google Certificate Manager DNS authorization."
}

output "dns_authorization_record_value" {
  value       = google_certificate_manager_dns_authorization.app_dns_auth.dns_resource_record[0].data
  description = "The DNS Resource Record Value (data) for Google Certificate Manager DNS authorization."
}

output "certificate_dns_authorization_name" {
  value       = google_certificate_manager_dns_authorization.app_dns_auth.dns_resource_record[0].name
  description = "The DNS Resource Record Name for Google Certificate Manager DNS authorization."
}

output "certificate_dns_authorization_type" {
  value       = google_certificate_manager_dns_authorization.app_dns_auth.dns_resource_record[0].type
  description = "The DNS Resource Record Type for Google Certificate Manager DNS authorization."
}

output "certificate_dns_authorization_value" {
  value       = google_certificate_manager_dns_authorization.app_dns_auth.dns_resource_record[0].data
  description = "The DNS Resource Record Value (data) for Google Certificate Manager DNS authorization."
}

output "root_dns_authorization_record_name" {
  value       = google_certificate_manager_dns_authorization.root_dns_auth.dns_resource_record[0].name
  description = "The DNS Resource Record Name for root domain Google Certificate Manager DNS authorization."
}

output "root_dns_authorization_record_type" {
  value       = google_certificate_manager_dns_authorization.root_dns_auth.dns_resource_record[0].type
  description = "The DNS Resource Record Type for root domain Google Certificate Manager DNS authorization."
}

output "root_dns_authorization_record_value" {
  value       = google_certificate_manager_dns_authorization.root_dns_auth.dns_resource_record[0].data
  description = "The DNS Resource Record Value (data) for root domain Google Certificate Manager DNS authorization."
}

output "root_certificate_dns_authorization_name" {
  value       = google_certificate_manager_dns_authorization.root_dns_auth.dns_resource_record[0].name
  description = "The DNS Resource Record Name for root domain Google Certificate Manager DNS authorization."
}

output "root_certificate_dns_authorization_type" {
  value       = google_certificate_manager_dns_authorization.root_dns_auth.dns_resource_record[0].type
  description = "The DNS Resource Record Type for root domain Google Certificate Manager DNS authorization."
}

output "root_certificate_dns_authorization_value" {
  value       = google_certificate_manager_dns_authorization.root_dns_auth.dns_resource_record[0].data
  description = "The DNS Resource Record Value (data) for root domain Google Certificate Manager DNS authorization."
}

output "web_neg_name" {
  value       = google_compute_region_network_endpoint_group.web_neg.name
  description = "The name of the Serverless NEG for croviq-web."
}

output "api_neg_name" {
  value       = google_compute_region_network_endpoint_group.api_neg.name
  description = "The name of the Serverless NEG for croviq-api."
}

output "web_backend_service_name" {
  value       = google_compute_backend_service.web.name
  description = "The name of the backend service for croviq-web."
}

output "api_backend_service_name" {
  value       = google_compute_backend_service.api.name
  description = "The name of the backend service for croviq-api."
}

output "url_map_name" {
  value       = google_compute_url_map.app.name
  description = "The name of the URL map for single-origin routing."
}

output "certificate_manager_certificate_name" {
  value       = google_certificate_manager_certificate.app_cert.name
  description = "The name of the Google Certificate Manager managed certificate."
}

output "certificate_map_name" {
  value       = google_certificate_manager_certificate_map.app_cert_map.name
  description = "The name of the Google Certificate Manager certificate map."
}

output "root_certificate_manager_certificate_name" {
  value       = google_certificate_manager_certificate.root_cert.name
  description = "The name of the Google Certificate Manager managed certificate for the root domain."
}

output "root_certificate_map_entry_name" {
  value       = google_certificate_manager_certificate_map_entry.root_cert_map_entry.name
  description = "The name of the Google Certificate Manager certificate map entry for the root domain."
}
