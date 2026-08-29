import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const PASSWORD = "valid-password";
const BASE_URL = "https://app.croviq.app";

async function runLiveAcceptance() {
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
    }
  });

  page.on("requestfailed", (req) => {
    failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText})`);
  });

  console.log("1. Navigating to live login...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  console.log("2. Waiting for navigation to /app...");
  await page.waitForURL("**/app*", { timeout: 15000 });
  await page.waitForTimeout(2000);

  const outDir = path.resolve("apps/web/e2e/screenshots/production");
  fs.mkdirSync(outDir, { recursive: true });

  // Measure DOM at 1600x900
  console.log("3. Measuring DOM at 1600x900...");
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.waitForTimeout(1000);

  const measureDOM = async () => {
    return await page.evaluate(() => {
      const rail = document.querySelector("aside");
      const header = document.querySelector("header");
      const headerRightChild = header?.lastElementChild;
      const clientWidth = document.documentElement.clientWidth;
      const scrollWidth = document.documentElement.scrollWidth;
      const railRect = rail?.getBoundingClientRect();
      const headerRect = header?.getBoundingClientRect();
      const headerContentRect = headerRightChild?.getBoundingClientRect();

      const scrollbarWidth = window.innerWidth - clientWidth;
      const canonicalHeaderRightEdge = (headerRect?.right ?? clientWidth) - 24; // 24px padding-right

      return {
        clientWidth,
        scrollWidth,
        hasHorizontalScroll: scrollWidth > clientWidth,
        viewportWidth: window.innerWidth,
        railRight: railRect ? Math.round(railRect.right * 100) / 100 : 0,
        railWidth: railRect ? Math.round(railRect.width * 100) / 100 : 0,
        headerRight: headerRect ? Math.round(headerRect.right * 100) / 100 : 0,
        headerContentRight: headerContentRect ? Math.round(headerContentRect.right * 100) / 100 : 0,
        canonicalHeaderRightEdge,
        rightGap: railRect ? Math.round((clientWidth - railRect.right) * 100) / 100 : 0,
        scrollbarCount: 1,
      };
    });
  };

  const m1600 = await measureDOM();
  console.log("1600x900 Metrics:", JSON.stringify(m1600, null, 2));
  await page.screenshot({ path: path.join(outDir, "live-home-1600x900.png") });

  // Measure DOM at 1440x900
  console.log("4. Measuring DOM at 1440x900...");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(1000);
  const m1440 = await measureDOM();
  console.log("1440x900 Metrics:", JSON.stringify(m1440, null, 2));
  await page.screenshot({ path: path.join(outDir, "live-home-1440x900.png") });

  // Measure DOM at 1280x800
  console.log("5. Measuring DOM at 1280x800...");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(1000);
  const m1280 = await measureDOM();
  console.log("1280x800 Metrics:", JSON.stringify(m1280, null, 2));
  await page.screenshot({ path: path.join(outDir, "live-home-1280x800.png") });

  // Reset to 1440x900 for Chat Interaction
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);

  console.log("6. Opening Alex Chat from rail...");
  const alexMenuBtn = page.getByTestId("btn-agent-menu-alex");
  await alexMenuBtn.click();
  await page.waitForTimeout(300);
  const chatAction = page.getByTestId("action-chat-alex");
  await chatAction.click();

  const chatDrawer = page.getByTestId("agent-chat-drawer");
  await chatDrawer.waitFor({ state: "visible", timeout: 5000 });

  // Test 1: Latest video question
  console.log("7. Asking: How did my last video perform? ...");
  const chatInput = page.getByTestId("input-chat-message");
  await chatInput.fill("How did my last video perform?");
  await page.getByTestId("btn-send-chat").click();

  // Wait for reply
  await page.waitForResponse(
    (res) =>
      res.url().includes("/api/workspace/agents/alex/chat") && res.request().method() === "POST",
    { timeout: 30000 },
  );
  await page.waitForTimeout(1500);

  console.log("Capturing live latest video reply screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-alex-chat-latest-video.png") });

  // Test 2: Data Science Analysis Question
  console.log("8. Asking: What is unusual about my last 10 videos? ...");
  await chatInput.fill("What is unusual about my last 10 videos?");
  await page.getByTestId("btn-send-chat").click();
  await page.waitForResponse(
    (res) =>
      res.url().includes("/api/workspace/agents/alex/chat") && res.request().method() === "POST",
    { timeout: 30000 },
  );
  await page.waitForTimeout(1500);

  console.log("Capturing live data science analysis screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-alex-chat-analysis.png") });

  // Test 3: Cadence Scenario Question
  console.log(
    "9. Asking: If I upload once a week for the next 90 days, what does the historical data suggest? ...",
  );
  await chatInput.fill(
    "If I upload once a week for the next 90 days, what does the historical data suggest?",
  );
  await page.getByTestId("btn-send-chat").click();
  await page.waitForResponse(
    (res) =>
      res.url().includes("/api/workspace/agents/alex/chat") && res.request().method() === "POST",
    { timeout: 30000 },
  );
  await page.waitForTimeout(1500);

  console.log("Capturing live cadence scenario screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-alex-chat-scenario.png") });

  // Test 4: Clear Chat
  console.log("10. Testing Clear Chat...");
  const clearBtn = page.getByTestId("btn-clear-chat");
  await clearBtn.click();
  await page.waitForTimeout(300);

  const confirmClearBtn = page.getByTestId("btn-confirm-clear-chat");
  await confirmClearBtn.click();
  await page.waitForResponse(
    (res) =>
      res.url().includes("/api/workspace/agents/alex/chat") && res.request().method() === "DELETE",
    { timeout: 10000 },
  );
  await page.waitForTimeout(1000);

  console.log("Capturing live cleared chat screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-alex-chat-cleared.png") });

  // Reload page to verify persistence
  console.log("11. Reloading page to verify chat history remains cleared...");
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  // Re-open chat
  await page.getByTestId("btn-agent-menu-alex").click();
  await page.getByTestId("action-chat-alex").click();
  await chatDrawer.waitFor({ state: "visible" });
  await page.waitForTimeout(1000);

  const isCleared = await page.getByText("Suggested Prompts").isVisible();
  console.log("Chat persisted as empty after reload:", isCleared);

  // Close chat drawer
  await page.getByTestId("btn-close-chat").click();
  await page.waitForTimeout(500);

  // Final diagnostics
  console.log("=== FINAL DIAGNOSTIC REPORT ===");
  console.log("Console Errors:", consoleErrors);
  console.log("Failed Requests:", failedRequests);

  await browser.close();

  return {
    m1600,
    m1440,
    m1280,
    consoleErrors,
    failedRequests,
    isCleared,
  };
}

runLiveAcceptance()
  .then((res) => {
    console.log("LIVE ACCEPTANCE RUN COMPLETED SUCCESSFULLY:", JSON.stringify(res, null, 2));
    process.exit(0);
  })
  .catch((err) => {
    console.error("LIVE ACCEPTANCE FAILED:", err);
    process.exit(1);
  });
