import { chromium, type Page } from "@playwright/test";

const VIEWPORTS = [
  { name: "1600x900", width: 1600, height: 900 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
];

async function main() {
  console.log("Connecting to browser for multi-resolution visual capture...");
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const context = browser.contexts()[0];
  const page = context.pages()[0];

  for (const vp of VIEWPORTS) {
    console.log(`\n========================================`);
    console.log(`CAPTURING RESOLUTION: ${vp.name} (${vp.width}x${vp.height})`);
    console.log(`========================================`);

    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(500);

    // 1. Home
    console.log("Navigating to Home (/app)...");
    await page.goto("https://app.croviq.app/app", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `/tmp/acceptance_artifacts/home_${vp.name}.png` });

    // 2. Alex Chat
    console.log("Opening Alex Chat...");
    const menuBtn = page.locator("[data-testid='btn-agent-menu-alex']").first();
    if (await menuBtn.isVisible()) {
      await menuBtn.click();
      const chatAction = page.locator("[data-testid='action-chat-alex']");
      await chatAction.waitFor({ state: "visible", timeout: 3000 });
      await chatAction.click();
      await page.waitForSelector("[data-testid='agent-chat-drawer']", { timeout: 5000 });
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `/tmp/acceptance_artifacts/alex_chat_${vp.name}.png` });

      // 3. Alex Settings
      console.log("Opening Alex Settings...");
      const chatSettingsBtn = page.locator("[data-testid='btn-chat-settings-shortcut']");
      if (await chatSettingsBtn.isVisible()) {
        await chatSettingsBtn.click();
        await page.waitForSelector("[data-testid='agent-settings-drawer']", { timeout: 5000 });
        await page.waitForTimeout(1000);
        await page.screenshot({ path: `/tmp/acceptance_artifacts/alex_settings_${vp.name}.png` });
        const closeSettings = page.locator("[data-testid='btn-close-settings']");
        if (await closeSettings.isVisible()) await closeSettings.click();
      }
    }

    // 4. New Project
    console.log("Navigating to New Project (/projects/new)...");
    await page.goto("https://app.croviq.app/projects/new", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `/tmp/acceptance_artifacts/new_project_${vp.name}.png` });
  }

  // 5. Editor and 6. Iris / QA Result (at 1440x900 and 1600x900)
  await page.setViewportSize({ width: 1440, height: 900 });
  console.log("Navigating to existing production in Editor...");
  // Let's get productions list from API to find a production ID
  const productionsResp = await page.evaluate(async () => {
    const res = await fetch("/api/productions");
    if (!res.ok) return [];
    const data = await res.json();
    return data.productions || data || [];
  });

  console.log(`Found ${productionsResp.length} productions in catalog.`);
  if (productionsResp.length > 0) {
    const prodId = productionsResp[0].production_id;
    console.log(`Navigating to Editor for ${prodId}...`);
    await page.goto(`https://app.croviq.app/productions/${prodId}/editor`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "/tmp/acceptance_artifacts/editor_1440x900.png" });

    console.log(`Navigating to Release / Iris QA for ${prodId}...`);
    await page.goto(`https://app.croviq.app/productions/${prodId}/release`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "/tmp/acceptance_artifacts/iris_check_result_1440x900.png" });
  }

  console.log("\nMulti-resolution screenshot capture complete!");
}

main().catch((err) => {
  console.error("Capture failed:", err);
  process.exit(1);
});
