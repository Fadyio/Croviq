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

variable "root_domain" {
  type        = string
  description = "The root domain hostname (e.g. croviq.app)."
  default     = "croviq.app"
}

variable "artifact_registry_repository_id" {
  type        = string
  description = "The Artifact Registry repository ID for API container images."
  default     = "croviq-api"
}
variable "artifact_registry_web_repository_id" {
  type        = string
  description = "The Artifact Registry repository ID for web container images."
  default     = "croviq-web"
}

variable "web_runtime_service_account_id" {
  type        = string
  description = "The service account ID for the Cloud Run web runtime."
  default     = "croviq-web-runtime"
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

variable "api_image" {
  type        = string
  description = "The immutable container image reference (must include sha256 digest) for the croviq-api Cloud Run service."

  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.api_image))
    error_message = "The api_image variable must specify an immutable image digest format: e.g., 'us-central1-docker.pkg.dev/PROJECT/REPO/IMAGE@sha256:HEX'."
  }
}
variable "web_image" {
  type        = string
  description = "The immutable container image reference (must include sha256 digest) for the croviq-web Cloud Run service."

  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.web_image))
    error_message = "The web_image variable must specify an immutable image digest format: e.g., 'us-central1-docker.pkg.dev/PROJECT/REPO/IMAGE@sha256:HEX'."
  }
}


variable "git_sha" {
  type        = string
  description = "The Git commit SHA associated with the deployed revision."
  default     = ""
}

variable "allowed_emails" {
  type        = string
  description = "The only Identity Platform email allowed to access the demo workspace."
  default     = "demo@croviq.app"
}

variable "firestore_location" {
  type        = string
  description = "The location ID for the Firestore database (e.g. us-central1)."
  default     = "us-central1"
}

variable "memory_bank_id" {
  type        = string
  description = "The identifier for the Google Agent Platform Memory Bank."
  default     = "croviq-channel-memory"
}
