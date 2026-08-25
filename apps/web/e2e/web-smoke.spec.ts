import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.describe("Web Application Smoke", () => {
  test("loads successfully with visible split-screen login and zero browser errors", async ({
    page,
  }, testInfo) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    const failedRequests: string[] = [];
    const directBackendRequests: string[] = [];

    // Capture network requests to verify single-origin routing
    page.on("request", (req) => {
      const url = req.url();
      if (url.includes(":8080")) {
        directBackendRequests.push(url);
      }
    });

    // Capture browser console errors
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    // Capture unhandled exceptions in the page
    page.on("pageerror", (err) => {
      pageErrors.push(err.message || String(err));
    });

    // Capture failed network requests
    page.on("requestfailed", (request) => {
      failedRequests.push(
        `${request.method()} ${request.url()}: ${request.failure()?.errorText ?? "unknown error"}`,
      );
    });

    // Navigate to local web frontend
    const targetUrl = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173";
    const response = await page.goto(targetUrl, { waitUntil: "networkidle" });

    // Assert page reached and returned successful HTTP status
    expect(response, "Expected non-null response from web server").not.toBeNull();
    expect(
      response?.ok(),
      `Expected successful HTTP response, got ${response?.status()}`,
    ).toBeTruthy();

    // Verify Croviq logo is visible
    const logo = page.getByRole("img", { name: "Croviq" });
    await expect(logo, "Croviq logo must be visible on the page").toBeVisible();

    // Verify concise statement
    const statement = page.getByRole("heading", { name: "CI/CD for video creators." });
    await expect(statement, "Statement must be visible").toBeVisible();

    // Verify Google Sign-In card elements
    const loginHeading = page.getByRole("heading", { name: "Sign in to Croviq" });
    await expect(loginHeading).toBeVisible();

    const googleButton = page.getByRole("button", { name: "Continue with Google" });
    await expect(googleButton, "Continue with Google button must be visible").toBeVisible();

    const demoNotice = page.getByText("Private hackathon demo — authorized account only.");
    await expect(demoNotice, "Hackathon notice must be visible").toBeVisible();

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

    // Verify single-origin routing: browser must not make direct calls to :8080
    expect(
      directBackendRequests,
      `Expected zero direct browser requests to :8080, found: ${JSON.stringify(directBackendRequests)}`,
    ).toEqual([]);

    // Capture screenshot on success
    const screenshotPath = path.resolve(__dirname, "screenshots", "web-smoke.png");
    const screenshotBuffer = await page.screenshot({ path: screenshotPath, fullPage: true });

    await testInfo.attach("web-smoke-success", {
      body: screenshotBuffer,
      contentType: "image/png",
    });
  });
});
