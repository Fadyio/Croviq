import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.describe("Viewport Layout and Responsive Smoke", () => {
  const targetUrl = process.env.TARGET_URL || "/";
  for (const vp of [
    { name: "1440px", width: 1440, height: 900 },
    { name: "1280px", width: 1280, height: 800 },
    { name: "390px", width: 390, height: 844 },
  ]) {
    test(`verifies production at ${vp.name} (${vp.width}x${vp.height}) with zero errors and responsive login`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      const consoleErrors: string[] = [];
      const pageErrors: string[] = [];
      const failedRequests: string[] = [];

      page.on("console", (msg) => {
        if (msg.type() === "error") {
          consoleErrors.push(msg.text());
        }
      });

      page.on("pageerror", (err) => {
        pageErrors.push(err.message || String(err));
      });

      page.on("requestfailed", (request) => {
        failedRequests.push(
          `${request.method()} ${request.url()}: ${request.failure()?.errorText ?? "unknown error"}`,
        );
      });

      const response = await page.goto(targetUrl, { waitUntil: "networkidle", timeout: 30000 });

      expect(response, "Expected non-null response from production server").not.toBeNull();
      expect(
        response?.ok(),
        `Expected successful HTTP 200 response, got ${response?.status()}`,
      ).toBeTruthy();

      // Verify Croviq logo
      const logo = page.getByRole("img", { name: "Croviq" });
      await expect(logo, "Croviq logo must be visible on the page").toBeVisible();

      // Verify Google sign-in button
      const googleButton = page.getByRole("button", { name: "Continue with Google" });
      await expect(googleButton, "'Continue with Google' button must be visible").toBeVisible();

      // Verify Hackathon notice
      const notice = page.getByText("Private hackathon demo — authorized account only.");
      await expect(notice, "Demo notice must be visible").toBeVisible();

      // Verify zero console errors, page errors, and failed network requests
      expect(
        consoleErrors,
        `Expected zero console errors, found: ${JSON.stringify(consoleErrors)}`,
      ).toEqual([]);
      expect(pageErrors, `Expected zero page errors, found: ${JSON.stringify(pageErrors)}`).toEqual(
        [],
      );
      expect(
        failedRequests,
        `Expected zero failed network requests, found: ${JSON.stringify(failedRequests)}`,
      ).toEqual([]);

      // Capture screenshot at specified viewport
      const screenshotPath = path.resolve(__dirname, "screenshots", `production-${vp.name}.png`);
      const screenshotBuffer = await page.screenshot({ path: screenshotPath, fullPage: true });

      await testInfo.attach(`production-${vp.name}`, {
        body: screenshotBuffer,
        contentType: "image/png",
      });
    });
  }
});
