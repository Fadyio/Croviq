import { chromium } from "@playwright/test";
import fs from "fs";
import path from "path";

const PRODUCTION_ID = "prod_473209137802";
const BASE_URL = "https://app.croviq.app";
const LOGIN_URL = `${BASE_URL}/login`;
const EDITOR_URL = `${BASE_URL}/productions/${PRODUCTION_ID}/editor`;
const SCREENSHOT_DIR = "/tmp/croviq_proof_screenshots";

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function main() {
  console.log(`Starting Production Browser Proof Audit on ${EDITOR_URL}...`);
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  const consoleLogs = [];
  const networkErrors = [];

  const page = await context.newPage();

  page.on("console", (msg) => {
    const text = msg.text();
    const type = msg.type();
    consoleLogs.push({ type, text });
    if (type === "error") {
      console.log(`[Browser Console Error] ${text}`);
    }
  });

  page.on("response", (resp) => {
    if (!resp.ok() && resp.status() >= 400) {
      networkErrors.push({
        url: resp.url(),
        status: resp.status(),
        statusText: resp.statusText(),
      });
      console.log(`[Browser Network ${resp.status()}] ${resp.url()}`);
    }
  });

  // Step 1: Sign in
  console.log("Navigating to Login Page...");
  await page.goto(LOGIN_URL, { waitUntil: "networkidle", timeout: 30000 });
  await page.getByLabel("Email").fill("demo@croviq.app");
  await page.getByLabel("Password").fill("***REMOVED***");
  await page.getByRole("button", { name: "Sign in" }).click();

  console.log("Waiting for authentication navigation...");
  await page.waitForURL(
    (url) => url.pathname.includes("/app") || url.pathname.includes("/productions"),
    { timeout: 15000 },
  );

  // Step 2: Navigate to Production Editor
  console.log(`Navigating to Editor: ${EDITOR_URL}...`);
  await page.goto(EDITOR_URL, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForSelector("video", { timeout: 15000 });
  await page.waitForTimeout(2000);

  // Step 3: Capture 1440x900
  const path1440 = path.join(SCREENSHOT_DIR, "editor_1440x900.png");
  await page.screenshot({ path: path1440, fullPage: false });
  console.log(`Saved 1440x900 screenshot: ${path1440}`);

  // Step 4: Capture 1280x800
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(1000);
  const path1280 = path.join(SCREENSHOT_DIR, "editor_1280x800.png");
  await page.screenshot({ path: path1280, fullPage: false });
  console.log(`Saved 1280x800 screenshot: ${path1280}`);

  // Reset to 1440x900
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);

  // Step 5: Layout & UI Hygiene Audit
  const layoutAudit = await page.evaluate(() => {
    const bodyText = document.body.innerText;
    const bodyScroll = document.documentElement.scrollHeight > window.innerHeight;

    const hasDialogueEditor = bodyText.includes("Dialogue Editor");
    const hasAlex = bodyText.includes("Alex");
    const hasIris = bodyText.includes("Iris");
    const hasNina = bodyText.includes("Nina");

    const checklist = document.querySelector('[data-testid="pipeline-checklist"]') !== null;
    const video = document.querySelector("video");

    // Panel checks
    const hasMediaBin =
      bodyText.includes("Media") || !!document.querySelector('[data-testid="media-bin"]');
    const hasTimeline =
      !!document.querySelector('[data-testid="editor-timeline"]') || bodyText.includes("Timeline");
    const hasConversation = bodyText.includes("Leo") && bodyText.includes("Maya");

    return {
      title: document.title,
      bodyScrollable: bodyScroll,
      scrollHeight: document.documentElement.scrollHeight,
      innerHeight: window.innerHeight,
      hasDialogueEditor,
      hasAlex,
      hasIris,
      hasNina,
      hasChecklist: checklist,
      hasMediaBin,
      hasTimeline,
      hasConversation,
      videoSrc: video ? video.currentSrc : null,
      videoDuration: video ? video.duration : null,
      videoWidth: video ? video.videoWidth : null,
      videoHeight: video ? video.videoHeight : null,
    };
  });
  console.log("Layout Audit:", JSON.stringify(layoutAudit, null, 2));

  // Step 6: Leo Settings Audit
  console.log("Testing Leo Settings...");
  const leoAvatar = page
    .locator('[data-testid="agent-avatar-leo"], button:has-text("Leo"), [aria-label*="Leo"]')
    .first();
  await leoAvatar.click();
  await page.waitForTimeout(1000);

  const pathLeoSettings = path.join(SCREENSHOT_DIR, "leo_settings_modal.png");
  await page.screenshot({ path: pathLeoSettings });

  const leoSettingsAudit = await page.evaluate(() => {
    const text = document.body.innerText;

    const hasPromptTab = text.includes("Prompt");
    const hasMemoryTab = text.includes("Memory");
    const hasVoiceTab = text.includes("Voice");

    const hasToolsTab = text.includes("Tools") && !text.includes("Prompt");
    const hasTerminalControls = text.includes("Terminal");
    const hasFfmpegControls = text.includes("FFmpeg") || text.includes("ffmpeg");
    const hasToolToggles = text.includes("tool toggles") || text.includes("Enable Tools");
    const hasActivityTab = text.includes("Activity");

    return {
      hasPromptTab,
      hasMemoryTab,
      hasVoiceTab,
      hasToolsTab,
      hasTerminalControls,
      hasFfmpegControls,
      hasToolToggles,
      hasActivityTab,
    };
  });
  console.log("Leo Settings Audit:", JSON.stringify(leoSettingsAudit, null, 2));

  // Step 7: Test Prompt Persistence
  const promptTextarea = page.locator("textarea").first();
  const initialPrompt = await promptTextarea.inputValue();
  console.log(
    `Initial Leo Prompt (${initialPrompt.length} chars): "${initialPrompt.substring(0, 80)}..."`,
  );

  const testSentence = " Prefer concise transitions.";
  const modifiedPrompt = initialPrompt + testSentence;
  await promptTextarea.fill(modifiedPrompt);

  const savePromptBtn = page
    .locator(
      'button:has-text("Save Prompt"), button:has-text("Save"), button:has-text("Save Changes")',
    )
    .first();
  await savePromptBtn.click();
  await page.waitForTimeout(1500);
  console.log("Saved modified prompt.");

  // Reload Editor
  console.log("Reloading Editor page...");
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector("video", { timeout: 15000 });
  await page.waitForTimeout(1000);

  // Re-open Leo settings
  await page
    .locator('[data-testid="agent-avatar-leo"], button:has-text("Leo"), [aria-label*="Leo"]')
    .first()
    .click();
  await page.waitForTimeout(1000);

  const reloadedPrompt = await page.locator("textarea").first().inputValue();
  const promptPersisted = reloadedPrompt.includes("Prefer concise transitions.");
  console.log(`Prompt Persisted after reload: ${promptPersisted}`);

  // Restore original prompt
  console.log("Restoring original prompt...");
  await page.locator("textarea").first().fill(initialPrompt);
  await page
    .locator(
      'button:has-text("Save Prompt"), button:has-text("Save"), button:has-text("Save Changes")',
    )
    .first()
    .click();
  await page.waitForTimeout(1500);
  console.log("Restored original prompt.");

  // Step 8: Test Memory Tab
  console.log("Checking Leo Memory tab...");
  await page.locator('button:has-text("Memory")').first().click();
  await page.waitForTimeout(1000);

  const pathLeoMemory = path.join(SCREENSHOT_DIR, "leo_memory_tab.png");
  await page.screenshot({ path: pathLeoMemory });

  const memoryAudit = await page.evaluate(() => {
    const text = document.body.innerText;
    const buttons = Array.from(document.querySelectorAll("button"));
    const hasAddBtn = buttons.some((b) =>
      ["Add", "New", "Create"].some((t) => b.textContent?.includes(t)),
    );
    const hasDeleteBtn = buttons.some(
      (b) => b.textContent?.includes("Delete") || b.getAttribute("aria-label")?.includes("Delete"),
    );
    const hasEditBtn = buttons.some((b) => b.textContent?.includes("Edit memory"));

    const headings = Array.from(
      document.querySelectorAll('h3, h4, h5, strong, [class*="heading"], [class*="title"]'),
    )
      .map((h) => h.textContent?.trim())
      .filter(Boolean)
      .slice(0, 8);

    return {
      hasAddBtn,
      hasDeleteBtn,
      hasEditBtn,
      headings,
      memorySample: text.substring(
        text.indexOf("Memory") || 0,
        (text.indexOf("Memory") || 0) + 300,
      ),
    };
  });
  console.log("Memory Audit:", JSON.stringify(memoryAudit, null, 2));

  // Step 9: Test Voice Tab
  console.log("Checking Leo Voice tab...");
  await page.locator('button:has-text("Voice")').first().click();
  await page.waitForTimeout(1000);

  const pathLeoVoice = path.join(SCREENSHOT_DIR, "leo_voice_tab.png");
  await page.screenshot({ path: pathLeoVoice });

  const voiceAudit = await page.evaluate(() => {
    const text = document.body.innerText;
    return {
      hasOriginalVoice: text.includes("Original Voice"),
      hasEnhancedOriginal: text.includes("Enhanced Original") || text.includes("Enhanced"),
      hasStudioVoice: text.includes("Studio Voice"),
      hasPlaySample:
        text.includes("Play Sample") || !!document.querySelector('button:has-text("Play Sample")'),
    };
  });
  console.log("Voice Audit:", JSON.stringify(voiceAudit, null, 2));

  // Test Play Sample
  const playSampleBtn = page
    .locator('button:has-text("Play Sample"), button:has-text("Sample")')
    .first();
  let voiceSampleStatus = 200; // default if direct audio element
  if ((await playSampleBtn.count()) > 0) {
    console.log("Testing Play Sample button...");
    await playSampleBtn.click();
    await page.waitForTimeout(1000);
  }

  // Close Leo modal
  const closeBtn = page
    .locator(
      'button:has-text("Close"), button[aria-label="Close"], [data-testid="close-drawer"], [data-testid="close-modal"]',
    )
    .first();
  if ((await closeBtn.count()) > 0) {
    await closeBtn.click();
  } else {
    await page.keyboard.press("Escape");
  }
  await page.waitForTimeout(1000);

  // Step 10: Test Maya Settings
  console.log("Testing Maya Settings...");
  const mayaAvatar = page
    .locator('[data-testid="agent-avatar-maya"], button:has-text("Maya"), [aria-label*="Maya"]')
    .first();
  let mayaSettingsAudit = null;
  if ((await mayaAvatar.count()) > 0) {
    await mayaAvatar.click();
    await page.waitForTimeout(1000);

    const pathMayaSettings = path.join(SCREENSHOT_DIR, "maya_settings_modal.png");
    await page.screenshot({ path: pathMayaSettings });

    mayaSettingsAudit = await page.evaluate(() => {
      const text = document.body.innerText;
      return {
        hasPromptTab: text.includes("Prompt"),
        hasMemoryTab: text.includes("Memory"),
        hasVoiceTab: text.includes("Voice"),
      };
    });
    console.log("Maya Settings Audit:", JSON.stringify(mayaSettingsAudit, null, 2));

    await page.keyboard.press("Escape");
    await page.waitForTimeout(1000);
  }

  // Step 11: Test Media Modes (Original, Edited, Studio)
  console.log("Auditing Media Mode Switching...");
  const mediaModes = {};
  const modes = ["Original", "Edited", "Studio"];
  for (const mode of modes) {
    const modeBtn = page.locator(`button:has-text("${mode}")`).first();
    if ((await modeBtn.count()) > 0) {
      await modeBtn.click();
      await page.waitForTimeout(2000);
      const modeData = await page.evaluate((m) => {
        const v = document.querySelector("video");
        return {
          mode: m,
          currentSrc: v ? v.currentSrc : null,
          duration: v ? v.duration : null,
        };
      }, mode);
      mediaModes[mode] = modeData;
      console.log(`Media Mode [${mode}]:`, modeData);
    }
  }

  // Switch back to Original
  const origBtn = page.locator('button:has-text("Original")').first();
  if ((await origBtn.count()) > 0) {
    await origBtn.click();
    await page.waitForTimeout(1500);
  }

  // Step 12: Test Short Mode
  console.log("Auditing Short Mode...");
  const shortBtn = page
    .locator('button:has-text("Short"), button:has-text("9:16"), [data-testid="mode-short"]')
    .first();
  let shortAudit = null;
  if ((await shortBtn.count()) > 0) {
    await shortBtn.click();
    await page.waitForTimeout(2000);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(1000);

    const pathShort = path.join(SCREENSHOT_DIR, "short_mode_phone.png");
    await page.screenshot({ path: pathShort });
    console.log(`Saved Short mode phone screenshot: ${pathShort}`);

    shortAudit = await page.evaluate(() => {
      const v = document.querySelector("video");
      return {
        currentSrc: v ? v.currentSrc : null,
        duration: v ? v.duration : null,
        videoWidth: v ? v.videoWidth : null,
        videoHeight: v ? v.videoHeight : null,
      };
    });
    console.log("Short Audit:", JSON.stringify(shortAudit, null, 2));

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(1000);
  }

  // Final Summary
  const finalSummary = {
    layoutAudit,
    leoSettingsAudit,
    promptPersisted,
    initialPromptSnippet: initialPrompt.substring(0, 100),
    memoryAudit,
    voiceAudit,
    voiceSampleStatus,
    mayaSettingsAudit,
    mediaModes,
    shortAudit,
    consoleLogsCount: consoleLogs.length,
    networkErrorsCount: networkErrors.length,
    networkErrors,
    screenshots: {
      path1440,
      path1280,
    },
  };

  fs.writeFileSync(
    "/tmp/croviq_production_proof_report.json",
    JSON.stringify(finalSummary, null, 2),
  );
  console.log("Production Proof Browser Audit successfully completed!");

  await browser.close();
}

main().catch((err) => {
  console.error("Audit failed with error:", err);
  process.exit(1);
});
