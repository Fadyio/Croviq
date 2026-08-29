import { chromium } from "@playwright/test";

async function main() {
  console.log("Connecting to Chrome over CDP for Memory Bank test...");
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const page = browser.contexts()[0].pages()[0];

  // Helper to open Alex Settings
  async function openAlexSettings() {
    const drawer = page.locator("[data-testid='agent-settings-drawer']");
    if (await drawer.isVisible()) return;

    const chatDrawer = page.locator("[data-testid='agent-chat-drawer']");
    if (await chatDrawer.isVisible()) {
      const chatSettingsBtn = page.locator("[data-testid='btn-chat-settings-shortcut']");
      if (await chatSettingsBtn.isVisible()) {
        await chatSettingsBtn.click();
        await page.waitForSelector("[data-testid='agent-settings-drawer']", { timeout: 5000 });
        return;
      }
      const closeChat = page.locator("[data-testid='btn-close-chat']");
      if (await closeChat.isVisible()) await closeChat.click();
    }

    const menuBtn = page.locator("[data-testid='btn-agent-menu-alex']").first();
    await menuBtn.click();
    const settingsAction = page.locator("[data-testid='action-settings-alex']");
    await settingsAction.waitFor({ state: "visible", timeout: 3000 });
    await settingsAction.click();
    await page.waitForSelector("[data-testid='agent-settings-drawer']", { timeout: 5000 });
  }

  await openAlexSettings();
  console.log("Alex Settings Drawer is open!");

  // Switch to Memory Tab
  const memoryTab = page.locator("[data-testid='tab-memory']");
  await memoryTab.click();
  await page.waitForTimeout(1000);

  // Click Add Memory Toggle
  console.log("Clicking Add Memory Toggle...");
  const addToggle = page.locator("[data-testid='btn-add-memory-toggle']");
  await addToggle.waitFor({ state: "visible", timeout: 5000 });
  await addToggle.click();

  const memoryTextarea = page.locator("[data-testid='textarea-new-memory']");
  await memoryTextarea.waitFor({ state: "visible", timeout: 3000 });
  const testFact = "Acceptance test memory — remove after verification.";
  await memoryTextarea.fill(testFact);

  console.log("Clicking Save Memory...");
  const saveMemoryBtn = page.locator("[data-testid='btn-save-new-memory']");
  await saveMemoryBtn.click();

  console.log("Waiting for persistence...");
  await page.waitForTimeout(4000);

  await page.screenshot({ path: "/tmp/acceptance_artifacts/memory_bank_created.png" });

  let memoryListText = await page.evaluate(() => {
    const el = document.querySelector("[data-testid='settings-memory-view']");
    return el ? el.innerText : "";
  });
  const inList = memoryListText.includes(testFact);
  console.log("Memory appears in list:", inList ? "YES (PASS)" : "NO (FAIL)");

  // Search test
  console.log("Testing search...");
  const searchInput = page.locator("[data-testid='input-memory-search']");
  await searchInput.fill("Acceptance test memory");
  await page.waitForTimeout(1500);

  let searchResultsText = await page.evaluate(() => {
    const el = document.querySelector("[data-testid='settings-memory-view']");
    return el ? el.innerText : "";
  });
  const found = searchResultsText.includes(testFact);
  console.log("Search finds memory:", found ? "YES (PASS)" : "NO (FAIL)");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/memory_bank_search.png" });

  // Clear search
  await searchInput.fill("");
  await page.waitForTimeout(1000);

  // Delete memory
  console.log("Deleting memory...");
  const cards = page.locator("[data-testid='memory-card']");
  const count = await cards.count();
  console.log(`Scanning ${count} memory cards...`);
  for (let i = 0; i < count; i++) {
    const card = cards.nth(i);
    const text = await card.innerText();
    if (text.includes(testFact)) {
      const deleteBtn = card.locator("[data-testid='btn-delete-memory']");
      await deleteBtn.click({ force: true });
      const confirmDeleteBtn = card.locator("[data-testid='btn-confirm-delete-memory']");
      await confirmDeleteBtn.waitFor({ state: "visible", timeout: 3000 });
      await confirmDeleteBtn.click();
      console.log("Delete confirmed!");
      break;
    }
  }

  await page.waitForTimeout(4000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/memory_bank_deleted.png" });

  memoryListText = await page.evaluate(() => {
    const el = document.querySelector("[data-testid='settings-memory-view']");
    return el ? el.innerText : "";
  });
  const gone = !memoryListText.includes(testFact);
  console.log("Memory is gone after delete:", gone ? "YES (PASS)" : "NO (FAIL)");

  console.log("Memory Bank acceptance test finished successfully!");
}

main().catch((err) => {
  console.error("Memory test failed:", err);
  process.exit(1);
});
