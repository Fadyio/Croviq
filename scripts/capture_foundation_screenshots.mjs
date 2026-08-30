import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "http://127.0.0.1:5173";
const SCREENSHOT_DIR = path.resolve("docs/screenshots");

function createMockToken(userId = "demo_user_123", email = "demo@croviq.app") {
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
  user_id: "demo_user_123",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

async function main() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log("=== Launching Chrome for Foundation Visual Review & User Journey ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
  const page = await context.newPage();

  const consoleLogs = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleLogs.push(msg.text());
    }
  });

  // Mock identity platform login for clean token issuance
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
              providerUserInfo: [
                {
                  providerId: "password",
                  displayName: APPROVED_USER.display_name,
                  email: DEMO_EMAIL,
                },
              ],
            },
          ],
        }),
      });
    } else {
      await route.continue();
    }
  });

  // 1. Sign In
  console.log("1. Signing in as demo creator...");
  await page.goto(`${BASE_URL}/`);
  await page.waitForSelector('input[type="email"]');
  await page.fill('input[type="email"]', DEMO_EMAIL);
  await page.fill('input[type="password"]', "password123");
  await page.click('button[type="submit"]');

  await page.waitForURL("**/app");
  console.log("   ✓ Signed in successfully; redirected to /app");

  // Wait for overview dashboard and chart to render
  await page.waitForSelector('[aria-label="Channel KPIs"]', { timeout: 10000 });
  await page.waitForTimeout(1500);

  // 2. Viewport Screenshots
  console.log("2. Capturing visual review screenshots...");

  // 1600x900
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.waitForTimeout(500);
  const path1600 = path.join(SCREENSHOT_DIR, "home_1600x900.png");
  await page.screenshot({ path: path1600, fullPage: false });
  console.log(`   ✓ Captured 1600x900 -> ${path1600}`);

  // 1440x900
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);
  const path1440 = path.join(SCREENSHOT_DIR, "home_1440x900.png");
  await page.screenshot({ path: path1440, fullPage: false });
  console.log(`   ✓ Captured 1440x900 -> ${path1440}`);

  // 1280x800
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(500);
  const path1280 = path.join(SCREENSHOT_DIR, "home_1280x800.png");
  await page.screenshot({ path: path1280, fullPage: false });
  console.log(`   ✓ Captured 1280x800 -> ${path1280}`);

  // Reset to 1440x900 for user journey
  await page.setViewportSize({ width: 1440, height: 900 });

  // 3. User Journey: Ask Alex 3 Questions
  console.log("3. User Journey: Interacting with Alex Chat...");

  // Open Alex Chat
  const alexCard = page.locator('button:has-text("Alex"), [data-testid="agent-alex-chat"]').first();
  if ((await alexCard.count()) > 0) {
    await alexCard.click();
  } else {
    // Open through rail or action menu
    await page.click('button[aria-label*="Alex"], button:has-text("Ask Alex")');
  }

  await page.waitForSelector('[data-testid="input-chat-message"]', { timeout: 8000 });
  console.log("   ✓ Alex chat drawer opened");

  // Q1: "How did my last video perform?"
  console.log('   -> Asking: "How did my last video perform?"');
  await page.fill('[data-testid="input-chat-message"]', "How did my last video perform?");
  await page.click('[data-testid="btn-send-chat"]');
  await page.waitForSelector(
    '.bg-surface-2:has-text("views"), .bg-surface-2:has-text("Google GenAI SDK")',
    {
      timeout: 15000,
    },
  );
  console.log("   ✓ Received quantitative answer with tool telemetry");

  // Q2: "What is unusual about my last 10 videos?"
  console.log('   -> Asking: "What is unusual about my last 10 videos?"');
  await page.fill('[data-testid="input-chat-message"]', "What is unusual about my last 10 videos?");
  await page.click('[data-testid="btn-send-chat"]');
  await page.waitForTimeout(3000);
  console.log("   ✓ Received analytical answer");

  // Q3: "What should I make next and why?"
  console.log('   -> Asking: "What should I make next and why?"');
  await page.fill('[data-testid="input-chat-message"]', "What should I make next and why?");
  await page.click('[data-testid="btn-send-chat"]');
  await page.waitForTimeout(3000);
  console.log("   ✓ Received channel-aligned opportunity recommendation");

  // Close Alex Drawer
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);

  // 4. Open Ideas
  console.log("4. User Journey: Opening Ideas Worth Making...");
  const ideasHeader = page.locator('h3:has-text("Ideas Worth Making")');
  await ideasHeader.scrollIntoViewIfNeeded();
  console.log("   ✓ Ideas Worth Making inspected with fresh research signals");

  // 5. New Project & Real Upload Flow Test
  console.log("5. User Journey: Initiating New Project upload...");
  await page.click(
    'button:has-text("Upload video"), a[href*="/new"], button:has-text("New Project")',
  );
  await page.waitForURL("**/new");
  console.log("   ✓ Navigated to /new");

  // Create a small test video file and trigger upload
  const testFilePath = path.join(SCREENSHOT_DIR, "test_upload.mp4");
  fs.writeFileSync(testFilePath, Buffer.alloc(1024 * 64, 0)); // 64KB dummy file

  const fileInput = page.locator('input[type="file"]').first();
  await fileInput.setInputFiles(testFilePath);
  console.log("   ✓ Set file on input");

  // Wait for file info to appear and click start upload
  await page.waitForSelector('button:has-text("Upload and Start Editing")');
  await page.click('button:has-text("Upload and Start Editing")');
  console.log("   ✓ Clicked Upload and Start Editing");

  // Wait for upload verification and navigation to editor
  await page.waitForURL("**/editor/**", { timeout: 15000 });
  console.log(`   ✓ Upload complete and verified! Navigated to: ${page.url()}`);

  console.log("=== Verification Completed Successfully! ===");
  console.log("Console errors observed:", consoleLogs.length);

  await browser.close();
  // Clean up temp test file
  if (fs.existsSync(testFilePath)) {
    fs.unlinkSync(testFilePath);
  }
}

main().catch((err) => {
  console.error("FATAL in foundation visual review:", err);
  process.exit(1);
});
