/**
 * Test authentication fixtures and dynamic JWT generator for Playwright E2E tests.
 * Builds unverified mock tokens dynamically at runtime to avoid hardcoding static JWT strings in repository files.
 */

export const DEMO_EMAIL = "demo@croviq.app";

export const APPROVED_USER = {
  user_id: "demo_user_123",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

export const WORKSPACE = {
  workspace_id: "ws_demo",
  owner_user_id: APPROVED_USER.user_id,
  name: "Croviq",
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

export function createMockFirebaseToken(claims: Record<string, unknown> = {}): string {
  const header = { alg: "none", typ: "JWT" };
  const payload = {
    iss: "https://securetoken.google.com/croviq-506602",
    aud: "croviq-506602",
    auth_time: 1,
    user_id: APPROVED_USER.user_id,
    sub: APPROVED_USER.user_id,
    iat: 1,
    exp: 4102444800,
    email: DEMO_EMAIL,
    email_verified: true,
    firebase: {
      identities: { email: [DEMO_EMAIL] },
      sign_in_provider: "password",
    },
    ...claims,
  };
  const headerB64 = Buffer.from(JSON.stringify(header)).toString("base64url");
  const payloadB64 = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${headerB64}.${payloadB64}.signature`;
}

export const FIREBASE_ID_TOKEN = createMockFirebaseToken();
