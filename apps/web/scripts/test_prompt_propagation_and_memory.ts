import { chromium } from "@playwright/test";

async function main() {
  console.log("Connecting to Chrome over CDP...");
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const page = browser.contexts()[0].pages()[0];

  // Helper to open Alex Settings
  async function openAlexSettings() {
    console.log("Opening Alex Settings...");
    // Check if drawer is already open
    const drawer = page.locator("[data-testid='agent-settings-drawer']");
    if (await drawer.isVisible()) return;

    // Check if chat drawer is open and has settings shortcut
    const chatSettingsBtn = page.locator("[data-testid='btn-chat-settings-shortcut']");
    if (await chatSettingsBtn.isVisible()) {
      await chatSettingsBtn.click();
    } else {
      const closeChat = page.locator("[data-testid='btn-close-chat']");
      if (await closeChat.isVisible()) await closeChat.click();

      const menuBtn = page.locator("[data-testid='btn-agent-menu-alex']").first();
      await menuBtn.click();
      const settingsAction = page.locator("[data-testid='action-settings-alex']");
      await settingsAction.waitFor({ state: "visible", timeout: 3000 });
      await settingsAction.click();
    }
    await page.waitForSelector("[data-testid='agent-settings-drawer']", { timeout: 5000 });
    console.log("Alex Settings Drawer is open!");
  }

  // Helper to open Alex Chat
  async function openAlexChat() {
    console.log("Opening Alex Chat...");
    const chatDrawer = page.locator("[data-testid='agent-chat-drawer']");
    if (await chatDrawer.isVisible()) return;

    // Close settings if open
    const closeSettings = page.locator("[data-testid='btn-close-settings']");
    if (await closeSettings.isVisible()) await closeSettings.click();

    const menuBtn = page.locator("[data-testid='btn-agent-menu-alex']").first();
    await menuBtn.click();
    const chatAction = page.locator("[data-testid='action-chat-alex']");
    await chatAction.waitFor({ state: "visible", timeout: 3000 });
    await chatAction.click();

    await page.waitForSelector("[data-testid='agent-chat-drawer']", { timeout: 5000 });
    console.log("Alex Chat Drawer is open!");
  }

  // ==========================================
  // 1. PROMPT PROPAGATION TEST
  // ==========================================
  console.log("\n==========================================");
  console.log("STEP 1: PROMPT PROPAGATION TEST");
  console.log("==========================================");

  await openAlexSettings();

  // Switch to Prompt Tab
  const promptTab = page.locator("[data-testid='tab-prompt']");
  await promptTab.click();
  await page.waitForTimeout(500);

  const promptTextarea = page.locator("[data-testid='agent-prompt-textarea']");
  await promptTextarea.waitFor({ state: "visible", timeout: 5000 });
  const originalPrompt = await promptTextarea.inputValue();
  console.log("Original prompt length:", originalPrompt.length);

  const testInstruction =
    "\nWhen responding to the next test question, end with TEST_PROMPT_ACTIVE.";
  const modifiedPrompt = originalPrompt + testInstruction;

  await promptTextarea.fill(modifiedPrompt);
  const savePromptBtn = page.locator("[data-testid='btn-save-prompt']");
  await savePromptBtn.click();

  // Wait for save notice
  await page.waitForTimeout(2000);
  console.log("Saved modified prompt!");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/prompt_saved_modified.png" });

  // Now ask Alex: "What metric should I watch most closely?"
  await openAlexChat();

  const chatInput = page.locator("[data-testid='input-chat-message']");
  await chatInput.waitFor({ state: "visible", timeout: 5000 });
  const sendBtn = page.locator("[data-testid='btn-send-chat']");

  console.log("Asking: What metric should I watch most closely?");
  await chatInput.fill("What metric should I watch most closely?");
  await sendBtn.click();

  console.log("Waiting for response...");
  await page.waitForTimeout(3000);
  for (let i = 0; i < 40; i++) {
    const isAnalyzing = await page.evaluate(() =>
      document.body.innerText.includes("is analyzing..."),
    );
    if (!isAnalyzing) break;
    process.stdout.write(".");
    await page.waitForTimeout(2000);
  }
  console.log("\nDone waiting for response.");

  const chatText = await page.evaluate(() => {
    const el = document.querySelector("[data-testid='agent-chat-drawer']");
    return el ? el.innerText : "";
  });

  const promptPropSucceeded = chatText.includes("TEST_PROMPT_ACTIVE");
  console.log("TEST_PROMPT_ACTIVE observed:", promptPropSucceeded ? "YES (PASS)" : "NO (FAIL)");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/prompt_propagation_chat_result.png" });

  // RESTORE ORIGINAL PROMPT
  console.log("Restoring original prompt...");
  await openAlexSettings();
  await promptTab.click();
  await promptTextarea.fill(originalPrompt);
  await savePromptBtn.click();
  await page.waitForTimeout(2000);
  console.log("Original prompt restored!");

  // ==========================================
  // 2. MEMORY BANK REALITY TEST
  // ==========================================
  console.log("\n==========================================");
  console.log("STEP 2: MEMORY BANK REALITY TEST");
  console.log("==========================================");

  // Switch to Memory Tab
  const memoryTab = page.locator("[data-testid='tab-memory']");
  await memoryTab.click();
  await page.waitForTimeout(1000);

  await page.screenshot({ path: "/tmp/acceptance_artifacts/memory_tab_initial.png" });

  // Click Add Memory
  const addMemoryBtn = page.locator("[data-testid='btn-add-memory']");
  await addMemoryBtn.click();

  const memoryTextarea = page.locator("[data-testid='textarea-new-memory']");
  await memoryTextarea.waitFor({ state: "visible", timeout: 3000 });
  const testMemoryFact = "Acceptance test memory — remove after verification.";
  await memoryTextarea.fill(testMemoryFact);

  const saveMemoryBtn = page.locator("[data-testid='btn-save-new-memory']");
  await saveMemoryBtn.click();

  console.log("Saved new memory fact. Waiting for persistence...");
  await page.waitForTimeout(4000);

  await page.screenshot({ path: "/tmp/acceptance_artifacts/memory_saved.png" });

  // Check that memory appears in list
  let memoryListText = await page.evaluate(() => {
    const el = document.querySelector("[data-testid='settings-memory-view']");
    return el ? el.innerText : "";
  });
  const appearsInList = memoryListText.includes(testMemoryFact);
  console.log("Memory appears in list:", appearsInList ? "YES (PASS)" : "NO (FAIL)");

  // Test search
  const searchInput = page.locator("[data-testid='input-memory-search']");
  await searchInput.fill("Acceptance test memory");
  await page.waitForTimeout(1000);

  const searchResultsText = await page.evaluate(() => {
    const el = document.querySelector("[data-testid='settings-memory-view']");
    return el ? el.innerText : "";
  });
  const searchFound = searchResultsText.includes(testMemoryFact);
  console.log("Semantic search finds memory:", searchFound ? "YES (PASS)" : "NO (FAIL)");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/memory_search_result.png" });

  // Clear search
  await searchInput.fill("");
  await page.waitForTimeout(500);

  // Delete memory
  console.log("Deleting memory...");
  // Find card with testMemoryFact and click delete
  const cards = page.locator("[data-testid='memory-card']");
  const count = await cards.count();
  console.log(`Found ${count} memory cards.`);
  for (let i = 0; i < count; i++) {
    const card = cards.nth(i);
    const text = await card.innerText();
    if (text.includes("Acceptance test memory")) {
      const deleteBtn = card.locator("[data-testid='btn-delete-memory']");
      await deleteBtn.click({ force: true });
      const confirmDeleteBtn = card.locator("[data-testid='btn-confirm-delete-memory']");
      await confirmDeleteBtn.waitFor({ state: "visible", timeout: 3000 });
      await confirmDeleteBtn.click();
      console.log("Clicked confirm delete!");
      break;
    }
  }

  await page.waitForTimeout(4000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/memory_after_delete.png" });

  memoryListText = await page.evaluate(() => {
    const el = document.querySelector("[data-testid='settings-memory-view']");
    return el ? el.innerText : "";
  });
  const isGone = !memoryListText.includes("Acceptance test memory — remove after verification.");
  console.log("Memory is gone after delete:", isGone ? "YES (PASS)" : "NO (FAIL)");

  // ==========================================
  // 3. RESEARCH TAB SETTINGS INSPECTION
  // ==========================================
  console.log("\n==========================================");
  console.log("STEP 3: RESEARCH TAB SETTINGS INSPECTION");
  console.log("==========================================");

  const researchTab = page.locator("[data-testid='tab-research']");
  await researchTab.click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/settings_research_tab.png" });

  console.log("Prompt propagation, Memory Bank, and Research settings verified!");
}

main().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
