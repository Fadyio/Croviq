# Croviq Cloudflare DNS Infrastructure (Terraform)

This directory contains the dedicated Terraform configuration for managing Cloudflare authoritative DNS for `croviq.app`.

## Decoupled Architecture

- **Independent Root**: This Terraform root is completely decoupled from the main Google Cloud application infrastructure root (`infra/`).
- **Separate Remote State**: State is stored in the remote GCS bucket (`croviq-506602-croviq-tfstate`) under the dedicated prefix `croviq/cloudflare-dns`.
- **Fault Isolation**: A failure, modification, or credential issue in this Cloudflare root does not block or impact GCP infrastructure planning, deployment, or execution, and vice-versa.

## Authentication & Security

- **Environment-Only Authentication**: Authentication to Cloudflare occurs exclusively via the `CLOUDFLARE_API_TOKEN` environment variable.
- **No Token in Configuration**: Secret tokens are never stored in HCL files, `tfvars`, remote state, Git, or backend configuration.
- **Least Privilege**: The token requires only read/edit permissions for DNS records and read permissions for zone lookups on `croviq.app`.

## Usage

### 1. Configure Remote Backend
```bash
cp backend.hcl.example backend.hcl
# Set bucket = "YOUR_PROJECT_ID-croviq-tfstate" and prefix = "croviq/cloudflare-dns"
```

### 2. Configure Variables (Optional)
```bash
cp terraform.tfvars.example terraform.tfvars
```

### 3. Initialize and Plan
```bash
export CLOUDFLARE_API_TOKEN="your-api-token"

terraform init -backend-config=backend.hcl
terraform validate
terraform plan
```
