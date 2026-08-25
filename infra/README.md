# Croviq Infrastructure (Terraform)

This directory contains the canonical Terraform configuration for provisioning Croviq's Google Cloud infrastructure.

## Design & Portability

- **No Hardcoded Project IDs**: All configurations are parameterized via variables.
- **Judge & Developer Reproducibility**: Evaluators can deploy a complete Croviq stack into their own Google Cloud project.
- **State**: Backend state is currently configured locally for development. Remote state and Workload Identity Federation are introduced during CI/CD promotion setup.

## Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `project_id` | `string` | *(required)* | Target Google Cloud project ID |
| `region` | `string` | `"us-central1"` | Primary Google Cloud region |
| `environment` | `string` | `"dev"` | Environment tag (`dev`, `staging`, `prod`) |
| `app_domain` | `string` | `"app.croviq.app"` | Application hostname |

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
