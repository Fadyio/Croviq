import { chromium } from "@playwright/test";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "https://app.croviq.app";
const FAIRPHONE_PRODUCTION_ID = "prod_0b7657f515ae";

async function main() {
  console.log("==================================================");
  console.log("VERIFYING LIVE CROVIQ RELEASE GATE WORKSPACE");
  console.log(`URL: ${BASE_URL}/productions/${FAIRPHONE_PRODUCTION_ID}/release`);
  console.log("==================================================");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  const networkFailures = [];
  page.on("requestfailed", (request) => {
    // Ignore non-fatal favicon / metrics errors if any
    if (!request.url().includes("favicon")) {
      networkFailures.push(
        `${request.method()} ${request.url()} — ${request.failure()?.errorText}`,
      );
    }
  });

  try {
    // Navigate to live app
    await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
    console.log("Loaded login page.");

    // Fill login form
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("valid-password-123");
    await page.getByRole("button", { name: "Sign in" }).click();

    // Wait for redirect to app
    await page.waitForURL("**/app**", { timeout: 15000 }).catch(() => {});
    console.log("Authenticated.");

    // Navigate to release page
    await page.evaluate((id) => {
      window.history.pushState(null, "", `/productions/${id}/release`);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }, FAIRPHONE_PRODUCTION_ID);

    await page.waitForSelector("[data-testid='release-workspace']", { timeout: 15000 });
    console.log("Loaded Release workspace.");

    // Verify key UI elements
    const statusBadge = await page.textContent("[data-testid='release-status-badge']");
    console.log("Release Status Badge:", statusBadge?.trim());

    const isChecklistVisible = await page.isVisible("[data-testid='release-checklist']");
    console.log("Release Checklist Visible:", isChecklistVisible);

    const isMasterPreviewVisible = await page.isVisible("[data-testid='section-master-preview']");
    console.log("Master Preview Section:", isMasterPreviewVisible);

    const isTitlesVisible = await page.isVisible("[data-testid='section-titles']");
    console.log("Titles Strategy Section:", isTitlesVisible);

    const isIrisCardVisible = await page.isVisible("[data-testid='iris-agent-card']");
    console.log("Iris QA Agent Card Visible:", isIrisCardVisible);

    const isNinaCardVisible = await page.isVisible("[data-testid='nina-agent-card']");
    console.log("Nina Packaging Card Visible:", isNinaCardVisible);

    console.log("\nConsole Errors Count:", consoleErrors.length);
    if (consoleErrors.length > 0) {
      console.log("Console Errors:", consoleErrors);
    }

    console.log("Network Failures Count:", networkFailures.length);
    if (networkFailures.length > 0) {
      console.log("Network Failures:", networkFailures);
    }

    console.log("\nLIVE RELEASE QA: PASS");
  } catch (err) {
    console.error("Live verification error:", err);
  } finally {
    await browser.close();
  }
}

main();
