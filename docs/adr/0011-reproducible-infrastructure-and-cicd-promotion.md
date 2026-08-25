# 0011: Reproducible Infrastructure and CI/CD Promotion

## Context
Croviq relies on cloud services (Cloud Run, Cloud Storage, Firestore, Vertex AI, Cloud Logging/Trace) that must be consistently reproducible, auditable, and isolated across environments. Hardcoding production-specific identifiers (such as project ID `croviq-506602`) or provisioning resources ad-hoc from application code creates brittle infrastructure, risks configuration drift, and prevents external evaluators (such as hackathon judges) from spinning up clean, isolated deployments in their own Google Cloud projects.

## Decision
1. **Canonical Infrastructure as Code**: Terraform is the single canonical definition of Croviq cloud infrastructure. Application code must never provision or mutate cloud infrastructure resources.
2. **Strict Reusability & Parameterization**: All Terraform modules and root configurations must be fully parameterized via variables (`project_id`, `region`, `environment`, `app_domain`, resource naming prefixes). No production values (including `croviq-506602`) may be hardcoded within reusable Terraform files.
3. **Production Target Baseline**:
   - Production Google Cloud project: `croviq-506602` (specified only via production variable configuration).
   - Primary region: `us-central1`.
   - Production application hostname: `app.croviq.app`.
   - Root domain `croviq.app` remains independent and reserved for marketing/documentation.
4. **CI/CD Promotion & GitHub Actions**:
   - GitHub Actions is the sole promotion mechanism for production deployments.
   - Every merge to `main` runs automated quality gates (formatting, linting, typechecking, tests, terraform validation).
   - Terraform plans are validated in CI; deployments apply infrastructure changes idempotently.
5. **Secure Authentication**: Production GCP deployments from GitHub Actions will use Google Cloud Workload Identity Federation, eliminating long-lived service account JSON keys.
6. **Edge & Cloudflare Decoupling**: Cloudflare edge routing and DNS are managed and deployed independently from Google Cloud infrastructure.
7. **Traceability & Proof of Action**: Every deployed container and infrastructure revision is stamped with its Git commit SHA and emitted in structured logs.
8. **Judge & Developer Portability**: External evaluators and developers must be able to deploy a complete, functional instance of Croviq into their own Google Cloud projects using only documented Terraform variables and setup commands.

## Consequences
- Guarantees 100% reproducible deployments across dev, staging, production, and isolated judge test projects.
- Eliminates security risks associated with stored long-lived service account keys.
- Enforces strict decoupling between infrastructure definitions and application runtime code.
