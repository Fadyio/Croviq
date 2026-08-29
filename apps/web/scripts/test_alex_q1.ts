import { chromium, type Page } from "@playwright/test";

async function main() {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const page = browser.contexts()[0].pages()[0];

  const consoleErrors: string[] = [];
  const networkFailures: string[] = [];
  const networkLogs: Array<{ method: string; url: string; status: number }> = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
      console.error("[Console Error]:", msg.text());
    }
  });

  page.on("requestfailed", (req) => {
    networkFailures.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
    console.error("[Request Failed]:", req.method(), req.url());
  });

  page.on("response", (res) => {
    if (res.url().includes("/api/")) {
      networkLogs.push({ method: res.request().method(), url: res.url(), status: res.status() });
    }
  });

  console.log("Navigating/checking Alex drawer...");

  // Check if Alex drawer or chat button is present
  // In Croviq UI, let's see how Alex chat is opened or if drawer is present
  const alexButton = page.getByRole("button", { name: /Alex/i }).first();
  if (await alexButton.isVisible()) {
    console.log("Clicking Alex button...");
    await alexButton.click();
    await page.waitForTimeout(1000);
  }

  // Let's inspect visible buttons / elements
  const buttons = await page.evaluate(() => {
    return Array.from(document.querySelectorAll("button")).map((b) => ({
      text: b.innerText.trim(),
      ariaLabel: b.getAttribute("aria-label"),
      title: b.getAttribute("title"),
    }));
  });
  console.log("Visible buttons:", buttons);

  // Take screenshot of current state
  await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_drawer_open.png" });

  // Look for chat textarea / input
  const chatInput = page
    .locator(
      "textarea, input[type='text'][placeholder*='Alex'], input[placeholder*='message'], textarea[placeholder*='Alex'], textarea[placeholder*='Ask']",
    )
    .first();
  console.log("Chat input visible:", await chatInput.isVisible());

  if (await chatInput.isVisible()) {
    console.log("Sending Question 1: How did my last video perform?");
    await chatInput.fill("How did my last video perform?");
    await page.keyboard.press("Enter");

    console.log("Waiting for Alex response...");
    // Wait for response to appear (streaming or completion)
    await page.waitForTimeout(15000);

    const messages = await page.evaluate(() => {
      const msgs = document.querySelectorAll(
        "[data-testid='chat-message'], .chat-message, [role='article'], .prose",
      );
      return Array.from(msgs).map((m) => (m as HTMLElement).innerText);
    });

    console.log("Chat messages retrieved:", messages);
    await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_q1_response.png" });
  }
}

main().catch(console.error);
