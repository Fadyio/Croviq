import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const PASSWORD = "valid-password";
const BASE_URL = "https://app.croviq.app";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  const consoleLogs = [];
  const failedRequests = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleLogs.push(msg.text());
    }
  });

  page.on("requestfailed", (req) => {
    failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText})`);
  });

  console.log("Navigating to login page on production...");
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  console.log("Waiting for navigation to /app...");
  await page.waitForURL("**/app*", { timeout: 15000 });
  await page.waitForTimeout(1500);

  // 1. Live Overview
  const outDir = path.resolve("apps/web/e2e/screenshots/production");
  fs.mkdirSync(outDir, { recursive: true });

  console.log("Capturing live overview screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-overview-1440.png"), fullPage: false });

  // 2. Live Performance
  console.log("Navigating to /app/performance...");
  await page.goto(`${BASE_URL}/app/performance`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  console.log("Capturing live performance screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-performance-1440.png"), fullPage: false });

  // 3. Live Experiments
  console.log("Navigating to /app/experiments...");
  await page.goto(`${BASE_URL}/app/experiments`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  console.log("Capturing live experiments screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-experiments-1440.png"), fullPage: false });

  // 4. Live New Project
  console.log("Navigating to /projects/new...");
  await page.goto(`${BASE_URL}/projects/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  console.log("Capturing live new project screenshot (1440)...");
  await page.screenshot({ path: path.join(outDir, "live-new-project-1440.png"), fullPage: false });

  // 5. Live New Project 1280
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(500);
  console.log("Capturing live new project screenshot (1280)...");
  await page.screenshot({ path: path.join(outDir, "live-new-project-1280.png"), fullPage: false });

  console.log("Console errors:", consoleLogs);
  console.log("Failed requests:", failedRequests);

  await browser.close();
}

main().catch((err) => {
  console.error("Failed to capture live screenshots:", err);
  process.exit(1);
});
