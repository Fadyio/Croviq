# Croviq Final Foundation Repair Audit & Ledger

## Audit Overview & Forensic Disposition

**Date**: 2026-08-29  
**Status**: IN_PROGRESS (Final Foundation Repair Before Editor Work)

Every issue reported in the forensic audit reports has been inspected against the current `main` branch, reproduced or proven stale, and classified into one of four canonical dispositions:
- `CONFIRMED`: Active defect reproduced in current code; requires repair.
- `ALREADY_FIXED`: Addressed by prior commits; verified clean.
- `OBSOLETE_BECAUSE_FEATURE_REMOVED`: Associated feature or agent (e.g. Nina, Shorts, old packaging pipeline) was sunset.
- `FALSE_POSITIVE`: Reported behavior is intentional, conforms to domain design, or was misdiagnosed.

---

## 1. Forensic Audit Ledger & Findings Classification

| ID | Area / Component | Reported Finding | Current State & Evidence | Classification | Planned Disposition |
|---|---|---|---|---|---|
| **AUD-001** | Architecture / Agents | Maya (Director) active in product code, prompts, UI, and docs | `AgentId` and `TargetAgent` only list Alex/Leo/Iris, but Maya references linger in `CONTEXT.md`, `README.md`, `PRODUCT.md`, `DESIGN-SYSTEM.md`, `verify_production_ui.mjs`, `ENGINEERING.md`, and scripts | `CONFIRMED` | Completely remove Maya from all active product docs, UI scripts, comments, diagrams, and fixtures. Canonical agents: Alex, Leo, Iris. |
| **AUD-002** | Architecture / Agents | Packaging-era remnants (Nina agent, `PackagingProposal` dependencies) | `NinaPackagingAgent` removed from `packages/agents`, but `PackagingProposal` dereferencing crashes Iris/Publish if `proposal` is `None` (`proposal.proposal_id` on `routes.py:2030`) | `CONFIRMED` | Make packaging optional & creator-owned. Fix `proposal.proposal_id` crash when `proposal` is `None`. Remove obsolete Nina tests/scripts. |
| **AUD-003** | API / Contracts | NewProjectPage upload routes mismatch (`/api/productions/upload` vs `/api/uploads`) | `NewProjectPage.tsx:151` calls `POST /api/productions/upload` and `:211` calls `POST /api/productions/{id}/verify-upload`, while FastAPI backend exposes `POST /api/uploads` and `POST /api/uploads/{id}/complete` | `CONFIRMED` | Align frontend to canonical `/api/uploads` and `/api/uploads/{upload_id}/complete` contract. Remove stale Playwright mocks. |
| **AUD-004** | API / Contracts | YouTube OAuth `auth_url` response field contract mismatch | Backend returns `YouTubeAuthUrlResponse` with `auth_url`. `ReleasePage.tsx:351` checked `authorization_url` instead of `auth_url` | `CONFIRMED` | Fix `ReleasePage.tsx` to consume `auth_url` typed directly from OpenAPI schema. |
| **AUD-005** | Security / Safety | Synthetic sample channel `croviq_syn_ai_eng_01` publish safety check bypass | `publish_service.py:167, 307` checked `channel_id.startswith("sample_") or channel_id == "sample_tech_channel"`, failing to block `croviq_syn_ai_eng_01` from YouTube publishing | `CONFIRMED` | Create canonical `is_sample_channel(channel_id)` domain helper and enforce strictly across all publish entry points. |
| **AUD-006** | Media / Runtime | `SourceMedia.duration_ms` invalid attribute access | `routes.py:1571` evaluates `prod.source_media.duration_ms`, which raises `AttributeError` since `SourceMedia` has no duration attribute | `CONFIRMED` | Replace invalid attribute access with canonical duration from EDL or transcript metadata. |
| **AUD-007** | Media / Runtime | Hardcoded `113824` Fairphone fixture duration in production UI | `edl-adapter.ts:169, 311`, `EditorPage.tsx:110, 220`, and `ReleasePage.tsx:124` fallback to `113824` ms | `CONFIRMED` | Remove magic `113824` constants from production code. Unknown duration renders empty/loading state without fabricating data. |
| **AUD-008** | Media / Voice | Voice audition endpoint returns 44-byte empty WAV header | `packages/agents/src/croviq_agents/voice.py:259` returns a static 44-byte header with 0 data bytes, mislabeled as audio sample | `CONFIRMED` | Implement real Gemini TTS audio generation or truthful graceful degradation if TTS client is unconfigured. |
| **AUD-009** | Media / STT | Transcription endpoint lacks idempotency across non-UPLOADED stages | `routes.py:756-764` rejects `prod.status != UPLOADED` with 400 before checking `transcript_repo.get_transcript_by_production_id`, preventing re-retrieval in later stages | `CONFIRMED` | Check transcript cache first and allow idempotent re-transcription query regardless of later stage (`ANALYZING`, `ANALYZED`, `READY`, `COMPLETED`). |
| **AUD-010** | Chat / Architecture | Fake canned responses for Leo & Iris chat and unbounded `_CONVERSATION_STORE` | `chat_service.py` returns hardcoded canned strings for Leo/Iris; `_CONVERSATION_STORE` is an unbounded in-memory dictionary without TTL or isolation | `CONFIRMED` | Disable Leo/Iris chat in UI until editing/QA phase implementation; replace `_CONVERSATION_STORE` with bounded storage with max messages, max characters, TTL, workspace/user/agent isolation. |
| **AUD-011** | Tooling / Quality | Dead files, unused re-exports, and obsolete scripts | `apps/web/verify_live_alex_refactor.mjs`, `apps/web/src/components/AgentSettingsDrawer.tsx`, `ProductionRunStrip.tsx`, `index.ts`, `InvertedLocalTinkOAuthTokenEncryptor` alias, redundant `.gitkeep` files, `.wrangler` tmp directory | `CONFIRMED` | Safely remove all confirmed dead files, dead imports, and redundant `.gitkeep` files. |
| **AUD-012** | Tooling / Quality | Fake frontend linter (`echo '@croviq/web: ok'`) in `apps/web/package.json` | `apps/web/package.json:10` has `"lint": "echo '@croviq/web: ok'"` which bypasses all static analysis | `CONFIRMED` | Install and configure Biome or ESLint in `apps/web`, catching unused variables, unused imports, React hook errors, and type correctness. |
| **AUD-013** | Tooling / DevOps | Playwright uses `bun run dev` and `docker-compose.yml` missing package volume mounts | `apps/web/playwright.config.ts:28` launches with `bun run dev`; `docker-compose.yml` lacks `./packages/agents` and `./packages/media` mounts; `wif-test.yml` runs redundantly on push | `CONFIRMED` | Update Playwright config to canonical `pnpm`, add missing mounts to `docker-compose.yml`, scope `wif-test.yml` to `workflow_dispatch`, and expand `.dockerignore`. |
| **AUD-014** | Data Science / UI | Analytical theater in Home Channel Performance chart ("Projection active", ±1σ/±2σ corridor) | `ChannelTrendChart.tsx` extrapolates linear trend with confidence cones and misleading assumptions | `CONFIRMED` | Remove rolling projection & uncertainty corridors. Implement relative day index (Day 1..28) current vs previous period comparison with subtle daily points, 7-day rolling mean, and clear tooltips. |
| **AUD-015** | Data Science / UI | Latest upload & Alex insight lacking rigor and actual video context | `LatestVideoAnalysis` shows simple +/- delta without percentile distribution; insight lacks clear MEASUREMENT / INTERPRETATION / ACTION separation | `CONFIRMED` | Add percentile distributions (views, retention, CTR, conversion per 1k views), structured 3-part Alex insight, and truthful freshness timestamps for Ideas Worth Making. |
| **AUD-016** | Background / Infra | Research scheduler HTTP 500 errors during periodic ticks | `process_scheduler_tick` lacked per-config exception handling, causing an unhandled error in one channel to crash the entire batch and retry continuously | `CONFIRMED` | Wrap per-config execution in try/except, advance `next_run_at`, log detailed error telemetry with `request_id`, and prevent duplicate run spikes. |

---

## 2. Verification Protocol

Each confirmed repair is validated through:
1. **Unit & Package Tests**: Domain, observability, media, agents, and API test suites via `make test`.
2. **TypeScript & Static Typechecking**: `make typecheck` with 0 errors.
3. **Frontend Quality Gate**: Real linter execution via `make lint`.
4. **OpenAPI & Generated Contracts**: Export OpenAPI and generate TypeScript contracts via `make openapi`.
5. **Formatting**: Canonical Prettier validation via `make format-check`.
6. **E2E & Visual Verification**: Playwright test suite and Chrome browser visual inspection at 1600x900, 1440x900, 1280x800 viewports.
