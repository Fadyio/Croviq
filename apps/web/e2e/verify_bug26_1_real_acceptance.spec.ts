import { expect, test, type Page } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";

const PRODUCTION_ID = "prod_473209137802";
const BASE_URL = "http://localhost:5173";
const API_URL = "http://localhost:8080";
const DEMO_TOKEN =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIyN2lFQlVNY3U2VG9EWXdwMk9kRUlIQnV3SUEzIiwidXNlcl9pZCI6IjI3aUVCVU1jdTZUb0RZd3AyT2RFSUhCdXdJQTMiLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCJ9.signature";

const SCREENSHOT_DIR = path.resolve(process.cwd(), "docs/screenshots/acceptance");

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
type BrowserDiagnostics = {
  consoleErrors: string[];
  pageErrors: string[];
  requestFailures: string[];
  failedResponses: string[];
};

const observeBrowserDiagnostics = (page: Page): BrowserDiagnostics => {
  const diagnostics: BrowserDiagnostics = {
    consoleErrors: [],
    pageErrors: [],
    requestFailures: [],
    failedResponses: [],
  };
  page.on("console", (message) => {
    if (message.type() === "error") diagnostics.consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => diagnostics.pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    diagnostics.requestFailures.push(
      `${request.method()} ${request.url()} — ${request.failure()?.errorText || "unknown error"}`,
    );
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      diagnostics.failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });
  return diagnostics;
};
const findUnexpectedRequestFailures = (diagnostics: BrowserDiagnostics): string[] =>
  diagnostics.requestFailures.filter(
    (failure) =>
      !failure.includes("storage.googleapis.com") || !failure.includes("net::ERR_ABORTED"),
  );

const setupPageAuthAndNavigate = async (page: Page, mode?: string) => {
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

  const targetUrl = mode
    ? `${BASE_URL}/productions/${PRODUCTION_ID}/editor?mode=${mode}`
    : `${BASE_URL}/productions/${PRODUCTION_ID}/editor`;

  await page.goto(targetUrl);
  await page.waitForSelector("[data-testid='video-stage']", { timeout: 30000 });
  await page.waitForSelector("[data-testid='video-element']", { timeout: 30000 });
};

async function ensureVideoPlays(
  page: Page,
  durationMs: number = 1500,
): Promise<{ advanced: boolean; startSec: number; endSec: number; error: string | null }> {
  const startSec = await page.evaluate(async () => {
    const v = document.querySelector("video") as HTMLVideoElement | null;
    if (!v) return -1;
    if (v.currentTime >= v.duration - 2.5 || v.ended) {
      v.currentTime = 1.0;
    }
    v.muted = true;
    try {
      await v.play();
    } catch {}
    return v.currentTime;
  });

  await sleep(durationMs);

  const res = await page.evaluate(() => {
    const v = document.querySelector("video") as HTMLVideoElement | null;
    if (!v) return { endSec: -1, error: "No video element found", readyState: 0, paused: true };
    return {
      endSec: v.currentTime,
      error: v.error ? `${v.error.code}: ${v.error.message}` : null,
      readyState: v.readyState,
      paused: v.paused,
      duration: v.duration,
    };
  });

  const advanced = res.endSec > startSec + 0.15;
  return { advanced, startSec, endSec: res.endSec, error: res.error };
}

async function waitForModeVideoReady(page: Page, expectedSrcSubstring?: string, timeoutMs = 45000) {
  await page.waitForFunction(
    (sub) => {
      const v = document.querySelector("video");
      if (!v) return false;
      if (sub && !(v.currentSrc || v.src).includes(sub)) return false;
      return v.readyState >= 1 && !Number.isNaN(v.duration) && v.duration > 0;
    },
    expectedSrcSubstring,
    { timeout: timeoutMs },
  );
}

async function seekVideo(page: Page, targetSec: number) {
  await page.evaluate((sec) => {
    const v = document.querySelector("video");
    if (v) {
      v.currentTime = sec;
    }
  }, targetSec);
  await page.waitForFunction(
    () => {
      const v = document.querySelector("video");
      return v && !v.seeking && v.readyState >= 1;
    },
    { timeout: 15000 },
  );
}

test.describe("BUG 26.1 — Real Production Browser Acceptance Suite", () => {
  test.skip(
    process.env.RUN_REAL_BUG26_1_ACCEPTANCE !== "1",
    "Requires the local API, web app, and real BUG 26.1 production artifacts",
  );
  test.beforeAll(() => {
    if (!fs.existsSync(SCREENSHOT_DIR)) {
      fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    }
  });

  test.beforeEach(async () => {
    test.setTimeout(120000);
  });
  test("1. Original Mode: Playback, Seeks, and Hard Refresh", async ({ page }) => {
    await setupPageAuthAndNavigate(page, "original");
    await waitForModeVideoReady(page, "github.mp4");

    const state = await page.evaluate(() => {
      const v = document.querySelector("video") as HTMLVideoElement;
      return {
        readyState: v.readyState,
        error: v.error ? `${v.error.code}` : null,
        duration: v.duration,
      };
    });
    console.log(
      `Original Mode - ReadyState: ${state.readyState}, Duration: ${state.duration}s, Error: ${state.error}`,
    );
    expect(state.readyState).toBeGreaterThanOrEqual(1);
    expect(state.error).toBeNull();
    expect(Math.round(state.duration)).toBe(101);

    // Play 0-2s
    await page.evaluate(() => {
      const v = document.querySelector("video") as HTMLVideoElement;
      v.currentTime = 0;
    });
    const play1 = await ensureVideoPlays(page, 2000);
    console.log(
      `Original Play (0s-2s): Advanced=${play1.advanced} (${play1.startSec.toFixed(2)}s -> ${play1.endSec.toFixed(2)}s)`,
    );
    expect(play1.advanced).toBe(true);

    // Seek middle (~50s)
    await seekVideo(page, 50.0);
    const play2 = await ensureVideoPlays(page, 1500);
    console.log(
      `Original Seek Middle (~50s): Advanced=${play2.advanced} (${play2.startSec.toFixed(2)}s -> ${play2.endSec.toFixed(2)}s)`,
    );
    expect(play2.advanced).toBe(true);

    // Seek final 10s (~92s)
    await seekVideo(page, 92.0);
    const play3 = await ensureVideoPlays(page, 1500);
    console.log(
      `Original Seek Final 10s (~92s): Advanced=${play3.advanced} (${play3.startSec.toFixed(2)}s -> ${play3.endSec.toFixed(2)}s)`,
    );
    expect(play3.advanced).toBe(true);

    // Screenshot
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug26-1-original-playing.png") });

    // Hard refresh in Original mode
    await page.getByTestId("preview-toggle-original").click();
    await expect(page).toHaveURL(/[?&]mode=original(?:&|$)/);
    await page.reload();
    await page.waitForSelector("[data-testid='video-element']", { timeout: 30000 });
    await waitForModeVideoReady(page, "github.mp4");
    const refreshPlay = await ensureVideoPlays(page, 1500);
    console.log(`Original Hard Refresh: Playable=${refreshPlay.advanced}`);
    expect(refreshPlay.advanced).toBe(true);
  });

  test("2. Edited Mode: Cut Count Parity (14 cuts), Playback, Seeks, and Hard Refresh", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page, "edited");
    await waitForModeVideoReady(page, "preview.mp4");

    const timelineText = await page.locator("[data-testid='editor-timeline']").textContent();
    const cutMatch = timelineText?.match(/(\d+)\s+cuts/);
    const displayedCuts = cutMatch ? parseInt(cutMatch[1], 10) : 0;
    console.log(`Edited Mode Timeline Summary: ${displayedCuts} cuts (Expected: 14)`);
    expect(displayedCuts).toBe(14);

    const state = await page.evaluate(() => {
      const v = document.querySelector("video") as HTMLVideoElement;
      return {
        readyState: v.readyState,
        error: v.error ? `${v.error.code}` : null,
        duration: v.duration,
      };
    });
    console.log(
      `Edited Mode - ReadyState: ${state.readyState}, Duration: ${state.duration}s, Error: ${state.error}`,
    );
    expect(state.readyState).toBeGreaterThanOrEqual(1);
    expect(state.error).toBeNull();
    expect(Math.round(state.duration)).toBe(58);

    // Play 0-2s
    await page.evaluate(() => {
      const v = document.querySelector("video") as HTMLVideoElement;
      v.currentTime = 0;
    });
    const play1 = await ensureVideoPlays(page, 2000);
    console.log(
      `Edited Play (0s-2s): Advanced=${play1.advanced} (${play1.startSec.toFixed(2)}s -> ${play1.endSec.toFixed(2)}s)`,
    );
    expect(play1.advanced).toBe(true);

    // Seek middle (~29s)
    await seekVideo(page, 29.0);
    const play2 = await ensureVideoPlays(page, 1500);
    console.log(
      `Edited Seek Middle (~29s): Advanced=${play2.advanced} (${play2.startSec.toFixed(2)}s -> ${play2.endSec.toFixed(2)}s)`,
    );
    expect(play2.advanced).toBe(true);

    // Seek final 10s (~48s)
    await seekVideo(page, 48.0);
    const play3 = await ensureVideoPlays(page, 1500);
    console.log(
      `Edited Seek Final 10s (~48s): Advanced=${play3.advanced} (${play3.startSec.toFixed(2)}s -> ${play3.endSec.toFixed(2)}s)`,
    );
    expect(play3.advanced).toBe(true);

    // Screenshot
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug26-1-edited-playing.png") });

    // Hard refresh in Edited mode
    await page.getByTestId("preview-toggle-edited").click();
    await expect(page).toHaveURL(/[?&]mode=edited(?:&|$)/);
    await page.reload();
    await page.waitForSelector("[data-testid='video-element']", { timeout: 30000 });
    await waitForModeVideoReady(page, "preview.mp4");
    const refreshPlay = await ensureVideoPlays(page, 1500);
    console.log(`Edited Hard Refresh: Playable=${refreshPlay.advanced}`);
    expect(refreshPlay.advanced).toBe(true);
  });

  test("3. Voiceover Mode: Playback, Seeks, and Hard Refresh", async ({ page }) => {
    await setupPageAuthAndNavigate(page, "studio_voice");
    await waitForModeVideoReady(page, "voiceover_preview.mp4");

    const state = await page.evaluate(() => {
      const v = document.querySelector("video") as HTMLVideoElement;
      return {
        readyState: v.readyState,
        error: v.error ? `${v.error.code}` : null,
        duration: v.duration,
      };
    });
    console.log(
      `Voiceover Mode - ReadyState: ${state.readyState}, Duration: ${state.duration}s, Error: ${state.error}`,
    );
    expect(state.readyState).toBeGreaterThanOrEqual(1);
    expect(state.error).toBeNull();
    expect(Math.round(state.duration)).toBe(58);

    // Play 0-2s
    await page.evaluate(() => {
      const v = document.querySelector("video") as HTMLVideoElement;
      v.currentTime = 0;
    });
    const play1 = await ensureVideoPlays(page, 2000);
    console.log(
      `Voiceover Play (0s-2s): Advanced=${play1.advanced} (${play1.startSec.toFixed(2)}s -> ${play1.endSec.toFixed(2)}s)`,
    );
    expect(play1.advanced).toBe(true);

    // Seek middle (~29s)
    await seekVideo(page, 29.0);
    const play2 = await ensureVideoPlays(page, 1500);
    console.log(
      `Voiceover Seek Middle (~29s): Advanced=${play2.advanced} (${play2.startSec.toFixed(2)}s -> ${play2.endSec.toFixed(2)}s)`,
    );
    expect(play2.advanced).toBe(true);

    // Seek final 10s (~48s)
    await seekVideo(page, 48.0);
    const play3 = await ensureVideoPlays(page, 1500);
    console.log(
      `Voiceover Seek Final 10s (~48s): Advanced=${play3.advanced} (${play3.startSec.toFixed(2)}s -> ${play3.endSec.toFixed(2)}s)`,
    );
    expect(play3.advanced).toBe(true);

    // Screenshot
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug26-1-voiceover-playing.png") });

    // Hard refresh in Voiceover mode
    await page.getByTestId("preview-toggle-studio-voice").click();
    await expect(page).toHaveURL(/[?&]mode=studio_voice(?:&|$)/);
    await page.reload();
    await page.waitForSelector("[data-testid='video-element']", { timeout: 30000 });
    await waitForModeVideoReady(page, "voiceover_preview.mp4");
    const refreshPlay = await ensureVideoPlays(page, 1500);
    console.log(`Voiceover Hard Refresh: Playable=${refreshPlay.advanced}`);
    expect(refreshPlay.advanced).toBe(true);
  });

  test("4. Final Mix Mode: Playback, Seeks, and Hard Refresh", async ({ page }) => {
    await setupPageAuthAndNavigate(page, "final_mix");
    await waitForModeVideoReady(page, "final_mix.mp4");

    const timelineText = await page.locator("[data-testid='editor-timeline']").textContent();
    const cutMatch = timelineText?.match(/(\d+)\s+cuts/);
    const displayedCuts = cutMatch ? parseInt(cutMatch[1], 10) : 0;
    console.log(`Final Mix Timeline Summary: ${displayedCuts} cuts (Expected: 14)`);
    expect(displayedCuts).toBe(14);

    const state = await page.evaluate(() => {
      const v = document.querySelector("video") as HTMLVideoElement;
      return {
        readyState: v.readyState,
        error: v.error ? `${v.error.code}` : null,
        duration: v.duration,
      };
    });
    console.log(
      `Final Mix Mode - ReadyState: ${state.readyState}, Duration: ${state.duration}s, Error: ${state.error}`,
    );
    expect(state.readyState).toBeGreaterThanOrEqual(1);
    expect(state.error).toBeNull();
    expect(Math.round(state.duration)).toBe(58);

    // Play 0-2s
    await page.evaluate(() => {
      const v = document.querySelector("video") as HTMLVideoElement;
      v.currentTime = 0;
    });
    const play1 = await ensureVideoPlays(page, 2000);
    console.log(
      `Final Mix Play (0s-2s): Advanced=${play1.advanced} (${play1.startSec.toFixed(2)}s -> ${play1.endSec.toFixed(2)}s)`,
    );
    expect(play1.advanced).toBe(true);

    // Seek middle (~29s)
    await seekVideo(page, 29.0);
    const play2 = await ensureVideoPlays(page, 1500);
    console.log(
      `Final Mix Seek Middle (~29s): Advanced=${play2.advanced} (${play2.startSec.toFixed(2)}s -> ${play2.endSec.toFixed(2)}s)`,
    );
    expect(play2.advanced).toBe(true);

    // Seek final 10s (~48s)
    await seekVideo(page, 48.0);
    const play3 = await ensureVideoPlays(page, 1500);
    console.log(
      `Final Mix Seek Final 10s (~48s): Advanced=${play3.advanced} (${play3.startSec.toFixed(2)}s -> ${play3.endSec.toFixed(2)}s)`,
    );
    expect(play3.advanced).toBe(true);

    // Screenshot
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "bug26-1-final-mix-playing.png") });

    // Hard refresh in Final Mix mode
    await page.getByTestId("preview-toggle-final-mix").click();
    await expect(page).toHaveURL(/[?&]mode=final_mix(?:&|$)/);
    await page.reload();
    await page.waitForSelector("[data-testid='video-element']", { timeout: 30000 });
    await waitForModeVideoReady(page, "final_mix.mp4");
    const refreshPlay = await ensureVideoPlays(page, 1500);
    console.log(`Final Mix Hard Refresh: Playable=${refreshPlay.advanced}`);
    expect(refreshPlay.advanced).toBe(true);
  });

  test("5. Mode Switch Stress Test: Original -> Edited -> Voiceover -> Final Mix -> Original -> Final Mix", async ({
    page,
  }) => {
    const diagnostics = observeBrowserDiagnostics(page);
    await setupPageAuthAndNavigate(page);
    await page.getByTestId("tab-transcript").click();

    const modeCases = {
      original: {
        name: "Original",
        buttonTestId: "preview-toggle-original",
        source: "github.mp4",
        labels: ["Video", "Original Audio"],
        absentLabels: ["Edits", "Voiceover", "Music"],
        hasCorrectedScript: false,
      },
      edited: {
        name: "Edited",
        buttonTestId: "preview-toggle-edited",
        source: "preview.mp4",
        labels: ["Video", "Audio", "Edits", "Chapters", "Captions"],
        absentLabels: ["Voiceover", "Music"],
        hasCorrectedScript: true,
      },
      studio_voice: {
        name: "Voiceover",
        buttonTestId: "preview-toggle-studio-voice",
        source: "voiceover_preview.mp4",
        labels: ["Video", "Edits", "Voiceover", "Chapters", "Captions"],
        absentLabels: ["Original Audio", "Audio", "Music"],
        hasCorrectedScript: true,
      },
      final_mix: {
        name: "Final Mix",
        buttonTestId: "preview-toggle-final-mix",
        source: "final_mix.mp4",
        labels: ["Video", "Edits", "Voiceover", "Music", "Chapters", "Captions"],
        absentLabels: ["Original Audio", "Audio"],
        hasCorrectedScript: true,
      },
    } as const;
    const modeSequence = [
      "original",
      "edited",
      "studio_voice",
      "final_mix",
      "original",
      "final_mix",
    ] as const;
    const timelineLabels = page
      .getByTestId("editor-timeline")
      .getByTestId("timeline-labels-column");
    const transcriptPanel = page.getByTestId("transcript-panel");

    for (let i = 0; i < modeSequence.length; i++) {
      const mode = modeSequence[i];
      const modeCase = modeCases[mode];
      await page.getByTestId(modeCase.buttonTestId).click();
      await expect(page).toHaveURL(new RegExp(`[?&]mode=${mode}(?:&|$)`));
      await waitForModeVideoReady(page, modeCase.source);
      for (const label of modeCase.labels) {
        await expect(timelineLabels.getByText(label, { exact: true })).toBeVisible();
      }
      for (const label of modeCase.absentLabels) {
        await expect(timelineLabels.getByText(label, { exact: true })).toHaveCount(0);
      }
      if (modeCase.hasCorrectedScript) {
        await expect(
          transcriptPanel.getByRole("button", { name: "Corrected Script" }),
        ).toBeVisible();
      } else {
        await expect(transcriptPanel.getByRole("button", { name: "Corrected Script" })).toHaveCount(
          0,
        );
        await expect(
          transcriptPanel.getByText("Original Transcript", { exact: true }),
        ).toBeVisible();
      }

      await seekVideo(page, 2);
      const playRes = await ensureVideoPlays(page, 1500);
      console.log(
        `Switch [${i + 1}/${modeSequence.length}] -> ${modeCase.name}: Playable=${playRes.advanced}, Error=${playRes.error}`,
      );
      expect(playRes.advanced).toBe(true);
      expect(playRes.error).toBeNull();
    }

    await page.reload();
    await waitForModeVideoReady(page, "final_mix.mp4");
    await expect(page.getByTestId("preview-toggle-final-mix")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    console.log(
      `Mode stress browser diagnostics: console=${diagnostics.consoleErrors.length}, page=${diagnostics.pageErrors.length}, requests=${diagnostics.requestFailures.length}, unexpectedRequests=${findUnexpectedRequestFailures(diagnostics).length}, failedResponses=${diagnostics.failedResponses.length}`,
    );
    expect(diagnostics.consoleErrors).toEqual([]);
    expect(diagnostics.pageErrors).toEqual([]);
    expect(findUnexpectedRequestFailures(diagnostics)).toEqual([]);
    expect(diagnostics.failedResponses).toEqual([]);
  });

  test("6. Automatic Signed URL Expiration Recovery", async ({ page }) => {
    const diagnostics = observeBrowserDiagnostics(page);
    let injectedFailures = 0;
    let playbackResponses = 0;
    page.on("response", (response) => {
      if (response.url().includes(`/api/productions/${PRODUCTION_ID}/playback`)) {
        playbackResponses += 1;
      }
    });
    await page.route(/\/preview\.mp4(?:\?|$)/, async (route) => {
      if (injectedFailures === 0) {
        injectedFailures += 1;
        await route.fulfill({
          status: 403,
          contentType: "text/plain",
          body: "Expired signed URL",
        });
        return;
      }
      await route.continue();
    });

    await setupPageAuthAndNavigate(page, "edited");
    await waitForModeVideoReady(page, "preview.mp4");
    await expect.poll(() => injectedFailures, { timeout: 15000 }).toBe(1);
    await expect.poll(() => playbackResponses, { timeout: 45000 }).toBeGreaterThan(1);

    await seekVideo(page, 12.5);
    const responsesBeforeMidstreamError = playbackResponses;
    await page.evaluate(() => {
      const video = document.querySelector("video") as HTMLVideoElement | null;
      if (!video) throw new Error("No video element");
      video.dispatchEvent(new Event("error"));
    });
    await expect
      .poll(() => playbackResponses, { timeout: 45000 })
      .toBeGreaterThan(responsesBeforeMidstreamError);
    await page.waitForFunction(
      () => {
        const video = document.querySelector("video");
        return (
          video &&
          video.readyState >= HTMLMediaElement.HAVE_METADATA &&
          video.currentTime > 10 &&
          !video.error &&
          !document.querySelector("[data-testid='video-error-overlay']")
        );
      },
      undefined,
      { timeout: 45000 },
    );

    const recoveryResult = await page.evaluate(() => {
      const video = document.querySelector("video") as HTMLVideoElement | null;
      return {
        source: video?.currentSrc || video?.src || "",
        currentTime: video?.currentTime || 0,
        hasErrorOverlay: Boolean(document.querySelector("[data-testid='video-error-overlay']")),
        readyState: video?.readyState || 0,
      };
    });
    const recoveryPlayback = await ensureVideoPlays(page, 1500);
    console.log(
      `Expired URL Recovery: PlaybackResponses=${playbackResponses}, HasErrorOverlay=${recoveryResult.hasErrorOverlay}, ReadyState=${recoveryResult.readyState}, Position=${recoveryResult.currentTime.toFixed(2)}, console=${diagnostics.consoleErrors.length}, page=${diagnostics.pageErrors.length}, requests=${diagnostics.requestFailures.length}, unexpectedRequests=${findUnexpectedRequestFailures(diagnostics).length}, failedResponses=${diagnostics.failedResponses.length}`,
    );
    expect(recoveryResult.source).toContain("preview.mp4");
    expect(recoveryResult.currentTime).toBeGreaterThan(10);
    expect(recoveryResult.hasErrorOverlay).toBe(false);
    expect(recoveryPlayback.advanced).toBe(true);
    expect(diagnostics.pageErrors).toEqual([]);
    expect(findUnexpectedRequestFailures(diagnostics)).toEqual([]);
    expect(diagnostics.failedResponses).toHaveLength(1);
    expect(diagnostics.failedResponses[0]).toContain("403");
  });

  test("7. Responsive Viewport Screenshots: 1600x900, 1440x900, 1280x800", async ({ page }) => {
    await setupPageAuthAndNavigate(page, "final_mix");
    await waitForModeVideoReady(page, "final_mix.mp4");

    const viewports = [
      { width: 1600, height: 900, name: "bug26-1-1600x900.png" },
      { width: 1440, height: 900, name: "bug26-1-1440x900.png" },
      { width: 1280, height: 800, name: "bug26-1-1280x800.png" },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await sleep(500);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, vp.name) });
      console.log(`Captured ${vp.name} at ${vp.width}x${vp.height}`);
    }
  });
});
