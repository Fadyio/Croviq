import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const FIREBASE_ID_TOKEN =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vY3JvdmlxLTUwNjYwMiIsImF1ZCI6ImNyb3ZpcS01MDY2MDIiLCJhdXRoX3RpbWUiOjEsInVzZXJfaWQiOiJkZW1vX3VzZXJfMTIzIiwic3ViIjoiZGVtb191c2VyXzEyMyIsImlhdCI6MSwiZXhwIjo0MTAyNDQ0ODAwLCJlbWFpbCI6ImRlbW9AY3JvdmlxLmFwcCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmaXJlYmFzZSI6eyJpZGVudGl0aWVzIjp7ImVtYWlsIjpbImRlbW9AY3JvdmlxLmFwcCJdfSwic2lnbl9pbl9wcm92aWRlciI6InBhc3N3b3JkIn19.signature";

const APPROVED_USER = {
  user_id: "demo_user_123",
  email: DEMO_EMAIL,
  display_name: "Croviq Demo",
  avatar_url: null,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const WORKSPACE = {
  workspace_id: "ws_demo",
  owner_user_id: APPROVED_USER.user_id,
  name: "Croviq",
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const FAIRPHONE_PRODUCTION_ID = "prod_0b7657f515ae";

const FAIRPHONE_PROPOSAL = {
  proposal_id: "pkg_fairphone6p_001",
  production_id: FAIRPHONE_PRODUCTION_ID,
  agent: "iris",
  model: "gemini-3.7-flash",
  primary_title: "Fairphone 6 Plus: The Modular Smartphone That Actually Makes Sense",
  title_candidates: [
    {
      text: "Fairphone 6 Plus: The Modular Smartphone That Actually Makes Sense",
      angle: "PROBLEM_SOLUTION",
      why_it_works: "Highlights modularity and practical repair.",
      confidence: 0.96,
    },
    {
      text: "We Took Apart the Fairphone 6 Plus (12 Replaceable Parts!)",
      angle: "DIRECT_VALUE",
      why_it_works: "Direct proof of repairability.",
      confidence: 0.93,
    },
  ],
  description:
    "Here is our hands-on look at the Fairphone 6 Plus! Featuring upgraded Snapdragon internals, 12GB RAM, microSD card expansion, swappable modular backplates, and up to 12 user-replaceable parts.\n\nStay tuned for the upcoming full Fairphone 6+ review!\n\n0:00 Introduction & Unboxing\n0:18 Modular Accessories & Swapping Backplates\n0:51 Repairability & 12 Replaceable Parts",
  chapters: [
    { start_ms: 0, end_ms: 18000, formatted_time: "0:00", title: "Introduction & Unboxing" },
    {
      start_ms: 18000,
      end_ms: 51000,
      formatted_time: "0:18",
      title: "Modular Accessories & Swapping Backplates",
    },
    {
      start_ms: 51000,
      end_ms: 113824,
      formatted_time: "0:51",
      title: "Repairability & 12 Replaceable Parts",
    },
  ],
  keywords: ["fairphone", "repairability", "teardown", "modular tech", "hardware review"],
  thumbnail_concepts: [
    {
      concept_id: "th_01",
      headline: "MODULAR PHONE!",
      visual_subject:
        "Fairphone 6 Plus cobalt blue backplate being removed with small screwdriver tool",
      composition: "Close up hands holding screwdriver loosening Fairphone module",
      emotion: "Curiosity",
      supporting_frame_ms: 28000,
      reason: "Shows modular repairability clearly",
      confidence: 0.96,
    },
    {
      concept_id: "th_02",
      headline: "12 PARTS SWAPPED",
      visual_subject: "Exploded view of modular components on workbench",
      composition: "Top-down geometric alignment",
      emotion: "Intrigue",
      supporting_frame_ms: 45000,
      reason: "Shows full component ecosystem",
      confidence: 0.92,
    },
  ],
  short_package: {
    title: "A Modern Smartphone You Can Actually Repair! 📱 #Shorts",
    description:
      "The Fairphone 6 Plus lets you replace up to 12 parts yourself. #fairphone #tech #shorts",
    hook: "You can actually repair this smartphone yourself!",
    hashtags: ["#fairphone", "#tech", "#shorts"],
  },
  packaging_summary: "Modular phone teardown and repairability overview.",
  channel_evidence: "Channel baseline supports technical hardware teardowns.",
  confidence: 0.95,
  created_at: "2026-08-28T08:00:00Z",
  prompt_version: 1,
};

const PASSED_QA_REVIEW = {
  review_id: "rev_qa_passed_02",
  production_id: FAIRPHONE_PRODUCTION_ID,
  agent: "iris",
  model: "gemini-3.7-flash",
  verdict: "PASS",
  summary:
    "All video continuity, audio loudness, caption timing, and packaging claims passed release gate.",
  issues: [],
  approved_for_release: true,
  confidence: 0.98,
  created_at: "2026-08-28T08:10:00Z",
  checklist: {
    master_video: true,
    audio: true,
    captions: true,
    chapters: true,
    short: true,
    packaging: true,
    claims: true,
  },
  claim_verifications: [
    {
      claim_text: "12 user-replaceable parts",
      location: "description",
      status: "SUPPORTED_BY_VIDEO",
      evidence: "At 00:51, host demonstrates phone disassembly and repair parts.",
      source_url: null,
    },
  ],
  thumbnail_evaluations: [
    {
      concept_index: 0,
      headline: "MODULAR PHONE!",
      verdict: "PASS",
      reason: "Frame at 28000ms accurately shows Fairphone backplate being removed.",
    },
  ],
  master_artifact_id: "art_master_01",
  packaging_proposal_id: "pkg_fairphone6p_001",
};

const MOCK_PREP_DATA = {
  production_id: FAIRPHONE_PRODUCTION_ID,
  channel_title: "Dave's Tech Hardware",
  channel_avatar_url: "",
  is_sample_channel: false,
  can_publish: true,
  has_upload_access: true,
  master_duration_ms: 113824,
  master_title: FAIRPHONE_PROPOSAL.primary_title,
  suggested_title: FAIRPHONE_PROPOSAL.primary_title,
  suggested_description: FAIRPHONE_PROPOSAL.description,
  suggested_chapters: FAIRPHONE_PROPOSAL.chapters,
  suggested_tags: FAIRPHONE_PROPOSAL.keywords,
  suggested_category_id: "28",
  suggested_synthetic_media: true,
  verified_thumbnail_frames: [
    {
      concept_index: 0,
      concept_id: "th_01",
      headline: "MODULAR PHONE!",
      frame_timestamp_ms: 28000,
      formatted_time: "0:28",
      visual_description:
        "Fairphone 6 Plus cobalt blue backplate being removed with small screwdriver tool",
    },
    {
      concept_index: 1,
      concept_id: "th_02",
      headline: "12 PARTS SWAPPED",
      frame_timestamp_ms: 45000,
      formatted_time: "0:45",
      visual_description: "Exploded view of modular components on workbench",
    },
  ],
  has_short: true,
  short_title: FAIRPHONE_PROPOSAL.short_package.title,
  short_description: FAIRPHONE_PROPOSAL.short_package.description,
  release_ready: true,
};

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

const mockPublishApis = async (
  page: Page,
  options: {
    job?: any;
    prepData?: any;
  } = {},
) => {
  const currentJob = options.job || null;
  const currentPrep = options.prepData || MOCK_PREP_DATA;

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  await page.route("**/api/auth/verify", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  await page.route("**/api/channels/youtube/connection", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        connected: true,
        channel_id: "UC_connected_creator",
        channel_title: "Dave's Tech Hardware",
        avatar_url: "",
        subscriber_count: 50000,
        has_monetary_access: false,
        has_upload_access: true,
        scopes: [
          "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/youtube.upload",
        ],
      }),
    });
  });

  await page.route("**/api/channels/sample/dashboard**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ summary: { total_views: 125000 }, videos: [] }),
    });
  });

  await page.route("**/api/channels/research/findings**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });

  await page.route("**/api/workspace", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(WORKSPACE),
    });
  });

  await page.route("**/api/workspace/agent-settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        iris_prompt: {
          agent_id: "iris",
          prompt_text: "Evaluate facts, loudness, captions, and chapters.",
          updated_at: "2026-08-28T00:00:00Z",
          version: 1,
        },
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "Dialogue editing.",
          updated_at: "2026-08-28T00:00:00Z",
          version: 1,
        },
        voice_settings: { narration_mode: "original", selected_voice: "Puck", language: "en-US" },
        voices: [],
      }),
    });
  });

  await page.route("**/api/workspace/agent-settings/memory", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        channel_title: "Hardware Teardowns & Engineering",
        style_guide: "Clear, crisp, component-level clarity.",
        creator_preferences: ["Avoid generic spec sheets", "Emphasize modular components"],
        lessons: [],
      }),
    });
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
        status: "uploaded",
        created_at: "2026-08-28T00:00:00Z",
        updated_at: "2026-08-28T00:00:00Z",
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/packaging`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        production_id: FAIRPHONE_PRODUCTION_ID,
        proposal: FAIRPHONE_PROPOSAL,
        overrides: null,
        effective_title: FAIRPHONE_PROPOSAL.primary_title,
        effective_description: FAIRPHONE_PROPOSAL.description,
        effective_chapters: FAIRPHONE_PROPOSAL.chapters,
        effective_short_package: FAIRPHONE_PROPOSAL.short_package,
        effective_thumbnail_concept_id: "th_01",
        master_artifact: {
          artifact_id: "art_fairphone_master",
          production_id: FAIRPHONE_PRODUCTION_ID,
          edl_id: "edl_fairphone_01",
          artifact_type: "MASTER",
          status: "completed",
          gcs_bucket: "croviq-media-renders",
          gcs_object: "master.mp4",
          duration_ms: 113824,
          size_bytes: 25000000,
          width: 1920,
          height: 1080,
          frame_rate: 30.0,
          video_codec: "h264",
          audio_codec: "aac",
        },
        has_master: true,
        has_short: true,
        status: "completed",
        generated_at: FAIRPHONE_PROPOSAL.created_at,
      }),
    });
  });

  await page.route(
    `**/api/productions/${FAIRPHONE_PRODUCTION_ID}/release-review`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: FAIRPHONE_PRODUCTION_ID,
          review: PASSED_QA_REVIEW,
          release_status: "ready_to_publish",
          release_ready: true,
          checklist: PASSED_QA_REVIEW.checklist,
          master_artifact: {
            artifact_id: "art_master_01",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: "edl_01",
            artifact_type: "MASTER",
            status: "completed",
            playback_url: "https://storage.googleapis.com/test-bucket/master.mp4",
            duration_ms: 113824,
            created_at: "2026-08-26T00:00:00Z",
          },
          generated_at: PASSED_QA_REVIEW.created_at,
        }),
      });
    },
  );

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/publish/prep`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(currentPrep),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/publish`, async (route) => {
    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON();
      const newJob = {
        publish_job_id: "pub_fairphone_live_01",
        production_id: FAIRPHONE_PRODUCTION_ID,
        workspace_id: "ws_demo",
        user_id: APPROVED_USER.user_id,
        connection_id: "conn_dave_tech",
        channel_id: "UC_connected_creator",
        release_review_id: PASSED_QA_REVIEW.review_id,
        package_version: 1,
        artifact_id: "art_fairphone_master",
        artifact_type: "MASTER",
        status: "uploading",
        requested_privacy: payload.requested_privacy || "private",
        actual_privacy: null,
        youtube_video_id: null,
        youtube_url: null,
        thumbnail_status: "pending",
        bytes_uploaded: 12500000,
        total_bytes: 25000000,
        progress_percent: 50.0,
        selected_title: payload.selected_title || FAIRPHONE_PROPOSAL.primary_title,
        description: payload.selected_description || FAIRPHONE_PROPOSAL.description,
        tags: payload.selected_tags || FAIRPHONE_PROPOSAL.keywords,
        category_id: payload.category_id || "28",
        made_for_kids: payload.made_for_kids || false,
        is_synthetic_media: payload.contains_synthetic_media || false,
        short_requested: payload.upload_short || false,
        audit_restriction_detected: false,
        idempotency_key: "idemp_key_01",
        created_at: "2026-08-28T08:30:00Z",
        updated_at: "2026-08-28T08:30:00Z",
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job: newJob,
          can_publish: true,
          has_upload_access: true,
          status_message: "Publishing initiated.",
          is_sample_channel: false,
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job: currentJob,
          can_publish: true,
          has_upload_access: true,
          status_message: currentJob
            ? currentJob.status === "completed"
              ? "Uploaded privately"
              : "Uploading to YouTube 50%"
            : "",
          is_sample_channel: false,
        }),
      });
    }
  });
};

const loginAndNavigateToRelease = async (
  page: Page,
  options: { job?: any; prepData?: any } = {},
) => {
  await mockFirebasePasswordSignIn(page);
  await mockPublishApis(page, options);

  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("/app");

  await page.evaluate((id) => {
    window.history.pushState(null, "", `/productions/${id}/release`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, FAIRPHONE_PRODUCTION_ID);

  await page.waitForSelector("[data-testid='section-iris-qa']");
};

test.describe("YouTube Publishing Workflow", () => {
  test("1. Ready to Publish Gate state and modal launch", async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    await loginAndNavigateToRelease(page);

    // Verify Ready to Publish card
    const releaseCard = page.getByTestId("release-gate-card");
    await expect(releaseCard).toBeVisible();
    await expect(page.getByTestId("release-gate-badge")).toHaveText("Gate Passed");

    const publishBtn = page.getByTestId("btn-publish-to-youtube");
    await expect(publishBtn).toBeVisible();
    await expect(publishBtn).toBeEnabled();
    await expect(publishBtn).toContainText("Publish to YouTube");

    // Capture screenshot 1: release-ready-1600x900.png
    await page.screenshot({
      path: "e2e/screenshots/release-ready-1600x900.png",
      fullPage: false,
    });

    // Click Publish to open confirmation modal
    await publishBtn.click();

    const modal = page.getByTestId("publish-confirmation-modal");
    await expect(modal).toBeVisible();
    await expect(page.getByTestId("section-channel-status")).toContainText("Dave's Tech Hardware");
    await expect(modal.getByTestId("input-publish-title")).toHaveValue(
      FAIRPHONE_PROPOSAL.primary_title,
    );
    await expect(page.getByTestId("section-privacy-selection")).toBeVisible();
    await expect(page.getByTestId("radio-privacy-private")).toBeChecked();
    await expect(page.getByTestId("section-made-for-kids")).toBeVisible();
    await expect(page.getByTestId("section-synthetic-media")).toBeVisible();
    await expect(page.getByTestId("btn-confirm-upload-to-youtube")).toBeVisible();

    await page.setViewportSize({ width: 1440, height: 900 });
    // Capture screenshot 2: publish-confirmation-1440x900.png
    await page.screenshot({
      path: "e2e/screenshots/publish-confirmation-1440x900.png",
      fullPage: false,
    });
  });

  test("2. Uploading in-progress state with live progress bar", async ({ page }) => {
    const uploadingJob = {
      publish_job_id: "pub_fairphone_uploading",
      production_id: FAIRPHONE_PRODUCTION_ID,
      workspace_id: "ws_demo",
      user_id: APPROVED_USER.user_id,
      connection_id: "conn_dave",
      channel_id: "UC_connected_creator",
      release_review_id: PASSED_QA_REVIEW.review_id,
      package_version: 1,
      artifact_id: "art_fairphone_master",
      artifact_type: "MASTER",
      status: "uploading",
      requested_privacy: "private",
      actual_privacy: null,
      youtube_video_id: null,
      youtube_url: null,
      thumbnail_status: "pending",
      bytes_uploaded: 10500000,
      total_bytes: 25000000,
      progress_percent: 42.0,
      selected_title: FAIRPHONE_PROPOSAL.primary_title,
      description: FAIRPHONE_PROPOSAL.description,
      tags: FAIRPHONE_PROPOSAL.keywords,
      category_id: "28",
      made_for_kids: false,
      is_synthetic_media: true,
      audit_restriction_detected: false,
      idempotency_key: "idemp_01",
      created_at: "2026-08-28T08:30:00Z",
      updated_at: "2026-08-28T08:30:00Z",
    };

    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigateToRelease(page, { job: uploadingJob });

    const progressSection = page.getByTestId("section-upload-progress");
    await expect(progressSection).toBeVisible();
    await expect(progressSection).toContainText("Uploading to YouTube 42%");
    await expect(progressSection).toContainText("10.0 MB / 23.8 MB");

    // Capture screenshot 3: publish-uploading-1440x900.png
    await page.screenshot({
      path: "e2e/screenshots/publish-uploading-1440x900.png",
      fullPage: false,
    });
  });

  test("3. Uploaded Privately success state with video link and thumbnail verification", async ({
    page,
  }) => {
    const completedJob = {
      publish_job_id: "pub_fairphone_completed",
      production_id: FAIRPHONE_PRODUCTION_ID,
      workspace_id: "ws_demo",
      user_id: APPROVED_USER.user_id,
      connection_id: "conn_dave",
      channel_id: "UC_connected_creator",
      release_review_id: PASSED_QA_REVIEW.review_id,
      package_version: 1,
      artifact_id: "art_fairphone_master",
      artifact_type: "MASTER",
      status: "completed",
      requested_privacy: "private",
      actual_privacy: "private",
      youtube_video_id: "dQw4w9WgXcQ",
      youtube_url: "https://youtu.be/dQw4w9WgXcQ",
      thumbnail_status: "completed",
      thumbnail_artifact_id: "thumb_fairphone_01",
      bytes_uploaded: 25000000,
      total_bytes: 25000000,
      progress_percent: 100.0,
      selected_title: FAIRPHONE_PROPOSAL.primary_title,
      description: FAIRPHONE_PROPOSAL.description,
      tags: FAIRPHONE_PROPOSAL.keywords,
      category_id: "28",
      made_for_kids: false,
      is_synthetic_media: true,
      audit_restriction_detected: false,
      idempotency_key: "idemp_01",
      created_at: "2026-08-28T08:30:00Z",
      updated_at: "2026-08-28T08:35:00Z",
      completed_at: "2026-08-28T08:35:00Z",
    };

    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigateToRelease(page, { job: completedJob });

    const completedSection = page.getByTestId("section-publish-completed");
    await expect(completedSection).toBeVisible();
    await expect(page.getByTestId("release-gate-badge")).toHaveText("Uploaded Privately");
    await expect(page.getByTestId("text-youtube-video-id")).toHaveText("ID: dQw4w9WgXcQ");
    await expect(completedSection).toContainText("Thumbnail uploaded");

    const openYtBtn = page.getByTestId("btn-open-on-youtube");
    await expect(openYtBtn).toBeVisible();
    await expect(openYtBtn).toHaveAttribute("href", "https://youtu.be/dQw4w9WgXcQ");

    // Capture screenshot 4: publish-complete-private-1440x900.png
    await page.screenshot({
      path: "e2e/screenshots/publish-complete-private-1440x900.png",
      fullPage: false,
    });
  });

  test("4. Audit restriction banner when project unverified", async ({ page }) => {
    const restrictedJob = {
      publish_job_id: "pub_fairphone_restricted",
      production_id: FAIRPHONE_PRODUCTION_ID,
      workspace_id: "ws_demo",
      user_id: APPROVED_USER.user_id,
      connection_id: "conn_dave",
      channel_id: "UC_connected_creator",
      release_review_id: PASSED_QA_REVIEW.review_id,
      package_version: 1,
      artifact_id: "art_fairphone_master",
      artifact_type: "MASTER",
      status: "completed",
      requested_privacy: "public",
      actual_privacy: "private", // Restricted by YouTube!
      youtube_video_id: "dQw4w9WgXcQ",
      youtube_url: "https://youtu.be/dQw4w9WgXcQ",
      thumbnail_status: "completed",
      bytes_uploaded: 25000000,
      total_bytes: 25000000,
      progress_percent: 100.0,
      selected_title: FAIRPHONE_PROPOSAL.primary_title,
      description: FAIRPHONE_PROPOSAL.description,
      tags: FAIRPHONE_PROPOSAL.keywords,
      category_id: "28",
      made_for_kids: false,
      is_synthetic_media: true,
      audit_restriction_detected: true,
      idempotency_key: "idemp_01",
      created_at: "2026-08-28T08:30:00Z",
      updated_at: "2026-08-28T08:35:00Z",
      completed_at: "2026-08-28T08:35:00Z",
    };

    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigateToRelease(page, { job: restrictedJob });

    const banner = page.getByTestId("banner-audit-restriction");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("YouTube restricted this API project to private uploads");
    await expect(page.getByTestId("release-gate-badge")).toHaveText("Uploaded Privately");
  });
});
