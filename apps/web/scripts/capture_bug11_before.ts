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

  console.log("=== Launching Chrome to inspect Bug 11 BEFORE state ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
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

  // Mock Firebase auth routes
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
        refresh_token: "mock-refresh-token",
        id_token: FIREBASE_ID_TOKEN,
        user_id: APPROVED_USER.user_id,
        project_id: "croviq-506602",
      }),
    });
  });

  // Navigate to login
  await page.goto(`${APP_URL}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', DEMO_EMAIL);
  await page.fill('input[type="password"]', "password123");
  await page.click('button[type="submit"]');

  await page.waitForURL("**/app**", { timeout: 10000 });
  await page.waitForSelector('[aria-labelledby="recent-videos-title"]', { timeout: 10000 });
  await page.waitForTimeout(1000);

  // Take screenshot of Recent Video Performance
  const recentSection = page.locator('[aria-labelledby="recent-videos-title"]');
  const screenshotPath = path.resolve(SCREENSHOT_DIR, "bug11-recent-video-performance-before.png");
  await recentSection.screenshot({ path: screenshotPath });
  console.log(`Saved before screenshot to ${screenshotPath}`);

  // Also take full page screenshot at 1440x900
  await page.screenshot({ path: path.resolve(SCREENSHOT_DIR, "bug11-home-before-1440x900.png") });

  // Extract all text content from the Recent Video Performance section
  const sectionText = await recentSection.innerText();
  console.log("\n--- RECENT VIDEO PERFORMANCE TEXT CONTENT ---");
  console.log(sectionText);
  console.log("---------------------------------------------\n");

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
