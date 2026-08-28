import { chromium } from "@playwright/test";

const BASE_URL = "https://app.croviq.app";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on("console", (msg) => console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`));
  page.on("response", (resp) => {
    if (!resp.ok()) {
      console.log(`[HTTP ${resp.status()}] ${resp.url()}`);
    }
  });

  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  console.log("On login page:", await page.title());

  await page.getByLabel("Email").fill("demo@croviq.app");
  await page.getByLabel("Password").fill("CroviqDemo2026!");
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForTimeout(4000);
  console.log("Current URL:", page.url());
  console.log("Body text:", await page.locator("body").innerText());

  await browser.close();
}

main().catch(console.error);
