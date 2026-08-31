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
    video.currentTime = Number(sec);
    return video.currentTime;
  }, targetSec);
}

async function run() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  console.log("==================================================");
  console.log("RUNNING BUG 15.2 FULL REAL CHROMIUM ACCEPTANCE");
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

  // Fetch initial EDL before tests
  const initialEdlPayload = await page.evaluate(
    async ({ prodId, token }) => {
      const res = await fetch(`/api/productions/${prodId}/edl`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return await res.json();
    },
    { prodId: TARGET_PROD_ID, token: FIREBASE_ID_TOKEN },
  );
  const initialEdl = initialEdlPayload.edl || initialEdlPayload;
  console.log(
    `Initial EDL: id=${initialEdl.edl_id}, version=${initialEdl.version}, cuts=${initialEdl.cuts?.length}, duration=${initialEdl.source_duration_ms}ms`,
  );

  const transcriptTab = page.getByRole("tab", { name: /transcript/i });
  const chatTab = page.getByRole("tab", { name: /chat|leo/i });
  const chatInput = page.locator("#leo-chat-input");

  // =========================================================================
  // TEST 1 — NO-OP TIGHTEN ON ALREADY-TIGHT / COVERED SECTION (Seg 04 / 16.2s-28.6s)
  // =========================================================================
  console.log("\n==================================================");
  console.log("TEST 1 — NO-OP TIGHTEN ON ALREADY-TIGHT SECTION");
  console.log("==================================================");

  await transcriptTab.click();
  await page.waitForTimeout(800);
  const origBtn = page.getByRole("button", { name: "Original Transcript" });
  if (await origBtn.isVisible()) {
    await origBtn.click();
    await page.waitForTimeout(600);
  }

  const sentenceBtns = page.locator('button[title*="Select sentence"]');
  if ((await sentenceBtns.count()) > 3) {
    await sentenceBtns.nth(3).click();
    console.log("Selected Seg 04 (16.2s -> 28.6s: 'To edit to edit your workflow...')");
  }
  await page.waitForTimeout(600);

  await chatTab.click();
  await page.waitForTimeout(800);

  const hasAttachment1 = await page
    .locator('[data-testid="leo-chat-selection-attachment"]')
    .isVisible();
  console.log(`Selection attachment attached: ${hasAttachment1}`);

  await chatInput.fill("Make this tighter.");
  console.log("Sending 'Make this tighter.' to Leo...");
  await chatInput.press("Enter");

  const chatRes1 = await page.waitForResponse(
    (res) => res.url().includes("/api/productions/") && res.url().includes("/chat"),
    { timeout: 120000 },
  );
  const chatJson1 = await chatRes1.json();
  console.log("Leo reply (Test 1):", chatJson1.content);
  console.log(`Timeline updated: ${chatJson1.timeline_updated}`);
  console.log(
    `EDL ID: ${chatJson1.edl?.edl_id}, Version: ${chatJson1.edl?.version}, Cuts: ${chatJson1.edl?.cuts?.length}`,
  );

  const test1NoOpPass =
    chatJson1.timeline_updated === false &&
    chatJson1.edl?.version === initialEdl.version &&
    chatJson1.edl?.edl_id === initialEdl.edl_id &&
    !chatJson1.content.includes("0.00s") &&
    (chatJson1.content.toLowerCase().includes("already") ||
      chatJson1.content.toLowerCase().includes("no long pauses"));
  console.log(`TEST 1 NO-OP VERIFICATION: ${test1NoOpPass ? "PASS" : "FAIL"}`);

  await page.waitForTimeout(3000);
  const shotNoOp = path.join(SCREENSHOT_DIR, "bug15_2_shot2_noop_tighten_1600x900.png");
  await page.screenshot({ path: shotNoOp, fullPage: false });
  console.log(`Saved screenshot (No-Op): ${shotNoOp}`);

  // =========================================================================
  // TEST 2 — REAL TIGHTEN ON GENUINELY TIGHTEN-ABLE SECTION (Seg 03 / 8.9s - 15.4s)
  // =========================================================================
  console.log("\n==================================================");
  console.log("TEST 2 — REAL TIGHTEN ON GENUINELY TIGHTEN-ABLE SECTION");
  console.log("==================================================");

  const edlBeforeTest2 = chatJson1.edl;
  const durBeforeTest2 = videoState.duration;

  await transcriptTab.click();
  await page.waitForTimeout(800);
  if ((await sentenceBtns.count()) > 2) {
    await sentenceBtns.nth(2).click();
    console.log("Selected Seg 03 (8.9s -> 15.4s: 'You can find the GitHub action in here.')");
  }
  await page.waitForTimeout(600);

  await chatTab.click();
  await page.waitForTimeout(800);

  await chatInput.fill("Make this tighter.");
  console.log("Sending 'Make this tighter.' for Real Tighten...");
  await chatInput.press("Enter");

  const chatRes2 = await page.waitForResponse(
    (res) => res.url().includes("/api/productions/") && res.url().includes("/chat"),
    { timeout: 120000 },
  );
  const chatJson2 = await chatRes2.json();
  console.log("Leo reply (Test 2):", chatJson2.content);
  console.log(`Timeline updated: ${chatJson2.timeline_updated}`);
  console.log(
    `New EDL ID: ${chatJson2.edl?.edl_id}, Version: ${chatJson2.edl?.version}, Cuts: ${chatJson2.edl?.cuts?.length}`,
  );

  console.log("Waiting for video player to refresh preview...");
  await page.waitForTimeout(8000);

  const realTightenVideoState = await inspectVideo(page);
  console.log("\nPost-Real-Tighten Video State:");
  console.log(
    `- readyState: ${realTightenVideoState.readyState}, duration: ${realTightenVideoState.duration}`,
  );

  const realPlayAdvance = await playAndObserveAdvance(page, 3000);
  console.log(`Real tighten playback advance: ${realPlayAdvance.advanced}`);

  const test2RealTightenPass =
    chatJson2.timeline_updated === true &&
    chatJson2.edl?.version > edlBeforeTest2.version &&
    !chatJson2.content.includes("0.00s") &&
    chatJson2.content.toLowerCase().includes("tightened this section by");
  console.log(`TEST 2 REAL TIGHTEN VERIFICATION: ${test2RealTightenPass ? "PASS" : "FAIL"}`);

  const shotRealTighten = path.join(SCREENSHOT_DIR, "bug15_2_shot3_real_tighten_1600x900.png");
  await page.screenshot({ path: shotRealTighten, fullPage: false });
  console.log(`Saved screenshot (Real Tighten): ${shotRealTighten}`);

  // =========================================================================
  // TEST 3 — REPEATED TIGHTEN ON SAME SECTION CONVERGES TO NO-OP
  // =========================================================================
  console.log("\n==================================================");
  console.log("TEST 3 — REPEATED TIGHTEN CONVERGENCE");
  console.log("==================================================");

  const edlAfterRealTighten = chatJson2.edl;

  // Re-select the now-tightened Seg 03
  await transcriptTab.click();
  await page.waitForTimeout(800);
  if ((await sentenceBtns.count()) > 2) {
    await sentenceBtns.nth(2).click();
    console.log("Re-selected now-tightened Seg 03 for repeated tighten test.");
  }
  await page.waitForTimeout(600);

  await chatTab.click();
  await page.waitForTimeout(800);

  await chatInput.fill("Make this tighter.");
  console.log("Sending repeated 'Make this tighter.' to verify convergence...");
  await chatInput.press("Enter");

  const chatRes3 = await page.waitForResponse(
    (res) => res.url().includes("/api/productions/") && res.url().includes("/chat"),
    { timeout: 120000 },
  );
  const chatJson3 = await chatRes3.json();
  console.log("Leo reply (Test 3):", chatJson3.content);
  console.log(`Timeline updated: ${chatJson3.timeline_updated}`);
  console.log(`EDL Version: ${chatJson3.edl?.version}`);

  const test3RepeatedPass =
    chatJson3.timeline_updated === false &&
    chatJson3.edl?.version === edlAfterRealTighten?.version &&
    chatJson3.edl?.edl_id === edlAfterRealTighten?.edl_id &&
    !chatJson3.content.includes("0.00s") &&
    (chatJson3.content.toLowerCase().includes("already") ||
      chatJson3.content.toLowerCase().includes("no long pauses"));
  console.log(`TEST 3 CONVERGENCE VERIFICATION: ${test3RepeatedPass ? "PASS" : "FAIL"}`);

  await page.waitForTimeout(3000);
  const shotRepeated = path.join(
    SCREENSHOT_DIR,
    "bug15_2_shot4_repeated_tighten_noop_1600x900.png",
  );
  await page.screenshot({ path: shotRepeated, fullPage: false });
  console.log(`Saved screenshot (Repeated Tighten): ${shotRepeated}`);

  // =========================================================================
  // TEST 4 — UNDO TEST
  // =========================================================================
  console.log("\n==================================================");
  console.log("TEST 4 — UNDO RESTORATION");
  console.log("==================================================");

  await chatInput.fill("Undo that.");
  console.log("Sending 'Undo that.' to Leo...");
  await chatInput.press("Enter");

  const chatRes4 = await page.waitForResponse(
    (res) => res.url().includes("/api/productions/") && res.url().includes("/chat"),
    { timeout: 120000 },
  );
  const chatJson4 = await chatRes4.json();
  console.log("Leo reply (Test 4):", chatJson4.content);
  console.log(`Undo EDL ID: ${chatJson4.edl?.edl_id}, Version: ${chatJson4.edl?.version}`);

  console.log("Waiting for restored video player...");
  await page.waitForTimeout(8000);

  const undoVideoState = await inspectVideo(page);
  console.log("\nPost-Undo Video State:");
  console.log(`- readyState: ${undoVideoState.readyState}, duration: ${undoVideoState.duration}`);

  const undoPlayAdvance = await playAndObserveAdvance(page, 3000);
  console.log(`Undo playback advance: ${undoPlayAdvance.advanced}`);

  const test4UndoPass =
    chatJson4.timeline_updated === true && chatJson4.content.toLowerCase().includes("undid");
  console.log(`TEST 4 UNDO VERIFICATION: ${test4UndoPass ? "PASS" : "FAIL"}`);

  const shotUndo = path.join(SCREENSHOT_DIR, "bug15_2_shot5_undo_restored_1600x900.png");
  await page.screenshot({ path: shotUndo, fullPage: false });
  console.log(`Saved screenshot (Undo): ${shotUndo}`);

  // Cleanup & Summary
  await browser.close();

  console.log("\n==================================================");
  console.log("ALL REAL BROWSER ACCEPTANCE TESTS COMPLETE");
  console.log("==================================================");
  console.log(`Console Errors: ${consoleErrors.length}`);
  console.log(`Failed Requests: ${failedRequests.length}`);
}

run().catch((err) => {
  console.error("FATAL acceptance test error:", err);
  process.exit(1);
});
