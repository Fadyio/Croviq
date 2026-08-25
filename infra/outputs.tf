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
