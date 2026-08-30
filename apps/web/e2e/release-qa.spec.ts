import { expect, test, type Page } from "@playwright/test";

import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";

const FAIRPHONE_PRODUCTION_ID = "prod_0b7657f515ae";

const INITIAL_FAIRPHONE_PROPOSAL = {
  proposal_id: "pkg_fairphone6p_001",
  production_id: FAIRPHONE_PRODUCTION_ID,
  agent: "creator",
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
      frame_verified: true,
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

const CORRECTED_FAIRPHONE_PROPOSAL = {
  ...INITIAL_FAIRPHONE_PROPOSAL,
  description:
    "Here is our hands-on look at the Fairphone 6 Plus! Featuring upgraded Snapdragon internals, 12GB RAM, microSD card expansion, swappable modular backplates, and up to 12 user-replaceable parts.\n\n0:00 Introduction & Unboxing\n0:18 Modular Accessories & Swapping Backplates\n0:51 Repairability & 12 Replaceable Parts",
  packaging_summary:
    "Modular phone teardown and repairability overview (Corrected based on QA feedback).",
};

const INITIAL_QA_REVIEW = {
  review_id: "rev_qa_initial_01",
  production_id: FAIRPHONE_PRODUCTION_ID,
  agent: "iris",
  model: "gemini-3.7-flash",
  verdict: "FIX_REQUIRED",
  summary: "Found 1 unsupported future promise in description.",
  issues: [
    {
      issue_id: "iss_claim_01",
      issue_type: "UNSUPPORTED_CLAIM",
      severity: "HIGH",
      source_start_ms: 0,
      source_end_ms: null,
      artifact_type: "packaging",
      related_decision_id: null,
      message: "Description claims an upcoming full review that isn't supported.",
      suggested_action: "Remove the upcoming review promise from YouTube description.",
      evidence:
        "Claim: 'Stay tuned for the upcoming full Fairphone 6+ review!' has no corroboration.",
    },
  ],
  approved_for_release: false,
  confidence: 0.95,
  created_at: "2026-08-28T08:05:00Z",
  checklist: {
    master_video: true,
    audio: true,
    captions: true,
    chapters: true,
    short: true,
    packaging: false,
    claims: false,
  },
  claim_verifications: [
    {
      claim_text: "12 user-replaceable parts",
      location: "description",
      status: "SUPPORTED_BY_VIDEO",
      evidence: "At 00:51, host demonstrates phone disassembly and repair parts.",
      source_url: null,
    },
    {
      claim_text: "Snapdragon internals",
      location: "description",
      status: "SUPPORTED_EXTERNALLY",
      evidence: "Verified hardware specs for Fairphone 6 Plus platform.",
      source_url: null,
    },
    {
      claim_text: "microSD",
      location: "description",
      status: "SUPPORTED_BY_VIDEO",
      evidence: "Spoken in video and visible on chassis expansion slot.",
      source_url: null,
    },
    {
      claim_text: "Stay tuned for the upcoming full Fairphone 6+ review!",
      location: "description",
      status: "UNSUPPORTED",
      evidence:
        "No planned future review or scheduling found in Croviq channel memory or production context.",
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
    {
      claim_text: "Snapdragon internals",
      location: "description",
      status: "SUPPORTED_EXTERNALLY",
      evidence: "Verified hardware specs for Fairphone 6 Plus platform.",
      source_url: null,
    },
    {
      claim_text: "microSD",
      location: "description",
      status: "SUPPORTED_BY_VIDEO",
      evidence: "Spoken in video and visible on chassis expansion slot.",
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

const mockReleaseApis = async (
  page: Page,
  state: {
    proposal: any;
    review: any;
    releaseReady: boolean;
    releaseStatus: string;
  },
) => {
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
        connected: false,
        channel_id: "croviq_syn_ai_eng_01",
        title: "Croviq",
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
        alex_prompt: {
          agent_id: "alex",
          prompt_text: "You are Alex, Croviq's Data Scientist...",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "You are Leo, Croviq's Video Editor...",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        iris_prompt: {
          agent_id: "iris",
          prompt_text: "You are Iris, Croviq's Quality Assurance Agent and Release Gatekeeper...",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
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
        lessons: [
          {
            topic: "Packaging",
            content: "Practical teardown framing outperforms spec sheets by 28% in CTR.",
            learned_from: "Fairphone 6 Launch",
          },
        ],
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
        proposal: state.proposal,
        overrides: null,
        effective_title: state.proposal.primary_title,
        effective_description: state.proposal.description,
        effective_chapters: state.proposal.chapters,
        effective_short_package: state.proposal.short_package,
        effective_thumbnail_concept_id: "th_01",
        has_master: true,
        has_short: true,
        status: "completed",
        generated_at: state.proposal.created_at,
      }),
    });
  });

  await page.route(
    `**/api/productions/${FAIRPHONE_PRODUCTION_ID}/release-review`,
    async (route) => {
      if (route.request().method() === "POST") {
        state.review = PASSED_QA_REVIEW;
        state.releaseReady = true;
        state.releaseStatus = "Ready to publish";
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: FAIRPHONE_PRODUCTION_ID,
          review: state.review,
          release_status: state.releaseStatus,
          release_ready: state.releaseReady,
          checklist: state.review.checklist,
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
          generated_at: state.review.created_at,
        }),
      });
    },
  );
};

const loginAndNavigateToRelease = async (page: Page, state: any) => {
  await mockFirebasePasswordSignIn(page);
  await mockReleaseApis(page, state);

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

test.describe("Iris QA Agent & Release Gate Workflow", () => {
  test("loads Release Quality Control with initial Fix required state and checklist", async ({
    page,
  }) => {
    const state = {
      proposal: INITIAL_FAIRPHONE_PROPOSAL,
      review: INITIAL_QA_REVIEW,
      releaseReady: false,
      releaseStatus: "Fix required",
    };

    await page.setViewportSize({ width: 1600, height: 900 });
    await loginAndNavigateToRelease(page, state);

    // Verify Release Status badge shows "Fix required"
    await expect(page.getByTestId("release-status-badge")).toContainText(/Fix required/i);

    // Verify Iris Quality Control section
    await expect(page.getByTestId("section-iris-qa")).toBeVisible();
    await expect(page.getByText("Iris — Quality Control")).toBeVisible();

    // Verify QA issue is displayed
    await expect(page.getByTestId("qa-issues-list")).toBeVisible();
    await expect(page.getByTestId("qa-issue-item-0")).toContainText("Unsupported Claim");
    await expect(page.getByTestId("qa-issue-item-0")).toContainText(
      "Description claims an upcoming full review",
    );
  });

  test("runs quality check and transitions to Ready to publish", async ({ page }) => {
    const state = {
      proposal: CORRECTED_FAIRPHONE_PROPOSAL,
      review: PASSED_QA_REVIEW,
      releaseReady: true,
      releaseStatus: "Ready to publish",
    };

    await page.setViewportSize({ width: 1600, height: 900 });
    await loginAndNavigateToRelease(page, state);

    // Click "Run Quality Check"
    await page.click('[data-testid="btn-run-qa"]');

    // Wait for state update
    await expect(page.getByTestId("release-status-badge")).toContainText(/Ready to publish/i);
    await expect(page.getByTestId("btn-open-publish-modal")).toBeVisible();
  });

  test("opens Iris Agent settings drawer on Iris avatar click", async ({ page }) => {
    const state = {
      proposal: INITIAL_FAIRPHONE_PROPOSAL,
      review: INITIAL_QA_REVIEW,
      releaseReady: false,
      releaseStatus: "Fix required",
    };

    await page.setViewportSize({ width: 1600, height: 900 });
    await loginAndNavigateToRelease(page, state);

    // Click Iris avatar
    await page.click('[data-testid="btn-iris-avatar"]');

    // Verify Drawer opens with Iris details
    await expect(page.getByRole("heading", { name: /Iris.*settings/i })).toBeVisible();
    await expect(page.getByText(/Quality/i).first()).toBeVisible();
    await expect(page.getByTestId("tab-prompt")).toBeVisible();
    await expect(page.getByTestId("tab-memory")).toBeVisible();
    await expect(page.getByTestId("tab-voice")).not.toBeVisible();
  });

  test("captures release QA visual screenshots across standard viewports", async ({ page }) => {
    const state = {
      proposal: CORRECTED_FAIRPHONE_PROPOSAL,
      review: PASSED_QA_REVIEW,
      releaseReady: true,
      releaseStatus: "Ready to publish",
    };

    // 1600x900
    await page.setViewportSize({ width: 1600, height: 900 });
    await loginAndNavigateToRelease(page, state);
    await page.waitForTimeout(500);
    await page.screenshot({ path: "e2e/screenshots/release-qa-1600x900.png", fullPage: true });

    // 1440x900
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: "e2e/screenshots/release-qa-1440x900.png", fullPage: true });
    // 1280x800
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: "e2e/screenshots/release-qa-1280x800.png", fullPage: true });
  });
});
