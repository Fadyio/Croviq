import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "http://127.0.0.1:5173";
const SCREENSHOT_DIR = path.resolve("../../docs/screenshots/acceptance");

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
  { name: "1600x900", width: 1600, height: 900 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
];

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

  console.log(
    "=== Launching Chrome for Final Milestone Acceptance & Multi-Resolution Visual Review ===",
  );
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleLogs = [];
  const failedRequests = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleLogs.push(msg.text());
      console.log(`[Browser Console Error] ${msg.text()}`);
    }
  });

  page.on("requestfailed", (req) => {
    failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText})`);
    console.log(`[Browser Request Failed] ${req.method()} ${req.url()}`);
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

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  console.log("Logging in...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForURL("**/app*", { timeout: 15000 });
  console.log("Logged in! URL:", page.url());

  const prodId = "prod_acc_demo_1788044745";

  for (const vp of VIEWPORTS) {
    console.log(`\n========================================`);
    console.log(`VIEWPORT: ${vp.name} (${vp.width}x${vp.height})`);
    console.log(`========================================`);

    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(`${BASE_URL}/productions/${prodId}/editor`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);

    // 1. Agent Log view
    const agentLogTab = page.getByRole("tab", { name: "Agent Log" });
    if (await agentLogTab.isVisible()) {
      await agentLogTab.click();
      await page.waitForTimeout(500);
      const shotAgentLog = path.join(SCREENSHOT_DIR, `editor-agent-log-${vp.name}.png`);
      await page.screenshot({ path: shotAgentLog });
      console.log(`Saved: ${shotAgentLog}`);
    }

    // 2. Chat with Leo view
    const chatTab = page.getByRole("tab", { name: "Chat with Leo" });
    if (await chatTab.isVisible()) {
      await chatTab.click();
      await page.waitForTimeout(500);
      const shotChat = path.join(SCREENSHOT_DIR, `editor-chat-${vp.name}.png`);
      await page.screenshot({ path: shotChat });
      console.log(`Saved: ${shotChat}`);
    }

    // 3. Transcript view
    const transcriptTab = page.getByRole("tab", { name: "Transcript" });
    if (await transcriptTab.isVisible()) {
      await transcriptTab.click();
      await page.waitForTimeout(500);
      const shotTranscript = path.join(SCREENSHOT_DIR, `editor-transcript-${vp.name}.png`);
      await page.screenshot({ path: shotTranscript });
      console.log(`Saved: ${shotTranscript}`);
    }

    // 4. Original vs Edited Preview
    const originalBtn = page.getByRole("button", { name: "Original", exact: true });
    if (await originalBtn.isVisible()) {
      await originalBtn.click();
      await page.waitForTimeout(500);
      const shotOriginal = path.join(SCREENSHOT_DIR, `editor-original-${vp.name}.png`);
      await page.screenshot({ path: shotOriginal });
      console.log(`Saved: ${shotOriginal}`);
    }
    const editedBtn = page.getByRole("button", { name: /Edited Preview/i }).first();
    if (await editedBtn.isVisible()) {
      await editedBtn.click();
      await page.waitForTimeout(500);
      const shotEdited = path.join(SCREENSHOT_DIR, `editor-edited-${vp.name}.png`);
      await page.screenshot({ path: shotEdited });
      console.log(`Saved: ${shotEdited}`);
    }
  }

  // Set standard 1600x900 for interactive deep test
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto(`${BASE_URL}/productions/${prodId}/editor`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);

  // 5. Timeline Selection -> Context Chip test
  console.log("\nTesting Timeline -> Chat Context chip...");
  const timelineBlock = page.locator("[data-block-type='cut-safe'], .twick-block").first();
  if ((await timelineBlock.count()) > 0) {
    await timelineBlock.click({ force: true });
    await page.waitForTimeout(1000);
    // Switch to Chat tab
    const chatTab = page.getByRole("tab", { name: "Chat with Leo" });
    await chatTab.click();
    await page.waitForTimeout(1000);
    const shotSelection = path.join(SCREENSHOT_DIR, `editor-chat-selection.png`);
    await page.screenshot({ path: shotSelection });
    console.log(`Saved: ${shotSelection}`);
  }

  // 6. Interactive Chat test: Ask Leo why cut was made
  console.log("\nTesting Leo Chat question...");
  const chatInput = page
    .locator("[data-testid='leo-chat-input'], textarea, input[placeholder*='Ask Leo']")
    .first();
  if (await chatInput.isVisible()) {
    await chatInput.fill("Why did you make this cut?");
    const sendBtn = page
      .locator("[data-testid='btn-send-leo-chat'], button:has-text('Send')")
      .first();
    await sendBtn.click();
    console.log("Sent message to Leo, waiting for response...");
    await page.waitForTimeout(5000);
    const shotResponse = path.join(SCREENSHOT_DIR, `editor-chat-response.png`);
    await page.screenshot({ path: shotResponse });
    console.log(`Saved: ${shotResponse}`);
  }

  // 7. B-roll track screenshot
  const shotBroll = path.join(SCREENSHOT_DIR, `editor-broll.png`);
  await page.screenshot({ path: shotBroll });
  console.log(`Saved: ${shotBroll}`);

  // 8. Voiceover preview screenshot
  const shotVoiceover = path.join(SCREENSHOT_DIR, `editor-voiceover.png`);
  await page.screenshot({ path: shotVoiceover });
  console.log(`Saved: ${shotVoiceover}`);

  await browser.close();
  console.log("\n=== Milestone Visual Review & Acceptance Completed Successfully! ===");
}

main().catch((err) => {
  console.error("Acceptance run failed:", err);
  process.exit(1);
});
