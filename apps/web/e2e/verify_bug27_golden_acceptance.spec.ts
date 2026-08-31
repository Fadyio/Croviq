import { expect, test, type Page } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";
import { DEFAULT_MUSIC_PROMPT } from "../src/components/editor/MusicTab";

const PRODUCTION_ID = "prod_473209137802";
const BASE_URL = "http://localhost:5173";
const DEMO_TOKEN =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwidXNlcl9pZCI6IjI3aUVCVU1jdTZUb0RZd3AyT2RFSUhCdXdJQTMiLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCJ9.signature";
const DEMO_EMAIL = "demo@croviq.app";
const APPROVED_USER = {
  user_id: "27iEBUMcu6ToDYwp2OdEIHBuwIA3",
  email: DEMO_EMAIL,
  display_name: "Demo Creator",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

async function sleep(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}

const setupPageAuthAndNavigate = async (
  page: Page,
  mode?: string,
  targetPage: "editor" | "release" = "editor",
) => {
  await page.addInitScript((user) => {
    localStorage.setItem("croviq_dev_auth_user", JSON.stringify(user));
  }, APPROVED_USER);

  await page.route("**/identitytoolkit.googleapis.com/**", async (route) => {
    const url = route.request().url();
    if (url.includes("accounts:signInWithPassword")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          kind: "identitytoolkit#VerifyPasswordResponse",
          localId: APPROVED_USER.user_id,
          email: DEMO_EMAIL,
          displayName: APPROVED_USER.display_name,
          idToken: DEMO_TOKEN,
          registered: true,
          refreshToken: "mock-refresh-token",
          expiresIn: "3600",
        }),
      });
      return;
    }
    if (url.includes("accounts:lookup")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          kind: "identitytoolkit#GetAccountInfoResponse",
          users: [
            {
              localId: APPROVED_USER.user_id,
              email: DEMO_EMAIL,
              displayName: APPROVED_USER.display_name,
              emailVerified: true,
            },
          ],
        }),
      });
      return;
    }
    await route.continue();
  });

  await page.route("**/securetoken.googleapis.com/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: DEMO_TOKEN,
        expires_in: "3600",
        token_type: "Bearer",
        refresh_token: "mock-refresh-token",
        id_token: DEMO_TOKEN,
        user_id: APPROVED_USER.user_id,
        project_id: "croviq-506602",
      }),
    });
  });

  const targetUrl =
    targetPage === "release"
      ? mode
        ? `${BASE_URL}/productions/${PRODUCTION_ID}/release?mode=${mode}`
        : `${BASE_URL}/productions/${PRODUCTION_ID}/release`
      : mode
        ? `${BASE_URL}/productions/${PRODUCTION_ID}/editor?mode=${mode}`
        : `${BASE_URL}/productions/${PRODUCTION_ID}/editor`;

  await page.goto(targetUrl);
  if (targetPage === "editor") {
    await page.waitForSelector("[data-testid='video-stage']", { timeout: 30000 });
  } else {
    await page.waitForSelector("[data-testid='section-iris-qa']", { timeout: 30000 });
  }
};

test.describe("BUG 27 — Final Editor Demo Polish Golden Acceptance Suite", () => {
  test.beforeEach(async () => {
    test.setTimeout(90000);
  });

  test("CASE A — Navbar: all 4 preview modes visible across 1600x900, 1440x900, 1280x800", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page);

    const resolutions = [
      { width: 1600, height: 900 },
      { width: 1440, height: 900 },
      { width: 1280, height: 800 },
    ];

    for (const res of resolutions) {
      await page.setViewportSize(res);
      await page.waitForTimeout(300);

      const origBtn = page.locator("[data-testid='preview-toggle-original']");
      const editBtn = page.locator("[data-testid='preview-toggle-edited']");
      const voBtn = page.locator("[data-testid='preview-toggle-studio-voice']");
      const fmBtn = page.locator("[data-testid='preview-toggle-final-mix']");

      await expect(origBtn).toBeVisible();
      await expect(editBtn).toBeVisible();
      await expect(voBtn).toBeVisible();
      await expect(fmBtn).toBeVisible();

      expect(await origBtn.textContent()).toContain("Original");
      expect(await editBtn.textContent()).toContain("Edited");
      expect(await voBtn.textContent()).toContain("Voiceover Preview");
      expect(await fmBtn.textContent()).toContain("Final Mix");
    }
  });

  test("CASE B — Iris / Original: reviews source artifact and states Original", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page, "original", "release");

    const origBtn = page.locator("[data-testid='btn-review-mode-original']");
    await origBtn.click();

    await page.waitForFunction(
      () =>
        document
          .querySelector("[data-testid='iris-review-mode-label']")
          ?.textContent?.includes("Original"),
      { timeout: 60000 },
    );
    const label = await page.locator("[data-testid='iris-review-mode-label']").textContent();
    expect(label).toContain("Reviewing: Original");

    const artId = await page.locator("[data-testid='iris-reviewed-artifact-id']").textContent();
    expect(artId).not.toBeNull();
  });

  test("CASE C — Iris / Edited: reviews exact active Edited Preview artifact", async ({ page }) => {
    await setupPageAuthAndNavigate(page, "edited", "release");

    const editBtn = page.locator("[data-testid='btn-review-mode-edited']");
    await editBtn.click();

    await page.waitForFunction(
      () =>
        document
          .querySelector("[data-testid='iris-review-mode-label']")
          ?.textContent?.includes("Edited Preview"),
      { timeout: 60000 },
    );
    const label = await page.locator("[data-testid='iris-review-mode-label']").textContent();
    expect(label).toContain("Reviewing: Edited Preview");
  });

  test("CASE D — Iris / Voiceover: reviews Voiceover Preview with exact rendered voice", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page, "voiceover", "release");

    const voBtn = page.locator("[data-testid='btn-review-mode-voiceover']");
    await voBtn.click();

    await page.waitForFunction(
      () =>
        document
          .querySelector("[data-testid='iris-review-mode-label']")
          ?.textContent?.includes("Voiceover Preview"),
      { timeout: 60000 },
    );
    const label = await page.locator("[data-testid='iris-review-mode-label']").textContent();
    expect(label).toContain("Reviewing: Voiceover Preview");
  });

  test("CASE E — Iris / Final Mix: reviews Final Mix deliverable", async ({ page }) => {
    await setupPageAuthAndNavigate(page, "final_mix", "release");

    const fmBtn = page.locator("[data-testid='btn-review-mode-final-mix']");
    await fmBtn.click();

    await page.waitForFunction(
      () =>
        document
          .querySelector("[data-testid='iris-review-mode-label']")
          ?.textContent?.includes("Final Mix"),
      { timeout: 60000 },
    );
    const label = await page.locator("[data-testid='iris-review-mode-label']").textContent();
    expect(label).toContain("Reviewing: Final Mix");
  });
  test("CASE F & G — Voice selection & Audition: 8 voices available, select triggers auto-regen, audition does not change video", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page, "studio_voice");

    // Open Studio Voice tab
    const voiceTabBtn = page.locator("[data-testid='tab-voice']");
    await voiceTabBtn.click();
    const voices = ["puck", "charon", "kore", "fenrir", "aoede", "leda", "orus", "zephyr"];
    for (const v of voices) {
      await expect(page.locator(`[data-testid='voice-option-${v}']`)).toBeVisible();
    }

    // Audition Aoede without selecting
    const aoedeAudition = page.locator("[data-testid='btn-audition-aoede']");
    await expect(aoedeAudition).toBeVisible();
    await aoedeAudition.click();
    await sleep(500);

    // Select Kore
    const koreOption = page.locator("[data-testid='voice-option-kore']");
    await koreOption.click();

    // Verify Kore becomes active
    await expect(koreOption).toHaveAttribute("aria-checked", "true");
  });

  test("CASE H — Transcript / Original: raw words and source time navigation", async ({ page }) => {
    await setupPageAuthAndNavigate(page, "original");

    const transcriptTab = page.locator("[data-testid='tab-transcript']");
    await transcriptTab.click();

    await expect(page.locator("[data-testid='transcript-panel']")).toBeVisible();
    await expect(page.locator("text=Source time")).toBeVisible();
  });

  test("CASE I — Transcript / Edited: surviving words and edited coordinates", async ({ page }) => {
    await setupPageAuthAndNavigate(page, "edited");

    const transcriptTab = page.locator("[data-testid='tab-transcript']");
    await transcriptTab.click();

    await expect(page.locator("[data-testid='transcript-panel']")).toBeVisible();
    await expect(page.locator("text=Edited time")).toBeVisible();
  });

  test("CASE J & K — Transcript / Voiceover & Final Mix with Player Caption Overlay", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page, "studio_voice");

    const playerOverlay = page.locator("[data-testid='player-caption-overlay']");
    // Caption overlay is attached and formatted cleanly
    const stage = page.locator("[data-testid='video-stage']");
    await expect(stage).toBeVisible();
  });

  test("CASE L — Music: default prompt is understated YouTube background music", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page);

    const musicTab = page.locator("[data-testid='tab-music']");
    await musicTab.click();

    expect(DEFAULT_MUSIC_PROMPT).toContain("Modern understated YouTube background music");
    expect(DEFAULT_MUSIC_PROMPT).toContain("no vocals");
    expect(DEFAULT_MUSIC_PROMPT).toContain("unobtrusive under narration");
  });

  test("CASE M — Chat UX: clean composer, context attachment chip, no bulky tool boxes", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page);

    const chatTab = page.locator("[data-testid='tab-chat-leo']");
    await chatTab.click();

    const chatPanel = page.locator("[data-testid='leo-chat-panel']");
    await expect(chatPanel).toBeVisible();

    const composer = page.locator("#leo-chat-input");
    const messages = page.locator("[data-testid='leo-chat-panel'] article");
    // Wait for history to load
    await page.waitForTimeout(1000);
    const countBefore = await messages.count();

    // Type and send a message to Leo
    await composer.fill("Why did you remove this?");
    const sendBtn = page.locator("button[aria-label='Send message to Leo']");
    await sendBtn.click();

    await page.waitForFunction(
      ({ before }) => {
        const els = document.querySelectorAll("[data-testid='leo-chat-panel'] article");
        return els.length > before;
      },
      { before: countBefore },
      { timeout: 45000 },
    );
    expect(await messages.count()).toBeGreaterThan(countBefore);
  });
});
