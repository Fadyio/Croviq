import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "http://localhost:5173";
const TARGET_PROD_ID = "prod_473209137802";
const SCREENSHOT_DIR = path.resolve("docs/screenshots/acceptance");

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
  { name: "1600", width: 1600, height: 900, file: "bug12-editor-1600x900.png" },
  { name: "1440", width: 1440, height: 900, file: "bug12-editor-1440x900.png" },
  { name: "1280", width: 1280, height: 800, file: "bug12-editor-1280x800.png" },
];

async function run() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log("=== Step 9: Responsive Visual Audit (1600x900, 1440x900, 1280x800) ===");
  const browser = await chromium.launch({ headless: true });

  for (const vp of VIEWPORTS) {
    console.log(`\n--- Auditing Viewport ${vp.width}x${vp.height} ---`);
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
    });
    const page = await context.newPage();

    const consoleErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
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

    await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/app*", { timeout: 15000 });

    await page.goto(`${BASE_URL}/productions/${TARGET_PROD_ID}/editor`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
    await page.waitForTimeout(3000);

    const layoutMetrics = await page.evaluate(() => {
      const workspace = document.querySelector("[data-testid='editor-workspace']");
      const videoStage = document.querySelector("[data-testid='video-stage']");
      const bin = document.querySelector("[data-testid='project-bin']");
      const rightPanel = document.querySelector("[data-testid='production-room']");
      const video = document.querySelector("video");

      return {
        workspaceScrollWidth: workspace?.scrollWidth || 0,
        workspaceClientWidth: workspace?.clientWidth || 0,
        hasHorizontalOverflow: (workspace?.scrollWidth || 0) > (workspace?.clientWidth || 0),
        stageWidth: videoStage?.clientWidth || 0,
        stageHeight: videoStage?.clientHeight || 0,
        binWidth: bin?.clientWidth || 0,
        rightPanelWidth: rightPanel?.clientWidth || 0,
        videoVisible: Boolean(video && video.src),
      };
    });

    console.log(`Metrics at ${vp.width}x${vp.height}:`, layoutMetrics);
    const screenshotPath = path.join(SCREENSHOT_DIR, vp.file);
    await page.screenshot({ path: screenshotPath });
    console.log(`Saved screenshot: ${screenshotPath}`);

    if (layoutMetrics.hasHorizontalOverflow) {
      throw new Error(`Accidental horizontal overflow detected at ${vp.width}x${vp.height}!`);
    }
    if (!layoutMetrics.videoVisible) {
      throw new Error(`Video element is not visible or has no source at ${vp.width}x${vp.height}!`);
    }

    await context.close();
  }

  await browser.close();
  console.log("=== Step 9 Responsive Visual Audit Complete ===");
}

run().catch((err) => {
  console.error("Error in Step 9:", err);
  process.exit(1);
});
