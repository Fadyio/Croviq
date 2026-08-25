# Croviq Infrastructure Root Module
# Canonical definition of Google Cloud resources for Croviq foundation.

# -----------------------------------------------------------------------------
# 1. Required Google Cloud APIs
# -----------------------------------------------------------------------------
locals {
  required_services = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "serviceusage.googleapis.com",
  ]
}

resource "google_project_service" "required_services" {
  for_each           = toset(local.required_services)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# 2. Artifact Registry
# -----------------------------------------------------------------------------
resource "google_artifact_registry_repository" "api_repo" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repository_id
  description   = "Docker repository for Croviq API container images"
  format        = "DOCKER"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 3. Service Accounts
# -----------------------------------------------------------------------------

# Runtime Service Account for Cloud Run API
resource "google_service_account" "api_runtime" {
  project      = var.project_id
  account_id   = var.api_runtime_service_account_id
  display_name = "Croviq API Runtime Service Account"
  description  = "Dedicated identity for Croviq API Cloud Run runtime"

  depends_on = [google_project_service.required_services]
}

# Deployment Service Account for GitHub Actions CI/CD
resource "google_service_account" "github_deployer" {
  project      = var.project_id
  account_id   = var.github_deployer_service_account_id
  display_name = "Croviq GitHub Actions Deployer"
  description  = "Dedicated identity used by GitHub Actions via Workload Identity Federation"

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 4. Least-Privilege IAM Bindings for Deployment Service Account
# -----------------------------------------------------------------------------

# Allow deployment service account to push/pull container images
resource "google_artifact_registry_repository_iam_member" "deployer_ar_writer" {
  project    = var.project_id
  location   = google_artifact_registry_repository.api_repo.location
  repository = google_artifact_registry_repository.api_repo.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to administer Cloud Run services
resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to act as runtime service account on Cloud Run
resource "google_service_account_iam_member" "deployer_sa_user" {
  service_account_id = google_service_account.api_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deployer.email}"
}


# -----------------------------------------------------------------------------
# 5. Workload Identity Federation (GitHub Actions OIDC)
# -----------------------------------------------------------------------------

# Workload Identity Pool for GitHub Actions
resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = var.project_id
  workload_identity_pool_id = var.workload_identity_pool_id
  display_name              = "GitHub Actions Pool"
  description               = "Workload Identity Pool for GitHub Actions workflows"

  depends_on = [google_project_service.required_services]
}

# GitHub OIDC Provider with repository restriction
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = var.workload_identity_pool_provider_id
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC Provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  attribute_condition = "assertion.repository == \"${var.github_repository_owner}/${var.github_repository_name}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Bind deployment service account to GitHub repository via WIF
resource "google_service_account_iam_member" "github_wif_user" {
  service_account_id = google_service_account.github_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repository_owner}/${var.github_repository_name}"
}

# -----------------------------------------------------------------------------
# 6. Cloud Run API Service
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "api" {
  project  = var.project_id
  name     = "croviq-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api_runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = var.api_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "CROVIQ_ENV"
        value = "production"
      }

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }

      env {
        name  = "GIT_SHA"
        value = var.git_sha
      }

      env {
        name  = "PORT"
        value = "8080"
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 0
        period_seconds        = 5
        failure_threshold     = 3
        timeout_seconds       = 2
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds    = 15
        failure_threshold = 3
        timeout_seconds   = 2
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.required_services,
    google_artifact_registry_repository.api_repo,
    google_service_account.api_runtime
  ]
}

# Public invoker IAM member for Cloud Run API
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
