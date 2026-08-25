# Croviq Infrastructure (Terraform)

This directory contains the canonical Terraform configuration for provisioning Croviq's Google Cloud infrastructure and remote state backend.

## Design & Portability

- **No Hardcoded Project IDs**: All configurations are parameterized via variables.
- **Judge & Developer Reproducibility**: Evaluators can deploy a complete Croviq stack into their own Google Cloud project.
- **Remote State Management**: Terraform state is securely stored in a private, versioned Google Cloud Storage bucket with uniform bucket-level access and deletion protection.
- **Decoupled Architecture**: Infrastructure foundation (APIs, Artifact Registry, IAM, Workload Identity Federation, Global External Application Load Balancer with Serverless NEGs) is managed cleanly via Terraform. Both `croviq-web` (React/Vite) and `croviq-api` (Python/FastAPI) are deployed to Cloud Run behind a single HTTPS origin (`https://app.croviq.app`) via path-based routing (`/*` and `/api/*`).
- **DNS Only on Cloudflare**: Cloudflare provides authoritative DNS only. All runtime execution, TLS certificates, load balancing, and application services run entirely on Google Cloud (ADR-0013).
- **Keyless Authentication**: Workload Identity Federation (WIF) eliminates long-lived service account JSON keys for CI/CD.

## Reproducible Fresh-Project Deployment

Follow this exact sequence to deploy Croviq infrastructure into a fresh Google Cloud project:

### 1. Authenticate to your own Google Cloud project
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

### 2. Bootstrap the Remote State Bucket
```bash
cd infra/bootstrap

# Copy example variables and configure your project ID
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars and set project_id = "YOUR_PROJECT_ID"

# Initialize and create the GCS state bucket (${project_id}-croviq-tfstate)
terraform init
terraform plan
terraform apply

# Migrate bootstrap stack state to the newly created GCS bucket
cp backend.hcl.example backend.hcl
# Edit backend.hcl with bucket = "YOUR_PROJECT_ID-croviq-tfstate"
terraform init -migrate-state -backend-config=backend.hcl
```

### 3. Initialize & Deploy Main Infrastructure
```bash
cd ../

# Configure main remote backend
cp backend.hcl.example backend.hcl
# Edit backend.hcl with bucket = "YOUR_PROJECT_ID-croviq-tfstate" and prefix = "croviq/main"

# Configure main variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with project_id = "YOUR_PROJECT_ID"

# Initialize with remote backend
terraform init -backend-config=backend.hcl

# Plan and apply
terraform plan
terraform apply
```

---

## Directory Structure

- `infra/`: Main infrastructure stack (Google Cloud APIs, Artifact Registry, IAM service accounts, WIF pool/provider, Identity Platform base configuration, Firestore in Native mode).
  - `backend.hcl.example`: Template for main remote state backend configuration.
  - `terraform.tfvars.example`: Example variable definitions.
- `infra/bootstrap/`: Dedicated bootstrap stack to provision and manage the remote GCS state bucket.
  - `backend.hcl.example`: Template for bootstrap remote state backend configuration.
  - `terraform.tfvars.example`: Example variable definitions.

---

## Variables (Main Stack)

| Variable | Type | Default | Description |
|---|---|---|---|
| `project_id` | `string` | *(required)* | Target Google Cloud project ID |
| `region` | `string` | `"us-central1"` | Primary Google Cloud region |
| `environment` | `string` | `"dev"` | Environment tag (`dev`, `staging`, `prod`) |
| `app_domain` | `string` | `"app.croviq.app"` | Application hostname |
| `artifact_registry_repository_id` | `string` | `"croviq-api"` | Artifact Registry repository ID for API container images |
| `api_runtime_service_account_id` | `string` | `"croviq-api-runtime"` | Service account ID for the Cloud Run API runtime |
| `github_deployer_service_account_id` | `string` | `"croviq-github-deployer"` | Service account ID for GitHub Actions deployment |
| `workload_identity_pool_id` | `string` | `"github-actions-pool"` | Workload Identity Pool ID for GitHub Actions |
| `workload_identity_pool_provider_id` | `string` | `"github-actions-provider"` | Workload Identity Provider ID for GitHub Actions |
| `github_repository_owner` | `string` | `"Fadyio"` | GitHub repository owner (org/user) |
| `github_repository_name` | `string` | `"Croviq"` | GitHub repository name |
| `api_image` | `string` | *(required)* | Immutable container image reference with `@sha256:` digest for Cloud Run |
| `git_sha` | `string` | `""` | Git commit SHA deployed to Cloud Run |
| `firestore_location` | `string` | `"us-central1"` | Location ID for the default Firestore database |

## Outputs (Main Stack)

| Output | Description |
|---|---|
| `artifact_registry_repository` | Fully qualified Artifact Registry repository resource name |
| `artifact_registry_location` | Artifact Registry repository location |
| `runtime_service_account_email` | Email of the Cloud Run API runtime service account |
| `deploy_service_account_email` | Email of the GitHub Actions deployment service account |
| `workload_identity_provider` | Full identifier of the Workload Identity Provider for GitHub Actions OIDC |
| `cloud_run_service_name` | Name of the Cloud Run API service |
| `cloud_run_url` | Live HTTPS URL of the deployed Cloud Run API service |
| `cloud_run_latest_revision` | Latest created revision identifier of the Cloud Run API service |
| `firestore_database_name` | Database ID of the default Firestore database instance |
| `firestore_database_location` | Location ID of the default Firestore database instance |
| `identity_platform_config_name` | Resource name of the Identity Platform configuration |
