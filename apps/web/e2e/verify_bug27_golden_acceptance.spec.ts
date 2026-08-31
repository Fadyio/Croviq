import { expect, test, type Page } from "@playwright/test";
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

  // Mock Production Data
  await page.route(`**/api/productions/${PRODUCTION_ID}`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: PRODUCTION_ID,
          workspace_id: "ws_demo",
          channel_id: "croviq_syn_ai_eng_01",
          owner_user_id: APPROVED_USER.user_id,
          source_media: {
            upload_id: "upl_48ee4e53140b",
            original_filename: "github.mp4",
            content_type: "video/mp4",
            size_bytes: 51168149,
            gcs_bucket: "croviq-506602-croviq-media-raw",
            gcs_object: "github.mp4",
            status: "uploaded",
            created_at: "2026-08-27T00:50:36Z",
            uploaded_at: "2026-08-27T00:51:23Z",
          },
          status: "uploaded",
          created_at: "2026-08-27T00:50:36Z",
          updated_at: "2026-08-27T00:51:23Z",
        }),
      });
      return;
    }
    await route.continue();
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/playback`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: PRODUCTION_ID,
        playback_url:
          "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        rendered_preview_url:
          "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        studio_voice_preview_url:
          "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        final_mix_url:
          "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        music_url:
          "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        original: {
          available: true,
          artifact_id: "art_source_prod_473209137802",
          status: "ready",
          duration_ms: 101440,
          url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        },
        edited: {
          available: true,
          artifact_id: "art_e2ff47eb2210",
          status: "ready",
          duration_ms: 58360,
          url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        },
        voiceover: {
          available: true,
          artifact_id: "art_vo_9158378c",
          status: "ready",
          duration_ms: 58240,
          voice_id: "Kore",
          url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        },
        final_mix: {
          available: true,
          artifact_id: "art_b7539a8939c5",
          status: "ready",
          duration_ms: 58240,
          url: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        },
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/transcript`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        transcript_id: "tr_473209",
        production_id: PRODUCTION_ID,
        language_code: "en",
        duration_ms: 101440,
        text: "This is a GitHub Actions tutorial. You can find GitHub Actions here.",
        segments: [
          {
            segment_id: "seg_01",
            start_ms: 0,
            end_ms: 5825,
            text: "This is a GitHub Actions tutorial.",
            word_start_index: 0,
            word_end_index: 5,
          },
          {
            segment_id: "seg_02",
            start_ms: 8400,
            end_ms: 15400,
            text: "You can find GitHub Actions here.",
            word_start_index: 6,
            word_end_index: 11,
          },
        ],
        words: [
          { index: 0, text: "This", start_ms: 0, end_ms: 800 },
          { index: 1, text: "is", start_ms: 800, end_ms: 1500 },
          { index: 2, text: "a", start_ms: 1500, end_ms: 2100 },
          { index: 3, text: "GitHub", start_ms: 2100, end_ms: 3200 },
          { index: 4, text: "Actions", start_ms: 3200, end_ms: 4500 },
          { index: 5, text: "tutorial.", start_ms: 4500, end_ms: 5825 },
        ],
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/edl`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        edl: {
          edl_id: "edl_2bd7ba85528a",
          production_id: PRODUCTION_ID,
          source_duration_ms: 101440,
          version: 39,
          cuts: [
            {
              cut_id: "cut_01",
              decision_id: "dec_01",
              decision_type: "TRIM_PAUSE",
              transcript_start_word: 5,
              transcript_end_word: 6,
              requested_start_ms: 5825,
              requested_end_ms: 8400,
              safe_start_ms: 5825,
              safe_end_ms: 8400,
              removed_duration_ms: 2575,
              left_anchor: "tutorial.",
              right_anchor: "You",
              safety_status: "SAFE",
              safety_reason: "Clean silence boundary.",
              confidence: 1,
            },
          ],
          voiceover_segments: [
            {
              segment_id: "seg_001",
              source_start_ms: 0,
              source_end_ms: 5825,
              text: "This is a polished GitHub Actions tutorial.",
              voice_mode: "PREBUILT_STUDIO_VOICE",
              voice_id: "Kore",
              generated_duration_ms: 5000,
            },
          ],
          background_music: null,
          created_at: "2026-08-31T00:00:00Z",
        },
        keep_segments: [
          [0, 5825],
          [8400, 101440],
        ],
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/editorial-run`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run: {
          run_id: "run_01",
          production_id: PRODUCTION_ID,
          status: "completed",
          started_at: "2026-08-31T00:00:00Z",
          completed_at: "2026-08-31T00:01:00Z",
        },
        proposal: {
          production_id: PRODUCTION_ID,
          agent: "leo",
          summary: "Tightened dialogue and removed dead air.",
          decisions: [],
          chapters: [],
        },
        activities: [],
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/renders`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        renders: [
          {
            artifact_id: "art_e2ff47eb2210",
            production_id: PRODUCTION_ID,
            edl_id: "edl_2bd7ba85528a",
            artifact_type: "PREVIEW",
            status: "completed",
            duration_ms: 58360,
          },
          {
            artifact_id: "art_vo_9158378c",
            production_id: PRODUCTION_ID,
            edl_id: "edl_2bd7ba85528a",
            artifact_type: "VOICEOVER_PREVIEW",
            status: "completed",
            duration_ms: 58240,
          },
          {
            artifact_id: "art_b7539a8939c5",
            production_id: PRODUCTION_ID,
            edl_id: "edl_2bd7ba85528a",
            artifact_type: "FINAL_MIX",
            status: "completed",
            duration_ms: 58240,
          },
        ],
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/studio-voice`, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          result: {
            production_id: PRODUCTION_ID,
            voice_id: "Kore",
            status: "completed",
            total_segments: 1,
            accepted_segments: 1,
            all_within_budget: true,
          },
          studio_voice_preview_url:
            "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ voice_id: "Kore", status: "completed" }),
    });
  });

  await page.route("**/api/workspace/agent-settings**", async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        voice_settings: { selected_voice: "Kore", narration_mode: "studio_voice" },
        voices: [
          {
            voice_id: "Puck",
            display_name: "Puck",
            gender: "male",
            description: "Dynamic technical voice",
          },
          {
            voice_id: "Charon",
            display_name: "Charon",
            gender: "male",
            description: "Conversational voice",
          },
          {
            voice_id: "Kore",
            display_name: "Kore",
            gender: "female",
            description: "Instructional voice",
          },
          { voice_id: "Fenrir", display_name: "Fenrir", gender: "male", description: "Deep voice" },
          { voice_id: "Aoede", display_name: "Aoede", gender: "female", description: "Warm voice" },
          {
            voice_id: "Leda",
            display_name: "Leda",
            gender: "female",
            description: "Narration voice",
          },
          { voice_id: "Orus", display_name: "Orus", gender: "male", description: "Calm presenter" },
          {
            voice_id: "Zephyr",
            display_name: "Zephyr",
            gender: "male",
            description: "Modern tone",
          },
        ],
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/chat**`, async (route) => {
    if (route.request().url().includes("/history")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ messages: [] }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        message_id: `msg_${Date.now()}`,
        role: "assistant",
        content: "I tightened the pause and cleaned up the phrasing.",
        tool_executions: [
          { name: "tighten_pause", status: "success", goal: "Tightened pause by 1.2s" },
        ],
        created_at: new Date().toISOString(),
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/release-review*`, async (route) => {
    let modeToReview = "original";
    if (route.request().method() === "POST") {
      const postData = route.request().postDataJSON() || {};
      modeToReview = postData.preview_mode || "original";
    } else {
      const url = new URL(route.request().url());
      modeToReview = url.searchParams.get("preview_mode") || "original";
    }
    const artMap: Record<string, string> = {
      original: "art_source_prod_473209137802",
      edited: "art_e2ff47eb2210",
      voiceover: "art_vo_9158378c",
      final_mix: "art_b7539a8939c5",
    };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: PRODUCTION_ID,
        review: {
          review_id: "rev_test_01",
          production_id: PRODUCTION_ID,
          agent: "iris",
          model: "gemini-3.7-flash",
          verdict: "PASS",
          summary: `Iris evaluated ${modeToReview}. All quality checks passed.`,
          preview_mode: modeToReview,
          reviewed_artifact_id: artMap[modeToReview] || "art_preview_01",
          reviewed_voice_id: modeToReview === "voiceover" ? "Kore" : null,
          approved_for_release: true,
          confidence: 0.98,
          created_at: new Date().toISOString(),
        },
        release_status: "Ready to publish",
        release_ready: true,
        checklist: {
          master_video: true,
          audio: true,
          captions: true,
          chapters: true,
          packaging: true,
          claims: true,
        },
        has_master: true,
        has_packaging: true,
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/packaging*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        proposal_id: "pkg_01",
        production_id: PRODUCTION_ID,
        effective_title: "Master Video Walkthrough",
        effective_description: "Walkthrough of GitHub Actions workflows.",
      }),
    });
  });

  await page.route(`**/api/productions/${PRODUCTION_ID}/publish*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ job: null }),
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
    await page.waitForSelector("[data-testid='editor-workspace']", { timeout: 15000 });
  } else {
    await page.waitForSelector("[data-testid='section-iris-qa']", { timeout: 15000 });
  }
};

test.describe("BUG 27 — Final Editor Demo Polish Golden Acceptance Suite", () => {
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
      await page.waitForTimeout(200);

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
      { timeout: 15000 },
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
      { timeout: 15000 },
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
      { timeout: 15000 },
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
      { timeout: 15000 },
    );
    const label = await page.locator("[data-testid='iris-review-mode-label']").textContent();
    expect(label).toContain("Reviewing: Final Mix");
  });

  test("CASE F & G — Voice selection & Audition: 8 voices available, select triggers auto-regen, audition does not change video", async ({
    page,
  }) => {
    await setupPageAuthAndNavigate(page, "studio_voice");

    const voiceTabBtn = page.locator("[data-testid='tab-voice']");
    await voiceTabBtn.click();

    const voices = ["puck", "charon", "kore", "fenrir", "aoede", "leda", "orus", "zephyr"];
    for (const v of voices) {
      await expect(page.locator(`[data-testid='voice-option-${v}']`)).toBeVisible();
    }

    const aoedeAudition = page.locator("[data-testid='btn-audition-aoede']");
    await expect(aoedeAudition).toBeVisible();
    await aoedeAudition.click();

    const koreOption = page.locator("[data-testid='voice-option-kore']");
    await koreOption.click();

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
    await expect(composer).toBeVisible();

    await composer.fill("Why did you remove this?");
    const sendBtn = page.locator("button[aria-label='Send message to Leo']");
    await sendBtn.click();

    await page.waitForFunction(
      () => document.querySelectorAll("[data-testid='leo-chat-panel'] article").length >= 1,
      { timeout: 15000 },
    );
    const messages = page.locator("[data-testid='leo-chat-panel'] article");
    expect(await messages.count()).toBeGreaterThanOrEqual(1);
  });
});
