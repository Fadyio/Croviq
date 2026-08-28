import { expect, test, type Page } from "@playwright/test";

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
  proposal_id: "pkg_fairphone_01",
  production_id: FAIRPHONE_PRODUCTION_ID,
  agent: "nina",
  model: "gemini-3.7-flash",
  primary_title: "Inside the Most Repairable Modern Smartphone",
  title_candidates: [
    {
      text: "Inside the Most Repairable Modern Smartphone",
      angle: "PROBLEM_SOLUTION",
      why_it_works:
        "Highlights the modularity solution to disposable electronics, matching channel's hardware audience.",
      confidence: 0.96,
    },
    {
      text: "Fairphone 6 Plus Is the Phone Everyone Says They Want",
      angle: "DIRECT_VALUE",
      why_it_works:
        "Directly addresses enthusiast demand for modularity and upgradeable components.",
      confidence: 0.93,
    },
    {
      text: "Why This Phone Lets You Replace Almost Everything",
      angle: "CURIOSITY",
      why_it_works: "Drives curiosity by contrasting with standard glued smartphones.",
      confidence: 0.91,
    },
    {
      text: "How to Repair and Upgrade a Modern Smartphone Yourself",
      angle: "HOW_TO",
      why_it_works: "Action-oriented tutorial framing for hardware DIY viewers.",
      confidence: 0.88,
    },
    {
      text: "Is Modular Hardware Finally Ready for Prime Time?",
      angle: "CONTRARIAN",
      why_it_works: "Challenges common assumptions about repairable phone compromises.",
      confidence: 0.86,
    },
  ],
  description:
    "A complete teardown and hardware walkthrough of the Fairphone 6 Plus.\n\nIn this video, we disassemble the modular chassis, inspect the upgraded motherboard and memory, and demonstrate how to swap individual components using standard tools.\n\n0:00 Introduction & Overview\n0:26 Chassis & Screws Disassembly\n1:15 Modular Component Replacement\n\nSubscribe for more in-depth hardware engineering walkthroughs and technical tutorials.",
  chapters: [
    {
      title: "Introduction & Overview",
      start_ms: 0,
      end_ms: 26160,
      formatted_time: "0:00",
      summary: "Overview of Fairphone 6 Plus features and upgraded specs",
    },
    {
      title: "Chassis & Screws Disassembly",
      start_ms: 26160,
      end_ms: 75000,
      formatted_time: "0:26",
      summary: "Removing screws and sliding off protective casing",
    },
    {
      title: "Modular Component Replacement",
      start_ms: 75000,
      end_ms: 113824,
      formatted_time: "1:15",
      summary: "Hands-on demonstration of modular parts and reassembly",
    },
  ],
  keywords: ["fairphone", "repairability", "teardown", "modular tech", "hardware review"],
  thumbnail_concepts: [
    {
      concept_id: "th_01",
      headline: "REPLACE EVERYTHING",
      visual_subject: "Close up hands holding screwdriver loosening Fairphone internal module",
      composition: "Tight macro focus on phone internals with screwdriver, high contrast lighting",
      emotion: "Curiosity / Empowerment",
      supporting_frame_ms: 35000,
      reason: "Direct visual evidence of modular repairability, visually proving the core hook.",
      confidence: 0.96,
      frame_verified: true,
    },
    {
      concept_id: "th_02",
      headline: "NO GLUE NEEDED",
      visual_subject: "Exploded view of separated screen and chassis modules",
      composition: "Centered hardware layout with clear separation between components",
      emotion: "Surprise / Satisfaction",
      supporting_frame_ms: 58000,
      reason: "Emphasizes zero glue architecture compared to mainstream flagship smartphones.",
      confidence: 0.92,
      frame_verified: true,
    },
    {
      concept_id: "th_03",
      headline: "INSIDE THE 6 PLUS",
      visual_subject: "Presenter holding the exposed motherboard next to upgraded battery module",
      composition: "Rule of thirds, presenter expression looking at camera holding hardware",
      emotion: "Intrigue / Direct value",
      supporting_frame_ms: 90000,
      reason: "Combines human creator presence with exposed circuit board hardware.",
      confidence: 0.89,
      frame_verified: true,
    },
  ],
  short_package: {
    title: "A Modern Smartphone You Can Actually Repair!",
    description:
      "Why the Fairphone 6 Plus lets you swap parts in seconds. #shorts #fairphone #tech",
    hook: "Tired of glued-together smartphones that break forever?",
    hashtags: ["#shorts", "#fairphone", "#tech", "#repair"],
  },
  packaging_summary:
    "High-converting packaging leveraging practical modular hardware demonstration.",
  channel_evidence:
    "Channel history indicates practical demonstration framing tends to outperform generic specification framing by 28% in CTR.",
  confidence: 0.94,
  created_at: "2026-08-28T08:00:00Z",
  prompt_version: 1,
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

const loginAndNavigateToRelease = async (
  page: Page,
  overridesState: { proposal: any; overrides: any } = {
    proposal: FAIRPHONE_PROPOSAL,
    overrides: null,
  },
) => {
  await mockFirebasePasswordSignIn(page);
  await mockReleaseApis(page, overridesState);

  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForURL("**/app*");
  await page.goto(`/productions/${FAIRPHONE_PRODUCTION_ID}/release`);
  await expect(page.getByTestId("release-workspace")).toBeVisible();
};
const mockReleaseApis = async (
  page: Page,
  overridesState: { proposal: any; overrides: any } = {
    proposal: FAIRPHONE_PROPOSAL,
    overrides: null,
  },
) => {
  await page.route("**/api/auth/verify", async (route) => {
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
      body: JSON.stringify(WORKSPACE),
    });
  });

  await page.route("**/api/workspace/agent-settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "You are Leo...",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        maya_prompt: {
          agent_id: "maya",
          prompt_text: "You are Maya...",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        alex_prompt: {
          agent_id: "alex",
          prompt_text: "You are Alex...",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        nina_prompt: {
          agent_id: "nina",
          prompt_text: "You are Nina, Croviq's Packaging Agent for YouTube creators...",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        voice_settings: {
          narration_mode: "original",
          selected_voice: "Puck",
          language: "en-US",
        },
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
        source_media: {
          upload_id: "upl_01",
          original_filename: "Fairphone 6 Plus teardown.mp4",
          content_type: "video/mp4",
          size_bytes: 45000000,
          gcs_bucket: "croviq-media-raw",
          gcs_object: "upl_01.mp4",
          status: "uploaded",
          created_at: "2026-08-28T00:00:00Z",
        },
        created_at: "2026-08-28T00:00:00Z",
        updated_at: "2026-08-28T00:00:00Z",
      }),
    });
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/packaging`, async (route) => {
    if (route.request().method() === "GET") {
      const p = overridesState.proposal;
      const o = overridesState.overrides;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: FAIRPHONE_PRODUCTION_ID,
          proposal: p,
          overrides: o,
          effective_title: o?.custom_title || o?.selected_title || p?.primary_title || "",
          effective_description: o?.custom_description || p?.description || "",
          effective_chapters: o?.custom_chapters || p?.chapters || [],
          effective_short_package: p?.short_package || null,
          effective_thumbnail_concept_id:
            o?.selected_thumbnail_concept_id || p?.thumbnail_concepts?.[0]?.concept_id || null,
          master_artifact: {
            artifact_id: "art_master_01",
            production_id: FAIRPHONE_PRODUCTION_ID,
            edl_id: "edl_01",
            artifact_type: "MASTER",
            status: "completed",
            duration_ms: 113824,
            created_at: "2026-08-28T00:00:00Z",
          },
          has_master: true,
          has_short: true,
          status: "completed",
          generated_at: p?.created_at || null,
        }),
      });
    } else if (route.request().method() === "PATCH") {
      const patchData = JSON.parse(route.request().postData() || "{}");
      overridesState.overrides = {
        ...overridesState.overrides,
        ...patchData,
        updated_at: new Date().toISOString(),
      };
      const p = overridesState.proposal;
      const o = overridesState.overrides;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: FAIRPHONE_PRODUCTION_ID,
          proposal: p,
          overrides: o,
          effective_title: o?.custom_title || o?.selected_title || p?.primary_title || "",
          effective_description: o?.custom_description || p?.description || "",
          effective_chapters: o?.custom_chapters || p?.chapters || [],
          effective_short_package: p?.short_package || null,
          effective_thumbnail_concept_id:
            o?.selected_thumbnail_concept_id || p?.thumbnail_concepts?.[0]?.concept_id || null,
          has_master: true,
          has_short: true,
          status: "completed",
          generated_at: p?.created_at || null,
        }),
      });
    }
  });

  await page.route(`**/api/productions/${FAIRPHONE_PRODUCTION_ID}/package`, async (route) => {
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
        has_master: true,
        has_short: true,
        status: "completed",
        generated_at: FAIRPHONE_PROPOSAL.created_at,
      }),
    });
  });
};

test.describe("Nina Packaging & Release Workspace", () => {
  test("loads Release workspace and displays Nina packaging proposal", async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    await loginAndNavigateToRelease(page);

    // Check title strategy
    await expect(page.getByTestId("input-primary-title")).toHaveValue(
      "Inside the Most Repairable Modern Smartphone",
    );
    await expect(page.getByTestId("list-title-candidates")).toBeVisible();

    // Check description
    await expect(page.getByTestId("textarea-description")).toContainText(
      "A complete teardown and hardware walkthrough of the Fairphone 6 Plus",
    );

    // Check chapters
    await expect(page.getByTestId("list-chapters")).toBeVisible();
    await expect(page.getByTestId("chapter-item-0")).toContainText("0:00");
    await expect(page.getByTestId("chapter-item-1")).toContainText("0:26");
    await expect(page.getByTestId("chapter-item-2")).toContainText("1:15");

    // Check thumbnail concepts & verified badges
    await expect(page.getByTestId("list-thumbnail-concepts")).toBeVisible();
    await expect(page.getByTestId("thumbnail-concept-0")).toContainText("REPLACE EVERYTHING");
    await expect(page.getByTestId("thumbnail-concept-0")).toContainText("Verified Frame");

    // Check right rail
    await expect(page.getByTestId("nina-agent-card")).toBeVisible();
    await expect(page.getByTestId("section-packaging-rationale")).toContainText(
      "Channel history indicates practical demonstration framing",
    );
    await expect(page.getByTestId("section-agent-activity")).toBeVisible();
  });

  test("allows selecting alternative title candidate and editing title", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigateToRelease(page);

    // Click candidate 1 (Direct Value)
    await page.getByTestId("btn-select-title-1").click();
    await expect(page.getByTestId("input-primary-title")).toHaveValue(
      "Fairphone 6 Plus Is the Phone Everyone Says They Want",
    );

    // Custom edit title
    await page.getByTestId("input-primary-title").fill("Custom Teardown Walkthrough");
    await page.getByTestId("btn-save-package-changes").click();
    await expect(page.getByText("Changes saved successfully!")).toBeVisible();
  });

  test("opens Nina settings drawer on avatar click with Prompt and Memory tabs", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigateToRelease(page);

    // Click Nina avatar
    await page.getByTestId("btn-nina-avatar").click();
    // Drawer should open
    await expect(page.getByRole("heading", { name: /Nina.*Settings/i })).toBeVisible();
    await expect(page.getByTestId("tab-prompt")).toBeVisible();
    await expect(page.getByTestId("tab-memory")).toBeVisible();

    // Verify Prompt tab is editable
    await expect(page.getByTestId("agent-prompt-textarea")).toBeVisible();
    // Switch to Memory tab
    await page.getByTestId("tab-memory").click();
    await expect(page.getByText("Channel Memory Bank")).toBeVisible();
    await expect(page.getByText("Clear, crisp, component-level clarity.")).toBeVisible();
  });
  test("takes visual acceptance screenshots (1600x900, 1440x900, 1280x800)", async ({ page }) => {
    // 1600x900
    await page.setViewportSize({ width: 1600, height: 900 });
    await loginAndNavigateToRelease(page);
    await page.waitForTimeout(400);
    await page.screenshot({ path: "e2e/screenshots/release-1600x900.png" });

    // 1440x900
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.screenshot({ path: "e2e/screenshots/release-1440x900.png" });

    // 1280x800
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.screenshot({ path: "e2e/screenshots/release-1280x800.png" });
  });
});
