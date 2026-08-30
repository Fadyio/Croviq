import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const APP_URL = "http://localhost:5173";
const SCREENSHOT_DIR = path.resolve(process.cwd(), "docs/screenshots/acceptance");

const DEMO_EMAIL = "demo@croviq.app";
const APPROVED_USER = {
  user_id: "demo_user_123",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

function createMockToken(userId = "demo_user_123", email = DEMO_EMAIL) {
  const header = { alg: "none", typ: "JWT" };
  const payload = {
    iss: "https://securetoken.google.com/croviq-506602",
    aud: "croviq-506602",
    auth_time: 1,
    user_id: userId,
    sub: userId,
    iat: 1,
    exp: 4102444800,
    email: email,
    email_verified: true,
    firebase: { identities: { email: [email] }, sign_in_provider: "password" },
  };
  return `${Buffer.from(JSON.stringify(header)).toString("base64url")}.${Buffer.from(JSON.stringify(payload)).toString("base64url")}.signature`;
}
const FIREBASE_ID_TOKEN = createMockToken();

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log("=== Launching Chrome to test Bug 5 Ideas Worth Making ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
      console.log(`[Browser Console Error] ${msg.text()}`);
    }
  });

  page.on("requestfailed", (req) => {
    if (!req.url().includes("favicon")) {
      failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText})`);
      console.log(`[Browser Request Failed] ${req.method()} ${req.url()}`);
    }
  });

  // Mock Firebase auth token responses
  await page.route("**/identitytoolkit.googleapis.com/**", async (route) => {
    const url = route.request().url();
    if (url.includes("accounts:signInWithPassword")) {
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
    } else if (url.includes("accounts:lookup")) {
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
    } else {
      await route.continue();
    }
  });

  await page.route("**/securetoken.googleapis.com/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: FIREBASE_ID_TOKEN,
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

  console.log("Navigating to login page...");
  await page.goto(`${APP_URL}/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForURL("**/app*", { timeout: 20000 });
  console.log("Authenticated! On /app page.");

  // Wait for AlexRail to load
  await page.waitForSelector("aside", { timeout: 15000 });
  await page.waitForTimeout(1000);

  // 1. Home — 1600x900
  console.log("Capturing 1600x900 Home...");
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.waitForTimeout(500);
  const shot1600 = path.join(SCREENSHOT_DIR, "home-1600x900.png");
  await page.screenshot({ path: shot1600 });
  console.log("Saved:", shot1600);

  // 2. Home — 1440x900
  console.log("Capturing 1440x900 Home...");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);
  const shot1440 = path.join(SCREENSHOT_DIR, "home-1440x900.png");
  await page.screenshot({ path: shot1440 });
  console.log("Saved:", shot1440);

  // 3. Home — 1280x800
  console.log("Capturing 1280x800 Home...");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(500);
  const shot1280 = path.join(SCREENSHOT_DIR, "home-1280x800.png");
  await page.screenshot({ path: shot1280 });
  console.log("Saved:", shot1280);

  // 4. All Findings Drawer — 1440x900
  console.log("Capturing All Findings Drawer at 1440x900...");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);

  const viewAllBtn = page.getByRole("button", { name: /View all .* findings/i });
  if (await viewAllBtn.isVisible()) {
    await viewAllBtn.click();
    await page.waitForSelector('[role="dialog"][aria-label="Ideas Worth Making"], [role="dialog"]', { timeout: 5000 });
    await page.waitForTimeout(500);
    const shotDrawer = path.join(SCREENSHOT_DIR, "all-findings-1440x900.png");
    await page.screenshot({ path: shotDrawer });
    console.log("Saved:", shotDrawer);
  } else {
    console.log("View all findings button not visible (<=3 findings), capturing rail close-up instead.");
    const rail = page.locator("aside");
    const shotDrawer = path.join(SCREENSHOT_DIR, "all-findings-1440x900.png");
    await rail.screenshot({ path: shotDrawer });
    console.log("Saved:", shotDrawer);
  }

  // Extract findings text from page to verify content
  const cardEntities = await page.locator('aside article span.uppercase').allTextContents();
  const cardTitles = await page.locator('aside article h4').allTextContents();

  console.log("\n=== VISIBLE TOP CARDS ===");
  console.log("Primary Entities:", cardEntities);
  console.log("Titles:", cardTitles);

  await browser.close();

  console.log("\n=== VERIFICATION RESULTS ===");
  console.log("Console Errors:", consoleErrors.length);
  console.log("Failed Requests:", failedRequests.length);
  console.log("1600 Screenshot:", shot1600);
  console.log("1440 Screenshot:", shot1440);
  console.log("1280 Screenshot:", shot1280);
}

main().catch((err) => {
  console.error("Error during verification:", err);
  process.exit(1);
});
