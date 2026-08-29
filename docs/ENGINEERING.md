# Engineering Principles & Guidelines

## 1. Core Principles

- **Decoupled components**: Clear separation between frontend workstation UI, deterministic engine/media rendering, and agent reasoning.
- **Single source of truth**: Python Pydantic v2 domain models are canonical; TypeScript contracts are OpenAPI-generated.
- **Idempotent operations**: Safe, repeatable execution across state transitions and external mutations.
- **Structured observability**: Single-line JSON to stdout, ingested automatically by Google Cloud Logging.
- **Least-privilege security**: Private GCS buckets, no client credentials, minimal IAM permissions.
- **Configuration separated from code**: Zero hardcoded environment assumptions or project IDs.
- **One vertical slice at a time**: Test locally in browser, verify logs, commit, push, deploy, and verify.

---

## 2. Mandatory Stop-and-Ask Rule

For every coding-agent task, if any of the following conditions arise, the agent **must stop before acting**:

- A decision that has not been explicitly approved;
- Credentials, secrets, API keys, passwords, OAuth client IDs, OAuth client secrets;
- Creation or modification of an external account/provider;
- A manual action required from the repository owner;
- A new paid service or potentially meaningful cost increase;
- Broader IAM permissions;
- Destructive operations;
- An architectural change;
- Choosing between materially different implementations;
- Assumptions about production configuration;
- Changing product scope;
- Silently replacing an approved Google service/model/framework with another.

The agent must return the structured blocker block:

```text
BLOCKED:
WHY:
DECISION OR ACTION REQUIRED FROM ME:
OPTIONS:
RECOMMENDATION:
```

And wait for explicit human approval.

---

## 3. Production Topology & Single Origin (ADR-0013)

- **Authoritative DNS**: Cloudflare (DNS only; no Workers, Pages, KV, R2, or edge runtime execution).
- **Public Entrypoint**: Single public origin at `https://app.croviq.app` via Google Global External Application Load Balancer with Serverless NEGs.
  - `https://app.croviq.app/*` → `croviq-web` (Cloud Run containerized React/Vite SPA).
  - `https://app.croviq.app/api/*` → `croviq-api` (Cloud Run Python 3.12 / FastAPI backend).
- **Native Routing**: FastAPI natively owns `/api` route prefixes; frontend uses relative `/api/...` calls without cross-origin CORS overhead.
- **Root Domain Redirect**: `https://croviq.app/*` → HTTP 308 permanent redirect to `https://app.croviq.app/*`.
- **Cloud Run Ingress**: Restricted to `internal-and-cloud-load-balancing`. Direct `*.run.app` URLs are blocked.

---

## 4. Observability & Logging Standards

### 4.1 Logging Model
Mental model:
```text
Python structured logger (packages/observability)
  -> Single-line JSON to stdout
  -> Cloud Run runtime
  -> Google Cloud Logging
```

### 4.2 Non-Goals
Do **not** introduce OpenTelemetry infrastructure, Prometheus, a tracing stack, Grafana, or in-app observability dashboards. Standard Cloud Logging is the authoritative logging store.

### 4.3 Canonical Fields
- `timestamp`, `severity`, `service`, `environment`, `event_type`, `request_id`, `user_id`, `route`, `status`, `latency_ms`, `git_sha`, `message`, `error_code`.

### 4.4 AI Call Fields
Every model call (Gemini via GenAI SDK) must log structured telemetry:
- `event_type`: `ai.call.started`, `ai.call.completed`, `ai.call.failed`
- `agent`: `director`, `editor`, `data_scientist`, `packaging`, `qa`
- `model`: actual runtime model identifier (e.g. `gemini-3.7-flash`)
- `run_id`, `job_id`, `request_id`
- `input_tokens`, `output_tokens`, `latency_ms`
- `status`, `error_code`

### 4.5 Security & Redaction
Never log: passwords, ID tokens, Authorization headers, OAuth tokens, API keys, private keys, or signed GCS URLs.

### 4.6 Agent Debugging Procedure
1. Reproduce issue in Chrome browser.
2. Inspect DevTools Network & Console.
3. Locate failing request and capture `x-request-id`.
4. Query Google Cloud Logging by that request ID.
5. Inspect correlated auth/workspace/media logs.
6. Inspect Firestore and GCS state read-only.
7. Determine root cause and report evidence before modifying code.
### 4.7 Canonical Cloud Logging Queries (Logs Explorer)
Use these canonical filter queries in Google Cloud Logs Explorer (Project: `croviq-506602`):

- **All API Logs**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  ```
- **Error & Failure Logs**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  (severity>=ERROR OR jsonPayload.status>=500)
  ```
- **Render Lifecycle Logs**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  (jsonPayload.event_type=~"^render\\." OR jsonPayload.route=~"/renders")
  ```
- **Correlated Request Tracing**:
  ```text
  resource.type="cloud_run_revision"
  resource.labels.service_name="croviq-api"
  jsonPayload.request_id="<REQUEST_ID>"
  ```

### 4.8 AI Observability & Independent Google-Side Proof

Croviq establishes a multi-layered, incontrovertible AI observability architecture to independently prove every model call on Google Cloud:

1. **Authentication Model**:
   - Application Default Credentials (ADC) bound to the Cloud Run API runtime service account identity:
     `croviq-api-runtime@croviq-506602.iam.gserviceaccount.com`
   - Zero API keys used for GenAI/Vertex. Zero fallback to Gemini Developer API or mock clients in production.

2. **Vertex AI / Agent Platform Endpoint**:
   - Service: `aiplatform.googleapis.com`
   - Global Foundation Model resource names: `projects/croviq-506602/locations/global/publishers/google/models/<MODEL_ID>`

3. **Google Cloud Data Access Audit Logging**:
   - Declared in Terraform via `google_project_iam_audit_config.aiplatform_audit` for service `aiplatform.googleapis.com`.
   - Captures `ADMIN_READ`, `DATA_READ`, `DATA_WRITE` without exemption.
   - Emits authoritative audit log entries under `cloudaudit.googleapis.com/data_access`.

4. **Gemini Request/Response BigQuery Logging Management**:
   - **Dataset & Storage**: `croviq-506602.croviq_ai_observability` (Terraform managed in `infra/main.tf` with location `US`).
   - **Table**: `gemini_requests` (time-partitioned by `logging_time`).
   - **IAM Permissions**: `google_bigquery_dataset_iam_member` and `google_project_iam_member` (Terraform managed in `infra/main.tf`).
   - **Publisher Model Configuration**: Configured via idempotent deployment script `scripts/configure_vertex_publisher_logging.py` invoking Vertex AI REST API `setPublisherModelConfig` across active Croviq models (`gemini-3.7-flash`, `gemini-3.5-transcribe-preview`, `gemini-3.1-flash-tts-preview`, `gemini-omni-1.1-flash-preview`).

5. **Safe First-Party Telemetry**:
   - Structured operational events: `ai.request.started`, `ai.request.completed`, `ai.request.failed`.
   - Metadata: `provider="google"`, `backend="vertex_ai"`, `location="global"`, `model`, `operation`, `production_id`, `run_id`, `agent`, `latency_ms`, `input_tokens`, `output_tokens`, `audio_duration_ms`, `status`.

6. **Canonical Logs Explorer Queries**:
   - **All Croviq AI Calls (Audit Log)**:
     ```text
     protoPayload.serviceName="aiplatform.googleapis.com"
     protoPayload.methodName="google.cloud.aiplatform.v1beta1.PredictionService.GenerateContent"
     protoPayload.authenticationInfo.principalEmail="croviq-api-runtime@croviq-506602.iam.gserviceaccount.com"
     ```
   - **Transcription Calls (Gemini 3.5 Transcribe Preview)**:
     ```text
     protoPayload.serviceName="aiplatform.googleapis.com"
     protoPayload.resourceName:"gemini-3.5-transcribe-preview"
     ```
   - **Studio Voice Synthesis Calls (Gemini 3.1 Flash TTS Preview)**:
     ```text
     protoPayload.serviceName="aiplatform.googleapis.com"
     protoPayload.resourceName:"gemini-3.1-flash-tts-preview"
     ```
   - **Reasoning Calls (Gemini 3.7 Flash: Leo, Maya, Alex, Nina, Iris)**:
     ```text
     protoPayload.serviceName="aiplatform.googleapis.com"
     protoPayload.resourceName:"gemini-3.7-flash"
     ```

7. **Safe BigQuery Metadata Inspection Query (Privacy-Preserving Default)**:
   ```sql
   SELECT
     logging_time,
     model,
     api_method,
     metadata
   FROM `croviq-506602.croviq_ai_observability.gemini_requests`
   ORDER BY logging_time DESC
   LIMIT 50;
   ```

8. **Privileged Forensic Inspection Query (Restricted Access Only)**:
   ```sql
   -- Privileged forensic investigation only: exposes prompt, reasoning, and response payloads.
   SELECT
     logging_time,
     model,
     api_method,
     metadata,
     request_payload,
     response_payload
   FROM `croviq-506602.croviq_ai_observability.gemini_requests`
   WHERE logging_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
   ORDER BY logging_time DESC
   LIMIT 10;
   ```

9. **Privacy Warning & Compliance**:
   - Deep request-response payloads contain prompts, raw transcripts, and model reasoning text. The default judge/inspection queries select only operational metadata (`logging_time`, `model`, `api_method`, `metadata`). Full payload access is strictly restricted to authorized forensic personnel.
   - First-party telemetry logs strictly exclude authorization tokens, bearer headers, API keys, and signed GCS URLs.

10. **End-to-End Proof Verification Procedure**:
   - Step A: Initiate operation in Croviq (e.g. `POST /api/productions/{id}/transcribe` or `POST /api/productions/{id}/studio-voice`).
   - Step B: Check Croviq structured operational log for `ai.request.started` and `ai.request.completed` with `request_id`.
   - Step C: Check Google Cloud Logging `cloudaudit.googleapis.com/data_access` for matching timestamp and `protoPayload.resourceName`.
   - Step D: Query BigQuery table `croviq_ai_observability.gemini_requests` using the safe metadata query.

## 5. Testing Seams

- **Seam 1 — Judge / Browser Seam (Highest Priority)**:
  Real Chrome E2E verification: sign in, select sample channel, upload raw video, observe live Maya/Leo interaction on timeline & transcript, verify natural cuts, verify master render and one Short.
- **Seam 2 — Agent Contract Seam**:
  Verify structured Gemini outputs, schema validation, batch review logic, bounded correction loops, and rejection of malformed agent responses.
- **Seam 3 — Media & EDL Seam**:
  Verify frame/audio-safe cuts, duration math, natural speech transitions, synchronized captions, vertical Short extraction (9:16 aspect ratio), and playable output files.
- **Seam 4 — Infrastructure & Production Seam**:
  Verify Cloud Run deployment, GCS private bucket isolation, Firestore persistence, Memory Bank access, and structured log ingestion with exact model IDs.

---

## 6. Definition of Done & Promotion Workflow

```text
LOCAL TEST IN BROWSER
→ INSPECT STRUCTURED LOGS
→ COMMIT
→ PUSH MAIN
→ GITHUB ACTIONS CI
→ TERRAFORM / DEPLOY
→ CLOUD LOGGING VERIFY
→ PRODUCTION BROWSER VERIFY
```
