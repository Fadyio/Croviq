provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

provider "cloudflare" {
  # Credentials read automatically from CLOUDFLARE_API_TOKEN environment variable.
}
