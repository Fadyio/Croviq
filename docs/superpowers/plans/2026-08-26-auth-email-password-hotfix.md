# Email/Password Demo Authentication Hotfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Google authentication with locked email/password access for the single Croviq demo account.

**Architecture:** Terraform configures Identity Platform's local email/password provider and signup restrictions; it does not manage a user or Google IdP resource. The web client keeps Firebase as the session authority, verifies every sign-in against `/api/auth/me`, and gets API tokens only at request time. The API enforces the exact deployed allowlist and records a strict, sanitized set of client auth events through its existing structured logger.

**Tech Stack:** Terraform Google provider, Firebase Web SDK, React 19, Motion, FastAPI, Pydantic v2, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-26-auth-email-password-hotfix-design.md`

## Global Constraints

- Permit only `demo@croviq.app`; do not trust a frontend email field.
- Do not create, request, generate, store, or log a password, secret, OAuth credential, Firebase credential, ID token, or Authorization header.
- Do not create/delete a Google IdP Terraform resource; the configuration has none.
- Identity Platform must allow password-required email authentication, deny public signup, and deny anonymous auth.
- Keep existing Cloud Logging and 100% load-balancer logging; add no logging infrastructure.
- Accept only `auth.login_attempt` and `auth.login_failed` through `/api/client-events`.
- Use Motion only for login-card entrance, button interaction, and error transition; no gradients or workflow decoration.
- Do not create the production demo user. Stop before this manual operation.

---

### Task 1: Lock Identity Platform and backend policy

**Files:**
- Modify: `infra/main.tf:274-292,361-378`
- Modify: `infra/variables.tf:109-114`
- Modify: `infra/terraform.tfvars.example:18-19`
- Modify: `apps/api/tests/test_auth.py:36-39,198-379`

**Interfaces:**
- Produces: `Settings.allowed_emails` containing exactly the Terraform-deployed demo email in production.
- Consumes: existing `get_current_principal` allowlist enforcement and `google_identity_platform_config.default`.

- [ ] **Step 1: Lock configuration and update the authorization fixture**

Set the Terraform default/example to `demo@croviq.app`, retain the existing Cloud Run environment variable wiring, and change the API fixture and approved-claim expectations from the former account to `demo@croviq.app`. The backend already verifies tokens and enforces the environment-provided allowlist; this task changes deployed configuration rather than backend behavior, so `terraform validate` is the relevant Terraform check.

- [ ] **Step 2: Configure Identity Platform**

```hcl
client {
  permissions {
    disabled_user_signup = true
  }
}

sign_in {
  email {
    enabled           = true
    password_required = true
  }
  anonymous {
    enabled = false
  }
}

monitoring {
  request_logging {
    enabled = true
  }
}
```

Do not add an IdP resource. Keep the existing backend-policy mechanism and change its test/configuration values to the locked email.

- [ ] **Step 3: Verify focused authorization and Terraform configuration**

Run: `uv run --directory apps/api pytest tests/test_auth.py -k 'allowed_verified_account or different_email or unverified_allowed_email' -v && terraform -chdir=infra validate`

Expected: all selected authorization cases pass and Terraform validates.

### Task 2: Add strict sanitized client-event logging

**Files:**
- Modify: `apps/api/src/croviq_api/schemas.py`
- Modify: `apps/api/src/croviq_api/auth/routes.py`
- Modify: `apps/api/tests/test_auth.py`
- Regenerate: `openapi.json`

**Interfaces:**
- Produces: `POST /api/client-events` accepting `ClientAuthEvent(event_type: Literal['auth.login_attempt', 'auth.login_failed'], error_code: Literal['invalid_credentials', 'demo_access_restricted'] | None)`.
- Consumes: `log_auth_event(event_type, status, request_id, error_code)`.

- [ ] **Step 1: Write failing endpoint tests**

Add tests that post a permitted login attempt and assert its structured log contains the required Cloud Logging fields. Add a test posting a password, ID token, authorization header, Firebase error text, or unknown event type; assert validation rejects it and captured logs contain none of the sensitive values.

- [ ] **Step 2: Run the focused telemetry tests and verify their expected failure**

Run: `uv run --directory apps/api pytest tests/test_auth.py -k 'client_event' -v`

Expected: FAIL because `/api/client-events` does not exist.

- [ ] **Step 3: Implement the strict request schema and route**

Use a Pydantic model with `ConfigDict(extra='forbid')`, literal event/error values, and no free-form message field. Log allowed events through the existing `log_auth_event` function with `200` status and the middleware request ID.

- [ ] **Step 4: Verify focused telemetry tests and refresh the OpenAPI artifact**

Run: `uv run --directory apps/api pytest tests/test_auth.py -k 'client_event' -v && pnpm export:openapi`

Expected: telemetry tests pass and `openapi.json` contains the strict client-event operation.

### Task 3: Replace Firebase login and token handling

**Files:**
- Modify: `apps/web/src/lib/firebase.ts`
- Modify: `apps/web/src/auth/AuthContext.tsx`
- Modify: `apps/web/src/pages/AppPage.tsx`
- Modify: `apps/web/src/App.tsx` only if routing needs a login-completion callback

**Interfaces:**
- Produces: `AuthContextValue.loginWithPassword(email: string, password: string): Promise<boolean>` and `firebaseUser: FirebaseUser | null`; no `idToken`, `loginWithGoogle`, or mock-auth APIs.
- Consumes: Firebase `setPersistence(auth, browserLocalPersistence)`, `signInWithEmailAndPassword`, `onAuthStateChanged`, `signOut`, and `/api/auth/me`.

- [ ] **Step 1: Rewrite browser tests for a failing email/password sign-in contract**

Replace Google/mock-session setup in `apps/web/e2e/auth-routing.spec.ts` with intercepted Identity Toolkit responses. The success fixture returns a synthetic Firebase sign-in response and intercepts `GET /api/auth/me` plus `/api/workspace`; the failure fixture returns `INVALID_LOGIN_CREDENTIALS`. Assert success reaches `/app`, a refresh retains `/app`, and failure displays the fixed friendly message rather than the Firebase code/text.

- [ ] **Step 2: Run the focused browser login test and verify its expected failure**

Run: `pnpm --filter @croviq/web test:e2e -- auth-routing.spec.ts --grep 'approved mocked sign-in'`

Expected: FAIL because the email/password controls and sign-in function are absent.

- [ ] **Step 3: Implement the password-only Firebase flow**

Remove `GoogleAuthProvider`, `googleProvider`, `signInWithPopup`, raw token state, session-storage mock state, and `loginWithGoogle`. Explicitly configure browser-local Firebase persistence. On password submission, send a sanitized `auth.login_attempt`, sign in with Firebase, get the token only to call `/api/auth/me`, and set the domain user on approval. Map credential failures and backend 403 to the exact approved text; emit sanitized `auth.login_failed` codes. Obtain a new token from `firebaseUser.getIdToken()` immediately before workspace requests. Logout signs out, clears both user states, posts the existing logout event, and redirects through the existing route behavior.

- [ ] **Step 4: Run focused browser auth tests and web typecheck**

Run: `pnpm --filter @croviq/web test:e2e -- auth-routing.spec.ts && pnpm --filter @croviq/web typecheck`

Expected: auth routing passes, including protected route, sign-in, persistence, friendly errors, and logout.

### Task 4: Distill and verify the login surface

**Files:**
- Modify: `apps/web/src/pages/LoginPage.tsx`
- Delete: `apps/web/src/components/PipelineBraid.tsx` if it has no remaining consumers
- Modify: `apps/web/e2e/auth-routing.spec.ts`

**Interfaces:**
- Consumes: `useAuth().loginWithPassword`, `isLoading`, `error`, and `clearError`.
- Produces: accessible Email and Password controls and a Sign in button.

- [ ] **Step 1: Write failing visible-surface assertions**

Assert that `/login` displays the logo, heading, `Email` input, `Password` input, and `Sign in` button. Assert Google/sign-up/reset UI and the removed marketing/pipeline copy are absent.

- [ ] **Step 2: Run the focused UI assertion and verify its expected failure**

Run: `pnpm --filter @croviq/web test:e2e -- auth-routing.spec.ts --grep 'password-only login UI'`

Expected: FAIL because the Google screen remains.

- [ ] **Step 3: Implement the neutral graphite login form**

Replace the split marketing layout with one centered, restrained graphite card. Use explicit visible labels, `type='email'`, `type='password'`, form submission, disabled submit state, and an accessible alert. Keep only the approved Motion animation surfaces. Remove obsolete imports and the pipeline component if unused.

- [ ] **Step 4: Verify login UI and actual browser surface**

Run: `pnpm --filter @croviq/web test:e2e -- auth-routing.spec.ts --grep 'password-only login UI|wrong credentials'`

Start the existing web test server, navigate to `/login`, and inspect desktop and mobile browser screenshots for the required restrained single-card layout.

### Task 5: Full validation, review, and commit

**Files:**
- Verify: changed Terraform, API, web, tests, generated OpenAPI, and approved docs.

- [ ] **Step 1: Run typechecks and direct test suites**

Run: `pnpm typecheck && uv run --directory apps/api pytest -v && pnpm --filter @croviq/web test:e2e`

Expected: all typechecks and suites pass without real demo credentials.

- [ ] **Step 2: Run formatting and infrastructure checks**

Run: `pnpm format:check && terraform -chdir=infra validate`

Expected: no formatting or Terraform errors.

- [ ] **Step 3: Review the complete diff against the approved spec**

Run the required two-axis code review against the pre-hotfix commit. Resolve every substantive standards or spec issue before committing.

- [ ] **Step 4: Commit the completed hotfix on the current branch**

```bash
git add infra apps openapi.json docs
git commit -m "fix(auth): require demo email password sign-in"
```

- [ ] **Step 5: Stop before manual production user creation**

Do not create `demo@croviq.app`. Report exact Firebase/Google Cloud Console steps for the user to create the account and enter the password themselves. Wait for confirmation before any production verification.
