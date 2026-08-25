# 0010: Authentication, Demo Allowlist, and Incremental YouTube OAuth

## Context
Croviq requires user authentication to secure Workspace data and authorization to interact with YouTube APIs (for reading analytics, syncing metadata, and uploading videos). For the hackathon evaluation, public end-user signups and unconstrained OAuth flows introduce security vulnerabilities and configuration complexity. Furthermore, evaluators need a reliable, pre-configured access path without manual account approval steps.

## Decision
We establish a secure, allowlist-backed authentication model decoupled from external platform authorization:

1. **Hackathon Authentication Model (Identity Platform Email/Password)**:
   - Google Cloud Identity Platform powers email/password authentication.
   - Judge/Demo account: `demo@croviq.app`.
   - Public end-user signups and anonymous authentication are disabled in Identity Platform.
   - Password reset flows and Google Sign-In buttons in the Croviq UI are omitted for hackathon simplicity.
   - Backend authorization is authoritative:
     ```text
     Valid Identity Platform ID Token
     + Email exists
     + Normalized email in CROVIQ_ALLOWED_EMAILS
     + Account enabled
     -> ALLOW (HTTP 200)
     ```
   - `email_verified` is not enforced for the pre-provisioned demo account.

2. **First-Use Channel Selection**:
   - **Connect YouTube Channel**: Incremental YouTube OAuth flow for real creator channels. Requests read-only scopes first (analytics/channel), deferring upload/publishing scopes until publishing is required.
   - **Use Sample Channel**: Instant activation of the deterministic sample AI engineering channel (~50,000 subscribers, 100 historical videos), enabling full feature testing without external OAuth credentials.

3. **Mandatory Stop-and-Ask on OAuth Provisioning**:
   - When implementation reaches OAuth client ID/secret creation or external provider configuration, the agent must stop and ask the owner. The agent must never create external credentials or OAuth clients silently.

## Consequences
- Zero friction for hackathon evaluators using `demo@croviq.app`.
- Strict multi-tenant security and zero anonymous data leakage.
- Clean separation between identity authentication and external platform authorization.
