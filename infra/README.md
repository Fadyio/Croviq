# Croviq Infrastructure (Terraform)

This directory contains the canonical Terraform configurations for provisioning Croviq's infrastructure across Google Cloud and Cloudflare authoritative DNS.

## Decoupled Architecture & Ownership

To ensure complete fault isolation, infrastructure is strictly partitioned into independent Terraform roots with separate remote state files and workflows:

- **`infra/` (Google Cloud Application Infrastructure)**:
  - **Ownership**: All Google Cloud runtime resources, APIs, Artifact Registry, IAM service accounts, WIF pool/provider, Identity Platform base configuration, Firestore database, and Cloud Run API.
  - **Remote State Prefix**: `croviq/main` in bucket `croviq-506602-croviq-tfstate`.
  - **Zero Cloudflare Coupling**: Executes `terraform init`, `validate`, and `plan`/`apply` with standard GCP credentials only, completely independent of Cloudflare API tokens or account IDs.

- **`infra/cloudflare-dns/` (Cloudflare Authoritative DNS)**:
  - **Ownership**: Cloudflare authoritative DNS zone lookups and DNS record management for `croviq.app`.
  - **Remote State Prefix**: `croviq/cloudflare-dns` in bucket `croviq-506602-croviq-tfstate`.
  - **Environment-Only Authentication**: Authenticates exclusively via `CLOUDFLARE_API_TOKEN` environment variable.
  - **Zero Application Coupling**: Managed independently; does not provision or depend on Google Cloud compute/storage resources.

- **`infra/bootstrap/` (Remote State Storage Bootstrap)**:
  - **Ownership**: Dedicated bootstrap stack provisioning the versioned, private GCS bucket (`${project_id}-croviq-tfstate`) and IAM permissions for remote state storage.
  - **Remote State Prefix**: `croviq/bootstrap` (or local bootstrap before migration).

> **Fault Isolation Guarantee**: A failure, modification, or credential error in the Cloudflare Terraform root never blocks GCP application infrastructure planning or deployment, and vice-versa.

---

## Design & Portability

- **No Hardcoded Project IDs**: All configurations are parameterized via variables.
- **Judge & Developer Reproducibility**: Evaluators can deploy a complete Croviq stack into their own Google Cloud project.
- **Remote State Management**: Terraform state is securely stored in a private, versioned Google Cloud Storage bucket with uniform bucket-level access and deletion protection.
- **Keyless Authentication**: Workload Identity Federation (WIF) eliminates long-lived service account JSON keys for CI/CD.
- **Secure Credentials**: Cloudflare API token (`CLOUDFLARE_API_TOKEN`) is provided exclusively via environment variable / CI secret. It is never stored in Terraform variables, tfvars, backend configuration, Git, or Terraform state.

---

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

### 3. Initialize & Deploy Main GCP Infrastructure
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

### 4. Initialize & Deploy Cloudflare DNS Infrastructure
```bash
cd cloudflare-dns

# Configure Cloudflare DNS remote backend
cp backend.hcl.example backend.hcl
# Edit backend.hcl with bucket = "YOUR_PROJECT_ID-croviq-tfstate" and prefix = "croviq/cloudflare-dns"

# Export Cloudflare API Token
export CLOUDFLARE_API_TOKEN="your-cloudflare-api-token"

# Initialize with remote backend
terraform init -backend-config=backend.hcl

# Plan and apply
terraform plan
terraform apply
```

---

## Directory Structure

- `infra/`: Main GCP infrastructure stack (Google Cloud APIs, Artifact Registry, IAM service accounts, WIF pool/provider, Identity Platform base configuration, Firestore in Native mode).
  - `backend.hcl.example`: Template for main remote state backend configuration (`croviq/main`).
  - `terraform.tfvars.example`: Example variable definitions for GCP.
- `infra/cloudflare-dns/`: Cloudflare DNS stack (authoritative DNS for `croviq.app`).
  - `backend.hcl.example`: Template for Cloudflare DNS remote state backend configuration (`croviq/cloudflare-dns`).
  - `terraform.tfvars.example`: Example variable definitions for Cloudflare.
- `infra/bootstrap/`: Dedicated bootstrap stack to provision and manage the remote GCS state bucket.
  - `backend.hcl.example`: Template for bootstrap remote state backend configuration.
  - `terraform.tfvars.example`: Example variable definitions.

---

## Variables (Main GCP Stack)

| Variable | Type | Default | Description |
|---|---|---|---|
| `project_id` | `string` | *(required)* | Target Google Cloud project ID |
| `region` | `string` | `"us-central1"` | Primary Google Cloud region |
| `environment` | `string` | `"dev"` | Environment tag (`dev`, `staging`, `prod`) |
| `app_domain` | `string` | `"app.croviq.app"` | Application hostname |
| `artifact_registry_repository_id` | `string` | `"croviq-api"` | Artifact Registry repository ID for API container images |
| `artifact_registry_web_repository_id` | `string` | `"croviq-web"` | Artifact Registry repository ID for web container images |
| `web_runtime_service_account_id` | `string` | `"croviq-web-runtime"` | Service account ID for the Cloud Run web runtime |
| `api_runtime_service_account_id` | `string` | `"croviq-api-runtime"` | Service account ID for the Cloud Run API runtime |
| `github_deployer_service_account_id` | `string` | `"croviq-github-deployer"` | Service account ID for GitHub Actions deployment |
| `workload_identity_pool_id` | `string` | `"github-actions-pool"` | Workload Identity Pool ID for GitHub Actions |
| `workload_identity_pool_provider_id` | `string` | `"github-actions-provider"` | Workload Identity Provider ID for GitHub Actions |
| `github_repository_owner` | `string` | `"Fadyio"` | GitHub repository owner (org/user) |
| `github_repository_name` | `string` | `"Croviq"` | GitHub repository name |
| `api_image` | `string` | *(required)* | Immutable container image reference with `@sha256:` digest for Cloud Run |
| `web_image` | `string` | *(required)* | Immutable container image reference with `@sha256:` digest for Cloud Run Web |
| `git_sha` | `string` | `""` | Git commit SHA deployed to Cloud Run |
| `firestore_location` | `string` | `"us-central1"` | Location ID for the default Firestore database |

## Outputs (Main GCP Stack)

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
| `web_cloud_run_service_name` | Name of the Cloud Run Web service |
| `web_cloud_run_url` | Live HTTPS URL of the deployed Cloud Run Web service |
| `web_cloud_run_latest_revision` | Latest created revision identifier of the Cloud Run Web service |
| `web_artifact_registry_repository` | Fully qualified Artifact Registry web repository resource name |
| `web_runtime_service_account_email` | Email of the Cloud Run Web runtime service account |
| `load_balancer_ip` | Static global external IPv4 address for the Application Load Balancer |
| `dns_authorization_record_name` | DNS Resource Record Name for Certificate Manager DNS authorization |
| `dns_authorization_record_type` | DNS Resource Record Type for Certificate Manager DNS authorization |
| `dns_authorization_record_value` | DNS Resource Record Value for Certificate Manager DNS authorization |
| `web_neg_name` | Name of the Serverless NEG for croviq-web |
| `api_neg_name` | Name of the Serverless NEG for croviq-api |
| `web_backend_service_name` | Name of the backend service for croviq-web |
| `api_backend_service_name` | Name of the backend service for croviq-api |
| `url_map_name` | Name of the URL map for single-origin routing |
| `certificate_manager_certificate_name` | Name of the Google Certificate Manager managed certificate |
| `certificate_map_name` | Name of the Google Certificate Manager certificate map |
