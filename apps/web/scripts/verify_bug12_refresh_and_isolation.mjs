import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "http://localhost:5173";
const PROD_A = "prod_473209137802";
const PROD_B = "prod_0b7657f515ae";
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

  console.log("=== Testing Step 7 & 8: Refresh Resilience and Project Isolation ===");
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

  const getEditorState = async () => {
    return await page.evaluate(() => {
      const video = document.querySelector("video");
      const title = document.querySelector("header .truncate")?.textContent?.trim();
      const timecodeDuration = document
        .querySelector("[data-testid='timecode-duration']")
        ?.textContent?.trim();
      const cutBadge = document
        .querySelector("[data-testid='preview-toggle-edited'] .font-mono")
        ?.textContent?.trim();
      const hasStudioVoice = Boolean(
        document.querySelector("[data-testid='preview-toggle-studio-voice']"),
      );
      const hasFinalMix = Boolean(
        document.querySelector("[data-testid='preview-toggle-final-mix']"),
      );
      const projectItems = Array.from(
        document.querySelectorAll("[data-testid='project-bin'] button"),
      ).map((b) => b.textContent?.trim());
      return {
        title,
        videoSrc: video?.src ? video.src.slice(0, 70) + "..." : null,
        timecodeDuration,
        cutBadge,
        hasStudioVoice,
        hasFinalMix,
        projectItems,
      };
    });
  };

  // --- STEP 7: REFRESH TEST ON PROD_A ---
  console.log("\n==========================================");
  console.log("TESTING STEP 7: REFRESH RESILIENCE");
  console.log("==========================================");

  await page.goto(`${BASE_URL}/productions/${PROD_A}/editor`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForTimeout(3000);

  const testModes = [
    { label: "Original", name: "original" },
    { label: "Edited Preview", name: "edited" },
    { label: "Voiceover Preview", name: "studio_voice" },
    { label: "Final Mix", name: "final_mix" },
  ];

  for (const m of testModes) {
    console.log(`Selecting mode ${m.name} before refresh...`);
    const btn = page.getByRole("button", { name: new RegExp(m.label, "i") }).first();
    if ((await btn.count()) > 0) {
      await btn.click();
      await page.waitForTimeout(1500);
      console.log(`Refreshing browser in mode ${m.name}...`);
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
      await page.waitForTimeout(3000);

      const refreshedState = await getEditorState();
      console.log(`State after refresh for mode ${m.name}:`, refreshedState);
      if (!refreshedState.videoSrc) {
        throw new Error(`Video src missing after reload in mode ${m.name}`);
      }
    }
  }

  // --- STEP 8: PROJECT ISOLATION TEST (PROD_A vs PROD_B) ---
  console.log("\n==========================================");
  console.log("TESTING STEP 8: PROJECT ISOLATION");
  console.log("==========================================");

  // 1. Open Production A
  console.log(`1. Opening Production A (${PROD_A})...`);
  await page.goto(`${BASE_URL}/productions/${PROD_A}/editor`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForTimeout(3000);
  const stateA = await getEditorState();
  console.log("Production A State:", stateA);

  if (stateA.cutBadge !== "20") {
    console.warn(`Expected 20 cuts in Production A, got: ${stateA.cutBadge}`);
  }
  if (!stateA.hasStudioVoice || !stateA.hasFinalMix) {
    console.warn(`Expected Studio Voice & Final Mix in Production A!`);
  }

  // 2. Return to Recent Projects
  console.log("2. Returning to Projects page...");
  await page.goto(`${BASE_URL}/projects/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("section[aria-labelledby='recent-projects-heading']", {
    timeout: 20000,
  });
  await page.waitForTimeout(1500);

  // 3. Open Production B
  console.log(`3. Opening Production B (${PROD_B})...`);
  await page.goto(`${BASE_URL}/productions/${PROD_B}/editor`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForTimeout(3000);
  const stateB = await getEditorState();
  console.log("Production B State:", stateB);

  // Assert isolation
  console.log("Verifying Production B does not contain Production A state...");
  if (stateB.title?.includes("github.mp4")) {
    throw new Error(`Isolation Failure: Production B title is showing Production A filename!`);
  }
  if (stateB.cutBadge === "20") {
    throw new Error(`Isolation Failure: Production B inherited 20 cuts from Production A!`);
  }
  if (stateB.hasStudioVoice) {
    throw new Error(`Isolation Failure: Production B shows Voiceover button from Production A!`);
  }
  if (stateB.hasFinalMix) {
    throw new Error(`Isolation Failure: Production B shows Final Mix button from Production A!`);
  }
  console.log("PASS: Production B has strict isolation from Production A.");

  // 4. Return to Production A and verify its state is fully preserved
  console.log(`4. Returning to Production A (${PROD_A})...`);
  await page.goto(`${BASE_URL}/productions/${PROD_A}/editor`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 60000 });
  await page.waitForTimeout(3000);
  const stateAReturn = await getEditorState();
  console.log("Production A Returned State:", stateAReturn);

  if (stateAReturn.cutBadge !== "20") {
    throw new Error(
      `State Loss: Production A returned cut count is ${stateAReturn.cutBadge} (expected 20)`,
    );
  }
  if (!stateAReturn.hasStudioVoice || !stateAReturn.hasFinalMix) {
    throw new Error(
      `State Loss: Production A returned is missing Studio Voice or Final Mix buttons!`,
    );
  }
  console.log("PASS: Production A state correctly preserved on return.");

  console.log(`\nTotal console errors: ${consoleErrors.length}`);
  await browser.close();
  console.log("=== Step 7 & 8 Completed Successfully ===");
}

run().catch((err) => {
  console.error("Error in Step 7 & 8:", err);
  process.exit(1);
});
