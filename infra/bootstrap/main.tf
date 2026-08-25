# Bootstrap Stack for Croviq Terraform Remote State Storage
# Provisions a dedicated, versioned, private, uniform-access GCS bucket for Terraform state.

resource "google_storage_bucket" "tfstate" {
  project                     = var.project_id
  name                        = "${var.project_id}-croviq-tfstate"
  location                    = var.region
  storage_class               = var.storage_class
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  labels = {
    managed_by  = "terraform"
    environment = "bootstrap"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Allow GitHub Actions deployer service account to manage Terraform state objects
resource "google_storage_bucket_iam_member" "deployer_tfstate_user" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:croviq-github-deployer@${var.project_id}.iam.gserviceaccount.com"
}
