output "state_bucket_name" {
  description = "The name of the Google Cloud Storage bucket used for remote state."
  value       = google_storage_bucket.tfstate.name
}

output "state_bucket_url" {
  description = "The GCS URL of the state bucket."
  value       = google_storage_bucket.tfstate.url
}
