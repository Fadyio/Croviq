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
