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

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
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

  const domSummary = await page.evaluate(() => {
    const wordBtns = Array.from(document.querySelectorAll("[data-word-index]")).map(el => ({
      index: el.getAttribute("data-word-index"),
      text: el.textContent?.trim(),
      aria: el.getAttribute("aria-label"),
    }));
    return {
      wordBtnCount: wordBtns.length,
      sampleIndices: wordBtns.slice(0, 20).map(w => w.index),
      panelText: document.querySelector("[data-testid='transcript-panel']")?.textContent?.slice(0, 200),
    };
  });

  console.log("DOM Summary:", JSON.stringify(domSummary, null, 2));

  // Let's capture the BEFORE screenshots directly:
  // 1. Original + Transcript
  console.log("4. Original + Transcript screenshot...");
  await page.getByRole("button", { name: /^Original/i }).first().click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-before-original-1600x900.png") });

  // 2. Edited Preview + Transcript
  console.log("5. Edited + Transcript screenshot...");
  await page.locator("[data-testid='preview-toggle-edited']").click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-before-edited-1600x900.png") });

  // 3. Timeline + Transcript visible together
  console.log("6. Timeline + Transcript screenshot...");
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-before-timeline-transcript-1600x900.png") });

  // 4. Cut boundary (around words 5 and 6)
  console.log("7. Cut boundary screenshot...");
  const word5 = page.locator("[data-word-index='5']");
  if (await word5.count() > 0) {
    await word5.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-before-cut-boundary.png") });
  }

  // 5. Word before cut (word 5)
  console.log("8. Word before cut screenshot...");
  const wordBeforeCut = page.locator("[data-word-index='5']");
  await wordBeforeCut.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-before-word-before-cut.png") });

  // 6. Word after cut (word 6)
  console.log("9. Word after cut screenshot...");
  const wordAfterCut = page.locator("[data-word-index='6']");
  await wordAfterCut.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug13-before-word-after-cut.png") });

  // Step 4: Click 10 transcript positions and measure seek in Original mode
  console.log("10. Testing 10 transcript seek positions in Original mode...");
  await page.getByRole("button", { name: /^Original/i }).first().click();
  await page.waitForTimeout(1000);

  const sampleIndices = [5, 16, 28, 39, 50, 61, 72, 84, 95, 106]; // approx 5%, 15%, 25%, 35%, 45%, 55%, 65%, 75%, 85%, 95%
  const seekResults = [];

  for (const idx of sampleIndices) {
    const btn = page.locator(`[data-word-index='${idx}']`);
    if (await btn.count() === 0) {
      console.log(`Word index ${idx} not found in DOM!`);
      continue;
    }
    const txt = await btn.textContent();
    const aria = await btn.getAttribute("aria-label");
    await btn.click();
    await page.waitForTimeout(500);

    const state = await page.evaluate(() => {
      const v = document.querySelector("video");
      const curDisplay = document.querySelector("[data-testid='timecode-current']");
      return {
        videoCurrentTimeSec: v?.currentTime ?? null,
        videoCurrentTimeMs: v ? Math.round(v.currentTime * 1000) : null,
        displayTimecode: curDisplay?.textContent?.trim(),
      };
    });

    seekResults.push({
      wordIndex: idx,
      wordText: txt?.trim(),
      ariaLabel: aria,
      playerCurrentTimeSec: state.videoCurrentTimeSec,
      playerCurrentTimeMs: state.videoCurrentTimeMs,
      displayTimecode: state.displayTimecode,
    });
  }

  console.log("Seek Results (Original):", JSON.stringify(seekResults, null, 2));

  await browser.close();
}

run().catch((err) => {
  console.error("Error in capture_bug13_before:", err);
  process.exit(1);
});
