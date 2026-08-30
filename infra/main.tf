# Croviq Infrastructure Root Module
# Canonical definition of Google Cloud resources for Croviq foundation.

# -----------------------------------------------------------------------------
# 1. Required Google Cloud APIs
# -----------------------------------------------------------------------------
locals {
  required_services = [
    "cloudresourcemanager.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
    "serviceusage.googleapis.com",
    "identitytoolkit.googleapis.com",
    "firestore.googleapis.com",
    "compute.googleapis.com",
    "certificatemanager.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudkms.googleapis.com",
    "youtube.googleapis.com",
    "youtubeanalytics.googleapis.com",
    "bigquery.googleapis.com",
    "logging.googleapis.com",
  ]
}

# -----------------------------------------------------------------------------
# 1.1 Project Data Source
# -----------------------------------------------------------------------------
data "google_project" "current" {
  project_id = var.project_id
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
resource "google_artifact_registry_repository" "web_repo" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_web_repository_id
  description   = "Docker repository for Croviq Web container images"
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
# Runtime Service Account for Cloud Run Web
resource "google_service_account" "web_runtime" {
  project      = var.project_id
  account_id   = var.web_runtime_service_account_id
  display_name = "Croviq Web Runtime Service Account"
  description  = "Dedicated identity for Croviq Web Cloud Run runtime"

  depends_on = [google_project_service.required_services]
}


# Dedicated Service Account for Cloud Scheduler Invoker
resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = var.scheduler_service_account_id
  display_name = "Croviq Cloud Scheduler Service Account"
  description  = "Dedicated identity used by Cloud Scheduler for invoking internal API endpoints"

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

# Allow deployment service account to administer and push/pull container images
resource "google_artifact_registry_repository_iam_member" "deployer_ar_writer" {
  project    = var.project_id
  location   = google_artifact_registry_repository.api_repo.location
  repository = google_artifact_registry_repository.api_repo.name
  role       = "roles/artifactregistry.admin"
  member     = "serviceAccount:${google_service_account.github_deployer.email}"
}
# Allow deployment service account to administer and push/pull web container images
resource "google_artifact_registry_repository_iam_member" "deployer_web_ar_writer" {
  project    = var.project_id
  location   = google_artifact_registry_repository.web_repo.location
  repository = google_artifact_registry_repository.web_repo.name
  role       = "roles/artifactregistry.admin"
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
# Allow deployment service account to act as web runtime service account on Cloud Run
resource "google_service_account_iam_member" "deployer_web_sa_user" {
  service_account_id = google_service_account.web_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deployer.email}"
}
# Allow deployment service account to act as scheduler service account when creating the Cloud Scheduler job
resource "google_service_account_iam_member" "deployer_scheduler_sa_user" {
  service_account_id = google_service_account.scheduler.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deployer.email}"
}


# Allow deployment service account to inspect service usage / enabled APIs for Terraform state refresh
resource "google_project_iam_member" "deployer_serviceusage_viewer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageViewer"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to consume Google Cloud services for Terraform state refresh and provisioning
resource "google_project_iam_member" "deployer_serviceusage_consumer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to inspect service accounts for Terraform state refresh
resource "google_project_iam_member" "deployer_iam_viewer" {
  project = var.project_id
  role    = "roles/iam.serviceAccountViewer"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to inspect WIF pools for Terraform state refresh
resource "google_project_iam_member" "deployer_wif_viewer" {
  project = var.project_id
  role    = "roles/iam.workloadIdentityPoolViewer"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to review IAM policies for Terraform state refresh
resource "google_project_iam_member" "deployer_security_reviewer" {
  project = var.project_id
  role    = "roles/iam.securityReviewer"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to administer Identity Platform configuration
resource "google_project_iam_member" "deployer_identity_admin" {
  project = var.project_id
  role    = "roles/identityplatform.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to administer Firestore database
resource "google_project_iam_member" "deployer_datastore_owner" {
  project = var.project_id
  role    = "roles/datastore.owner"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}
# Allow deployment service account to administer Compute Engine / Load Balancer resources
resource "google_project_iam_member" "deployer_compute_admin" {
  project = var.project_id
  role    = "roles/compute.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to administer Certificate Manager resources
resource "google_project_iam_member" "deployer_cert_manager_owner" {
  project = var.project_id
  role    = "roles/certificatemanager.owner"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to provision/update Agent Platform Memory Bank (least privilege)
resource "google_project_iam_member" "deployer_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to administer GCS storage buckets for Terraform
resource "google_project_iam_member" "deployer_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow the deployment service account to create Secret Manager metadata and
# maintain the secret-level runtime IAM policy. Secret payloads are never
# managed by Terraform.
resource "google_project_iam_member" "deployer_secretmanager_admin" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to administer Cloud KMS key rings and crypto keys for Terraform
resource "google_project_iam_member" "deployer_kms_admin" {
  project = var.project_id
  role    = "roles/cloudkms.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to administer Cloud Scheduler jobs for Terraform
resource "google_project_iam_member" "deployer_scheduler_admin" {
  project = var.project_id
  role    = "roles/cloudscheduler.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# Allow deployment service account to administer service accounts for Terraform
resource "google_project_iam_member" "deployer_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

# YouTube OAuth application client secret metadata only. The owner creates secret versions outside Terraform.
resource "google_secret_manager_secret" "youtube_oauth_client_secret" {
  project   = var.project_id
  secret_id = "youtube-oauth-client-secret"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  depends_on = [google_project_service.required_services]
}

resource "google_secret_manager_secret_iam_member" "api_runtime_youtube_oauth_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.youtube_oauth_client_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api_runtime.email}"
}

# -----------------------------------------------------------------------------
# 4b. Cloud KMS: KeyRing & CryptoKey for YouTube OAuth Token Envelope Encryption
# -----------------------------------------------------------------------------
resource "google_kms_key_ring" "croviq_keyring" {
  project  = var.project_id
  name     = "croviq-keyring"
  location = var.region

  depends_on = [google_project_service.required_services]
}

resource "google_kms_crypto_key" "youtube_oauth_kek" {
  name            = "youtube-oauth-kek"
  key_ring        = google_kms_key_ring.croviq_keyring.id
  purpose         = "ENCRYPT_DECRYPT"
  rotation_period = "7776000s" # 90-day automatic rotation

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "api_runtime_kms_encrypter_decrypter" {
  crypto_key_id = google_kms_crypto_key.youtube_oauth_kek.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.api_runtime.email}"
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
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

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
          cpu    = "2"
          memory = "2Gi"
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
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "CROVIQ_ALLOWED_EMAILS"
        value = var.allowed_emails
      }

      env {
        name  = "MEMORY_BANK_LOCATION"
        value = var.region
      }

      env {
        name  = "MEMORY_BANK_ID"
        value = var.memory_bank_id
      }

      env {
        name  = "MEMORY_STORE_PROVIDER"
        value = "google"
      }

      env {
        name  = "MEDIA_BUCKET_NAME"
        value = google_storage_bucket.media_raw.name
      }

      env {
        name  = "MEDIA_STORAGE_PROVIDER"
        value = "google"
      }

      env {
        name  = "GENAI_BACKEND_PROVIDER"
        value = "google"
      }

      env {
        name  = "GEMINI_MODEL_ID"
        value = "gemini-3.7-flash"
      }
      env {
        name  = "VERTEXAI_LOCATION"
        value = "global"
      }

      env {
        name  = "SPEECH_SERVICE_PROVIDER"
        value = "google"
      }
      env {
        name  = "GEMINI_TRANSCRIPTION_MODEL"
        value = "gemini-3.5-transcribe-preview"
      }

      env {
        name  = "SIGNED_URL_EXPIRY_SECONDS"
        value = "1800"
      }

      env {
        name  = "MAX_UPLOAD_SIZE_BYTES"
        value = "1073741824"
      }

      env {
        name  = "CLOUD_RUN_SERVICE_URL"
        value = var.cloud_run_service_url
      }

      env {
        name = "GOOGLE_OAUTH_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.youtube_oauth_client_secret.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 8080
        }
        initial_delay_seconds = 0
        period_seconds        = 5
        failure_threshold     = 10
        timeout_seconds       = 4
      }

      liveness_probe {
        http_get {
          path = "/api/health"
          port = 8080
        }
        period_seconds    = 15
        failure_threshold = 3
        timeout_seconds   = 5
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
    google_service_account.api_runtime,
    google_secret_manager_secret.youtube_oauth_client_secret,
    google_secret_manager_secret_iam_member.api_runtime_youtube_oauth_secret_accessor,
  ]
  lifecycle {
    ignore_changes = [
      scaling,
    ]
  }
}

# Public invoker IAM member for Cloud Run API
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Dedicated Cloud Scheduler invoker IAM member for Cloud Run API
resource "google_cloud_run_v2_service_iam_member" "scheduler_api_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# -----------------------------------------------------------------------------
# 6b. Cloud Scheduler: Hourly Background Research Tick
# -----------------------------------------------------------------------------
resource "google_cloud_scheduler_job" "research_tick" {
  project          = var.project_id
  name             = "croviq-research-tick"
  description      = "Hourly background research tick for Alex Data Scientist agent"
  schedule         = "0 * * * *"
  time_zone        = "Etc/UTC"
  region           = var.region
  attempt_deadline = "320s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.api.uri}/api/channels/research/tick"

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloud_run_v2_service.api.uri
    }
  }

  depends_on = [
    google_project_service.required_services,
    google_cloud_run_v2_service_iam_member.scheduler_api_invoker,
  ]
}

# -----------------------------------------------------------------------------
# 7. Least-Privilege IAM Bindings for API Runtime Service Account
# -----------------------------------------------------------------------------

# Allow API runtime service account to access Firestore documents (least privilege)
resource "google_project_iam_member" "api_runtime_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api_runtime.email}"
}

# Allow API runtime service account to access Agent Platform Memory Bank (least privilege)
resource "google_project_iam_member" "api_runtime_aiplatform_memory_user" {
  project = var.project_id
  role    = "roles/aiplatform.memoryUser"
  member  = "serviceAccount:${google_service_account.api_runtime.email}"
}

# Allow API runtime service account to sign V4 GCS upload URLs via IAM Credentials API (least privilege on itself)
resource "google_service_account_iam_member" "api_runtime_token_creator" {
  service_account_id = google_service_account.api_runtime.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.api_runtime.email}"
}

# Allow API runtime service account to invoke Vertex AI Foundation Models (least privilege)
resource "google_project_iam_member" "api_runtime_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.api_runtime.email}"
}

# -----------------------------------------------------------------------------
# 7a. Private Media Storage Bucket & Bucket-Level IAM
# -----------------------------------------------------------------------------

resource "google_storage_bucket" "media_raw" {
  project                     = var.project_id
  name                        = "${var.project_id}-croviq-media-raw"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  cors {
    origin          = ["https://${var.app_domain}", "http://localhost:5173", "http://127.0.0.1:5173"]
    method          = ["GET", "PUT", "OPTIONS", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  depends_on = [google_project_service.required_services]
}

# Allow API runtime service account to manage objects in the media bucket
resource "google_storage_bucket_iam_member" "api_runtime_object_user" {
  bucket = google_storage_bucket.media_raw.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.api_runtime.email}"
}

# -----------------------------------------------------------------------------
# 8. Identity Platform Base Configuration
# -----------------------------------------------------------------------------

# Project-level Identity Platform base configuration
resource "google_identity_platform_config" "default" {
  project                    = var.project_id
  autodelete_anonymous_users = false

  authorized_domains = [
    "localhost",
    "127.0.0.1",
    var.app_domain,
    var.root_domain,
    "${var.project_id}.firebaseapp.com",
    "${var.project_id}.web.app",
  ]

  client {
    permissions {
      disabled_user_signup = true
    }
  }

  sign_in {
    email {
      enabled           = true
      password_required = true
    }

    anonymous {
      enabled = false
    }

    phone_number {
      enabled = false
    }
  }

  monitoring {
    request_logging {
      enabled = true
    }
  }

  multi_tenant {
    allow_tenants = false
  }
  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 9. Firestore Database (Native Mode)
# -----------------------------------------------------------------------------

# Default Cloud Firestore database in Native mode
resource "google_firestore_database" "default" {
  project                 = var.project_id
  name                    = "(default)"
  location_id             = var.firestore_location
  type                    = "FIRESTORE_NATIVE"
  delete_protection_state = "DELETE_PROTECTION_ENABLED"
  deletion_policy         = "DELETE"

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 9b. Firestore Composite Indexes
# -----------------------------------------------------------------------------

# Collection Group index for Cloud Scheduler hourly research due tick
resource "google_firestore_index" "channel_intelligence_due_idx" {
  project     = var.project_id
  database    = google_firestore_database.default.name
  collection  = "channel_intelligence"
  query_scope = "COLLECTION_GROUP"

  fields {
    field_path = "enabled"
    order      = "ASCENDING"
  }

  fields {
    field_path = "next_run_at"
    order      = "ASCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "ASCENDING"
  }

  depends_on = [google_firestore_database.default]
}

# Collection index for ranked research findings by channel
resource "google_firestore_index" "research_findings_channel_idx" {
  project     = var.project_id
  database    = google_firestore_database.default.name
  collection  = "research_findings"
  query_scope = "COLLECTION"

  fields {
    field_path = "channel_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "opportunity_score"
    order      = "DESCENDING"
  }

  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.default]
}

# -----------------------------------------------------------------------------
# 10. Cloud Run Web Service
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "web" {
  project             = var.project_id
  name                = "croviq-web"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  deletion_protection = false


  template {
    service_account = google_service_account.web_runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = var.web_image

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
    google_artifact_registry_repository.web_repo,
    google_service_account.web_runtime
  ]

  lifecycle {
    ignore_changes = [
      scaling,
    ]
  }
}

# Public invoker IAM member for Cloud Run Web (traffic authorized via Load Balancer)
resource "google_cloud_run_v2_service_iam_member" "web_public_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.web.location
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# -----------------------------------------------------------------------------
# 11. Static Global External IP Address
# -----------------------------------------------------------------------------

resource "google_compute_global_address" "app_ip" {
  project     = var.project_id
  name        = "croviq-app-ip"
  description = "Static global external IPv4 address for ${var.app_domain} load balancer"
  ip_version  = "IPV4"

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 12. Serverless Network Endpoint Groups (NEGs)
# -----------------------------------------------------------------------------

resource "google_compute_region_network_endpoint_group" "web_neg" {
  project               = var.project_id
  name                  = "croviq-web-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.web.name
  }

  depends_on = [google_project_service.required_services]
}

resource "google_compute_region_network_endpoint_group" "api_neg" {
  project               = var.project_id
  name                  = "croviq-api-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 13. Backend Services
# -----------------------------------------------------------------------------

resource "google_compute_backend_service" "web" {
  project               = var.project_id
  name                  = "croviq-web-backend"
  description           = "Backend service for croviq-web Cloud Run via Serverless NEG"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  enable_cdn            = false

  backend {
    group = google_compute_region_network_endpoint_group.web_neg.id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
  depends_on = [google_project_service.required_services]
}

resource "google_compute_backend_service" "api" {
  project               = var.project_id
  name                  = "croviq-api-backend"
  description           = "Backend service for croviq-api Cloud Run via Serverless NEG"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  enable_cdn            = false

  backend {
    group = google_compute_region_network_endpoint_group.api_neg.id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 14. URL Map (Single-Origin Routing)
# -----------------------------------------------------------------------------

resource "google_compute_url_map" "app" {
  project         = var.project_id
  name            = "croviq-app-url-map"
  description     = "URL Map for ${var.app_domain} routing and ${var.root_domain} permanent redirect"
  default_service = google_compute_backend_service.web.id

  host_rule {
    hosts        = [var.app_domain]
    path_matcher = "croviq-app-routes"
  }

  host_rule {
    hosts        = [var.root_domain]
    path_matcher = "croviq-root-redirect"
  }
  path_matcher {
    name            = "croviq-app-routes"
    default_service = google_compute_backend_service.web.id

    path_rule {
      paths   = ["/api", "/api/*"]
      service = google_compute_backend_service.api.id
    }
  }

  path_matcher {
    name = "croviq-root-redirect"
    default_url_redirect {
      host_redirect          = var.app_domain
      https_redirect         = true
      redirect_response_code = "PERMANENT_REDIRECT"
      strip_query            = false
    }
  }

  test {
    service     = google_compute_backend_service.web.id
    host        = var.app_domain
    path        = "/"
    description = "Root path routes to croviq-web"
  }

  test {
    service     = google_compute_backend_service.web.id
    host        = var.app_domain
    path        = "/dashboard"
    description = "SPA route routes to croviq-web"
  }

  test {
    service     = google_compute_backend_service.api.id
    host        = var.app_domain
    path        = "/api/health"
    description = "/api/* routes to croviq-api"
  }

  test {
    host                            = var.root_domain
    path                            = "/"
    expected_output_url             = "https://${var.app_domain}/"
    expected_redirect_response_code = 308
    description                     = "Root domain root path redirects to app domain with 308"
  }

  test {
    host                            = var.root_domain
    path                            = "/foo?x=1"
    expected_output_url             = "https://${var.app_domain}/foo?x=1"
    expected_redirect_response_code = 308
    description                     = "Root domain subpath and query redirects to app domain with 308"
  }

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 15. Certificate Manager (DNS Authorization and Google-Managed SSL)
# -----------------------------------------------------------------------------

resource "google_certificate_manager_dns_authorization" "app_dns_auth" {
  project     = var.project_id
  name        = "croviq-app-dns-auth"
  location    = "global"
  description = "DNS authorization for ${var.app_domain}"
  domain      = var.app_domain

  depends_on = [google_project_service.required_services]
}

resource "google_certificate_manager_certificate" "app_cert" {
  project     = var.project_id
  name        = "croviq-app-cert"
  location    = "global"
  description = "Google-managed SSL certificate for ${var.app_domain}"
  scope       = "DEFAULT"

  managed {
    domains = [var.app_domain]
    dns_authorizations = [
      google_certificate_manager_dns_authorization.app_dns_auth.id
    ]
  }

  depends_on = [google_project_service.required_services]
}

resource "google_certificate_manager_certificate_map" "app_cert_map" {
  project     = var.project_id
  name        = "croviq-app-cert-map"
  description = "Certificate map for ${var.app_domain}"

  depends_on = [google_project_service.required_services]
}

resource "google_certificate_manager_certificate_map_entry" "app_cert_map_entry" {
  project      = var.project_id
  name         = "croviq-app-cert-map-entry"
  description  = "Certificate map entry for ${var.app_domain}"
  map          = google_certificate_manager_certificate_map.app_cert_map.name
  hostname     = var.app_domain
  certificates = [google_certificate_manager_certificate.app_cert.id]

  depends_on = [google_project_service.required_services]
}

resource "google_certificate_manager_dns_authorization" "root_dns_auth" {
  project     = var.project_id
  name        = "croviq-root-dns-auth"
  location    = "global"
  description = "DNS authorization for ${var.root_domain}"
  domain      = var.root_domain

  depends_on = [google_project_service.required_services]
}

resource "google_certificate_manager_certificate" "root_cert" {
  project     = var.project_id
  name        = "croviq-root-cert"
  location    = "global"
  description = "Google-managed SSL certificate for ${var.root_domain}"
  scope       = "DEFAULT"

  managed {
    domains = [var.root_domain]
    dns_authorizations = [
      google_certificate_manager_dns_authorization.root_dns_auth.id
    ]
  }

  depends_on = [google_project_service.required_services]
}

resource "google_certificate_manager_certificate_map_entry" "root_cert_map_entry" {
  project      = var.project_id
  name         = "croviq-root-cert-map-entry"
  description  = "Certificate map entry for ${var.root_domain}"
  map          = google_certificate_manager_certificate_map.app_cert_map.name
  hostname     = var.root_domain
  certificates = [google_certificate_manager_certificate.root_cert.id]

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 16. HTTPS Frontend (Target HTTPS Proxy & Global Forwarding Rule)
# -----------------------------------------------------------------------------

resource "google_compute_target_https_proxy" "app_https_proxy" {
  project         = var.project_id
  name            = "croviq-app-https-proxy"
  description     = "Target HTTPS proxy for ${var.app_domain}"
  url_map         = google_compute_url_map.app.id
  certificate_map = "//certificatemanager.googleapis.com/${google_certificate_manager_certificate_map.app_cert_map.id}"

  depends_on = [google_project_service.required_services]
}

resource "google_compute_global_forwarding_rule" "app_https_forwarding_rule" {
  project               = var.project_id
  name                  = "croviq-app-https-forwarding-rule"
  description           = "Global HTTPS forwarding rule for ${var.app_domain}"
  target                = google_compute_target_https_proxy.app_https_proxy.id
  port_range            = "443"
  ip_address            = google_compute_global_address.app_ip.address
  load_balancing_scheme = "EXTERNAL_MANAGED"

  depends_on = [google_project_service.required_services]
}

# HTTP to HTTPS redirect
resource "google_compute_url_map" "http_redirect" {
  project     = var.project_id
  name        = "croviq-app-http-redirect"
  description = "HTTP to HTTPS redirect URL map for ${var.app_domain}"

  default_url_redirect {
    https_redirect         = true
    strip_query            = false
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
  }

  depends_on = [google_project_service.required_services]
}

resource "google_compute_target_http_proxy" "http_redirect" {
  project     = var.project_id
  name        = "croviq-app-http-proxy"
  description = "Target HTTP proxy for HTTPS redirection on ${var.app_domain}"
  url_map     = google_compute_url_map.http_redirect.id

  depends_on = [google_project_service.required_services]
}

resource "google_compute_global_forwarding_rule" "app_http_forwarding_rule" {
  project               = var.project_id
  name                  = "croviq-app-http-forwarding-rule"
  description           = "Global HTTP forwarding rule for HTTPS redirection on ${var.app_domain}"
  target                = google_compute_target_http_proxy.http_redirect.id
  port_range            = "80"
  ip_address            = google_compute_global_address.app_ip.address
  load_balancing_scheme = "EXTERNAL_MANAGED"

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 16. Agent Platform / Vertex AI Data Access Audit Logging
# -----------------------------------------------------------------------------

resource "google_project_iam_audit_config" "aiplatform_audit" {
  project = var.project_id
  service = "aiplatform.googleapis.com"

  audit_log_config {
    log_type = "ADMIN_READ"
  }

  audit_log_config {
    log_type = "DATA_READ"
  }

  audit_log_config {
    log_type = "DATA_WRITE"
  }

  depends_on = [google_project_service.required_services]
}

# -----------------------------------------------------------------------------
# 17. AI Observability BigQuery Dataset & Access
# -----------------------------------------------------------------------------

resource "google_bigquery_dataset" "ai_observability" {
  project                    = var.project_id
  dataset_id                 = "croviq_ai_observability"
  friendly_name              = "Croviq AI Observability"
  description                = "Dedicated dataset for Vertex AI / Gemini request and response logs"
  location                   = "US"
  delete_contents_on_destroy = false

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  depends_on = [google_project_service.required_services]
}

# Allow Vertex AI Service Agent to write request/response logs into BigQuery dataset
resource "google_bigquery_dataset_iam_member" "aiplatform_sa_bq_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.ai_observability.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
}

# Allow API Runtime Service Account to read/query request/response logs from BigQuery dataset
resource "google_bigquery_dataset_iam_member" "api_runtime_bq_viewer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.ai_observability.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.api_runtime.email}"
}

resource "google_project_iam_member" "api_runtime_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.api_runtime.email}"
}

