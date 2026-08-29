import { chromium } from "@playwright/test";

async function main() {
  console.log("Connecting to Chrome over CDP...");
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const page = browser.contexts()[0].pages()[0];

  const consoleErrors: string[] = [];
  const networkFailures: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  page.on("requestfailed", (req) => {
    networkFailures.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
  });

  console.log("Locating Alex menu button...");
  const menuBtn = page.locator("[data-testid='btn-agent-menu-alex']").first();
  await menuBtn.click();
  console.log("Clicked Alex menu button!");

  const chatAction = page.locator("[data-testid='action-chat-alex']");
  await chatAction.waitFor({ state: "visible", timeout: 3000 });
  await chatAction.click();
  console.log("Clicked Chat with Alex action!");

  const drawer = page.locator("[data-testid='agent-chat-drawer']");
  await drawer.waitFor({ state: "visible", timeout: 5000 });
  console.log("Agent Chat Drawer is open!");

  const input = page.locator("[data-testid='input-chat-message']");
  await input.waitFor({ state: "visible", timeout: 5000 });
  const sendBtn = page.locator("[data-testid='btn-send-chat']");

  async function ask(question: string) {
    console.log(`\n========================================`);
    console.log(`ASKING: ${question}`);
    console.log(`========================================`);

    await input.fill(question);
    await sendBtn.click();

    console.log("Message sent. Waiting for Alex response to complete...");
    // Wait for "is analyzing..." indicator to appear and then disappear
    await page.waitForTimeout(3000);
    for (let i = 0; i < 40; i++) {
      const isAnalyzing = await page.evaluate(() => {
        return document.body.innerText.includes("is analyzing...");
      });
      if (!isAnalyzing) {
        console.log("Analysis complete!");
        break;
      }
      process.stdout.write(".");
      await page.waitForTimeout(2000);
    }
    console.log("");

    const response = await page.evaluate(() => {
      const msgs = document.querySelectorAll("[data-testid='agent-chat-drawer'] .prose");
      if (msgs.length === 0) return "NO_PROSE_FOUND";
      return (msgs[msgs.length - 1] as HTMLElement).innerText;
    });

    console.log(`\n[ALEX RESPONSE]:\n${response}\n`);
    return response;
  }

  // 1. Question 1
  const r1 = await ask("How did my last video perform?");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_q1.png" });

  // 2. Question 2
  const r2 = await ask("What is unusual about my last 10 videos?");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_q2.png" });

  // 3. Question 3
  const r3 = await ask("What should I make next and why?");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/alex_q3.png" });

  console.log("All 3 questions completed!");
  console.log("Console errors:", consoleErrors);
  console.log("Network failures:", networkFailures);
}

main().catch((err) => {
  console.error("Script failed:", err);
  process.exit(1);
});
