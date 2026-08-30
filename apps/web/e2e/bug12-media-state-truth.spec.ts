import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN } from "./test-auth-fixtures";

const mockAuthAndCommonRoutes = async (page: Page) => {
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
          idToken: FIREBASE_ID_TOKEN,
          registered: true,
          refreshToken: "mock-refresh-token",
          expiresIn: "3600",
        }),
      });
    } else if (url.includes("accounts:lookup")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users: [
            {
              localId: APPROVED_USER.user_id,
              email: DEMO_EMAIL,
              emailVerified: true,
              displayName: APPROVED_USER.display_name,
            },
          ],
        }),
      });
    } else {
      await route.continue();
    }
  });

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  await page.route("**/api/client-events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.route("**/api/productions/*/transcribe", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "completed" }),
    });
  });

  await page.route("**/api/productions/*/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "completed" }),
    });
  });

  await page.route("**/api/productions/*/renders/preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "completed" }),
    });
  });
};

const loginUser = async (page: Page) => {
  await mockAuthAndCommonRoutes(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*");
};

test.describe("BUG 12 — Editor Media State Truth and Consistency", () => {
  test("CASE A: Source only production — Original available, all outputs unavailable", async ({
    page,
  }) => {
    const prodId = "prod_case_a_source_only";
    await mockAuthAndCommonRoutes(page);

    await page.route(`**/api/productions/${prodId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          workspace_id: "ws_demo",
          status: "uploaded",
          source_media: {
            upload_id: "upl_source_a",
            original_filename: "raw_recording.mp4",
            content_type: "video/mp4",
            size_bytes: 1024000,
            gcs_bucket: "bucket",
            gcs_object: "raw.mp4",
            status: "uploaded",
          },
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/playback`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          playback_url: "http://localhost:5173/mock_source.mp4",
          original: {
            available: true,
            artifact_id: "upl_source_a",
            url: "http://localhost:5173/mock_source.mp4",
            duration_ms: 60000,
            status: "ready",
          },
          edited: { available: false, status: "unavailable" },
          voiceover: { available: false, status: "unavailable" },
          final_mix: { available: false, status: "unavailable" },
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/transcript`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          transcript_id: "tr_a",
          production_id: prodId,
          duration_ms: 60000,
          words: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/editorial-run`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            run_id: "run_a",
            production_id: prodId,
            status: "completed",
            editor_proposal_id: null,
          },
          proposal: null,
          activities: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/edl`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    await page.route(`**/api/productions/${prodId}/renders`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodId, renders: [] }),
      });
    });

    await page.route(`**/api/productions/${prodId}/broll`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodId, artifacts: [] }),
      });
    });

    await page.route(`**/api/productions/${prodId}/corrected-script`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    await loginUser(page);
    await page.goto(`/productions/${prodId}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");

    // Original must be available and active
    const originalBtn = page.getByRole("button", { name: /^Original$/i });
    await expect(originalBtn).toBeVisible();

    // Outputs must NOT be present as playable options
    await expect(page.getByTestId("preview-toggle-edited")).toHaveCount(0);
    await expect(page.getByTestId("preview-toggle-studio-voice")).toHaveCount(0);
    await expect(page.getByTestId("preview-toggle-final-mix")).toHaveCount(0);

    // Video must play source video
    const video = page.locator("video");
    await expect(video).toBeVisible();
    await expect(video).toHaveAttribute("src", "http://localhost:5173/mock_source.mp4");
  });

  test("CASE B: Source + active EDL + edited render — Original + Edited available, others unavailable", async ({
    page,
  }) => {
    const prodId = "prod_case_b_edited";
    const activeEdlId = "edl_active_b";
    await mockAuthAndCommonRoutes(page);

    await page.route(`**/api/productions/${prodId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          workspace_id: "ws_demo",
          status: "uploaded",
          source_media: {
            upload_id: "upl_source_b",
            original_filename: "interview.mp4",
            content_type: "video/mp4",
            size_bytes: 2048000,
            gcs_bucket: "bucket",
            gcs_object: "interview.mp4",
            status: "uploaded",
          },
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/playback`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          playback_url: "http://localhost:5173/source_b.mp4",
          rendered_preview_url: "http://localhost:5173/preview_b.mp4",
          original: {
            available: true,
            artifact_id: "upl_source_b",
            url: "http://localhost:5173/source_b.mp4",
            duration_ms: 100000,
            status: "ready",
          },
          edited: {
            available: true,
            artifact_id: "art_prev_b",
            edl_id: activeEdlId,
            url: "http://localhost:5173/preview_b.mp4",
            duration_ms: 75000,
            status: "ready",
          },
          voiceover: { available: false, status: "unavailable" },
          final_mix: { available: false, status: "unavailable" },
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/edl`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          edl: {
            edl_id: activeEdlId,
            production_id: prodId,
            version: 1,
            source_duration_ms: 100000,
            cuts: [
              {
                cut_id: "cut_b1",
                decision_id: "dec_1",
                decision_type: "TRIM_PAUSE",
                safety_status: "SAFE",
                safe_start_ms: 10000,
                safe_end_ms: 35000,
                removed_duration_ms: 25000,
              },
            ],
          },
          keep_segments: [
            [0, 10000],
            [35000, 100000],
          ],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/transcript`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          transcript_id: "tr_b",
          production_id: prodId,
          duration_ms: 100000,
          words: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/editorial-run`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            run_id: "run_b",
            production_id: prodId,
            status: "completed",
            editor_proposal_id: "prop_b",
          },
          proposal: {
            production_id: prodId,
            decisions: [],
            chapters: [],
            summary: "Edited cuts applied",
            overall_confidence: 0.95,
          },
          activities: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/renders`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          renders: [
            {
              artifact_id: "art_prev_b",
              production_id: prodId,
              edl_id: activeEdlId,
              artifact_type: "PREVIEW",
              status: "completed",
              playback_url: "http://localhost:5173/preview_b.mp4",
              duration_ms: 75000,
            },
          ],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/broll`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodId, artifacts: [] }),
      });
    });

    await page.route(`**/api/productions/${prodId}/corrected-script`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    await loginUser(page);
    await page.goto(`/productions/${prodId}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");

    // Both Original and Edited Preview must be available
    await expect(page.getByRole("button", { name: /^Original$/i })).toBeVisible();
    await expect(page.getByTestId("preview-toggle-edited")).toBeVisible();

    // Voiceover and Final Mix must NOT be visible
    await expect(page.getByTestId("preview-toggle-studio-voice")).toHaveCount(0);
    await expect(page.getByTestId("preview-toggle-final-mix")).toHaveCount(0);

    // Edited Preview must be active by default with preview URL
    const video = page.locator("video");
    await expect(video).toHaveAttribute("src", "http://localhost:5173/preview_b.mp4");

    // Cut badge must show 1 cut
    await expect(page.getByTestId("preview-toggle-edited")).toContainText("1");
  });

  test("CASE C: Full pipeline — all real existing outputs mapped to active EDL", async ({
    page,
  }) => {
    const prodId = "prod_case_c_full";
    const activeEdlId = "edl_active_c";
    await mockAuthAndCommonRoutes(page);

    await page.route(`**/api/productions/${prodId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          workspace_id: "ws_demo",
          status: "uploaded",
          source_media: {
            upload_id: "upl_source_c",
            original_filename: "complete_pipeline.mp4",
            content_type: "video/mp4",
            size_bytes: 3000000,
            gcs_bucket: "bucket",
            gcs_object: "raw.mp4",
            status: "uploaded",
          },
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/playback`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          playback_url: "http://localhost:5173/source_c.mp4",
          rendered_preview_url: "http://localhost:5173/preview_c.mp4",
          studio_voice_preview_url: "http://localhost:5173/voiceover_c.mp4",
          final_mix_url: "http://localhost:5173/finalmix_c.mp4",
          original: {
            available: true,
            artifact_id: "upl_source_c",
            url: "http://localhost:5173/source_c.mp4",
            duration_ms: 120000,
            status: "ready",
          },
          edited: {
            available: true,
            artifact_id: "art_prev_c",
            edl_id: activeEdlId,
            url: "http://localhost:5173/preview_c.mp4",
            duration_ms: 90000,
            status: "ready",
          },
          voiceover: {
            available: true,
            artifact_id: "art_sv_c",
            edl_id: activeEdlId,
            url: "http://localhost:5173/voiceover_c.mp4",
            duration_ms: 90000,
            status: "ready",
          },
          final_mix: {
            available: true,
            artifact_id: "art_fm_c",
            edl_id: activeEdlId,
            url: "http://localhost:5173/finalmix_c.mp4",
            duration_ms: 90000,
            status: "ready",
          },
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/edl`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          edl: {
            edl_id: activeEdlId,
            production_id: prodId,
            version: 1,
            source_duration_ms: 120000,
            cuts: [
              {
                cut_id: "cut_c1",
                decision_type: "TRIM_PAUSE",
                safety_status: "SAFE",
                safe_start_ms: 20000,
                safe_end_ms: 50000,
                removed_duration_ms: 30000,
              },
            ],
          },
          keep_segments: [
            [0, 20000],
            [50000, 120000],
          ],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/transcript`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          transcript_id: "tr_c",
          production_id: prodId,
          duration_ms: 120000,
          words: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/editorial-run`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            run_id: "run_c",
            production_id: prodId,
            status: "completed",
            editor_proposal_id: "prop_c",
          },
          proposal: {
            production_id: prodId,
            decisions: [],
            chapters: [],
            summary: "Full pipeline generated",
            overall_confidence: 0.98,
          },
          activities: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/renders`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          renders: [
            {
              artifact_id: "art_prev_c",
              production_id: prodId,
              edl_id: activeEdlId,
              artifact_type: "PREVIEW",
              status: "completed",
              playback_url: "http://localhost:5173/preview_c.mp4",
              duration_ms: 90000,
            },
            {
              artifact_id: "art_sv_c",
              production_id: prodId,
              edl_id: activeEdlId,
              artifact_type: "STUDIO_VOICE_PREVIEW",
              status: "completed",
              playback_url: "http://localhost:5173/voiceover_c.mp4",
              duration_ms: 90000,
            },
            {
              artifact_id: "art_fm_c",
              production_id: prodId,
              edl_id: activeEdlId,
              artifact_type: "FINAL_MIX",
              status: "completed",
              playback_url: "http://localhost:5173/finalmix_c.mp4",
              duration_ms: 90000,
            },
          ],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/broll`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodId, artifacts: [] }),
      });
    });

    await page.route(`**/api/productions/${prodId}/corrected-script`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    await loginUser(page);
    await page.goto(`/productions/${prodId}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");

    // All 4 buttons must be visible
    await expect(page.getByRole("button", { name: /^Original$/i })).toBeVisible();
    await expect(page.getByTestId("preview-toggle-edited")).toBeVisible();
    await expect(page.getByTestId("preview-toggle-studio-voice")).toBeVisible();
    await expect(page.getByTestId("preview-toggle-final-mix")).toBeVisible();

    // Default should resolve to highest artifact: Final Mix
    const video = page.locator("video");
    await expect(video).toHaveAttribute("src", "http://localhost:5173/finalmix_c.mp4");

    // Switch to Voiceover Preview
    await page.getByTestId("preview-toggle-studio-voice").click();
    await expect(video).toHaveAttribute("src", "http://localhost:5173/voiceover_c.mp4");

    // Switch to Edited Preview
    await page.getByTestId("preview-toggle-edited").click();
    await expect(video).toHaveAttribute("src", "http://localhost:5173/preview_c.mp4");

    // Switch to Original
    await page.getByRole("button", { name: /^Original$/i }).click();
    await expect(video).toHaveAttribute("src", "http://localhost:5173/source_c.mp4");
  });

  test("CASE D: Stale render from superseded EDL — stale output NOT treated as active", async ({
    page,
  }) => {
    const prodId = "prod_case_d_stale_edl";
    const currentEdlId = "edl_v2_current";
    const oldEdlId = "edl_v1_superseded";
    await mockAuthAndCommonRoutes(page);

    await page.route(`**/api/productions/${prodId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          workspace_id: "ws_demo",
          status: "uploaded",
          source_media: {
            upload_id: "upl_source_d",
            original_filename: "superseded.mp4",
            content_type: "video/mp4",
            size_bytes: 1000000,
            gcs_bucket: "bucket",
            gcs_object: "raw.mp4",
            status: "uploaded",
          },
        }),
      });
    });

    // Backend correctly indicates edited is unavailable for active edl_v2_current
    await page.route(`**/api/productions/${prodId}/playback`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          playback_url: "http://localhost:5173/source_d.mp4",
          original: {
            available: true,
            artifact_id: "upl_source_d",
            url: "http://localhost:5173/source_d.mp4",
            duration_ms: 80000,
            status: "ready",
          },
          edited: { available: false, edl_id: currentEdlId, status: "unavailable" },
          voiceover: { available: false, status: "unavailable" },
          final_mix: { available: false, status: "unavailable" },
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/edl`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          edl: {
            edl_id: currentEdlId,
            production_id: prodId,
            version: 2,
            source_duration_ms: 80000,
            cuts: [],
          },
          keep_segments: [[0, 80000]],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/transcript`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          transcript_id: "tr_d",
          production_id: prodId,
          duration_ms: 80000,
          words: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/editorial-run`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            run_id: "run_d",
            production_id: prodId,
            status: "completed",
            editor_proposal_id: null,
          },
          proposal: null,
          activities: [],
        }),
      });
    });

    // Renders contains an old render belonging to oldEdlId
    await page.route(`**/api/productions/${prodId}/renders`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          renders: [
            {
              artifact_id: "art_stale_old",
              production_id: prodId,
              edl_id: oldEdlId,
              artifact_type: "PREVIEW",
              status: "completed",
              playback_url: "http://localhost:5173/stale_render.mp4",
              duration_ms: 50000,
            },
          ],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/broll`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodId, artifacts: [] }),
      });
    });

    await page.route(`**/api/productions/${prodId}/corrected-script`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    await loginUser(page);
    await page.goto(`/productions/${prodId}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");

    // Stale render must NOT be treated as active edited preview
    await expect(page.getByTestId("preview-toggle-edited")).toHaveCount(0);

    // Original must be active with source video
    const video = page.locator("video");
    await expect(video).toHaveAttribute("src", "http://localhost:5173/source_d.mp4");
  });

  test("CASE E: Missing artifact object — truthful unavailable state, NEVER silent fallback", async ({
    page,
  }) => {
    const prodId = "prod_case_e_missing_artifact";
    await mockAuthAndCommonRoutes(page);

    await page.route(`**/api/productions/${prodId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          workspace_id: "ws_demo",
          status: "uploaded",
          source_media: {
            upload_id: "upl_source_e",
            original_filename: "missing.mp4",
            content_type: "video/mp4",
            size_bytes: 1000000,
            gcs_bucket: "bucket",
            gcs_object: "raw.mp4",
            status: "uploaded",
          },
        }),
      });
    });

    // Playback indicates edited is failed / missing
    await page.route(`**/api/productions/${prodId}/playback`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          playback_url: "http://localhost:5173/source_e.mp4",
          original: {
            available: true,
            artifact_id: "upl_source_e",
            url: "http://localhost:5173/source_e.mp4",
            duration_ms: 60000,
            status: "ready",
          },
          edited: { available: false, status: "failed" },
          voiceover: { available: false, status: "unavailable" },
          final_mix: { available: false, status: "unavailable" },
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/edl`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          edl: {
            edl_id: "edl_e",
            production_id: prodId,
            version: 1,
            source_duration_ms: 60000,
            cuts: [],
          },
          keep_segments: [[0, 60000]],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/transcript`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          transcript_id: "tr_e",
          production_id: prodId,
          duration_ms: 60000,
          words: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/editorial-run`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            run_id: "run_e",
            production_id: prodId,
            status: "completed",
            editor_proposal_id: null,
          },
          proposal: null,
          activities: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/renders`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodId,
          renders: [
            {
              artifact_id: "art_failed_e",
              production_id: prodId,
              edl_id: "edl_e",
              artifact_type: "PREVIEW",
              status: "failed",
              playback_url: null,
            },
          ],
        }),
      });
    });

    await page.route(`**/api/productions/${prodId}/broll`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodId, artifacts: [] }),
      });
    });

    await page.route(`**/api/productions/${prodId}/corrected-script`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    await loginUser(page);
    await page.goto(`/productions/${prodId}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");

    // Falls back explicitly to Original since edited is failed
    const video = page.locator("video");
    await expect(video).toBeVisible();
    await expect(video).toHaveAttribute("src", "http://localhost:5173/source_e.mp4");

    // Edited button is NOT visible as playable
    await expect(page.getByTestId("preview-toggle-edited")).toHaveCount(0);
  });

  test("CASE F: Strict project isolation between two productions", async ({ page }) => {
    const prodA = "prod_case_f_alpha";
    const prodB = "prod_case_f_beta";
    await mockAuthAndCommonRoutes(page);

    // Setup Production A
    await page.route(`**/api/productions/${prodA}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodA,
          workspace_id: "ws_demo",
          status: "uploaded",
          source_media: {
            upload_id: "upl_alpha",
            original_filename: "Alpha_Video.mp4",
            content_type: "video/mp4",
            size_bytes: 1000000,
            gcs_bucket: "bucket",
            gcs_object: "alpha.mp4",
            status: "uploaded",
          },
        }),
      });
    });

    await page.route(`**/api/productions/${prodA}/playback`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodA,
          playback_url: "http://localhost:5173/source_alpha.mp4",
          rendered_preview_url: "http://localhost:5173/preview_alpha.mp4",
          studio_voice_preview_url: "http://localhost:5173/voiceover_alpha.mp4",
          original: {
            available: true,
            artifact_id: "upl_alpha",
            url: "http://localhost:5173/source_alpha.mp4",
            duration_ms: 100000,
            status: "ready",
          },
          edited: {
            available: true,
            artifact_id: "art_prev_alpha",
            edl_id: "edl_alpha",
            url: "http://localhost:5173/preview_alpha.mp4",
            duration_ms: 60000,
            status: "ready",
          },
          voiceover: {
            available: true,
            artifact_id: "art_sv_alpha",
            edl_id: "edl_alpha",
            url: "http://localhost:5173/voiceover_alpha.mp4",
            duration_ms: 60000,
            status: "ready",
          },
          final_mix: { available: false, status: "unavailable" },
        }),
      });
    });

    await page.route(`**/api/productions/${prodA}/edl`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          edl: {
            edl_id: "edl_alpha",
            production_id: prodA,
            version: 1,
            source_duration_ms: 100000,
            cuts: [
              {
                cut_id: "cut_a1",
                decision_type: "TRIM_PAUSE",
                safety_status: "SAFE",
                safe_start_ms: 10000,
                safe_end_ms: 50000,
                removed_duration_ms: 40000,
              },
            ],
          },
          keep_segments: [
            [0, 10000],
            [50000, 100000],
          ],
        }),
      });
    });

    await page.route(`**/api/productions/${prodA}/transcript`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          transcript_id: "tr_alpha",
          production_id: prodA,
          duration_ms: 100000,
          words: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodA}/editorial-run`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            run_id: "run_alpha",
            production_id: prodA,
            status: "completed",
            editor_proposal_id: null,
          },
          proposal: null,
          activities: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodA}/renders`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodA,
          renders: [
            {
              artifact_id: "art_prev_alpha",
              production_id: prodA,
              edl_id: "edl_alpha",
              artifact_type: "PREVIEW",
              status: "completed",
              playback_url: "http://localhost:5173/preview_alpha.mp4",
              duration_ms: 60000,
            },
            {
              artifact_id: "art_sv_alpha",
              production_id: prodA,
              edl_id: "edl_alpha",
              artifact_type: "STUDIO_VOICE_PREVIEW",
              status: "completed",
              playback_url: "http://localhost:5173/voiceover_alpha.mp4",
              duration_ms: 60000,
            },
          ],
        }),
      });
    });

    await page.route(`**/api/productions/${prodA}/broll`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodA, artifacts: [] }),
      });
    });

    await page.route(`**/api/productions/${prodA}/corrected-script`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    // Setup Production B
    await page.route(`**/api/productions/${prodB}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodB,
          workspace_id: "ws_demo",
          status: "uploaded",
          source_media: {
            upload_id: "upl_beta",
            original_filename: "Beta_Video.mp4",
            content_type: "video/mp4",
            size_bytes: 500000,
            gcs_bucket: "bucket",
            gcs_object: "beta.mp4",
            status: "uploaded",
          },
        }),
      });
    });

    await page.route(`**/api/productions/${prodB}/playback`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: prodB,
          playback_url: "http://localhost:5173/source_beta.mp4",
          original: {
            available: true,
            artifact_id: "upl_beta",
            url: "http://localhost:5173/source_beta.mp4",
            duration_ms: 30000,
            status: "ready",
          },
          edited: { available: false, status: "unavailable" },
          voiceover: { available: false, status: "unavailable" },
          final_mix: { available: false, status: "unavailable" },
        }),
      });
    });

    await page.route(`**/api/productions/${prodB}/edl`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    await page.route(`**/api/productions/${prodB}/transcript`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          transcript_id: "tr_beta",
          production_id: prodB,
          duration_ms: 30000,
          words: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodB}/editorial-run`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            run_id: "run_beta",
            production_id: prodB,
            status: "completed",
            editor_proposal_id: null,
          },
          proposal: null,
          activities: [],
        }),
      });
    });

    await page.route(`**/api/productions/${prodB}/renders`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodB, renders: [] }),
      });
    });

    await page.route(`**/api/productions/${prodB}/broll`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ production_id: prodB, artifacts: [] }),
      });
    });

    await page.route(`**/api/productions/${prodB}/corrected-script`, async (route) => {
      await route.fulfill({ status: 404 });
    });

    await loginUser(page);

    // 1. Open Production A
    await page.goto(`/productions/${prodA}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");
    await expect(page.locator("header")).toContainText("Alpha_Video.mp4");
    await expect(page.getByTestId("preview-toggle-studio-voice")).toBeVisible();

    // 2. Open Production B
    await page.goto(`/productions/${prodB}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");
    await expect(page.locator("header")).toContainText("Beta_Video.mp4");
    await expect(page.locator("header")).not.toContainText("Alpha_Video.mp4");
    await expect(page.getByTestId("preview-toggle-studio-voice")).toHaveCount(0);

    const videoB = page.locator("video");
    await expect(videoB).toHaveAttribute("src", "http://localhost:5173/source_beta.mp4");

    // 3. Return to Production A
    await page.goto(`/productions/${prodA}/editor`);
    await page.waitForSelector("[data-testid='editor-workspace']");
    await expect(page.locator("header")).toContainText("Alpha_Video.mp4");
    await expect(page.getByTestId("preview-toggle-studio-voice")).toBeVisible();
  });
});
