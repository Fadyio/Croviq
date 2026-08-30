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

  console.log("=== BUG 13: Full Live Browser Acceptance Run ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const failedRequests = [];

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

  console.log("1. Logging in...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*", { timeout: 15000 });

  console.log(`2. Opening ${TARGET_PROD_ID}...`);
  await page.goto(`${BASE_URL}/productions/${TARGET_PROD_ID}/editor`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForSelector("[data-testid='video-stage']", { timeout: 60000 });
  await page.waitForTimeout(2000);

  console.log("3. Switching to TRANSCRIPT tab...");
  await page.click("[data-testid='tab-transcript']");
  await page.waitForSelector("[data-testid='transcript-panel']", { timeout: 15000 });
  await page.waitForTimeout(1000);

  // STEP 4: Source Mode Acceptance (10 positions across video: 5%, 15%, 25%, 35%, 45%, 55%, 65%, 75%, 85%, 95%)
  console.log("\n=== STEP 4: AUDIT ORIGINAL MODE SEEK (10 POSITIONS) ===");
  await page.getByRole("button", { name: /^Original/i }).first().click();
  await page.waitForTimeout(1000);

  const sampleIndices = [5, 16, 28, 39, 50, 61, 72, 84, 95, 106];
  const originalSeekAudit = [];

  for (const idx of sampleIndices) {
    const btn = page.locator(`[data-word-index='${idx}']`);
    const txt = (await btn.textContent())?.trim();
    await btn.click();
    await page.waitForTimeout(400);

    const playerState = await page.evaluate(() => {
      const v = document.querySelector("video");
      const curDisplay = document.querySelector("[data-testid='timecode-current']");
      return {
        videoCurrentTimeSec: v?.currentTime ?? 0,
        videoCurrentTimeMs: v ? Math.round(v.currentTime * 1000) : 0,
        displayTimecode: curDisplay?.textContent?.trim() || "",
      };
    });

    const wordInfo = await page.evaluate((wordIdx) => {
      const b = document.querySelector(`[data-word-index='${wordIdx}']`);
      const aria = b?.getAttribute("aria-label") || "";
      return { aria };
    }, idx);

    originalSeekAudit.push({
      wordIndex: idx,
      wordText: txt,
      aria: wordInfo.aria,
      playerCurrentTimeSec: playerState.videoCurrentTimeSec,
      playerCurrentTimeMs: playerState.videoCurrentTimeMs,
      displayTimecode: playerState.displayTimecode,
    });
  }

  console.log("Original Mode 10-point Seek Audit:", JSON.stringify(originalSeekAudit, null, 2));

  // STEP 5: Cut Boundary Acceptance (Original vs Edited)
  console.log("\n=== STEP 5: AUDIT CUT BOUNDARIES & REMOVED WORDS ===");
  console.log("5a. Original Mode: Clicking removed Word 15 ('To')...");
  const word15Btn = page.locator("[data-word-index='15']");
  await word15Btn.click();
  await page.waitForTimeout(400);
  const origWord15Seek = await page.evaluate(() => {
    const v = document.querySelector("video");
    return {
      sec: v?.currentTime ?? 0,
      ms: v ? Math.round(v.currentTime * 1000) : 0,
    };
  });
  console.log("Word 15 Seek in Original (expected ~16200ms / 16.2s):", origWord15Seek);

  // Switch to Edited Mode
  console.log("5b. Switching to Edited Preview Mode...");
  await page.locator("[data-testid='preview-toggle-edited']").click();
  await page.waitForTimeout(1000);

  // Check Word 15 in Edited Mode (should be styled as removed / line-through)
  const isWord15Removed = await page.evaluate(() => {
    const b = document.querySelector("[data-word-index='15']");
    return {
      hasDataRemoved: b?.getAttribute("data-removed") === "true",
      className: b?.className || "",
    };
  });
  console.log("Word 15 in Edited Mode:", isWord15Removed);

  // Click Word 15 in Edited Mode -> should show Removed Word Notice
  console.log("5c. Clicking Word 15 in Edited Mode (should show removed notice)...");
  await word15Btn.click();
  await page.waitForTimeout(500);
  const removedNotice = await page.evaluate(() => {
    const n = document.querySelector("[data-testid='removed-word-notice']");
    return {
      visible: Boolean(n),
      text: n?.textContent?.trim() || null,
    };
  });
  console.log("Removed Word Notice:", removedNotice);

  // Click Word 17 ("to" [22700-22900ms], post-cut C)
  console.log("5d. Clicking Word 17 ('to') post-cut in Edited Mode...");
  const word17Btn = page.locator("[data-word-index='17']");
  await word17Btn.click();
  await page.waitForTimeout(500);
  const editedWord17Seek = await page.evaluate(() => {
    const v = document.querySelector("video");
    return {
      sec: v?.currentTime ?? 0,
      ms: v ? Math.round(v.currentTime * 1000) : 0,
    };
  });
  console.log("Word 17 Seek in Edited (expected ~11250ms / 11.25s):", editedWord17Seek);

  // STEP 8 & 9: Player / Timeline synchronization
  console.log("\n=== STEP 8 & 9: TIMELINE / PLAYER -> TRANSCRIPT SYNCHRONIZATION ===");
  await page.getByRole("button", { name: /^Original/i }).first().click();
  await page.waitForTimeout(500);

  await page.evaluate(() => {
    const v = document.querySelector("video");
    if (v) {
      v.currentTime = 30.9;
      v.dispatchEvent(new Event("timeupdate"));
    }
  });
  await page.waitForTimeout(500);

  const activeWordAt30s = await page.evaluate(() => {
    const activeBtn = document.querySelector("[data-word-index].bg-primary");
    return {
      index: activeBtn?.getAttribute("data-word-index"),
      text: activeBtn?.textContent?.trim(),
    };
  });
  console.log("Active Word when playing at 30.9s (Original):", activeWordAt30s);

  // STEP 13: Capture AFTER Screenshots across Viewports (1600x900, 1440x900, 1280x800)
  console.log("\n=== STEP 13: CAPTURE AFTER SCREENSHOTS ===");

  // 1600x900: Original
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.getByRole("button", { name: /^Original/i }).first().click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-after-original-1600x900.png") });

  // 1600x900: Edited
  await page.locator("[data-testid='preview-toggle-edited']").click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-after-edited-1600x900.png") });

  // 1600x900: Cut Boundary / Removed Word
  await word15Btn.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-after-cut-boundary-1600x900.png") });

  // 1440x900
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-after-editor-1440x900.png") });

  // 1280x800
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-after-editor-1280x800.png") });

  await browser.close();

  console.log("\n=== VERIFICATION SUMMARY ===");
  console.log(`Console errors count: ${consoleErrors.length}`);
  console.log(`Failed requests count: ${failedRequests.length}`);
  console.log("All AFTER screenshots captured successfully.");
}

run().catch((err) => {
  console.error("Error in run_bug13_real_acceptance:", err);
  process.exit(1);
});
