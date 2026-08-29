import { chromium } from "@playwright/test";

async function main() {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const contexts = browser.contexts();
  const context = contexts[0];
  const pages = context.pages();
  const page = pages[0];

  console.log("Current page URL:", page.url());
  console.log("Page Title:", await page.title());

  const authInfo = await page.evaluate(() => {
    return {
      localStorageKeys: Object.keys(localStorage),
      sessionStorageKeys: Object.keys(sessionStorage),
      pathname: window.location.pathname,
      bodyTextSnippet: document.body.innerText.slice(0, 500),
    };
  });

  console.log("Auth info & page state:", JSON.stringify(authInfo, null, 2));

  await page.screenshot({ path: "/tmp/acceptance_artifacts/initial_state.png", fullPage: true });
  console.log("Saved initial screenshot to /tmp/acceptance_artifacts/initial_state.png");
}

main().catch(console.error);
