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

  console.log("=== Testing Step 5 & 6: Player and Timeline Consistency ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
      console.log(`[Console Error] ${msg.text()}`);
    }
  });

  page.on("response", async (res) => {
    if (res.url().includes("/api/")) {
      console.log(`[API Response] ${res.status()} ${res.request().method()} ${res.url()}`);
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

  console.log("1. Logging in...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*", { timeout: 15000 });

  console.log("2. Navigating to New Project -> Recent Projects...");
  await page.goto(`${BASE_URL}/projects/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("section[aria-labelledby='recent-projects-heading']", {
    timeout: 10000,
  });

  console.log(`3. Navigating to production ${TARGET_PROD_ID}...`);
  await page.goto(`${BASE_URL}/productions/${TARGET_PROD_ID}/editor`, {
    waitUntil: "domcontentloaded",
  });
  console.log("Waiting for Editor Workspace to load...");
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForSelector("[data-testid='video-stage']", { timeout: 60000 });
  console.log("Editor Workspace loaded successfully!");
  await page.waitForTimeout(3000);
  const getMediaDetails = async () => {
    return await page.evaluate(() => {
      const video = document.querySelector("video");
      const durationDisplay = document.querySelector(
        ".font-mono, [data-testid='duration-display']",
      );
      const timecodeText = durationDisplay ? durationDisplay.textContent : "";
      return {
        videoSrc: video?.src ? video.src.slice(0, 80) + "..." : null,
        videoDuration: video?.duration || null,
        videoCurrentTime: video?.currentTime || null,
        videoPaused: video?.paused ?? null,
        timecodeText,
      };
    });
  };

  const modes = [
    { name: "original", label: "Original" },
    { name: "edited", label: "Edited Preview" },
    { name: "studio_voice", label: "Voiceover Preview" },
    { name: "final_mix", label: "Final Mix" },
  ];

  for (const m of modes) {
    console.log(`\n--- Testing Mode: ${m.name} ---`);
    const btn = page.getByRole("button", { name: new RegExp(m.label, "i") }).first();
    if ((await btn.count()) === 0) {
      console.log(`Mode button ${m.name} not found!`);
      continue;
    }
    await btn.click();
    await page.waitForTimeout(2500);

    const initialDetails = await getMediaDetails();
    console.log(`Initial state for ${m.name}:`, initialDetails);

    // Verify video tag is loaded
    if (!initialDetails.videoSrc) {
      throw new Error(`Mode ${m.name} has no video src!`);
    }

    // Seek to 25%, 50%, 75%
    for (const pct of [0.25, 0.5, 0.75]) {
      console.log(`Seeking to ${pct * 100}%...`);
      const scrubber = page.locator("[role='slider'][aria-label='Video scrubber']");
      const box = await scrubber.boundingBox();
      if (box) {
        await page.mouse.click(box.x + box.width * pct, box.y + box.height / 2);
        await page.waitForTimeout(1000);
        const seekDetails = await getMediaDetails();
        console.log(
          `At ${pct * 100}%: currentTime=${seekDetails.videoCurrentTime?.toFixed(2)}s, timecode=${seekDetails.timecodeText}`,
        );
      }
    }

    // Play & Pause
    console.log("Testing Play / Pause...");
    const playPauseBtn = page.getByRole("button", { name: /Play|Pause/i }).first();
    await playPauseBtn.click();
    await page.waitForTimeout(1500);
    const playingDetails = await getMediaDetails();
    console.log("Playing state:", playingDetails.videoPaused === false ? "PLAYING" : "PAUSED");

    await playPauseBtn.click();
    await page.waitForTimeout(1000);
    const pausedDetails = await getMediaDetails();
    console.log("Paused state:", pausedDetails.videoPaused === true ? "PAUSED" : "PLAYING");
  }

  // Verify EDL cut behavior: in Original vs Edited
  console.log("\n--- Verifying Removed Material In Original vs Edited ---");
  // Switch to Original
  await page
    .getByRole("button", { name: /^Original$/i })
    .first()
    .click();
  await page.waitForTimeout(2000);
  const origDetails = await getMediaDetails();
  console.log(`Original duration: ${origDetails.videoDuration}s`);

  // Switch to Edited
  await page
    .getByRole("button", { name: /Edited Preview/i })
    .first()
    .click();
  await page.waitForTimeout(2000);
  const editedDetails = await getMediaDetails();
  console.log(`Edited duration: ${editedDetails.videoDuration}s`);

  if (origDetails.videoDuration && editedDetails.videoDuration) {
    if (origDetails.videoDuration <= editedDetails.videoDuration) {
      console.warn(
        `WARNING: Original duration (${origDetails.videoDuration}s) should be longer than Edited duration (${editedDetails.videoDuration}s)!`,
      );
    } else {
      console.log(
        `PASS: Original duration (${origDetails.videoDuration}s) > Edited duration (${editedDetails.videoDuration}s)`,
      );
    }
  }

  console.log(`Console Errors count: ${consoleErrors.length}`);
  if (consoleErrors.length > 0) {
    console.error("Console errors found:", consoleErrors);
  }

  await browser.close();
  console.log("=== Step 5 & 6 Verification Complete ===");
}

run().catch((err) => {
  console.error("Error in Step 5 & 6:", err);
  process.exit(1);
});
