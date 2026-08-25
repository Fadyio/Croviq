# Email/Password Demo Authentication Hotfix

**Status:** Approved 2026-08-26

## Goal

Replace Croviq's production Google sign-in flow with the locked email/password demo flow. Only the Identity Platform account `demo@croviq.app` may access Croviq.

## Scope

### Identity Platform and Terraform

Terraform is the only infrastructure configuration path. `google_identity_platform_config` enables password-required email authentication, disables anonymous authentication and end-user signup, and enables Identity Platform request logging. The existing load-balancer request logging remains enabled at 100% sampling. The existing Terraform configuration contains no Google IdP resource; none will be created or deleted.

Terraform deploys exactly `demo@croviq.app` as `CROVIQ_ALLOWED_EMAILS`. It does not create a user, password, secret, or OAuth credential.

### Web authentication

The login route contains only the Croviq logo, heading, email and password controls, a Sign in button, and friendly error feedback. It uses Motion only for card entrance, button interaction, and error transition. It has no Google button, marketing content, pipeline graphic, gradients, signup, password reset, or anonymous flow.

`AuthProvider` explicitly selects Firebase browser-local persistence. It calls `signInWithEmailAndPassword`, obtains an ID token only to verify through `GET /api/auth/me`, and does not persist raw tokens in application state or browser storage. Authenticated API calls obtain a fresh Firebase token from the in-memory Firebase user when needed. Logout calls Firebase `signOut`, clears Croviq state, records the existing logout event, and returns to `/login`.

Firebase credential errors map to `Email or password is incorrect.` Backend access denial maps to `This account is not authorized to access Croviq.` Firebase error strings and raw error codes never render.

### Backend authorization and logging

The backend remains authoritative: it validates Identity Platform ID tokens and email-verification claims before applying the deployed allowlist. Any other authenticated email receives `403` with `demo_access_restricted`.

`POST /api/client-events` accepts only `auth.login_attempt` and `auth.login_failed`, with a controlled optional error code and no extra fields. It logs structured entries through the existing JSON stdout/Cloud Logging path. It never accepts, stores, or logs passwords, ID tokens, authorization headers, Firebase credentials, or raw Firebase exception data. Existing successful events remain unchanged.

### Verification

Browser tests use intercepted Firebase Auth responses and API routes; no real user credentials are used. They cover protected-route redirects, email/password-only login UI, friendly credential errors, raw-error suppression, approved sign-in, persistence, logout, and telemetry sanitization. API tests cover exact allowlisting and strict client-event sanitization. Terraform validation, typechecking, targeted tests, the full suite, UI browser checks, and code review precede the commit.

## Production-user boundary

After code and Terraform are ready, stop before creating `demo@croviq.app`. The user creates that account manually in Google Cloud Console or Firebase Console and enters the password locally. Production verification starts only after the user confirms completion.
