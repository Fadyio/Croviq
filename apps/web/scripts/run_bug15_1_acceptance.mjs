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

const APPROVED_USER = {
  user_id: "27iEBUMcu6ToDYwp2OdEIHBuwIA3",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const FIREBASE_ID_TOKEN = createMockToken();

async function inspectVideo(page) {
  return await page.evaluate(() => {
    const video = document.querySelector("video");
    const errorOverlay = document.querySelector('[data-testid="video-error-overlay"]');
    const unavailableCard = document.querySelector('[data-testid="media-unavailable-card"]');
    const stage = document.querySelector('[data-testid="video-stage"]');
    return {
      hasVideoStage: !!stage,
      hasVideo: !!video,
      src: video?.src || null,
      currentSrc: video?.currentSrc || null,
      readyState: video?.readyState ?? null,
      error: video?.error ? { code: video.error.code, message: video.error.message } : null,
      duration: video?.duration ?? null,
      currentTime: video?.currentTime ?? null,
      paused: video?.paused ?? null,
      errorOverlayText: errorOverlay ? errorOverlay.textContent : null,
      unavailableCardText: unavailableCard ? unavailableCard.textContent : null,
    };
  });
}

async function playAndObserveAdvance(page, durationMs = 3000) {
  const startTime = await page.evaluate(async () => {
    const video = document.querySelector("video");
    if (!video) throw new Error("No video element found");
    if (video.paused) {
      await video.play();
    }
    return video.currentTime;
  });

  await page.waitForTimeout(durationMs);

  const endTime = await page.evaluate(() => {
    const video = document.querySelector("video");
    return video ? video.currentTime : null;
  });

  return { startTime, endTime, advanced: endTime > startTime };
}

async function seekVideo(page, targetSec) {
  return await page.evaluate((sec) => {
    const video = document.querySelector("video");
    if (!video) throw new Error("No video element found");
    video.currentTime = sec;
    return video.currentTime;
  }, targetSec);
}

async function run() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  console.log("==================================================");
  console.log("RUNNING BUG 15.1 FULL REAL CHROMIUM ACCEPTANCE");
  console.log("==================================================");

  let videoState;

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
      console.log(`[Browser Console Error] ${msg.text()}`);
    }
  });

  page.on("requestfailed", (req) => {
    failedRequests.push({ url: req.url(), failure: req.failure()?.errorText });
  });

  page.on("response", async (res) => {
    const url = res.url();
    if (res.status() >= 400 && (url.includes("/api/") || url.includes("storage.googleapis.com"))) {
      console.log(`[HTTP ${res.status()}] ${url.slice(0, 110)}`);
    }
  });

  // Mock Firebase auth identitytoolkit endpoints
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

  // Mock Firebase securetoken refresh endpoint
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

  console.log("\n1. Logging in via /login...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*", { timeout: 15000 });

  console.log("2. Navigating client-side to Editor for:", TARGET_PROD_ID);
  await page.evaluate((prodId) => {
    window.history.pushState(null, "", `/productions/${prodId}/editor`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, TARGET_PROD_ID);

  console.log("3. Waiting for video stage...");
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(1000);
    const hasStage = await page.evaluate(
      () => !!document.querySelector('[data-testid="video-stage"]'),
    );
    if (hasStage) {
      console.log(`Video stage mounted at tick ${i}!`);
      break;
    }
  }
  await page.waitForTimeout(2000);

  // Switch to Edited Preview mode
  const editedBtn = page
    .getByRole("button", { name: "Edited Preview" })
    .or(page.locator('button:has-text("Edited Preview")'))
    .first();
  if (await editedBtn.isVisible()) {
    await editedBtn.click();
    console.log("Switched to Edited Preview mode.");
    await page.waitForTimeout(1000);
  }

  videoState = await inspectVideo(page);
  console.log("\nInitial Edited Preview Video State:");
  console.log(
    `- hasVideo: ${videoState.hasVideo}, readyState: ${videoState.readyState}, error: ${videoState.error}, duration: ${videoState.duration}`,
  );

  // ----------------------------------------------------
  // STEP 8 — CUT ACCEPTANCE
  // ----------------------------------------------------
  console.log("\n==================================================");
  console.log("STEP 8 — CUT ACCEPTANCE: 'Cut this.' (approx 00:31.13 -> 00:34.00)");
  console.log("==================================================");

  // Select on transcript (Seg 04: 30.70s -> 48.10s)
  console.log(
    "Selecting Seg 04 (30.7s -> 48.1s: 'You can find here the name of the workflow...') on transcript...",
  );
  const transcriptTab = page.getByRole("tab", { name: /transcript/i });
  await transcriptTab.click();
  await page.waitForTimeout(800);

  const origBtn = page.getByRole("button", { name: "Original Transcript" });
  if (await origBtn.isVisible()) {
    await origBtn.click();
    await page.waitForTimeout(600);
  }

  const sentenceBtns = page.locator('button[title*="Select sentence"]');
  if ((await sentenceBtns.count()) > 4) {
    await sentenceBtns.nth(4).click();
    console.log("Clicked sentence button 4 (30.7s -> 48.1s) for Cut.");
  }
  await page.waitForTimeout(600);

  // Open Leo Chat
  const chatTab = page.getByRole("tab", { name: /chat|leo/i });
  await chatTab.click();
  await page.waitForTimeout(800);

  const hasAttachment = await page
    .locator('[data-testid="leo-chat-selection-attachment"]')
    .isVisible();
  console.log(`Selection attachment attached in chat: ${hasAttachment}`);

  const chatInput = page.locator("#leo-chat-input");
  await chatInput.fill("Cut this.");
  console.log("Sending 'Cut this.' to Leo...");
  await chatInput.press("Enter");

  console.log("Waiting for Leo cut mutation response & FFmpeg render...");
  const chatRes1 = await page.waitForResponse(
    (res) => res.url().includes("/api/productions/") && res.url().includes("/chat"),
    { timeout: 120000 },
  );
  const chatJson1 = await chatRes1.json();
  console.log("Leo reply:", chatJson1.content);
  console.log(
    `New EDL ID: ${chatJson1.edl?.edl_id} (version: ${chatJson1.edl?.version}, cuts: ${chatJson1.edl?.cuts?.length})`,
  );

  console.log("Waiting for video player to refresh with new render artifact...");
  await page.waitForTimeout(8000);

  videoState = await inspectVideo(page);
  console.log("\nPost-Cut Video State:");
  console.log(`- hasVideo: ${videoState.hasVideo}`);
  console.log(`- readyState: ${videoState.readyState}`);
  console.log(`- error: ${JSON.stringify(videoState.error)}`);
  console.log(`- duration: ${videoState.duration}`);
  console.log(`- errorOverlay: ${videoState.errorOverlayText}`);
  console.log(`- unavailableCard: ${videoState.unavailableCardText}`);

  // Screenshot 2: After cut — video visibly rendered
  const shotCutRendered = path.join(SCREENSHOT_DIR, "bug15_1_after_cut_rendered_1600x900.png");
  await page.screenshot({ path: shotCutRendered, fullPage: false });
  console.log(`Saved screenshot: ${shotCutRendered}`);

  // Seek before cut, play across cut seam, observe time advance
  console.log("Testing playback across cut seam...");
  await seekVideo(page, 15.0);
  const cutPlayAdvance = await playAndObserveAdvance(page, 3000);
  console.log(
    `Play advance: start=${cutPlayAdvance.startTime.toFixed(2)}s -> end=${cutPlayAdvance.endTime.toFixed(2)}s, advanced=${cutPlayAdvance.advanced}`,
  );

  // Screenshot 3: After cut — actively playing
  const shotCutPlaying = path.join(SCREENSHOT_DIR, "bug15_1_after_cut_playing_1600x900.png");
  await page.screenshot({ path: shotCutPlaying, fullPage: false });
  console.log(`Saved screenshot (Cut Playing): ${shotCutPlaying}`);

  // ----------------------------------------------------
  // STEP 9 — TIGHTEN ACCEPTANCE
  // ----------------------------------------------------
  console.log("\n==================================================");
  console.log("STEP 9 — TIGHTEN ACCEPTANCE: 'Make this tighter.'");
  console.log("==================================================");

  // Select section on transcript for tightening (Seg 03: 16.2s -> 29.0s)
  console.log("Selecting Seg 03 on transcript for tightening...");
  await transcriptTab.click();
  await page.waitForTimeout(800);
  if (await origBtn.isVisible()) {
    await origBtn.click();
    await page.waitForTimeout(500);
  }
  if ((await sentenceBtns.count()) > 3) {
    await sentenceBtns.nth(3).click();
    console.log("Clicked sentence button 3 for tightening.");
  }
  await chatTab.click();
  await page.waitForTimeout(800);

  await chatInput.fill("Make this tighter.");
  console.log("Sending 'Make this tighter.' to Leo...");
  await chatInput.press("Enter");

  console.log("Waiting for Leo tighten response & FFmpeg render...");
  const chatRes2 = await page.waitForResponse(
    (res) => res.url().includes("/api/productions/") && res.url().includes("/chat"),
    { timeout: 120000 },
  );
  const chatJson2 = await chatRes2.json();
  console.log("Leo reply:", chatJson2.content);
  console.log(
    `Tighten EDL ID: ${chatJson2.edl?.edl_id} (version: ${chatJson2.edl?.version}, cuts: ${chatJson2.edl?.cuts?.length})`,
  );

  console.log("Waiting for video player to refresh with tighten artifact...");
  await page.waitForTimeout(8000);

  const tightenVideoState = await inspectVideo(page);
  console.log("\nPost-Tighten Video State:");
  console.log(
    `- readyState: ${tightenVideoState.readyState}, error: ${tightenVideoState.error}, duration: ${tightenVideoState.duration}`,
  );

  console.log("Testing playback on tightened preview...");
  await seekVideo(page, 5.0);
  const tightenPlayAdvance = await playAndObserveAdvance(page, 3000);
  console.log(
    `Tighten Play advance: start=${tightenPlayAdvance.startTime.toFixed(2)}s -> end=${tightenPlayAdvance.endTime.toFixed(2)}s, advanced=${tightenPlayAdvance.advanced}`,
  );

  // Screenshot 4: After tighten — actively playing
  const shotTightenPlaying = path.join(
    SCREENSHOT_DIR,
    "bug15_1_after_tighten_playing_1600x900.png",
  );
  await page.screenshot({ path: shotTightenPlaying, fullPage: false });
  console.log(`Saved screenshot (Tighten Playing): ${shotTightenPlaying}`);

  // ----------------------------------------------------
  // STEP 10 — UNDO ACCEPTANCE
  // ----------------------------------------------------
  console.log("\n==================================================");
  console.log("STEP 10 — UNDO ACCEPTANCE: 'Undo that.'");
  console.log("==================================================");

  await chatInput.fill("Undo that.");
  console.log("Sending 'Undo that.' to Leo...");
  await chatInput.press("Enter");

  console.log("Waiting for Leo undo response & preview restoration...");
  const chatRes3 = await page.waitForResponse(
    (res) => res.url().includes("/api/productions/") && res.url().includes("/chat"),
    { timeout: 120000 },
  );
  const chatJson3 = await chatRes3.json();
  console.log("Leo reply:", chatJson3.content);
  console.log(
    `Undo EDL ID: ${chatJson3.edl?.edl_id} (version: ${chatJson3.edl?.version}, cuts: ${chatJson3.edl?.cuts?.length})`,
  );

  console.log("Waiting for restored video preview...");
  await page.waitForTimeout(8000);

  const undoVideoState = await inspectVideo(page);
  console.log("\nPost-Undo Video State:");
  console.log(
    `- readyState: ${undoVideoState.readyState}, error: ${undoVideoState.error}, duration: ${undoVideoState.duration}`,
  );

  console.log("Testing playback on restored preview...");
  await seekVideo(page, 10.0);
  const undoPlayAdvance = await playAndObserveAdvance(page, 3000);
  console.log(
    `Undo Play advance: start=${undoPlayAdvance.startTime.toFixed(2)}s -> end=${undoPlayAdvance.endTime.toFixed(2)}s, advanced=${undoPlayAdvance.advanced}`,
  );

  // Screenshot 5: After undo — actively playing
  const shotUndoPlaying = path.join(SCREENSHOT_DIR, "bug15_1_after_undo_playing_1600x900.png");
  await page.screenshot({ path: shotUndoPlaying, fullPage: false });
  console.log(`Saved screenshot (Undo Playing): ${shotUndoPlaying}`);

  // ----------------------------------------------------
  // HARD REFRESH ACCEPTANCE
  // ----------------------------------------------------
  console.log("\n==================================================");
  console.log("HARD REFRESH ACCEPTANCE");
  console.log("==================================================");

  console.log("Hard refreshing browser page...");
  await page.reload({ waitUntil: "domcontentloaded" });
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(1000);
    const hasStage = await page.evaluate(
      () => !!document.querySelector('[data-testid="video-stage"]'),
    );
    if (hasStage) break;
  }
  await page.waitForTimeout(3000);

  const refreshVideoState = await inspectVideo(page);
  console.log("\nPost-Refresh Video State:");
  console.log(
    `- readyState: ${refreshVideoState.readyState}, error: ${refreshVideoState.error}, duration: ${refreshVideoState.duration}`,
  );

  console.log("Testing playback after hard refresh...");
  await seekVideo(page, 8.0);
  const refreshPlayAdvance = await playAndObserveAdvance(page, 3000);
  console.log(
    `Refresh Play advance: start=${refreshPlayAdvance.startTime.toFixed(2)}s -> end=${refreshPlayAdvance.endTime.toFixed(2)}s, advanced=${refreshPlayAdvance.advanced}`,
  );

  // Screenshot 6: After refresh — actively playing
  const shotRefreshPlaying = path.join(
    SCREENSHOT_DIR,
    "bug15_1_after_refresh_playing_1600x900.png",
  );
  await page.screenshot({ path: shotRefreshPlaying, fullPage: false });
  console.log(`Saved screenshot (Refresh Playing): ${shotRefreshPlaying}`);

  // ----------------------------------------------------
  // STEP 12 — ORIGINAL PLAYBACK TOGGLE TEST
  // ----------------------------------------------------
  console.log("\n==================================================");
  console.log("STEP 12 — ORIGINAL PLAYBACK TOGGLE TEST");
  console.log("==================================================");

  const origBtnMode = page
    .getByRole("button", { name: "Original" })
    .or(page.locator('button:has-text("Original")'))
    .first();
  await origBtnMode.click();
  console.log("Switched to Original mode.");
  await page.waitForTimeout(2000);

  const origVideoState = await inspectVideo(page);
  console.log("\nOriginal Video State:");
  console.log(
    `- readyState: ${origVideoState.readyState}, error: ${origVideoState.error}, duration: ${origVideoState.duration}`,
  );

  const origPlayAdvance = await playAndObserveAdvance(page, 2000);
  console.log(
    `Original Play advance: start=${origPlayAdvance.startTime.toFixed(2)}s -> end=${origPlayAdvance.endTime.toFixed(2)}s, advanced=${origPlayAdvance.advanced}`,
  );

  // Switch back to Edited Preview
  await editedBtn.click();
  await page.waitForTimeout(2000);
  console.log("Switched back to Edited Preview.");

  // Summary results
  console.log("\n==================================================");
  console.log("ACCEPTANCE RESULTS SUMMARY");
  console.log("==================================================");
  console.log(`Cut Play Advance: ${cutPlayAdvance.advanced ? "PASS" : "FAIL"}`);
  console.log(`Tighten Play Advance: ${tightenPlayAdvance.advanced ? "PASS" : "FAIL"}`);
  console.log(`Undo Play Advance: ${undoPlayAdvance.advanced ? "PASS" : "FAIL"}`);
  console.log(`Refresh Play Advance: ${refreshPlayAdvance.advanced ? "PASS" : "FAIL"}`);
  console.log(`Original Play Advance: ${origPlayAdvance.advanced ? "PASS" : "FAIL"}`);
  console.log(`Console Errors: ${consoleErrors.length}`);

  await browser.close();
}

run().catch((err) => {
  console.error("FATAL in acceptance:", err);
  process.exit(1);
});
