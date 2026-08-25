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

---

## Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `cloudflare_zone_name` | `string` | `"croviq.app"` | The Cloudflare zone domain name |
| `certificate_dns_authorization_name` | `string` | `"_acme-challenge.app.croviq.app."` | DNS Resource Record Name for Google Certificate Manager DNS authorization |
| `certificate_dns_authorization_type` | `string` | `"CNAME"` | DNS Resource Record Type for Google Certificate Manager DNS authorization |
| `certificate_dns_authorization_value` | `string` | `"37a12037-33a6-40bc-9905-b7e8d0287946.12.authorize.certificatemanager.goog."` | DNS Resource Record Value for Google Certificate Manager DNS authorization |

## Outputs

| Output | Description |
|---|---|
| `cloudflare_zone_id` | The Cloudflare zone ID resolved from the zone name |
| `cloudflare_zone_name` | The Cloudflare zone name |
| `certificate_dns_authorization_record_id` | The Cloudflare DNS record ID for the certificate authorization record |
| `certificate_dns_authorization_record_hostname` | The FQDN of the certificate authorization record |
