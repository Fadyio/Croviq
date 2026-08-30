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

async function run() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log("=== Step 11: Real Acceptance Run (Chrome Live Stack) ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const failedRequests = [];
  const apiResponses = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
      console.log(`[Console Error] ${msg.text()}`);
    }
  });

  page.on("requestfailed", (req) => {
    failedRequests.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
    console.log(`[Request Failed] ${req.method()} ${req.url()}`);
  });

  page.on("response", (res) => {
    if (res.url().includes("/api/")) {
      apiResponses.push({
        status: res.status(),
        method: res.request().method(),
        url: res.url(),
      });
      if (res.status() >= 400) {
        failedRequests.push(`HTTP ${res.status()} on ${res.request().method()} ${res.url()}`);
      }
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

  console.log("1. Logging in with credentials...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*", { timeout: 15000 });

  console.log("2. Navigating to New Project -> Recent Projects...");
  await page.goto(`${BASE_URL}/projects/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("section[aria-labelledby='recent-projects-heading']", {
    timeout: 15000,
  });

  console.log(`3. Opening ${TARGET_PROD_ID}...`);
  await page.goto(`${BASE_URL}/productions/${TARGET_PROD_ID}/editor`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForSelector("[data-testid='video-stage']", { timeout: 60000 });
  await page.waitForTimeout(3000);

  const getMediaDetails = async (modeName) => {
    return await page.evaluate((mode) => {
      const video = document.querySelector("video");
      const durationDisplay = document.querySelector("[data-testid='timecode-duration']");
      const currentDisplay = document.querySelector("[data-testid='timecode-current']");
      const cutBadge = document.querySelector("[data-testid='preview-toggle-edited'] .font-mono");
      return {
        mode,
        videoSrc: video?.src ? video.src.slice(0, 75) + "..." : null,
        videoDuration: video?.duration || null,
        videoCurrentTime: video?.currentTime || null,
        videoPaused: video?.paused ?? null,
        timecodeCurrent: currentDisplay?.textContent?.trim() || "",
        timecodeDuration: durationDisplay?.textContent?.trim() || "",
        cutCount: cutBadge?.textContent?.trim() || "",
      };
    }, modeName);
  };

  const results = {};

  // Inspect Original
  console.log("\n4. Testing Mode: Original");
  await page
    .getByRole("button", { name: /^Original$/i })
    .first()
    .click();
  await page.waitForTimeout(2000);
  results.original = await getMediaDetails("Original");
  console.log("Original:", results.original);

  // Inspect Edited Preview
  console.log("\n5. Testing Mode: Edited Preview");
  await page
    .getByRole("button", { name: /Edited Preview/i })
    .first()
    .click();
  await page.waitForTimeout(2000);
  results.edited = await getMediaDetails("Edited Preview");
  console.log("Edited Preview:", results.edited);

  // Inspect Voiceover Preview
  console.log("\n6. Testing Mode: Voiceover Preview");
  await page
    .getByRole("button", { name: /Voiceover Preview/i })
    .first()
    .click();
  await page.waitForTimeout(2000);
  results.voiceover = await getMediaDetails("Voiceover Preview");
  console.log("Voiceover Preview:", results.voiceover);

  // Inspect Final Mix
  console.log("\n7. Testing Mode: Final Mix");
  await page
    .getByRole("button", { name: /Final Mix/i })
    .first()
    .click();
  await page.waitForTimeout(2000);
  results.final_mix = await getMediaDetails("Final Mix");
  console.log("Final Mix:", results.final_mix);

  // Capture acceptance screenshots
  console.log("\n8. Capturing final acceptance screenshots...");
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "bug12-acceptance-finalmix-1600x900.png"),
  });

  await page
    .getByRole("button", { name: /^Original$/i })
    .first()
    .click();
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "bug12-acceptance-original-1600x900.png"),
  });

  await page
    .getByRole("button", { name: /Edited Preview/i })
    .first()
    .click();
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "bug12-acceptance-edited-1600x900.png"),
  });

  console.log("\n=== REAL ACCEPTANCE RESULTS SUMMARY ===");
  console.log("Console Errors:", consoleErrors);
  console.log("Failed Requests:", failedRequests);
  console.log("Mode Details:", JSON.stringify(results, null, 2));

  await browser.close();
  console.log("=== Step 11 Completed Successfully ===");
}

run().catch((err) => {
  console.error("Error in Step 11:", err);
  process.exit(1);
});
