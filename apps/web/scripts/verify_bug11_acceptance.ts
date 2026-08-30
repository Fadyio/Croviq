import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const APP_URL = "http://localhost:5173";
const ACCEPTANCE_DIR = path.resolve(process.cwd(), "docs/screenshots/acceptance");
const E2E_SCREENSHOT_DIR = path.resolve(process.cwd(), "apps/web/e2e/screenshots");

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

const VIEWPORTS = [
  { name: "1600x900", width: 1600, height: 900 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
];

async function main() {
  fs.mkdirSync(ACCEPTANCE_DIR, { recursive: true });
  fs.mkdirSync(E2E_SCREENSHOT_DIR, { recursive: true });

  console.log("=== Launching Chrome for Bug 11 Multi-Resolution Acceptance ===");
  const browser = await chromium.launch({ headless: true });

  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];

  for (const vp of VIEWPORTS) {
    console.log(`\nTesting viewport: ${vp.name} (${vp.width}x${vp.height})`);
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
    });
    const page = await context.newPage();

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(`[${vp.name}] ${msg.text()}`);
        console.error(`[Browser Console Error] ${msg.text()}`);
      }
    });

    page.on("requestfailed", (req) => {
      if (!req.url().includes("favicon")) {
        failedRequests.push(`[${vp.name}] ${req.method()} ${req.url()}`);
        console.error(`[Browser Request Failed] ${req.method()} ${req.url()}`);
      }
    });

    // Mock Firebase auth endpoints
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

    // Navigate to Login and sign in
    await page.goto(`${APP_URL}/login`, { waitUntil: "networkidle" });
    await page.fill('input[type="email"]', DEMO_EMAIL);
    await page.fill('input[type="password"]', "password123");
    await page.click('button[type="submit"]');

    await page.waitForURL("**/app**", { timeout: 10000 });
    const recentSection = page.locator('[aria-labelledby="recent-videos-title"]');
    await recentSection.waitFor({ state: "visible", timeout: 10000 });
    await page.waitForTimeout(500);

    // Save screenshots
    const accShot = path.resolve(ACCEPTANCE_DIR, `bug11-recent-${vp.name}.png`);
    const e2eShot = path.resolve(E2E_SCREENSHOT_DIR, `bug11-after-${vp.name}.png`);
    await recentSection.screenshot({ path: accShot });
    await page.screenshot({ path: e2eShot });
    console.log(`Saved screenshot: ${accShot}`);
    console.log(`Saved full screenshot: ${e2eShot}`);

    // Verify DOM structure on 1440x900
    if (vp.name === "1440x900") {
      const sectionText = await recentSection.innerText();
      console.log("\n--- Section Text (1440x900) ---");
      console.log(sectionText);
      console.log("-------------------------------\n");

      // Verify Header and Subtitle
      if (!sectionText.includes("Recent video performance")) {
        throw new Error("Missing 'Recent video performance' heading");
      }
      if (!sectionText.includes("Compared with your channel's historical median (100 videos)")) {
        throw new Error(
          "Missing 'Compared with your channel's historical median (100 videos)' subtitle",
        );
      }

      // Verify Latest Upload Badge
      const latestBadges = page.locator('text="Latest Upload"');
      const badgeCount = await latestBadges.count();
      if (badgeCount !== 1) {
        throw new Error(`Expected exactly 1 'Latest Upload' badge, found ${badgeCount}`);
      }

      // Verify First Video Identity
      if (!sectionText.includes("Google GenAI SDK Tutorial for Beginners (Part 5)")) {
        throw new Error("Missing latest video title");
      }
      if (!sectionText.includes("Aug 13, 2026")) {
        throw new Error("Missing latest video publish date");
      }

      // Verify Metrics & Deltas
      if (!sectionText.includes("23.3K") || !sectionText.includes("↓ 22% vs channel median")) {
        throw new Error("Views metric or delta mismatch");
      }
      if (!sectionText.includes("33.4%") || !sectionText.includes("↓ 25.6 pts vs channel median")) {
        throw new Error("Retention metric or delta mismatch");
      }
      if (!sectionText.includes("4.3%") || !sectionText.includes("↓ 3.5 pts vs channel median")) {
        throw new Error("CTR metric or delta mismatch");
      }
      if (
        !sectionText.includes("14.3") ||
        !sectionText.includes("+303 net") ||
        !sectionText.includes("↓ 2.4% vs channel median")
      ) {
        throw new Error("Subs/1K metric or delta mismatch");
      }

      // Verify Alex commentary
      if (
        !sectionText.includes("Alex:") ||
        !sectionText.includes(
          "Retention is the main weakness here. The video is 25.6 points below your channel median.",
        )
      ) {
        throw new Error("Alex commentary mismatch");
      }
      if (
        !sectionText.includes("Next:") ||
        !sectionText.includes("Inspect the first 30 seconds for delayed demonstration or setup.")
      ) {
        throw new Error("Next action recommendation mismatch");
      }

      // Verify refresh preserves identical state
      console.log("Refreshing page to test idempotency...");
      await page.reload({ waitUntil: "networkidle" });
      await recentSection.waitFor({ state: "visible", timeout: 10000 });
      const refreshedText = await recentSection.innerText();
      if (refreshedText !== sectionText) {
        throw new Error("Refreshed text differs from initial render");
      }
      console.log("✓ Refresh preserves exact identical results");
    }

    await context.close();
  }

  await browser.close();

  console.log("\n==========================================");
  console.log(`Console Errors: ${consoleErrors.length}`);
  console.log(`Failed Requests: ${failedRequests.length}`);
  console.log("==========================================");

  if (consoleErrors.length > 0) {
    throw new Error(`Encountered browser console errors: ${consoleErrors.join(", ")}`);
  }
  if (failedRequests.length > 0) {
    throw new Error(`Encountered failed requests: ${failedRequests.join(", ")}`);
  }

  console.log("✓ Browser Acceptance Passed with 0 errors!");
}

main().catch((err) => {
  console.error("Acceptance failed:", err);
  process.exit(1);
});
