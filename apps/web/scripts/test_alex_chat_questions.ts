import { chromium } from "@playwright/test";

async function main() {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const page = browser.contexts()[0].pages()[0];

  const consoleErrors: string[] = [];
  const networkFailures: string[] = [];
  const apiCalls: Array<{ method: string; url: string; status: number }> = [];

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
      apiCalls.push({ method: res.request().method(), url: res.url(), status: res.status() });
    }
  });

  console.log("Opening Chat with Alex...");
  const chatWithAlexBtn = page.getByRole("button", { name: "Chat with Alex" }).first();
  if (await chatWithAlexBtn.isVisible()) {
    await chatWithAlexBtn.click();
    await page.waitForTimeout(1000);
  }

  // Check drawer title and inputs
  const chatInput = page.getByPlaceholder(/Ask Alex|Message Alex|Type a message/i).first();
  console.log("Chat input located:", await chatInput.isVisible());

  // Function to send a message and wait for Alex response
  async function askAlex(question: string): Promise<string> {
    console.log(`\n========================================`);
    console.log(`Asking: "${question}"`);
    console.log(`========================================`);

    await chatInput.fill(question);
    const sendButton = page
      .locator("button[type='submit'], button[aria-label*='Send'], button:has-text('Send')")
      .last();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await chatInput.press("Enter");
    }

    // Wait for response to finish generating
    console.log("Waiting for Alex to finish response...");
    // Let's poll until the response stabilizes or stop indicator goes away
    await page.waitForTimeout(4000);

    for (let i = 0; i < 30; i++) {
      await page.waitForTimeout(2000);
      const isGenerating = await page.evaluate(() => {
        return !!document.querySelector(
          "[data-testid='generating-indicator'], .animate-pulse, [aria-label='Generating']",
        );
      });
      if (!isGenerating) {
        // Wait another 2s to be certain
        await page.waitForTimeout(2000);
        break;
      }
      console.log(`Still generating... (${i * 2}s)`);
    }

    // Extract the latest message
    const lastMessageText = await page.evaluate(() => {
      const messages = document.querySelectorAll(
        ".prose, [data-message-role='assistant'], [data-testid='assistant-message']",
      );
      if (messages.length > 0) {
        return (messages[messages.length - 1] as HTMLElement).innerText;
      }
      // Fallback to all chat text
      const container = document.querySelector(
        "[data-testid='chat-messages-container'], .chat-messages",
      );
      return container ? (container as HTMLElement).innerText : document.body.innerText;
    });

    console.log(`\n[Alex Response]:\n${lastMessageText}\n`);
    return lastMessageText;
  }

  // 1. Question 1
  const q1Response = await askAlex("How did my last video perform?");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_q1_full.png" });

  // 2. Question 2
  const q2Response = await askAlex("What is unusual about my last 10 videos?");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_q2_full.png" });

  // 3. Question 3
  const q3Response = await askAlex("What should I make next and why?");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_q3_full.png" });

  console.log("All 3 questions completed.");
  console.log("Console errors during chat:", consoleErrors);
  console.log("Network failures during chat:", networkFailures);
}

main().catch(console.error);
