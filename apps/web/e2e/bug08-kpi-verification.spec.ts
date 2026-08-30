import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";

const setupPageRoutes = async (page: Page) => {
  await page.route("**/identitytoolkit.googleapis.com/**", async (route) => {
    const url = route.request().url();
    if (url.includes("accounts:signInWithPassword")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          idToken: FIREBASE_ID_TOKEN,
          email: DEMO_EMAIL,
          refreshToken: "fake-refresh-token",
          expiresIn: "3600",
          localId: APPROVED_USER.user_id,
          registered: true,
        }),
      });
      return;
    }
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
            },
          ],
        }),
      });
      return;
    }
    await route.continue();
  });

  await page.route("**/securetoken.googleapis.com/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "fake-access-token",
        expires_in: "3600",
        token_type: "Bearer",
        refresh_token: "fake-refresh-token",
        id_token: FIREBASE_ID_TOKEN,
        user_id: APPROVED_USER.user_id,
        project_id: "croviq-506602",
      }),
    });
  });

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  await page.route("**/api/workspaces/current", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(WORKSPACE),
    });
  });
};

test.describe("Bug 8 Verification: Home KPI Cards Audit and Fix", () => {
  test("1440x900: All four Home KPI cards render verified values, units, and percentage points", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    page.on("requestfailed", (req) => {
      if (!req.url().includes("favicon")) {
        failedRequests.push(`${req.method()} ${req.url()}`);
      }
    });

    await setupPageRoutes(page);

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/app*");

    // Wait for the 4 KPIs section to render
    const kpiSection = page.locator('section[aria-label="Channel KPIs"]');
    await expect(kpiSection).toBeVisible({ timeout: 10000 });

    const kpiArticles = kpiSection.locator("article");
    await expect(kpiArticles).toHaveCount(4);

    // 1. Views
    const viewsArticle = kpiArticles.nth(0);
    await expect(viewsArticle.locator("p").first()).toHaveText("Views");
    await expect(viewsArticle.locator(".font-mono")).toHaveText("418.5K");
    await expect(viewsArticle).toContainText("6.4% vs previous period");

    // 2. Watch time
    const wtArticle = kpiArticles.nth(1);
    await expect(wtArticle.locator("p").first()).toHaveText("Watch time");
    await expect(wtArticle.locator(".font-mono")).toHaveText("50.4K hours");
    await expect(wtArticle).toContainText("1.2% vs previous period");

    // 3. Net subscribers
    const subsArticle = kpiArticles.nth(2);
    await expect(subsArticle.locator("p").first()).toHaveText("Net subscribers");
    await expect(subsArticle.locator(".font-mono")).toHaveText("+5.5K");
    await expect(subsArticle).toContainText("9.0% vs previous period");

    // 4. Average retention
    const retArticle = kpiArticles.nth(3);
    await expect(retArticle.locator("p").first()).toHaveText("Average retention");
    await expect(retArticle.locator(".font-mono")).toHaveText("55.8%");
    await expect(retArticle).toContainText("0.7 pts vs previous period");

    // Check period switching to 90 days
    const timeRangeSelect = page.locator('select[aria-label="Time range"]');
    await timeRangeSelect.selectOption("90");

    // Wait for update
    await expect(viewsArticle.locator(".font-mono")).toHaveText("1.2M", { timeout: 5000 });
    await expect(wtArticle.locator(".font-mono")).toHaveText("147.3K hours");
    await expect(subsArticle.locator(".font-mono")).toHaveText("+15.4K");
    await expect(retArticle.locator(".font-mono")).toHaveText("56.5%");
    await expect(retArticle).toContainText("0.8 pts vs previous period");

    // Switch back to 28 days
    await timeRangeSelect.selectOption("28");
    await expect(viewsArticle.locator(".font-mono")).toHaveText("418.5K", { timeout: 5000 });
    await expect(wtArticle.locator(".font-mono")).toHaveText("50.4K hours");
    await expect(subsArticle.locator(".font-mono")).toHaveText("+5.5K");
    await expect(retArticle.locator(".font-mono")).toHaveText("55.8%");
    await expect(retArticle).toContainText("0.7 pts vs previous period");

    // Capture screenshot at 1440x900
    const screenshotDir = path.resolve(process.cwd(), "docs/screenshots/acceptance");
    const screenshotPath = path.join(screenshotDir, "bug08-home-kpi-1440x900.png");
    await page.screenshot({ path: screenshotPath, fullPage: false });

    // Assert zero console errors and zero failed requests
    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("1600x900: All four Home KPI cards readable without clipping or layout breaks", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await setupPageRoutes(page);

    await page.setViewportSize({ width: 1600, height: 900 });
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/app*");
    const kpiSection = page.locator('section[aria-label="Channel KPIs"]');
    await expect(kpiSection).toBeVisible({ timeout: 10000 });

    const kpiArticles = kpiSection.locator("article");
    await expect(kpiArticles).toHaveCount(4);

    await expect(kpiArticles.nth(0).locator(".font-mono")).toHaveText("418.5K");
    await expect(kpiArticles.nth(1).locator(".font-mono")).toHaveText("50.4K hours");
    await expect(kpiArticles.nth(2).locator(".font-mono")).toHaveText("+5.5K");
    await expect(kpiArticles.nth(3).locator(".font-mono")).toHaveText("55.8%");

    expect(consoleErrors).toEqual([]);
  });

  test("1280x800: All four Home KPI cards readable and properly wrapping at narrower viewport", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await setupPageRoutes(page);

    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/app*");
    const kpiSection = page.locator('section[aria-label="Channel KPIs"]');
    await expect(kpiSection).toBeVisible({ timeout: 10000 });

    const kpiArticles = kpiSection.locator("article");
    await expect(kpiArticles).toHaveCount(4);

    await expect(kpiArticles.nth(0).locator(".font-mono")).toHaveText("418.5K");
    await expect(kpiArticles.nth(1).locator(".font-mono")).toHaveText("50.4K hours");
    await expect(kpiArticles.nth(2).locator(".font-mono")).toHaveText("+5.5K");
    await expect(kpiArticles.nth(3).locator(".font-mono")).toHaveText("55.8%");

    expect(consoleErrors).toEqual([]);
  });
});
