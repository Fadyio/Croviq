import { test, expect } from "@playwright/test";

const MOCK_APPROVED_USER = {
  user_id: "google_user_fadynagh10",
  email: "fadynagh10@gmail.com",
  display_name: "Fady Nagh",
  avatar_url: "https://lh3.googleusercontent.com/a/photo-sample.jpg",
  created_at: "2026-08-25T06:00:00Z",
  updated_at: "2026-08-25T06:00:00Z",
};

test.describe("Authentication & Protected Routing", () => {
  test("unauthenticated access to /app redirects to /login", async ({ page }) => {
    await page.goto("/app");
    await page.waitForURL("**/login");
    expect(page.url()).toContain("/login");

    // Verify login card is visible
    const loginHeading = page.getByRole("heading", { name: "Sign in to Croviq" });
    await expect(loginHeading).toBeVisible();
  });

  test("login screen renders all required design elements", async ({ page }) => {
    await page.goto("/login");

    // Left pane brand elements
    const logo = page.getByRole("img", { name: "Croviq" });
    await expect(logo).toBeVisible();

    const statement = page.getByRole("heading", { name: "CI/CD for video creators." });
    await expect(statement).toBeVisible();

    // Verify pipeline stage labels in left pane
    await expect(page.getByText("Ingest", { exact: true })).toBeVisible();
    await expect(page.getByText("Analysis", { exact: true })).toBeVisible();
    await expect(page.getByText("Cut & EDL", { exact: true })).toBeVisible();
    await expect(page.getByText("Truth QA", { exact: true })).toBeVisible();
    await expect(page.getByText("Publish", { exact: true })).toBeVisible();

    // Right pane card elements
    const googleButton = page.getByRole("button", { name: "Continue with Google" });
    await expect(googleButton).toBeVisible();
    await expect(googleButton).toBeEnabled();

    // Hackathon demo notice
    const notice = page.getByText("Private hackathon demo — authorized account only.");
    await expect(notice).toBeVisible();
  });

  test("motion does not break in prefers-reduced-motion mode", async ({ page }) => {
    // Emulate reduced motion
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/login");

    const logo = page.getByRole("img", { name: "Croviq" });
    await expect(logo).toBeVisible();

    const googleButton = page.getByRole("button", { name: "Continue with Google" });
    await expect(googleButton).toBeVisible();
  });

  test("protected route behavior with mocked authenticated state", async ({ page }) => {
    // Mock /api/workspace endpoint so /app workspace fetch resolves cleanly
    await page.route("**/api/workspace", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          workspace_id: "ws_demo_fady",
          owner_user_id: MOCK_APPROVED_USER.user_id,
          name: "Croviq Demo Workspace",
          channel_description: "Production channel for AI video pipelines",
          brand_kit: {
            tone: ["concise", "informative"],
            target_audience: "Video creators & developers",
            content_style: "Technical walkthrough",
          },
          created_at: "2026-08-25T06:00:00Z",
          updated_at: "2026-08-25T06:00:00Z",
        }),
      });
    });

    // Inject mock user into sessionStorage before navigating
    await page.addInitScript((mockUser) => {
      sessionStorage.setItem("__CROVIQ_MOCK_USER__", JSON.stringify(mockUser));
      window.__CROVIQ_MOCK_USER__ = mockUser;
    }, MOCK_APPROVED_USER);

    await page.goto("/app");

    // Verify /app loads and displays user identity and workspace
    const logo = page.getByRole("img", { name: "Croviq" });
    await expect(logo).toBeVisible();

    const workspaceName = page.getByText("Croviq Demo Workspace").first();
    await expect(workspaceName).toBeVisible();

    const userName = page.getByText("Fady Nagh").first();
    await expect(userName).toBeVisible();

    const userEmail = page.getByText("fadynagh10@gmail.com").first();
    await expect(userEmail).toBeVisible();

    const apiConnectedBadge = page.getByText("API Connected");
    await expect(apiConnectedBadge).toBeVisible();

    const logoutButton = page.getByRole("button", { name: "Logout" });
    await expect(logoutButton).toBeVisible();

    // Authenticated user navigating to /login or / should auto-redirect to /app
    await page.goto("/login");
    await page.waitForURL("**/app");
    expect(page.url()).toContain("/app");
  });

  test("logout clears application state and returns to /login", async ({ page }) => {
    await page.route("**/api/workspace", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          workspace_id: "ws_demo_fady",
          owner_user_id: MOCK_APPROVED_USER.user_id,
          name: "Croviq Demo Workspace",
          created_at: "2026-08-25T06:00:00Z",
          updated_at: "2026-08-25T06:00:00Z",
        }),
      });
    });

    await page.route("**/api/auth/logout", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });

    // Inject mock user
    await page.addInitScript((mockUser) => {
      sessionStorage.setItem("__CROVIQ_MOCK_USER__", JSON.stringify(mockUser));
      window.__CROVIQ_MOCK_USER__ = mockUser;
    }, MOCK_APPROVED_USER);

    await page.goto("/app");

    const logoutButton = page.getByRole("button", { name: "Logout" });
    await expect(logoutButton).toBeVisible();
    await logoutButton.click();

    // Verify redirected back to /login
    await page.waitForURL("**/login");
    expect(page.url()).toContain("/login");

    const loginHeading = page.getByRole("heading", { name: "Sign in to Croviq" });
    await expect(loginHeading).toBeVisible();
  });
});
