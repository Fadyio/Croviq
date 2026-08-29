import { chromium } from "@playwright/test";

async function main() {
  console.log("Connecting to browser CDP...");
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const context = browser.contexts()[0];
  const page = context.pages()[0];

  console.log("Page URL:", page.url());

  // Let's check if the chat drawer is already open
  let drawer = page.locator("[data-testid='agent-chat-drawer']");
  if (!(await drawer.isVisible())) {
    console.log("Chat drawer not visible. Clicking 'Chat with Alex'...");
    // Let's click AgentActionMenu button first if needed or direct "Chat with Alex"
    const chatBtn = page.getByRole("button", { name: "Chat with Alex" }).first();
    if (await chatBtn.isVisible()) {
      await chatBtn.click();
    } else {
      const alexMenu = page.getByRole("button", { name: "Open Alex menu" }).first();
      if (await alexMenu.isVisible()) {
        await alexMenu.click();
        await page.waitForTimeout(500);
        await page.getByRole("button", { name: "Chat with Alex" }).click();
      }
    }
  }

  await page.waitForSelector("[data-testid='agent-chat-drawer']", { timeout: 5000 });
  console.log("Chat drawer is OPEN!");

  const input = page.locator("[data-testid='input-chat-message']");
  await input.waitFor({ state: "visible", timeout: 5000 });
  console.log("Input is visible!");

  // 1. Question 1: "How did my last video perform?"
  console.log("Sending: How did my last video perform?");
  await input.fill("How did my last video perform?");
  await page.locator("[data-testid='btn-send-chat']").click();

  console.log("Waiting for response...");
  // Wait until sending indicator finishes
  await page.waitForTimeout(3000);
  for (let i = 0; i < 30; i++) {
    const isSending = await page.evaluate(() => {
      return document.body.innerText.includes("is analyzing...");
    });
    if (!isSending) {
      console.log("Finished analyzing!");
      break;
    }
    console.log(`Waiting for analysis to finish (${i * 2}s)...`);
    await page.waitForTimeout(2000);
  }

  // Get the last assistant message
  const chatMessages = await page.evaluate(() => {
    const msgs = document.querySelectorAll("[data-testid='agent-chat-drawer'] .prose");
    return Array.from(msgs).map((m) => (m as HTMLElement).innerText);
  });

  console.log("=== Q1 RESPONSE ===");
  console.log(chatMessages[chatMessages.length - 1]);
  console.log("===================");

  await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_q1_result.png" });

  await browser.close();
}

main().catch((err) => {
  console.error("Error in script:", err);
  process.exit(1);
});
