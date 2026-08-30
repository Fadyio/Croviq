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

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
  const page = await context.newPage();

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
  await page.goto(`${BASE_URL}/productions/prod_acc_demo_1788044745/editor`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2000);

  // Click Transcript tab
  console.log("Clicking Transcript tab...");
  const transcriptTabBtn = page.getByRole("button", { name: "Transcript" });
  await transcriptTabBtn.click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "audit_github_transcript.png") });
  console.log("Saved audit_github_transcript.png");

  // Click a cut in the timeline to inspect Decision Inspector
  console.log("Clicking a timeline cut block...");
  const cutBlock = page
    .locator("[data-block-type='cut-safe'], .twick-block, [data-testid='timeline-block']")
    .first();
  if ((await cutBlock.count()) > 0) {
    await cutBlock.click({ force: true });
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "audit_github_decision_inspector.png"),
    });
    console.log("Saved audit_github_decision_inspector.png");
  }

  await browser.close();
}

main().catch(console.error);
