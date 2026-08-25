variable "project_id" {
  type        = string
  description = "The Google Cloud project ID."
}

variable "region" {
  type        = string
  description = "The primary Google Cloud region for resources."
  default     = "us-central1"
}

variable "storage_class" {
  type        = string
  description = "The storage class of the state bucket."
  default     = "STANDARD"
}
