> **HISTORICAL — SUPERSEDED**: This implementation plan records the historical transition of Groq Secret Manager metadata before Croviq migrated to the pure Google GenAI stack (Gemini 3.5 Transcribe Preview). It is preserved for audit and historical decision tracking.

# Groq Secret Manager Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject the Groq API key into the existing Croviq API Cloud Run service without storing its value in source control or Terraform state.

**Architecture:** Terraform enables Secret Manager, creates only the `groq-api-key` secret metadata, grants the deployer project-level Secret Manager administration, grants the runtime service account secret-level accessor access, and maps the secret's latest version to `GROQ_API_KEY` in the existing Cloud Run API service. The existing `Settings` object remains the sole application reader of the environment variable; no application Secret Manager client is added.

**Tech Stack:** Terraform Google provider, Google Secret Manager, Cloud Run v2, Python pytest.

**Spec:** `issue://25`

## Global Constraints

- Secret ID is exactly `groq-api-key`; Cloud Run environment variable is exactly `GROQ_API_KEY`.
- Terraform manages API enablement, secret metadata, deployer IAM, runtime secret IAM, and the Cloud Run reference only.
- Terraform MUST NOT declare `google_secret_manager_secret_version` or any Groq key value.
- The deployer receives `roles/secretmanager.admin` only at project `croviq-506602` scope.
- The API runtime service account receives only `roles/secretmanager.secretAccessor` on `groq-api-key`.
- No Secret Manager client library, plaintext configuration, frontend exposure, Firestore persistence, logs, or CI plaintext environment injection.
- Do not begin Issue #26. Stop after Terraform applies; the owner manually creates the first secret version in Google Cloud Console.

---

### Task 1: Prove and configure bounded Secret Manager infrastructure

**Files:**
- Modify: `apps/api/tests/test_infra_config.py`
- Modify: `infra/main.tf`

**Interfaces:**
- Consumes: existing `google_cloud_run_v2_service.api`, `google_service_account.api_runtime`, `google_service_account.github_deployer`, and `local.required_services`.
- Produces: `google_secret_manager_secret.groq_api_key`, the exact secret-level runtime binding, and `GROQ_API_KEY` Cloud Run `secret_key_ref`.

- [ ] **Step 1: Write the failing infrastructure contract test**

```python
def test_groq_secret_is_metadata_only_and_scoped_to_runtime() -> None:
    content = get_infra_main_content()
    assert '"secretmanager.googleapis.com"' in content
    assert 'resource "google_secret_manager_secret" "groq_api_key"' in content
    assert 'secret_id = "groq-api-key"' in content
    assert 'resource "google_secret_manager_secret_version"' not in content
    assert 'role    = "roles/secretmanager.secretAccessor"' in content
    assert 'secret_id = google_secret_manager_secret.groq_api_key.id' in content
    assert 'name = "GROQ_API_KEY"' in content
    assert 'secret  = google_secret_manager_secret.groq_api_key.secret_id' in content
```

- [ ] **Step 2: Run the focused test and confirm the missing secret configuration fails**

Run: `uv run --project apps/api pytest apps/api/tests/test_infra_config.py::test_groq_secret_is_metadata_only_and_scoped_to_runtime -q`

Expected: FAIL because `infra/main.tf` has no Secret Manager API, secret resource, runtime secret accessor, or Cloud Run secret reference.

- [ ] **Step 3: Add only the approved Terraform resources**

```hcl
resource "google_project_iam_member" "deployer_secretmanager_admin" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_secret_manager_secret" "groq_api_key" {
  project   = var.project_id
  secret_id = "groq-api-key"

  replication { auto {} }
}

resource "google_secret_manager_secret_iam_member" "api_runtime_groq_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.groq_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api_runtime.email}"
}
```

Add `secretmanager.googleapis.com` to `local.required_services`, add the `GROQ_API_KEY` `value_source.secret_key_ref` to the existing API container, and add the Secret Manager resource and binding to the Cloud Run service `depends_on`. Do not add a secret version resource or a plaintext variable.

- [ ] **Step 4: Run the focused test and Terraform validation**

Run: `uv run --project apps/api pytest apps/api/tests/test_infra_config.py -q && terraform -chdir=infra validate`

Expected: PASS; Terraform validates with no secret payload configuration.

### Task 2: Inspect the production Terraform change and apply metadata only

**Files:**
- Modify: `infra/main.tf`

**Interfaces:**
- Consumes: the Task 1 Terraform resources and existing configured GCP project.
- Produces: empty `groq-api-key` resource, scoped IAM bindings, and a Cloud Run secret reference after apply.

- [ ] **Step 1: Create an executable plan**

Run: `terraform -chdir=infra plan -out=tfplan-groq-secret`

Expected: only Secret Manager API enablement, deployer `roles/secretmanager.admin`, `google_secret_manager_secret.groq_api_key`, secret-level runtime `roles/secretmanager.secretAccessor`, and an in-place Cloud Run API secret environment-reference update. Stop if any unrelated resource appears.

- [ ] **Step 2: Apply the reviewed plan**

Run: `terraform -chdir=infra apply tfplan-groq-secret`

Expected: creates no secret version and prints no secret value.

- [ ] **Step 3: Verify secret metadata and IAM scopes through gcloud**

Run: `gcloud secrets describe groq-api-key --project=croviq-506602 --format=json(name)` and inspect the Cloud Run API service configuration for `GROQ_API_KEY` secret reference.

Expected: secret metadata exists; the runtime service account is the only accessor binding created by this work; no secret value is requested or emitted.

- [ ] **Step 4: Stop for owner-managed secret entry**

Do not run production transcription. Ask the owner to add one version to `groq-api-key` through Google Cloud Console, without entering the key in chat or a shell command.

### Task 3: Verify existing Issue #25 implementation without provider credentials

**Files:**
- Test: `packages/media/tests/test_groq_transcription_service.py`
- Test: `apps/api/tests/test_transcription_api.py`
- Test: `apps/api/tests/test_infra_config.py`

**Interfaces:**
- Consumes: existing `GroqTranscriptionService`, `FakeTranscriptionService`, and `POST /api/productions/{production_id}/transcribe`.
- Produces: evidence that the mocked Groq adapter maps canonical transcripts, endpoint authorization/idempotency/error handling remain covered, and configuration cannot expose the secret value.

- [ ] **Step 1: Run isolated no-network provider and API contract tests**

Run: `uv run --project packages/media pytest packages/media/tests/test_groq_transcription_service.py -q` and `uv run --project apps/api pytest apps/api/tests/test_transcription_api.py -q`

Expected: PASS without `GROQ_API_KEY` and without any HTTP call to Groq.

- [ ] **Step 2: Run workspace type checks and full tests**

Run: `pnpm typecheck`, then `uv run --project packages/media pytest packages/media/tests apps/api/tests packages/domain/tests packages/observability/tests -q`, then `pnpm test`.

Expected: all suites PASS. Do not use a real Groq key or execute production transcription.

- [ ] **Step 3: Review, commit, and keep Issue #25 open**

Run the repository code-review workflow, resolve any accepted findings, then commit the approved Issue #25 changes on the current branch. Do not close Issue #25: real owner-recorded video acceptance remains pending.
