# Croviq

Production hostname:
app.croviq.app

Infrastructure:
Terraform

Production GCP project:
croviq-506602

Primary region:
us-central1

> **Portability Note**: Reusable Terraform configurations in `infra/` accept any standard Google Cloud `project_id` via variables, allowing judges and developers to deploy isolated Croviq environments into their own GCP projects.

## Repository Structure

```
Croviq/
├── apps/
├── packages/
├── infra/
├── scripts/
├── docs/
├── .gitignore
└── README.md
```

## Documentation

- [Engineering Principles](docs/ENGINEERING.md)
