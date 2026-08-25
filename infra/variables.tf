variable "project_id" {
  type        = string
  description = "The Google Cloud project ID."
}

variable "region" {
  type        = string
  description = "The primary Google Cloud region for resources."
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "The deployment environment (e.g. dev, staging, prod)."
  default     = "dev"
}

variable "app_domain" {
  type        = string
  description = "The application hostname (e.g. app.croviq.app)."
  default     = "app.croviq.app"
}

variable "artifact_registry_repository_id" {
  type        = string
  description = "The Artifact Registry repository ID for API container images."
  default     = "croviq-api"
}

variable "api_runtime_service_account_id" {
  type        = string
  description = "The service account ID for the Cloud Run API runtime."
  default     = "croviq-api-runtime"
}

variable "github_deployer_service_account_id" {
  type        = string
  description = "The service account ID for GitHub Actions deployment."
  default     = "croviq-github-deployer"
}

variable "workload_identity_pool_id" {
  type        = string
  description = "The ID of the Workload Identity Pool for GitHub Actions."
  default     = "github-actions-pool"
}

variable "workload_identity_pool_provider_id" {
  type        = string
  description = "The ID of the Workload Identity Provider for GitHub Actions."
  default     = "github-actions-provider"
}

variable "github_repository_owner" {
  type        = string
  description = "The GitHub organization or username owning the repository."
  default     = "Fadyio"
}

variable "github_repository_name" {
  type        = string
  description = "The GitHub repository name."
  default     = "Croviq"
}
