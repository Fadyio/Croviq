import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "http://127.0.0.1:5173";
const SCREENSHOT_DIR = path.resolve("../../docs/screenshots/audit");

function createMockToken(userId = "27iEBUMcu6ToDYwp2OdEIHBuwIA3", email = "demo@croviq.app") {
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

const APPROVED_USER = {
  user_id: "27iEBUMcu6ToDYwp2OdEIHBuwIA3",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const VIEWPORTS = [
  { name: "1600x900", width: 1600, height: 900 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
];

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log("=== Launching Chrome for Phase 1 Live Editor Audit ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleLogs = [];
  const failedRequests = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleLogs.push(msg.text());
      console.log(`[Browser Console Error] ${msg.text()}`);
    }
  });
  page.on("response", (res) => {
    if (res.status() >= 400) {
      console.log(`[API Error ${res.status()}] ${res.request().method()} ${res.url()}`);
    }
  });
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

  // Also mock auth me to return user
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  console.log("Navigating to login...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForURL("**/app*", { timeout: 15000 });
  console.log("Logged in successfully! Current URL:", page.url());

  const productionsToAudit = [
    { id: "prod_acc_demo_1788044745", name: "github-actions" },
    { id: "prod_f0b41bfd429e", name: "fairphone" },
  ];

  for (const prod of productionsToAudit) {
    console.log(`\n========================================`);
    console.log(`AUDITING PRODUCTION: ${prod.name} (${prod.id})`);
    console.log(`========================================`);

    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto(`${BASE_URL}/productions/${prod.id}/editor`, { waitUntil: "networkidle" });
      await page.waitForTimeout(2000);

      const shotPath = path.join(SCREENSHOT_DIR, `audit_${prod.name}_${vp.name}.png`);
      await page.screenshot({ path: shotPath, fullPage: false });
      console.log(`Saved screenshot: ${shotPath}`);

      const summaryText = await page.evaluate(() => {
        const h1 = document.querySelector("h1")?.innerText;
        const timelineStats = document.querySelector(
          "[data-testid='timeline-summary-stats'], .timeline-stats",
        )?.innerText;
        return { h1, timelineStats };
      });
      console.log(`  [${vp.name}] Summary:`, summaryText);
    }
  }

  await browser.close();
  console.log("\n=== Phase 1 Audit Finished ===");
}

main().catch((err) => {
  console.error("Audit failed:", err);
  process.exit(1);
});
