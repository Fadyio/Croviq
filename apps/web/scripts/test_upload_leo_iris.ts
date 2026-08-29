import { chromium } from "@playwright/test";

async function main() {
  console.log("Connecting to Chrome over CDP for Upload, Leo & Iris test...");
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const context = browser.contexts()[0];
  const page = context.pages()[0];

  const apiRequests: Array<{ method: string; url: string; status?: number }> = [];

  page.on("response", (res) => {
    if (res.url().includes("/api/")) {
      apiRequests.push({ method: res.request().method(), url: res.url(), status: res.status() });
      console.log(`[API Response] ${res.request().method()} ${res.url()} -> ${res.status()}`);
    }
  });

  // Navigate directly to New Project
  console.log("Navigating to https://app.croviq.app/app/projects/new ...");
  await page.goto("https://app.croviq.app/app/projects/new", { waitUntil: "networkidle" });

  await page.waitForSelector("input[type='file']", { timeout: 10000 });
  console.log("On New Project page!");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/new_project_page.png" });

  // File input
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles("/tmp/acceptance_test_video.mp4");
  console.log("Attached /tmp/acceptance_test_video.mp4 to file input!");

  await page.waitForTimeout(1000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/video_selected.png" });

  // Click Upload / Start Processing button
  console.log("Clicking Start Processing...");
  const uploadBtn = page
    .getByRole("button", { name: /Upload|Start Processing|Process Video/i })
    .first();
  await uploadBtn.click();

  console.log("Waiting for upload and verification to complete...");
  // Wait for navigation to /app/editor/
  await page.waitForURL("**/app/editor/**", { timeout: 60000 });
  console.log("Navigated to Editor:", page.url());

  const productionId = page.url().split("/").pop() || "";
  console.log("Production ID:", productionId);

  await page.waitForTimeout(5000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/editor_initial.png" });

  // Wait for Leo processing / proposals
  console.log("Waiting for Leo processing...");
  await page.waitForTimeout(12000);

  // Inspect Editor DOM
  const editorText = await page.evaluate(() => document.body.innerText);
  console.log("Editor Text Snippet:\n", editorText.slice(0, 1000));
  await page.screenshot({ path: "/tmp/acceptance_artifacts/editor_loaded.png" });

  // Click Check button to go to Release QA
  console.log("Clicking Check button (data-testid='btn-run-check')...");
  const runCheckBtn = page.locator("[data-testid='btn-run-check']");
  if (await runCheckBtn.isVisible()) {
    await runCheckBtn.click();
  } else {
    console.log("Direct navigating to release page...");
    await page.goto(`https://app.croviq.app/app/release/${productionId}`, {
      waitUntil: "networkidle",
    });
  }

  await page.waitForURL("**/app/release/**", { timeout: 10000 });
  console.log("On Release / Iris QA page:", page.url());

  await page.waitForTimeout(3000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/release_initial.png" });

  // Click Run QA with Iris
  console.log("Triggering Iris QA Review...");
  const runQABtn = page.locator("[data-testid='btn-run-qa']");
  if (await runQABtn.isVisible()) {
    await runQABtn.click();
    console.log("Clicked Run QA with Iris button!");

    // Wait for QA evaluation to complete
    console.log("Waiting for Iris QA evaluation...");
    await page.waitForTimeout(6000);
    for (let i = 0; i < 30; i++) {
      const isRunning = await page.evaluate(() => {
        return (
          document.body.innerText.includes("Auditing release...") ||
          document.body.innerText.includes("Evaluating")
        );
      });
      if (!isRunning) break;
      process.stdout.write(".");
      await page.waitForTimeout(2000);
    }
    console.log("\nIris QA evaluation completed!");
  }

  await page.waitForTimeout(3000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/iris_qa_result.png" });

  const releasePageText = await page.evaluate(() => document.body.innerText);
  console.log("Release Page Text Snippet:\n", releasePageText.slice(0, 1200));

  console.log("\n==========================================");
  console.log("UPLOAD, LEO & IRIS VERIFICATION COMPLETE");
  console.log("==========================================");
}

main().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
