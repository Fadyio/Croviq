import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN } from "./test-auth-fixtures";

const FAIRPHONE_PRODUCTION_ID = "prod_f0b41bfd429e";
const FAIRPHONE_TRANSCRIPT_ID = "tr_b9ab6b65d13e";
const FAIRPHONE_RUN_ID = "run_1787720797_fd429e";

const mockFirebasePasswordSignIn = async (page: Page) => {
  await page.route("**/identitytoolkit.googleapis.com/**", async (route) => {
    const url = route.request().url();
    if (url.includes("accounts:signInWithPassword")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          idToken: FIREBASE_ID_TOKEN,
          email: DEMO_EMAIL,
          refreshToken: "fake-refresh-token",
          expiresIn: "3600",
          localId: "demo_user_123",
          registered: true,
        }),
      });
      return;
    }
    if (url.includes("accounts:lookup")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users: [
            {
              localId: "demo_user_123",
              email: DEMO_EMAIL,
              emailVerified: true,
              displayName: "Croviq Demo",
            },
          ],
        }),
      });
      return;
    }
    await route.continue();
  });
};

const createMockWords = (count = 50) => {
  const sampleWords = [
    "The", "Fairphone", "6", "Plus", "is", "an", "upgraded", "version", "of", "the",
    "original", "Fairphone", "with", "more", "memory.", "However,", "you", "will",
    "have", "to", "undo", "a", "couple", "of", "screws", "so", "make", "sure",
    "you", "do", "it", "carefully.", "That", "slides", "off,", "bung", "the",
    "new", "one", "on,", "and", "there", "you", "go.", "Clean", "and", "easy", "fix."
  ];
  return Array.from({ length: count }, (_, idx) => ({
    index: idx,
    word: sampleWords[idx % sampleWords.length],
    text: sampleWords[idx % sampleWords.length],
    start_ms: idx * 400,
    end_ms: idx * 400 + 350,
    confidence: 0.98,
    speaker: "SPEAKER_0",
  }));
};

const setupEditorMocks = async (page: Page) => {
  await mockFirebasePasswordSignIn(page);

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  await page.route("**/api/workspace", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workspace_id: "ws_demo",
        owner_user_id: APPROVED_USER.user_id,
        name: "Workspace",
        created_at: "2026-08-26T00:00:00Z",
        updated_at: "2026-08-26T00:00:00Z",
      }),
    });
  });

  await page.route("**/api/client-events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.route("**/api/productions", async (route) => {
    if (route.request().url().endsWith("/api/productions")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          productions: [],
          total: 0,
        }),
      });
    } else {
      await route.fallback();
    }
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: FAIRPHONE_PRODUCTION_ID,
        workspace_id: "ws_demo",
        channel_id: "croviq_syn_ai_eng_01",
        owner_user_id: APPROVED_USER.user_id,
        status: "COMPLETED",
        source_media: {
          upload_id: "upl_fairphone_01",
          original_filename: "github.mp4",
          content_type: "video/mp4",
          size_bytes: 48800000,
          gcs_bucket: "croviq-media-raw",
          gcs_object: "github.mp4",
          status: "uploaded",
          duration_ms: 113824,
          created_at: "2026-08-27T10:00:00Z",
          uploaded_at: "2026-08-27T10:00:00Z",
        },
        created_at: "2026-08-27T10:00:00Z",
        updated_at: "2026-08-27T10:05:00Z",
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/playback`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        original: {
          available: true,
          status: "ready",
          url: "https://storage.googleapis.com/croviq-media-raw/github.mp4",
          playback_url: "https://storage.googleapis.com/croviq-media-raw/github.mp4",
          duration_ms: 113824,
        },
        edited: {
          available: true,
          status: "ready",
          edl_id: "edl_01",
          url: "https://storage.googleapis.com/croviq-media-rendered/edited.mp4",
          playback_url: "https://storage.googleapis.com/croviq-media-rendered/edited.mp4",
          duration_ms: 109304,
        },
        voiceover: {
          available: true,
          status: "ready",
          edl_id: "edl_01",
          url: "https://storage.googleapis.com/croviq-media-rendered/voiceover.mp4",
          playback_url: "https://storage.googleapis.com/croviq-media-rendered/voiceover.mp4",
          duration_ms: 109304,
        },
        final_mix: {
          available: true,
          status: "ready",
          edl_id: "edl_01",
          url: "https://storage.googleapis.com/croviq-media-rendered/final_mix.mp4",
          playback_url: "https://storage.googleapis.com/croviq-media-rendered/final_mix.mp4",
          duration_ms: 109304,
        },
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/transcript`, async (route) => {
    const words = createMockWords(48);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        transcript_id: FAIRPHONE_TRANSCRIPT_ID,
        production_id: FAIRPHONE_PRODUCTION_ID,
        language: "en",
        duration_ms: 113824,
        created_at: "2026-08-27T10:00:00Z",
        words,
        segments: [
          {
            segment_id: "seg_01",
            start_ms: 0,
            end_ms: 6000,
            text: "The Fairphone 6 Plus is an upgraded version of the original Fairphone with more memory.",
            word_start_index: 0,
            word_end_index: 14,
          },
          {
            segment_id: "seg_02",
            start_ms: 6100,
            end_ms: 12000,
            text: "However, you will have to undo a couple of screws so make sure you do it carefully.",
            word_start_index: 15,
            word_end_index: 31,
          },
        ],
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/editorial-run`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run: {
          run_id: FAIRPHONE_RUN_ID,
          production_id: FAIRPHONE_PRODUCTION_ID,
          status: "completed",
          created_at: "2026-08-27T10:00:00Z",
          updated_at: "2026-08-27T10:05:00Z",
        },
        proposal: {
          decisions: [
            {
              decision_id: "dec_01",
              decision_type: "REMOVE_FILLER",
              concise_reason: "Remove filler word repetition",
              source_start_ms: 2000,
              source_end_ms: 3500,
              transcript_start_word: 4,
              transcript_end_word: 7,
            },
            {
              decision_id: "dec_02",
              decision_type: "SOURCE_COVER",
              concise_reason: "Macro close-up coverage",
              source_start_ms: 6100,
              source_end_ms: 10000,
              transcript_start_word: 15,
              transcript_end_word: 25,
            },
          ],
          chapters: [
            {
              title: "Introduction",
              source_start_ms: 0,
              source_end_ms: 60000,
              summary: "Overview of Fairphone 6 Plus",
            },
            {
              title: "Teardown",
              source_start_ms: 60000,
              source_end_ms: 113824,
              summary: "Unscrewing and modular components",
            },
          ],
        },
        activities: [
          {
            activity_id: "act_01",
            production_id: FAIRPHONE_PRODUCTION_ID,
            run_id: FAIRPHONE_RUN_ID,
            agent: "leo",
            activity_type: "editorial_proposal",
            message: "Removed filler repetition at 00:02.0",
            created_at: "2026-08-27T10:01:00Z",
          },
        ],
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/edl`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        edl_id: "edl_01",
        production_id: FAIRPHONE_PRODUCTION_ID,
        source_duration_ms: 113824,
        created_at: "2026-08-27T10:02:00Z",
        cuts: [
          {
            cut_id: "cut_01",
            decision_id: "dec_01",
            decision_type: "REMOVE_FILLER",
            transcript_start_word: 4,
            transcript_end_word: 7,
            safe_start_ms: 2000,
            safe_end_ms: 3500,
            removed_duration_ms: 1500,
            left_anchor: "original",
            right_anchor: "original",
          },
        ],
        coverage_markers: [
          {
            marker_id: "cov_01",
            decision_id: "dec_02",
            source_start_ms: 6100,
            source_end_ms: 10000,
            coverage_type: "SOURCE_SCREEN",
            reason: "Macro close-up coverage",
          },
        ],
        voiceover_segments: [
          {
            segment_id: "vo_01",
            source_start_ms: 0,
            source_end_ms: 6000,
            text: "The Fairphone 6 Plus is an upgraded version with more memory.",
            voice_mode: "PREBUILT_STUDIO_VOICE",
          },
        ],
        background_music: {
          style: "Minimal modern technology documentary underscore",
          volume_db: -24.0,
          ducking_db: -14.0,
          is_muted: false,
        },
        chapters: [
          {
            chapter_id: "chap_01",
            title: "Introduction",
            source_start_ms: 0,
            source_end_ms: 60000,
          },
          {
            chapter_id: "chap_02",
            title: "Teardown",
            source_start_ms: 60000,
            source_end_ms: 113824,
          },
        ],
        captions: [
          {
            caption_id: "cap_01",
            text: "The Fairphone 6 Plus teardown",
            start_ms: 0,
            end_ms: 5000,
          },
        ],
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/renders`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        renders: [
          {
            render_id: "rnd_preview",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: "edl_01",
            artifact_type: "PREVIEW",
            status: "completed",
            playback_url: "https://storage.googleapis.com/croviq-media-rendered/preview.mp4",
            duration_ms: 109304,
          },
          {
            render_id: "rnd_master",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: "edl_01",
            artifact_type: "MASTER",
            status: "completed",
            playback_url: "https://storage.googleapis.com/croviq-media-rendered/master.mp4",
            duration_ms: 109304,
          },
          {
            render_id: "rnd_vo",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: "edl_01",
            artifact_type: "STUDIO_VOICE_PREVIEW",
            status: "completed",
            playback_url: "https://storage.googleapis.com/croviq-media-rendered/voiceover.mp4",
            duration_ms: 109304,
          },
          {
            render_id: "rnd_fm",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: "edl_01",
            artifact_type: "FINAL_MIX",
            status: "completed",
            playback_url: "https://storage.googleapis.com/croviq-media-rendered/final_mix.mp4",
            duration_ms: 109304,
          },
        ],
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/corrected-script`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: FAIRPHONE_PRODUCTION_ID,
        corrected_transcript: {
          segments: [
            {
              segment_id: "corr_01",
              change_type: "CORRECTED",
              entailment_verdict: "SUPPORTED",
              source_start_ms: 0,
              source_end_ms: 6000,
              edited_start_ms: 0,
              edited_end_ms: 4500,
              original_text: "The Fairphone 6 Plus is an upgraded version of the original Fairphone with more memory.",
              corrected_text: "The Fairphone 6 Plus features upgraded memory and improved performance.",
              correction_reason: "Clarity and concise spoken phrasing.",
            },
          ],
        },
      }),
    });
  });

  await page.route("**/api/workspace/agent-settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        voice_settings: { selected_voice: "Puck" },
        voices: [{ voice_id: "Puck", name: "Puck", description: "Clear and energetic" }],
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/studio-voice`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ voice_id: "Puck" }),
    });
  });
};

const loginAndNavigate = async (page: Page) => {
  await setupEditorMocks(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*");

  await page.evaluate((id) => {
    window.history.pushState(null, "", `/productions/${id}/editor`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, FAIRPHONE_PRODUCTION_ID);

  await page.waitForSelector("[data-testid='editor-workspace']");
};

test.describe("BUG 26 — Editor UI Cleanup / Layout Isolation", () => {
  test("1. Left project sidebar is completely removed and desktop layout is 2 columns", async ({
    page,
  }) => {
    await loginAndNavigate(page);

    // Left project sidebar (MediaBin / project-bin) MUST NOT exist
    await expect(page.getByTestId("project-bin")).toHaveCount(0);
    await expect(page.getByTestId("media-bin")).toHaveCount(0);
    await expect(page.getByText("PROJECT", { exact: true })).toHaveCount(0);
    await expect(page.getByText("OUTPUTS", { exact: true })).toHaveCount(0);

    // Main workspace must contain Video Stage and Right Leo Rail
    const videoStage = page.locator("[data-testid='video-stage']");
    const leoRail = page.locator("[data-testid='production-room']");
    await expect(videoStage).toBeVisible();
    await expect(leoRail).toBeVisible();

    // Verify Leo panel is ~360px wide
    const leoBox = await leoRail.boundingBox();
    expect(leoBox?.width).toBeCloseTo(360, -1);
  });

  test("2. Player width expands into freed space without sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigate(page);

    const videoStage = page.locator("[data-testid='video-stage']");
    const videoBox = await videoStage.boundingBox();
    expect(videoBox).not.toBeNull();

    // At 1440px width with 360px right rail and no 192px sidebar, player width is ~1080px (significantly > 850px)
    expect(videoBox!.width).toBeGreaterThan(1000);
  });

  test("3. Idle 'Edit ready' pill is removed from top navigation", async ({ page }) => {
    await loginAndNavigate(page);

    // Status banner is absent when idle
    await expect(page.getByTestId("compact-status-banner")).toHaveCount(0);
    await expect(page.getByText("Edit ready")).toHaveCount(0);
  });

  test("4. QA button is renamed to 'Send to Iris' with tooltip and QC icon", async ({ page }) => {
    await loginAndNavigate(page);

    const irisBtn = page.getByTestId("btn-run-check");
    await expect(irisBtn).toBeVisible();
    await expect(irisBtn).toContainText("Send to Iris");
    await expect(irisBtn).toHaveAttribute("title", "Send this cut to Iris for quality review");
    // Button must contain ShieldCheck SVG icon
    await expect(irisBtn.locator("svg")).toBeVisible();
  });

  test("5. Timeline track row heights and labels align perfectly with 0px offset drift", async ({
    page,
  }) => {
    await loginAndNavigate(page);

    const timeline = page.locator("[data-testid='editor-timeline']");
    await expect(timeline).toBeVisible();

    // In Final Mix mode, check all active track labels exist and align
    const labelsCol = timeline.getByTestId("timeline-labels-column");
    await expect(labelsCol.getByText("Video", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Edits", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Music", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Chapters", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Captions", { exact: true })).toBeVisible();
  });

  test("6. Timeline tracks change dynamically with preview mode", async ({ page }) => {
    await loginAndNavigate(page);

    const previewToggle = page.getByRole("group", { name: "Preview Mode Selection" });
    const timeline = page.locator("[data-testid='editor-timeline']");
    const labelsCol = timeline.getByTestId("timeline-labels-column");

    // ORIGINAL: Only Video + Original Audio
    await previewToggle.getByRole("button", { name: "Original", exact: true }).click();
    await expect(labelsCol.getByText("Video", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Original Audio", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Edits", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Music", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Chapters", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Captions", { exact: true })).toHaveCount(0);

    // EDITED PREVIEW: Video, Audio, Edits, Chapters, Captions. (Voiceover, Music hidden)
    await previewToggle.getByRole("button", { name: /Edited Preview/i }).click();
    await expect(labelsCol.getByText("Video", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Audio", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Edits", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Chapters", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Captions", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Music", { exact: true })).toHaveCount(0);

    // VOICEOVER PREVIEW: Video, Edits, Voiceover, Chapters, Captions. (Original Audio, Music hidden)
    await previewToggle.getByRole("button", { name: /Voiceover Preview/i }).click();
    await expect(labelsCol.getByText("Video", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Edits", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Chapters", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Captions", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Original Audio", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Audio", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Music", { exact: true })).toHaveCount(0);

    // FINAL MIX: Video, Edits, Voiceover, Music, Chapters, Captions. (Original Audio hidden)
    await previewToggle.getByRole("button", { name: /Final Mix/i }).click();
    await expect(labelsCol.getByText("Video", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Edits", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Music", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Chapters", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Captions", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Original Audio", { exact: true })).toHaveCount(0);
  });

  test("7. Transcript follows preview mode and synchronizes cleanly", async ({ page }) => {
    await loginAndNavigate(page);

    const previewToggle = page.getByRole("group", { name: "Preview Mode Selection" });
    await page.getByTestId("tab-transcript").click();
    const transcriptPanel = page.locator("[data-testid='transcript-panel']");
    await expect(transcriptPanel).toBeVisible();

    // 1. Select Original preview mode
    await previewToggle.getByRole("button", { name: "Original", exact: true }).click();
    // In Original, Corrected Script toggle is hidden and only Original Transcript is shown
    await expect(transcriptPanel.getByText("Original Transcript", { exact: true })).toBeVisible();
    await expect(transcriptPanel.getByRole("button", { name: "Corrected Script" })).toHaveCount(0);
    // Word tokens are visible without cut badges or strike-throughs
    await expect(transcriptPanel.locator("[data-word-index='0']")).toBeVisible();
    await expect(transcriptPanel.getByText("s cut")).toHaveCount(0);

    // 2. Switch to Edited Preview mode
    await previewToggle.getByRole("button", { name: /Edited Preview/i }).click();
    // In Edited mode, defaults to Corrected Script and shows toggle
    await expect(transcriptPanel.getByRole("button", { name: "Corrected Script" })).toBeVisible();
    await expect(transcriptPanel.getByRole("button", { name: "Original Transcript" })).toBeVisible();
    await expect(transcriptPanel.getByText("Original:").first()).toBeVisible();

    // 3. User switches to Original Transcript tab inside Edited preview
    await transcriptPanel.getByRole("button", { name: "Original Transcript" }).click();
    await expect(transcriptPanel.locator("[data-word-index='0']")).toBeVisible();

    // 4. User switches back to Original preview mode -> auto-resets to Original Transcript view without Corrected Script toggle
    await previewToggle.getByRole("button", { name: "Original", exact: true }).click();
    await expect(transcriptPanel.getByRole("button", { name: "Corrected Script" })).toHaveCount(0);
    await expect(transcriptPanel.getByText("Original Transcript")).toBeVisible();
  });

  test("8. Responsive layouts and screenshots at 1600x900, 1440x900, 1280x800", async ({
    page,
  }) => {
    await loginAndNavigate(page);

    const resolutions = [
      { width: 1600, height: 900, suffix: "1600x900" },
      { width: 1440, height: 900, suffix: "1440x900" },
      { width: 1280, height: 800, suffix: "1280x800" },
    ];

    for (const res of resolutions) {
      await page.setViewportSize({ width: res.width, height: res.height });
      await page.waitForTimeout(300);

      // Verify no document scroll
      const isDocumentScrollable = await page.evaluate(
        () => document.documentElement.scrollHeight > window.innerHeight,
      );
      expect(isDocumentScrollable).toBeFalsy();

      // Verify player expands
      const videoBox = await page.locator("[data-testid='video-stage']").boundingBox();
      expect(videoBox?.width).toBeGreaterThan(800);

      // Verify no left sidebar
      await expect(page.getByTestId("project-bin")).toHaveCount(0);
      await expect(page.getByTestId("compact-status-banner")).toHaveCount(0);
      await expect(page.getByTestId("btn-run-check")).toBeVisible();

      // Capture screenshot
      await page.screenshot({
        path: `e2e/screenshots/bug26-layout-${res.suffix}.png`,
        fullPage: true,
      });
    }
  });

  test("9. Captures mode screenshots: Original, Edited, Voiceover, Final Mix", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigate(page);

    const previewToggle = page.getByRole("group", { name: "Preview Mode Selection" });

    // 1. Original
    await previewToggle.getByRole("button", { name: "Original", exact: true }).click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: "e2e/screenshots/bug26-original.png" });

    // 2. Edited
    await previewToggle.getByRole("button", { name: /Edited Preview/i }).click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: "e2e/screenshots/bug26-edited.png" });

    // 3. Voiceover
    await previewToggle.getByRole("button", { name: /Voiceover Preview/i }).click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: "e2e/screenshots/bug26-voiceover.png" });

    // 4. Final Mix
    await previewToggle.getByRole("button", { name: /Final Mix/i }).click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: "e2e/screenshots/bug26-final-mix.png" });
  });

  test("10. Full Section 10 Manual UX Sequence: Modes, Transcript, Alignment, Resize, Hard Refresh", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("requestfailed", (req) => {
      failedRequests.push(req.url());
    });

    // 1. Open github.mp4
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigate(page);

    const previewToggle = page.getByRole("group", { name: "Preview Mode Selection" });
    const timeline = page.locator("[data-testid='editor-timeline']");
    const labelsCol = timeline.getByTestId("timeline-labels-column");
    const videoStage = page.locator("[data-testid='video-stage']");

    // 2. Select Original
    await previewToggle.getByRole("button", { name: "Original", exact: true }).click();

    // 3. Confirm player expands
    const videoBoxOriginal = await videoStage.boundingBox();
    expect(videoBoxOriginal).not.toBeNull();
    expect(videoBoxOriginal!.width).toBeGreaterThan(1000);

    // 4. Confirm timeline contains only Video + Original Audio
    await expect(labelsCol.getByText("Video", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Original Audio", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Edits", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Music", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Chapters", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Captions", { exact: true })).toHaveCount(0);

    // 5. Open Transcript
    await page.getByTestId("tab-transcript").click();
    const transcriptPanel = page.locator("[data-testid='transcript-panel']");
    await expect(transcriptPanel).toBeVisible();

    // 6. Confirm only raw Original Transcript is presented
    await expect(transcriptPanel.getByText("Original Transcript", { exact: true })).toBeVisible();
    await expect(transcriptPanel.getByRole("button", { name: "Corrected Script" })).toHaveCount(0);
    await expect(transcriptPanel.locator("[data-word-index='0']")).toBeVisible();

    // 7. Select Edited Preview
    await previewToggle.getByRole("button", { name: /Edited Preview/i }).click();

    // 8. Confirm Edits/Chapters/Captions appear
    await expect(labelsCol.getByText("Video", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Audio", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Edits", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Chapters", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Captions", { exact: true })).toBeVisible();

    // 9. Confirm Voiceover and Music do not appear
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Music", { exact: true })).toHaveCount(0);

    // 10. Select Voiceover Preview
    await previewToggle.getByRole("button", { name: /Voiceover Preview/i }).click();

    // 11. Confirm Voiceover row appears and Original Audio disappears
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Original Audio", { exact: true })).toHaveCount(0);
    await expect(labelsCol.getByText("Audio", { exact: true })).toHaveCount(0);

    // 12. Select Final Mix
    await previewToggle.getByRole("button", { name: /Final Mix/i }).click();

    // 13. Confirm Voiceover + Music appear
    await expect(labelsCol.getByText("Voiceover", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Music", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Original Audio", { exact: true })).toHaveCount(0);

    // 14. Inspect every track-label/content-row alignment
    const finalTracks = ["Video", "Edits", "Voiceover", "Music", "Chapters", "Captions"];
    for (const name of finalTracks) {
      const labelElem = labelsCol.getByText(name, { exact: true });
      await expect(labelElem).toBeVisible();
      const box = await labelElem.boundingBox();
      expect(box).not.toBeNull();
    }

    // 15. Resize browser to 1600, 1440, and 1280 widths
    for (const w of [1600, 1440, 1280]) {
      await page.setViewportSize({ width: w, height: 900 });
      await page.waitForTimeout(150);
      const box = await videoStage.boundingBox();
      expect(box?.width).toBeGreaterThan(800);
    }

    // 16. Hard refresh
    await page.reload();
    await expect(page.locator("[data-testid='editor-workspace']")).toBeVisible();

    // 17. Repeat mode switching once more
    await previewToggle.getByRole("button", { name: "Original", exact: true }).click();
    await expect(labelsCol.getByText("Original Audio", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Edits", { exact: true })).toHaveCount(0);

    await previewToggle.getByRole("button", { name: /Final Mix/i }).click();
    await expect(labelsCol.getByText("Music", { exact: true })).toBeVisible();
    await expect(labelsCol.getByText("Original Audio", { exact: true })).toHaveCount(0);

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });
});
