# Croviq Infrastructure (Terraform)

This directory contains the canonical Terraform configuration for provisioning Croviq's Google Cloud infrastructure.

## Design & Portability

- **No Hardcoded Project IDs**: All configurations are parameterized via variables.
- **Judge & Developer Reproducibility**: Evaluators can deploy a complete Croviq stack into their own Google Cloud project.
- **Decoupled Architecture**: Infrastructure foundation (APIs, Artifact Registry, IAM, Workload Identity Federation) is managed without deploying placeholder images. Cloud Run services are deployed using immutable container image digests.
- **Keyless Authentication**: Workload Identity Federation (WIF) eliminates long-lived service account JSON keys for CI/CD.

## Variables

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

## Outputs

| Output | Description |
|---|---|
| `artifact_registry_repository` | Fully qualified Artifact Registry repository resource name |
| `artifact_registry_location` | Artifact Registry repository location |
| `runtime_service_account_email` | Email of the Cloud Run API runtime service account |
| `deploy_service_account_email` | Email of the GitHub Actions deployment service account |
| `workload_identity_provider` | Full identifier of the Workload Identity Provider for GitHub Actions OIDC |

## Quickstart (Local Validation)

1. Copy the example variables file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```
2. Edit `terraform.tfvars` with your Google Cloud project ID.
3. Initialize and validate Terraform:
   ```bash
   terraform init
   terraform validate
   ```
4. Format check:
   ```bash
   terraform fmt -check -recursive
   ```
