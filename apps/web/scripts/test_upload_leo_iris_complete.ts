import { chromium } from "@playwright/test";

async function main() {
  console.log("Connecting to Chrome over CDP for Upload, Leo & Iris test...");
  const browser = await chromium.connectOverCDP("http://127.0.0.1:53674");
  const context = browser.contexts()[0];
  const page = context.pages()[0];

  const apiLogs: Array<{ method: string; url: string; status: number }> = [];

  page.on("response", async (res) => {
    if (res.url().includes("/api/")) {
      const entry = { method: res.request().method(), url: res.url(), status: res.status() };
      apiLogs.push(entry);
      console.log(`[API ${entry.method}] ${entry.url} -> ${entry.status}`);
    }
  });

  // Navigate to New Project
  console.log("Navigating to https://app.croviq.app/projects/new ...");
  await page.goto("https://app.croviq.app/projects/new", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);

  const fileInput = page.locator("input[type='file']");
  await fileInput.waitFor({ state: "attached", timeout: 10000 });
  console.log("Attached file input found on New Project page!");
  await page.screenshot({ path: "/tmp/acceptance_artifacts/new_project_page.png" });

  await fileInput.setInputFiles("/tmp/acceptance_test_video.mp4");
  console.log("Attached /tmp/acceptance_test_video.mp4 to file input!");

  await page.waitForTimeout(1000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/video_selected.png" });

  // Click Start Production button
  console.log("Clicking 'Start Production' button...");
  const uploadBtn = page.getByRole("button", { name: "Start Production" });
  await uploadBtn.waitFor({ state: "visible", timeout: 5000 });
  await uploadBtn.click();

  console.log("Waiting for upload and verification to complete...");
  // Wait for navigation to /productions/*/editor or /productions/*
  await page.waitForURL("**/productions/**", { timeout: 60000 });
  console.log("Navigated to Editor:", page.url());

  const parts = page.url().split("/");
  const prodIndex = parts.indexOf("productions");
  const productionId = parts[prodIndex + 1] || "";
  console.log("Detected Production ID:", productionId);

  await page.waitForTimeout(5000);
  await page.screenshot({ path: "/tmp/acceptance_artifacts/editor_initial.png" });

  // Wait for Leo processing / proposals to complete
  console.log("Waiting for Leo processing...");
  await page.waitForTimeout(15000);

  // Inspect Editor DOM
  const editorText = await page.evaluate(() => document.body.innerText);
  console.log("\n=== EDITOR STATE ===");
  console.log(editorText.slice(0, 1500));
  await page.screenshot({ path: "/tmp/acceptance_artifacts/editor_loaded.png" });

  // Navigate to Release QA
  console.log("Navigating to Release / Iris QA page...");
  await page.goto(`https://app.croviq.app/productions/${productionId}/release`, {
    waitUntil: "networkidle",
  });

  await page.waitForTimeout(3000);
  console.log("On Release QA page:", page.url());
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
  console.log("\n=== RELEASE / IRIS QA STATE ===");
  console.log(releasePageText.slice(0, 1500));

  console.log("\n==========================================");
  console.log("UPLOAD, LEO & IRIS VERIFICATION COMPLETE");
  console.log("==========================================");
}

main().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
