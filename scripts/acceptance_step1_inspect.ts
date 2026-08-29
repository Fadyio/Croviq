import { chromium } from "@playwright/test";

async function main() {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const contexts = browser.contexts();
  const context = contexts[0];
  const pages = context.pages();
  const page = pages[0];

  console.log("Current page URL:", page.url());
  console.log("Page Title:", await page.title());

  // Listen to console and request events
  const consoleMessages: string[] = [];
  const errors: string[] = [];
  const failedRequests: string[] = [];
  const responses: Array<{ url: string; status: number; method: string }> = [];

  page.on("console", (msg) => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
    if (msg.type() === "error") {
      errors.push(msg.text());
    }
  });

  page.on("pageerror", (err) => {
    errors.push(err.message || String(err));
  });

  page.on("requestfailed", (req) => {
    failedRequests.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText || "failed"}`);
  });

  page.on("response", (res) => {
    responses.push({ url: res.url(), status: res.status(), method: res.request().method() });
  });

  // Evaluate user state from localStorage / DOM
  const authInfo = await page.evaluate(() => {
    return {
      localStorageKeys: Object.keys(localStorage),
      sessionStorageKeys: Object.keys(sessionStorage),
      pathname: window.location.pathname,
      bodyTextSnippet: document.body.innerText.slice(0, 500),
    };
  });

  console.log("Auth info & page state:", JSON.stringify(authInfo, null, 2));

  // Take an initial screenshot
  await page.screenshot({ path: "/tmp/acceptance_artifacts/initial_state.png", fullPage: true });
  console.log("Saved initial screenshot to /tmp/acceptance_artifacts/initial_state.png");
}

main().catch(console.error);
