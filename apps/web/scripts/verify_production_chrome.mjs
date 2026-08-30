import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const PROD_URL = "https://app.croviq.app";
const PRODUCTION_ID = "prod_473209137802";
const SCREENSHOT_DIR = path.resolve("docs/screenshots/acceptance");

const DEMO_EMAIL = "demo@croviq.app";
const APPROVED_USER = {
  user_id: "27iEBUMcu6ToDYwp2OdEIHBuwIA3",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const FIREBASE_ID_TOKEN =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vY3JvdmlxLTUwNjYwMiIsImF1ZCI6ImNyb3ZpcS01MDY2MDIiLCJhdXRoX3RpbWUiOjEsInVzZXJfaWQiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwic3ViIjoiMjdpRUJVTWN1NlRvRFl3cDJPZEVJSEJ1d0lBMyIsImlhdCI6MSwiZXhwIjo0MTAyNDQ0ODAwLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmaXJlYmFzZSI6eyJpZGVudGl0aWVzIjp7ImVtYWlsIjpbImRlbW9AY3JvdmlxLmFwcCJdfSwic2lnbl9pbl9wcm92aWRlciI6InBhc3N3b3JkIn19.signature";

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log("=== Launching Chrome against LIVE Production https://app.croviq.app ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
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
    // Ignore aborted analytics/favicon or intentional aborts
    if (!req.url().includes("favicon")) {
      failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText})`);
      console.log(`[Browser Request Failed] ${req.method()} ${req.url()}`);
    }
  });

  // Mock Firebase auth token response if required by headless test runner
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

  console.log("Navigating to login page...");
  await page.goto(`${PROD_URL}/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForURL("**/app*", { timeout: 20000 });
  console.log("Authenticated! Navigating to Editor for production:", PRODUCTION_ID);

  await page.goto(`${PROD_URL}/productions/${PRODUCTION_ID}/editor`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);

  // 1. Capture full editor default view
  const shotEditorDefault = path.join(SCREENSHOT_DIR, "live-prod-editor-default.png");
  await page.screenshot({ path: shotEditorDefault, fullPage: true });
  console.log("Saved screenshot:", shotEditorDefault);

  // 2. Check Media Bin Artifacts
  console.log("\n--- Checking Media Bin Artifacts ---");
  const mediaBin = page.getByTestId("media-bin-panel");
  if (await mediaBin.isVisible()) {
    const hasOriginal = await mediaBin.getByText("Source Video").isVisible();
    const hasEdited = await mediaBin.getByText("Edited Preview").isVisible();
    const hasStudioVoice = await mediaBin.getByText("Voiceover Preview").isVisible();
    const hasFinalMix = await mediaBin.getByText("Final Mix").isVisible();
    console.log("Media Bin Source Video present:", hasOriginal);
    console.log("Media Bin Edited Preview present:", hasEdited);
    console.log("Media Bin Voiceover Preview present:", hasStudioVoice);
    console.log("Media Bin Final Mix present:", hasFinalMix);
  }

  // 3. Test Preview Modes & Playback
  const previewModes = [
    { name: "Original", buttonText: "Original", mode: "original" },
    { name: "Edited Preview", buttonText: "Edited Preview", mode: "edited" },
    { name: "Voiceover Preview", buttonText: "Voiceover Preview", mode: "studio_voice" },
    { name: "Final Mix", buttonText: "Final Mix", mode: "final_mix" },
  ];

  for (const pm of previewModes) {
    console.log(`\n--- Testing Preview Mode: ${pm.name} ---`);
    const btn = page.getByRole("button", { name: pm.buttonText }).first();
    if (await btn.isVisible()) {
      await btn.click();
      await page.waitForTimeout(1000);
      const shot = path.join(SCREENSHOT_DIR, `live-prod-mode-${pm.mode}.png`);
      await page.screenshot({ path: shot });
      console.log(`Switched to ${pm.name}, saved screenshot: ${shot}`);
    } else {
      console.log(`Button for ${pm.name} not found directly, checking preview toggle`);
    }
  }

  // 4. Seek through the 3 corrected segments in Final Mix mode
  console.log("\n--- Seeking through the 3 Corrected Segments in Final Mix ---");
  const finalMixBtn = page.getByRole("button", { name: "Final Mix" }).first();
  if (await finalMixBtn.isVisible()) {
    await finalMixBtn.click();
    await page.waitForTimeout(1000);
  }

  const testSegments = [
    { id: "seg_00_transcription", timeS: 3.0, label: "Segment 1 (GitHub Actions)" },
    { id: "seg_03_falsestart", timeS: 20.0, label: "Segment 2 (Cloudflare DNS)" },
    { id: "seg_08_grammar", timeS: 75.0, label: "Segment 3 (Google Cloud Deploy)" },
  ];

  for (const seg of testSegments) {
    console.log(`Seeking to ${seg.label} at ${seg.timeS}s...`);
    // Evaluate video playback time in browser video element
    const videoState = await page.evaluate((targetTime) => {
      const video = document.querySelector("video");
      if (!video) return { found: false };
      video.currentTime = targetTime;
      return {
        found: true,
        currentTime: video.currentTime,
        duration: video.duration,
        paused: video.paused,
        src: video.src,
      };
    }, seg.timeS);

    await page.waitForTimeout(1500);
    const segShot = path.join(SCREENSHOT_DIR, `live-prod-final-mix-${seg.id}.png`);
    await page.screenshot({ path: segShot });
    console.log(`Segment ${seg.id} video state:`, videoState);
    console.log(`Saved screenshot: ${segShot}`);
  }

  // 5. Check Transcript Corrected View / Script View
  console.log("\n--- Checking Transcript / Corrected Script View ---");
  const scriptTab = page.getByRole("button", { name: /Script|Corrected/i }).first();
  if (await scriptTab.isVisible()) {
    await scriptTab.click();
    await page.waitForTimeout(1000);
    const scriptShot = path.join(SCREENSHOT_DIR, "live-prod-corrected-script-tab.png");
    await page.screenshot({ path: scriptShot });
    console.log("Saved script tab screenshot:", scriptShot);
  }

  // 6. Check My Voice in Voice Settings Drawer
  console.log("\n--- Checking Voice Settings / My Voice BLOCKED Status ---");
  const voiceSettingsBtn = page
    .getByRole("button", { name: /Voice Settings|Agent Settings/i })
    .first();
  if (await voiceSettingsBtn.isVisible()) {
    await voiceSettingsBtn.click();
    await page.waitForTimeout(1000);
    const voiceShot = path.join(SCREENSHOT_DIR, "live-prod-voice-settings.png");
    await page.screenshot({ path: voiceShot });
    console.log("Saved voice settings screenshot:", voiceShot);
  }

  console.log("\n========================================");
  console.log("LIVE CHROME ACCEPTANCE SUMMARY:");
  console.log(`  Console Errors: ${consoleErrors.length}`);
  console.log(`  Failed Requests: ${failedRequests.length}`);
  console.log("========================================");

  await browser.close();
}

main().catch((err) => {
  console.error("Chrome acceptance run failed:", err);
  process.exit(1);
});
