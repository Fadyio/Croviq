import { expect, test, type Page } from "@playwright/test";

const DEMO_EMAIL = "demo@croviq.app";
const FIREBASE_ID_TOKEN =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vY3JvdmlxLTUwNjYwMiIsImF1ZCI6ImNyb3ZpcS01MDYwMiIsImF1dGhfdGltZSI6MSwidXNlcl9pZCI6ImRlbW9fdXNlcl8xMjMiLCJzdWIiOiJkZW1vX3VzZXJfMTIzIiwiaWF0IjoxLCJleHAiOjQxMDI0NDQ4MDAsImVtYWlsIjoiZGVtb0Bjcm92aXEuYXBwIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZW1haWwiOlsiZGVtb0Bjcm92aXEuYXBwIl19LCJzaWduX2luX3Byb3ZpZGVyIjoicGFzc3dvcmQifX0.signature";

const APPROVED_USER = {
  user_id: "demo_user_123",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const WORKSPACE = {
  workspace_id: "ws_demo",
  owner_user_id: APPROVED_USER.user_id,
  name: "Croviq",
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const mockClientEvents = async (page: Page, events: Record<string, unknown>[]) => {
  await page.route("**/api/client-events", async (route) => {
    events.push(JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });
};

const mockFirebasePasswordSignIn = async (page: Page, succeeds: boolean) => {
  await page.route("**/identitytoolkit.googleapis.com/**", async (route) => {
    const url = route.request().url();
    if (url.includes("accounts:lookup")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users: [
            {
              localId: APPROVED_USER.user_id,
              email: DEMO_EMAIL,
              emailVerified: true,
              displayName: APPROVED_USER.display_name,
              providerUserInfo: [
                {
                  providerId: "password",
                  email: DEMO_EMAIL,
                },
              ],
              createdAt: "0",
              lastLoginAt: "0",
            },
          ],
        }),
      });
      return;
    }

    if (!url.includes("accounts:signInWithPassword")) {
      await route.abort();
      return;
    }

    if (!succeeds) {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ error: { message: "INVALID_LOGIN_CREDENTIALS" } }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        kind: "identitytoolkit#VerifyPasswordResponse",
        localId: APPROVED_USER.user_id,
        email: DEMO_EMAIL,
        displayName: APPROVED_USER.display_name,
        idToken: FIREBASE_ID_TOKEN,
        registered: true,
        refreshToken: "mock-refresh-token",
        expiresIn: "3600",
      }),
    });
  });
};

const mockApprovedApi = async (page: Page) => {
  await page.route("**/api/auth/me", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${FIREBASE_ID_TOKEN}`);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });
  await page.route("**/api/workspace", async (route) => {
    expect(route.request().headers().authorization).toBe(`Bearer ${FIREBASE_ID_TOKEN}`);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(WORKSPACE),
    });
  });
  await page.route("**/api/productions", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ productions: [], total: 0 }),
    });
  });
};

const signIn = async (page: Page) => {
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("test-only-password");
  await page.getByRole("button", { name: "Sign in" }).click();
};

test.describe("Email/password authentication", () => {
  test("unauthenticated access to /app redirects to /login", async ({ page }) => {
    await page.goto("/app");
    await page.waitForURL("**/login");
    await expect(page.getByRole("heading", { name: "Sign in to Croviq" })).toBeVisible();
  });

  test("password-only login UI omits Google and signup controls", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByRole("img", { name: "Croviq" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sign in to Croviq" })).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveAttribute("type", "email");
    await expect(page.getByLabel("Password")).toHaveAttribute("type", "password");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
    await expect(page.getByRole("button", { name: /Google/i })).toHaveCount(0);
    await expect(page.getByText("CI/CD for video creators.")).toHaveCount(0);
    await expect(page.getByText("Private hackathon demo")).toHaveCount(0);
    await expect(page.getByRole("link", { name: /sign up|forgot password/i })).toHaveCount(0);
  });

  test("wrong credentials show a friendly error without raw Firebase details", async ({ page }) => {
    const events: Record<string, unknown>[] = [];
    await mockClientEvents(page, events);
    await mockFirebasePasswordSignIn(page, false);
    await page.goto("/login");

    await signIn(page);

    await expect(page.getByRole("alert")).toHaveText("Email or password is incorrect.");
    await expect(page.getByText("auth/invalid-credential", { exact: false })).toHaveCount(0);
    await expect(page.getByText("INVALID_LOGIN_CREDENTIALS", { exact: false })).toHaveCount(0);
    await expect
      .poll(() => events)
      .toEqual([
        { event_type: "auth.login_attempt" },
        { event_type: "auth.login_failed", error_code: "invalid_credentials" },
      ]);
  });

  test("an authenticated non-demo account receives the authorization message", async ({ page }) => {
    const events: Record<string, unknown>[] = [];
    await mockClientEvents(page, events);
    await mockFirebasePasswordSignIn(page, true);
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ error_code: "demo_access_restricted" }),
      });
    });
    await page.goto("/login");

    await signIn(page);

    await expect(page.getByRole("alert")).toHaveText(
      "This account is not authorized to access Croviq.",
    );
    await expect
      .poll(() =>
        events.some(
          (e) => e.event_type === "auth.login_failed" && e.error_code === "demo_access_restricted",
        ),
      )
      .toBe(true);
  });

  test("approved mocked sign-in reaches /app and persists across refresh", async ({ page }) => {
    const events: Record<string, unknown>[] = [];
    await mockClientEvents(page, events);
    await mockFirebasePasswordSignIn(page, true);
    await mockApprovedApi(page);
    await page.goto("/login");

    await signIn(page);
    await page.waitForURL("**/app");
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("Your autonomous video production team.")).toBeVisible();
    await expect(page.getByText(DEMO_EMAIL, { exact: true })).toBeVisible();

    await page.reload();
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("Your autonomous video production team.")).toBeVisible();
    await expect
      .poll(() => events.some((e) => e.event_type === "auth.session.restored"))
      .toBe(true);
  });

  test("backend temporary 500 keeps user authenticated without logout", async ({ page }) => {
    const events: Record<string, unknown>[] = [];
    await mockClientEvents(page, events);
    await mockFirebasePasswordSignIn(page, true);
    await mockApprovedApi(page);
    await page.goto("/login");

    await signIn(page);
    await page.waitForURL("**/app");
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();

    // Mock /api/auth/me returning temporary 500
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Internal server error" }),
      });
    });

    await page.reload();
    // User must remain authenticated on /app
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText(DEMO_EMAIL, { exact: true })).toBeVisible();
  });

  test("backend network error keeps user authenticated without logout", async ({ page }) => {
    const events: Record<string, unknown>[] = [];
    await mockClientEvents(page, events);
    await mockFirebasePasswordSignIn(page, true);
    await mockApprovedApi(page);
    await page.goto("/login");

    await signIn(page);
    await page.waitForURL("**/app");
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();

    // Mock /api/auth/me network failure
    await page.route("**/api/auth/me", async (route) => {
      await route.abort("failed");
    });

    await page.reload();
    // User must remain authenticated on /app
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText(DEMO_EMAIL, { exact: true })).toBeVisible();
  });

  test("logout clears the Firebase session and returns to /login", async ({ page }) => {
    const events: Record<string, unknown>[] = [];
    await mockClientEvents(page, events);
    await mockFirebasePasswordSignIn(page, true);
    await mockApprovedApi(page);
    await page.route("**/api/auth/logout", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });
    await page.goto("/login");

    await signIn(page);
    await page.waitForURL("**/app");
    await page.getByRole("button", { name: "Logout" }).click();

    await page.waitForURL("**/login");
    await expect(page.getByRole("heading", { name: "Sign in to Croviq" })).toBeVisible();
    await expect.poll(() => events.some((e) => e.event_type === "auth.explicit_logout")).toBe(true);
  });
  test("login remains usable with reduced motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/login");

    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
  });
});
