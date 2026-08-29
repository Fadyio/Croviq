# Croviq Overnight Autonomous Bug Hunt, Truth Audit, and Repair Ledger

## Convergence Status & Ledger Summary

- **TOTAL BUGS**: 17
- **FIXED**: 17
- **BLOCKED**: 0
- **UNVERIFIED**: 0

**COMMITS**:
- `deddfc8`: fix: overnight audit repairs BUG-001 through BUG-013
- `7fb3aa5`: fix: overnight audit repairs BUG-014 through BUG-017

- **BACKEND TESTS**: PASS (154 domain + 10 observability + 70 media + 96 agents + 219 API = 549 total backend tests passing)
- **PLAYWRIGHT**: PASS (102 E2E test suites passing)
- **TYPECHECK**: PASS (0 TypeScript errors)
- **SECURITY**: PASS (5/5 automated security audit checks passing)

- **LOCAL STATUS**: VERIFIED_LOCAL
- **PRODUCTION STATUS**: NOT RUN

- **REAL YOUTUBE DISCOVERY**: NO (Truthfully labeled as Gemini 3.7 Flash + Google Search Grounding; YouTube Data API `/search` is not invoked for discovery to prevent quota exhaustion and avoid misleading trending claims)
- **RESEARCH SOURCE TRUTH**: PASS (All prompts, models, mock fallbacks, UI summaries, and provenance tables truthfully describe research as grounded web discovery)
- **SOURCE ALLOWLIST ENFORCEMENT**: PASS (Post-model citation URL allowlist validator strictly enforces exact domains and subdomains, rejects lookalikes, invalid URLs, and protects against SSRF with private IP/loopback/cloud metadata filtering)
- **ANALYTICS SEMANTICS**: PASS (View-weighted retention and additive metrics align mathematically with YouTube Analytics API day and period metrics)
- **PRODUCTION FAIL-CLOSED**: PASS (All dependency factories, KMS encryptors, Firestore repositories, and Alex grounded research fail closed in production when credentials/GCP project are missing)

- **EXPLORATORY PASS 1**: NO NEW P0/P1/P2
- **EXPLORATORY PASS 2**: NO NEW P0/P1/P2

- **CONVERGED**: YES

**REMAINING OWNER ACTIONS**:
- Configure live creator Google OAuth Client ID and Secret in GCP Secret Manager for production YouTube channel authorization.
- Grant `youtube.upload` scope authorization on creator YouTube channel for live video publishing.

---

## Data Provenance Table (Audit 4)

| UI Surface / KPI | Path / Component | Domain Service / Route | Provider Implementation | Upstream Source | Provenance Classification | Verification Level |
|---|---|---|---|---|---|---|
| Channel Header / Selector | `AppPage.tsx` | `/api/channels/youtube/connection` | `YouTubeConnectionRepository` | Firestore (KMS AAD Encrypted) / YouTube Data API v3 | `VERIFIED_LOCAL` (when connected in local env) / `SAMPLE_DATA` (when sample selected) | `LOCAL_BROWSER` |
| Overview KPIs (Views, Watch Time, Net Subs, Retention) | `OverviewView.tsx` | `/api/channels/youtube/dashboard` / `/api/channels/sample/dashboard` | `build_channel_dashboard` + `YouTubeChannelDataProvider` / `SampleChannelDataProvider` | YouTube Analytics API v2 (`/reports`) / Deterministic 100-video sample | `VERIFIED_LOCAL` / `SAMPLE_DATA` | `LOCAL_BROWSER` |
| Performance Charts & Video Catalog | `PerformanceView.tsx` | `/api/channels/youtube/dashboard` | `build_channel_dashboard` | YouTube Data API v3 (`/videos`) + YouTube Analytics API v2 | `VERIFIED_LOCAL` / `SAMPLE_DATA` | `LOCAL_BROWSER` |
| Trend Time Series | `ChannelTrendChart.tsx` | `/api/channels/youtube/dashboard` | `build_channel_dashboard` | YouTube Analytics API v2 (`dimensions=day`) | `VERIFIED_LOCAL` / `SAMPLE_DATA` | `LOCAL_BROWSER` |
| Traffic Sources Distribution | `TrafficSourceChart.tsx` | `/api/channels/youtube/dashboard` | `build_channel_dashboard` | YouTube Analytics API v2 | `VERIFIED_LOCAL` / `SAMPLE_DATA` (clean empty state rendered when unavailable) | `LOCAL_BROWSER` |
| Experiments & Baselines | `ExperimentsView.tsx` | `/api/channels/youtube/dashboard` | `build_channel_dashboard` | Statistical correlation over video dataset | `VERIFIED_LOCAL` / `SAMPLE_DATA` | `LOCAL_BROWSER` |
| Worth Watching Research | `AlexRail.tsx` | `/api/channels/research/findings` | `AlexDataScientist.run_grounded_research` | Gemini 3.7 Flash + Google Search Grounding | `VERIFIED_LOCAL` (Deterministic provider in local testing; Gemini when GCP project configured) | `LOCAL_BROWSER` / `UNIT` |

*Note: In accordance with audit ledger rules, `VERIFIED_LIVE` is strictly reserved for instances where `LIVE_UPSTREAM` evidence is actively observed against live Google APIs in production. Local browser/API execution is classified as `VERIFIED_LOCAL`.*

---

## Alex Settings Runtime Audit Table

| Setting | UI Field | API Field | Persisted Field | Runtime Consumer | Model/Tool Effect | Test |
|---|---|---|---|---|---|---|
| Working Prompt | `Working prompt` textarea | `POST /api/workspaces/{id}/agent-settings/alex` (`prompt_text`) | Firestore `workspaces/{id}/agent_configs/alex` | `AlexDataScientist.run_grounded_research(custom_prompt=...)` | Prepends custom persona/directives to Gemini system prompt | `test_alex_custom_prompt_persisted_and_passed_to_research` |
| Research Cadence | `Schedule` select | `PUT /api/channels/research/config` (`cadence`) | Firestore `workspaces/{id}/research/config` (`cadence`) | Cloud Scheduler tick & `ResearchConfig.next_scheduled_at()` | Governs interval between automatic background research runs | `test_update_research_config_persists_new_cadence_and_prompts` |
| Prompt Enabled | `Enabled` checkbox | `PUT /api/channels/research/config` (`prompts[].enabled`) | Firestore `workspaces/{id}/research/config` | `AlexDataScientist.run_grounded_research` | Filters active research prompts before query construction | `test_alex_runs_grounded_research_with_citations` |
| Prompt Text | `Research prompt` textarea | `PUT /api/channels/research/config` (`prompts[].text`) | Firestore `workspaces/{id}/research/config` | `AlexDataScientist.run_grounded_research` | Directly constructs Gemini search queries | `test_alex_research_multi_lane_prompting` |
| Broad Web Search | `Search broader web` checkbox | `PUT /api/channels/research/config` (`prompts[].use_broad_web_search`) | Firestore `workspaces/{id}/research/config` | `AlexDataScientist.run_grounded_research` | When False, strictly restricts search queries and validates citation allowlist post-model | `test_alex_strict_preferred_sources_filters_citations_and_findings` |
| Preferred Sources | `Preferred public sources` pills + input | `PUT /api/channels/research/config` (`prompts[].preferred_sources`) | Firestore `workspaces/{id}/research/config` | `AlexDataScientist.run_grounded_research` | Injects domain constraints into prompt and strictly filters returned citations | `test_is_url_allowed_by_sources_*` |
| Channel Knowledge | Read-only Memory cards | `GET /api/workspaces/{id}/agent-memory/alex` | Memory Bank / Firestore | Drawer UI & `AlexDataScientist` channel profile injection | Injects content pillars, lessons, and performance history into research prompt | `test_memory.py` |

---

## Bug Ledger

| Bug ID | Severity | Area | Status | Symptom / Description | Fix Summary | Verification Level |
|---|---|---|---|---|---|---|
| **BUG-001** | P0 | Auth / Data | `FIXED` | YouTube connection produces 401 analytics error after token expires (1h) | Implemented `refresh_youtube_access_token_if_needed` shared token refresh service across channels & publishing | `UNIT` |
| **BUG-002** | P0 | Auth / Truth | `FIXED` | OAuth callback swallowed token exchange / metadata errors and invented fake 12,500 subscriber fallback | Removed fake 12.5k subscriber fallback; raised authentic HTTP 400 / 502 with exact Google/YouTube error detail | `UNIT` |
| **BUG-003** | P0 | Frontend / Auth | `FIXED` | "Connect YouTube Channel" button posted mock auth code instead of redirecting to Google OAuth | Implemented real browser redirect to Google OAuth `auth_url` and query parameter (`?code=...&state=...`) parsing on return | `LOCAL_BROWSER` |
| **BUG-004** | P1 | Agents | `FIXED` | Alex custom working prompt saved in settings was never consumed by research execution | Injected `AgentConfigRepository` and passed `custom_prompt` into `AlexDataScientist.run_grounded_research` | `UNIT` |
| **BUG-005** | P2 | Navigation | `FIXED` | Croviq logo on AppPage and ReleasePage was static and did not navigate to `/app` | Wrapped `CroviqLogo` in accessible navigation buttons resetting to overview / navigating home | `LOCAL_BROWSER` |
| **BUG-006** | P2 | UI | `FIXED` | `TrafficSourceChart` rendered blank empty canvas when traffic sources were unavailable | Added clean empty state container explaining data distribution status | `LOCAL_BROWSER` |
| **BUG-007** | P1 | Data / Robustness | `FIXED` | `build_channel_dashboard` crashed with `ValueError: zip() len() mismatch` on sparse historical dates | Replaced strict zip with resilient date-offset alignment and zero-fill for missing historical dates | `UNIT` |
| **BUG-008** | P0 | Auth / Truth | `FIXED` | Expired OAuth token with missing credentials or rejected refresh was returned as valid rather than requiring reauth | Raised `YouTubeReauthRequiredError`, returning HTTP 401 on dashboard sync and `AUTH_EXPIRED` on publish jobs | `UNIT` |
| **BUG-009** | P1 | Security / Prod | `FIXED` | Missing strict fail-closed guards in `media` and `memory` dependency injectors if fake provider configured in prod | Added explicit runtime checks raising errors if fake storage/transcription/memory is resolved in production | `UNIT` |
| **BUG-010** | P2 | UI / Runtime | `FIXED` | `OverviewView` crashed with `TypeError: Cannot read properties of undefined (reading 'toFixed')` on missing retention | Made `retention_percentage` access resilient with nullish coalescing default in `OverviewView.tsx` | `LOCAL_BROWSER` |
| **BUG-011** | P1 | Security / Prod | `FIXED` | Token encryptor and GenAI client factories silently fell back to local/in-memory mocks in production when Cloud KMS or GCP project was missing | Enforced strict fail-closed assertions across `token_encryption.py`, `productions/dependencies.py`, and all repository factories | `UNIT` |
| **BUG-012** | P1 | Research / Truth | `FIXED` | Alex research fabricated `published_at = now()` on source citations, lacked multi-lane intent exploration, and omitted channel profile propagation | Eliminated publication date fabrication (`published_at=None` when unknown), expanded multi-lane intent directives, and injected channel profile | `UNIT` |
| **BUG-013** | P2 | UI / Truth | `FIXED` | YouTube connection public summary and dashboard lacked explicit connection status (`reauth_required`) and mapped all errors to generic 502 | Added `status` and `error_message` fields, mapped specific 401/403/429 upstream errors, and added reconnect action buttons | `LOCAL_BROWSER` |
| **BUG-014** | P1 | Research / Truth | `FIXED` | Alex research prompts and fallbacks claimed "YouTube Category 28 tech signals" despite upstream source being Gemini Google Search Grounding | Truthfully labeled research provenance as Gemini 3.7 Flash + Google Search Grounding; removed misleading YouTube trending claims | `UNIT` |
| **BUG-015** | P1 | Security / Truth | `FIXED` | Preferred sources relied only on model prompt compliance; non-allowed domains and SSRF URLs could leak into citations | Implemented strict post-model citation URL validator with exact/subdomain allowlist matching, lookalike rejection, and SSRF private IP protection | `UNIT` |
| **BUG-016** | P2 | Auth / Robustness | `FIXED` | Reauth required state was transient in frontend and was lost across page refreshes | Added persistent `status` and `error_message` to `YouTubeConnection` across Firestore and in-memory repositories; differentiated 401 auth vs 403 permission vs 429 quota vs 502 upstream | `LOCAL_BROWSER` / `UNIT` |
| **BUG-017** | P1 | Security / Prod | `FIXED` | `AlexDataScientist` silently fell back to deterministic mock in production if GCP project ID was missing | Added strict fail-closed production check raising `RuntimeError` if GCP credentials are not configured in production | `UNIT` |

---

## Detailed Findings & Remediation History (Continuation #4)

### BUG-014: Truthful Research Labeling & Provenance Integrity
- **Status**: `FIXED`
- **Severity**: `P1`
- **Area**: `Agents / Research Provenance`
- **Verification Level**: `UNIT`
- **Symptom**: Alex research prompts and fallbacks claimed "YouTube Category 28 tech signals" despite the real upstream discovery source being Gemini 3.7 Flash + Google Search Grounding.
- **Root Cause**: Overstated prompt instructions and mock data referencing YouTube internal category signals rather than truthful web search discovery.
- **Files**: `packages/agents/src/croviq_agents/alex.py`, `packages/agents/tests/test_alex.py`
- **Tests Added**: `packages/agents/tests/test_alex.py::test_alex_research_provenance_labels`
- **Local Verification**: PASSED (all agent tests passing)

### BUG-015: Strict Post-Model Preferred Source & Citation Allowlist Enforcement with SSRF Protection
- **Status**: `FIXED`
- **Severity**: `P1`
- **Area**: `Security / Grounded Research`
- **Verification Level**: `UNIT`
- **Symptom**: When `use_broad_web_search == False`, prompt instructions (`site:<domain>`) were trusted without backend post-model validation. Model hallucinations, lookalike hostnames, or SSRF endpoints could leak into persisted citations.
- **Root Cause**: Absence of post-model citation filtering against configured source allowlist and lack of URL/SSRF security verification.
- **Files**: `packages/agents/src/croviq_agents/alex.py`, `packages/agents/tests/test_alex.py`
- **Tests Added**:
  - `packages/agents/tests/test_alex.py::test_is_url_allowed_by_sources_allowed_exact_and_subdomain`
  - `packages/agents/tests/test_alex.py::test_is_url_allowed_by_sources_unrelated_and_lookalike_rejected`
  - `packages/agents/tests/test_alex.py::test_is_url_allowed_by_sources_invalid_and_ssrf_rejected`
  - `packages/agents/tests/test_alex.py::test_alex_strict_preferred_sources_filters_citations_and_findings`
- **Local Verification**: PASSED (44 URL/search security tests passing)

### BUG-016: Persistent Channel Connection Status and Error Semantics
- **Status**: `FIXED`
- **Severity**: `P2`
- **Area**: `Auth / Connection Persistence`
- **Verification Level**: `LOCAL_BROWSER` / `UNIT`
- **Symptom**: `reauth_required` state was computed dynamically and was lost across page refreshes if refresh token existed but was revoked or failed upstream.
- **Root Cause**: `YouTubeConnection` and `YouTubeConnectionRecord` lacked persistent `status` and `error_message` fields.
- **Files**: `apps/api/src/croviq_api/channels/youtube_repository.py`, `apps/api/src/croviq_api/channels/token_refresh.py`, `apps/api/src/croviq_api/channels/routes.py`, `apps/api/tests/test_youtube_oauth_and_research_api.py`
- **Tests Added**:
  - `apps/api/tests/test_youtube_oauth_and_research_api.py::test_reauth_required_status_persists_across_connection_reloads`
  - `apps/api/tests/test_youtube_oauth_and_research_api.py::test_upstream_error_mappings_preserve_connection_semantics`
- **Local Verification**: PASSED (all API tests passing)

### BUG-017: Fail-Closed Production Grounded Research Safety
- **Status**: `FIXED`
- **Severity**: `P1`
- **Area**: `Security / Production Safety`
- **Verification Level**: `UNIT`
- **Symptom**: `AlexDataScientist.run_grounded_research` fell back to deterministic mock if GCP project ID was missing even when running in production environment.
- **Root Cause**: Missing production environment check in `AlexDataScientist`.
- **Files**: `packages/agents/src/croviq_agents/alex.py`, `packages/agents/tests/test_alex.py`
- **Tests Added**: `packages/agents/tests/test_alex.py::test_alex_production_fails_closed_without_gcp_project`
- **Local Verification**: PASSED (all agent tests passing)
