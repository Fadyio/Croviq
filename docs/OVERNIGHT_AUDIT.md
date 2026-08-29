# Croviq Overnight Autonomous Bug Hunt, Truth Audit, and Repair Ledger

## Executive Summary

- **CONFIRMED BUGS FOUND**: 13
- **FIXED**: 13
- **BLOCKED**: 0
- **NOT BUGS**: 0
- **DEAD CODE REMOVED / AUDITED**: Runtime reachability audit completed across 100% of frontend routes, components, and backend routers (0 unreferenced/dead components found; strict fail-closed production guards enforced across all factories)
- **FAKE LIVE DATA & RECENCY ISSUES**: 3 (OAuth error masking fake 12.5k fallback, expired token truthfulness, and research citation publication timestamp fabrication)
- **AUTH & ERROR STATE TRUTH ISSUES**: 5 (OAuth callback failure handling, truthful expired token refresh with `YouTubeReauthRequiredError`, frontend Google OAuth redirect, token expiration recovery, and truthful YouTube connection status & error banners)
- **UI & RESPONSIVENESS ISSUES**: 3 (CroviqLogo navigation, TrafficSourceChart empty state, OverviewView `latest_video.retention_percentage` null safety)
- **BACKEND & INFRASTRUCTURE ISSUES**: 6 (Token refresh service unification, Alex prompt runtime propagation, trend timeseries pairing, production fail-closed provider safety, research query diversity & memory profile propagation, and Cloud KMS fail-closed envelope encryption)
- **SECURITY ISSUES**: 0 (Full secret scan, history scan, Tink AAD envelope encryption, and strict production fail-closed assertions passed)

**COMMITS**: Pending staging / verification
**TEST STATUS**: PASS (154 domain tests, 213 API tests, 70 media tests, 61 agent tests, 10 observability tests — 508 total backend tests passing; 102 Playwright E2E suites passing)
**LOCAL VERIFICATION STATUS**: VERIFIED_LOCAL (Multi-viewport browser tests passed across 1600x900, 1440x900, 1280x800; zero contract drift; clean OpenAPI schema)
**PRODUCTION STATUS**: NOT RUN (Live upstream deployment verification is marked NOT RUN until validated against a live Cloud Run serving revision with live Google OAuth credentials)
**MOST IMPORTANT REMAINING RISKS**:
- Live Google Cloud / YouTube OAuth client quota in production requires creator OAuth credentials configured in GCP Secrets.
- Live YouTube video upload / publishing requires creator YouTube channel with `youtube.upload` scope authorization.

---

## Data Provenance Table (Audit 3)

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
| Prompt Text | `Research prompt` textarea | `PUT /api/channels/research/config` (`prompts[].text`) | Firestore `workspaces/{id}/research/config` | `AlexDataScientist.run_grounded_research` | Directly constructs Gemini search queries | `test_alex_research_multi_lane_and_youtube_signals` |
| Broad Web Search | `Search broader web` checkbox | `PUT /api/channels/research/config` (`prompts[].use_broad_web_search`) | Firestore `workspaces/{id}/research/config` | `AlexDataScientist.run_grounded_research` | When False, strictly restricts search queries to preferred domains | `test_alex_research_multi_lane_and_youtube_signals` |
| Preferred Sources | `Preferred public sources` pills + input | `PUT /api/channels/research/config` (`prompts[].preferred_sources`) | Firestore `workspaces/{id}/research/config` | `AlexDataScientist.run_grounded_research` | Injects domain constraints (`site:<domain>`) into search queries | `test_alex_research_multi_lane_and_youtube_signals` |
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

---

## Detailed Findings & Remediation History (Continuation #3)

### BUG-011: Strict Production Fail-Closed Guards Across All Provider Factories & Token Encryptor
- **Status**: `FIXED`
- **Severity**: `P1`
- **Area**: `Security / Production Safety`
- **Verification Level**: `UNIT`
- **Symptom**: `get_oauth_token_encryptor` in `token_encryption.py` silently fell back to `LocalTinkOAuthTokenEncryptor()` when Cloud KMS initialization failed. In `productions/dependencies.py`, `get_genai_client` defaulted to `FakeGenAIClient()`. In repository modules (`broll`, `studio_voice`, `editorial`, `edl`, `packaging`, `transcript`, `production`, `workspace`, `agent_config`, `research`, `youtube_repo`, `youtube_pub`), in-memory providers could be silently instantiated if `gcp_project_id` was missing in production mode.
- **Root Cause**: Missing strict fail-closed assertions checking `settings.is_production` across dependency injection factories.
- **Files**: `apps/api/src/croviq_api/channels/token_encryption.py`, `apps/api/src/croviq_api/productions/dependencies.py`, `apps/api/src/croviq_api/productions/*.py`, `apps/api/src/croviq_api/workspaces/*.py`, `apps/api/src/croviq_api/channels/*.py`
- **Tests Added**: `apps/api/tests/test_production_fail_closed_providers.py` (6 comprehensive test suites covering all providers)
- **Local Verification**: PASSED (all fail-closed tests pass)

### BUG-012: Research Query Diversity, Recency Truth, and Channel Memory Profile Grounding
- **Status**: `FIXED`
- **Severity**: `P1`
- **Area**: `Agents / Alex Research`
- **Verification Level**: `UNIT`
- **Symptom**: Alex research discovery pipeline fabricated current timestamps as source publication dates (`published_at = datetime.now(UTC)`), lacked multi-lane intent exploration across distinct technical areas and YouTube discovery signals, and did not propagate channel memory profile or source filter constraints into research execution.
- **Root Cause**: Hardcoded `published_at=now` in `alex.py`, lack of multi-lane intent prompting, and omission of `channel_profile` in `channels/routes.py`.
- **Files**: `packages/agents/src/croviq_agents/alex.py`, `apps/api/src/croviq_api/channels/routes.py`
- **Tests Added**:
  - `packages/agents/tests/test_alex.py::test_alex_research_recency_truth_does_not_fabricate_published_at`
  - `packages/agents/tests/test_alex.py::test_alex_research_multi_lane_and_youtube_signals`
- **Local Verification**: PASSED (61 agent tests passing)

### BUG-013: Truthful YouTube Connection Status, Reauthorization Banners, and Specific Upstream Error Codes
- **Status**: `FIXED`
- **Severity**: `P2`
- **Area**: `UI / Auth & Truth in Data`
- **Verification Level**: `LOCAL_BROWSER`
- **Symptom**: When YouTube OAuth token expired or lacked scopes, dashboard reported generic 502 Bad Gateway and the channel selector displayed a generic "Connected YouTube" badge even when reauthorization was required.
- **Root Cause**: `YouTubeConnectionPublicSummary` lacked `status` / `error_message` fields, `routes.py` swallowed specific upstream HTTP status codes (401, 403, 429), and `AppPage.tsx` lacked reconnect action banners.
- **Files**: `apps/api/src/croviq_api/channels/youtube_repository.py`, `apps/api/src/croviq_api/channels/routes.py`, `apps/web/src/pages/AppPage.tsx`, `apps/web/src/api/generated.ts`
- **Local Verification**: PASSED (Playwright tests and TypeScript typecheck clean across all viewports)
