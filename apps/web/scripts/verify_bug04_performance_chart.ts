import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const APP_URL = "http://localhost:5173";
const SCREENSHOT_DIR = path.resolve(process.cwd(), "../../docs/screenshots/acceptance");

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

  console.log("=== Launching Chrome to test Bug 4 Home Performance Chart ===");
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

  // Mock Firebase auth token response
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

  // Wait for dashboard to load and chart to render
  await page.waitForSelector('[aria-label="Channel Performance"]', { timeout: 15000 });
  await page.waitForTimeout(1000); // allow chart canvas to finish rendering

  const chartSection = page.locator('[aria-label="Channel Performance"]');
  await chartSection.scrollIntoViewIfNeeded();

  // 1. Views — 1600x900
  console.log("Testing 1600x900 Views...");
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.waitForTimeout(500);
  const shot1600 = path.join(SCREENSHOT_DIR, "views-1600.png");
  await chartSection.screenshot({ path: shot1600 });
  console.log("Saved:", shot1600);

  // 2. Views — 1440x900
  console.log("Testing 1440x900 Views...");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);
  const shot1440 = path.join(SCREENSHOT_DIR, "views-1440.png");
  await chartSection.screenshot({ path: shot1440 });
  console.log("Saved:", shot1440);

  // 3. Views — 1280x800
  console.log("Testing 1280x800 Views...");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(500);
  const shot1280 = path.join(SCREENSHOT_DIR, "views-1280.png");
  await chartSection.screenshot({ path: shot1280 });
  console.log("Saved:", shot1280);

  // Set back to 1440x900 for switching metrics and tooltip
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);

  // 4. Watch time — 1440x900
  console.log("Switching to Watch time...");
  await chartSection.getByRole("tab", { name: "Watch time" }).click();
  await page.waitForTimeout(500);
  const shotWatch1440 = path.join(SCREENSHOT_DIR, "watch-time-1440.png");
  await chartSection.screenshot({ path: shotWatch1440 });
  console.log("Saved:", shotWatch1440);
  // 5. Subscribers — 1440x900
  console.log("Switching to Subscribers...");
  await chartSection.getByRole("tab", { name: "Subscribers" }).click();
  await page.waitForTimeout(500);
  const shotSubs1440 = path.join(SCREENSHOT_DIR, "subscribers-1440.png");
  await chartSection.screenshot({ path: shotSubs1440 });
  console.log("Saved:", shotSubs1440);

  // 6. Tooltip — 1440x900 (Switch back to Views and hover middle point)
  console.log("Testing Tooltip on Views...");
  await chartSection.getByRole("tab", { name: "Views" }).click();
  await page.waitForTimeout(500);

  // Find canvas element inside chart
  const canvas = chartSection.locator("canvas").first();
  const box = await canvas.boundingBox();
  if (box) {
    // Move mouse in steps across canvas
    await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.5);
    await page.waitForTimeout(500);
  }
  // Also dispatch echarts showTip to guarantee tooltip is visible
  await page.evaluate(() => {
    const dom = document.querySelector('[aria-label="Channel Performance"] [role="img"]') as any;
    if (dom?.__echarts_instance__) {
      dom.__echarts_instance__.dispatchAction({
        type: "showTip",
        dataIndex: 15,
        seriesIndex: 0,
      });
    }
  });
  await page.waitForTimeout(600);
  const shotTooltip1440 = path.join(SCREENSHOT_DIR, "tooltip-1440.png");
  await chartSection.screenshot({ path: shotTooltip1440 });
  console.log("Saved:", shotTooltip1440);

  await browser.close();

  console.log("\n=== VERIFICATION RESULTS ===");
  console.log("Console Errors:", consoleErrors.length);
  console.log("Failed Requests:", failedRequests.length);
  console.log("1600 Screenshot:", shot1600);
  console.log("1440 Screenshot:", shot1440);
  console.log("1280 Screenshot:", shot1280);
  console.log("Watch Time Screenshot:", shotWatch1440);
  console.log("Subscribers Screenshot:", shotSubs1440);
  console.log("Tooltip Screenshot:", shotTooltip1440);
}

main().catch((err) => {
  console.error("Error during verification:", err);
  process.exit(1);
});
