import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "http://localhost:5173";
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

const TARGET_PROD_ID = "prod_473209137802";

async function run() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log(`=== Launching Chrome to Reproduce Step 1 with ${TARGET_PROD_ID} ===`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
  const page = await context.newPage();

  const networkRequests = [];
  const consoleErrors = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
      console.log(`[Console Error] ${msg.text()}`);
    } else {
      console.log(`[Console Log] ${msg.text()}`);
    }
  });

  page.on("request", (req) => {
    if (req.url().includes("/api/")) {
      networkRequests.push({
        method: req.method(),
        url: req.url(),
      });
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
  console.log("2. Logged in! Navigating to New Project -> Recent Projects...");

  await page.goto(`${BASE_URL}/projects/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("section[aria-labelledby='recent-projects-heading']", {
    timeout: 10000,
  });

  console.log(`3. Opening ${TARGET_PROD_ID}...`);
  // Navigate by changing history / pushState or page.goto
  await page.goto(`${BASE_URL}/productions/${TARGET_PROD_ID}/editor`, {
    waitUntil: "domcontentloaded",
  });

  await page.waitForTimeout(5000);

  const bodyText = await page.evaluate(() => document.body.innerText);
  console.log("Body text snippet:", bodyText.slice(0, 300));

  const hasWorkspace = await page.locator("[data-testid='editor-workspace']").count();
  console.log(`Editor workspace element count: ${hasWorkspace}`);

  if (hasWorkspace === 0) {
    const errorEl = await page
      .locator(".text-danger")
      .textContent()
      .catch(() => null);
    console.log("Error element text:", errorEl);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug12-debug-failed-load.png") });
  }

  const inspectPlayerState = async (modeName) => {
    return await page.evaluate((mode) => {
      const video = document.querySelector("video");
      const durationDisplay = document.querySelector("[data-testid='duration-display']");
      const toggleBtns = Array.from(document.querySelectorAll("button"))
        .filter((b) =>
          [
            "Original",
            "Edited",
            "Edited Preview",
            "Studio Voice",
            "Voiceover",
            "Voiceover Preview",
            "Final Mix",
          ].some((t) => b.textContent?.includes(t)),
        )
        .map((b) => ({ text: b.textContent?.trim(), className: b.className }));

      return {
        mode,
        videoSrc: video?.src || null,
        videoDuration: video?.duration || null,
        videoCurrentTime: video?.currentTime || null,
        videoPaused: video?.paused ?? null,
        videoReadyState: video?.readyState ?? null,
        durationDisplayText: durationDisplay?.textContent || null,
        toggleBtns,
      };
    }, modeName);
  };

  console.log("\n4. Inspecting and capturing available modes for prod_473209137802...");

  // 1. Edited Preview (default)
  console.log("State: Default / Edited Preview");
  const stateEdited = await inspectPlayerState("Edited");
  console.log("Edited state:", JSON.stringify(stateEdited, null, 2));
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "bug12-before-prod473-edited-1600x900.png"),
  });

  // 2. Original
  const originalBtn = page
    .getByRole("button", { name: /^Original$/i })
    .or(page.getByText(/^Original$/i));
  if ((await originalBtn.count()) > 0) {
    console.log("Switching to Original...");
    await originalBtn.first().click();
    await page.waitForTimeout(2000);
    const stateOriginal = await inspectPlayerState("Original");
    console.log("Original state:", JSON.stringify(stateOriginal, null, 2));
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "bug12-before-prod473-original-1600x900.png"),
    });
  }

  // 3. Voiceover Preview / Studio Voice
  const voBtn = page
    .getByRole("button", { name: /Voiceover|Studio Voice/i })
    .or(page.getByText(/Voiceover|Studio Voice/i));
  if ((await voBtn.count()) > 0) {
    console.log("Switching to Voiceover Preview...");
    await voBtn.first().click();
    await page.waitForTimeout(2000);
    const stateVo = await inspectPlayerState("Voiceover");
    console.log("Voiceover state:", JSON.stringify(stateVo, null, 2));
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "bug12-before-prod473-voiceover-1600x900.png"),
    });
  }

  // 4. Final Mix
  const fmBtn = page.getByRole("button", { name: /Final Mix/i }).or(page.getByText(/Final Mix/i));
  if ((await fmBtn.count()) > 0) {
    console.log("Switching to Final Mix...");
    await fmBtn.first().click();
    await page.waitForTimeout(2000);
    const stateFm = await inspectPlayerState("Final Mix");
    console.log("Final Mix state:", JSON.stringify(stateFm, null, 2));
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "bug12-before-prod473-finalmix-1600x900.png"),
    });
  }

  // 5. Timeline visible
  console.log("Capturing full editor with timeline visible...");
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "bug12-before-prod473-timeline-1600x900.png"),
  });

  console.log("\n=== ALL RECORDED NETWORK REQUESTS ===");
  for (const r of networkRequests) {
    console.log(`${r.method} ${r.url}`);
  }

  console.log(`\nConsole Errors count: ${consoleErrors.length}`);

  await browser.close();
  console.log("=== Step 1 Complete for prod_473209137802 ===");
}

run().catch((err) => {
  console.error("Error running Step 1:", err);
  process.exit(1);
});
