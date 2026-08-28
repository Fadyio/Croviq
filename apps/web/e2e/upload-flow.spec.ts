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

const mockBackendApis = async (page: Page, productions: unknown[] = []) => {
  const researchConfig = {
    workspace_id: "ws_demo",
    channel_id: "croviq_syn_ai_eng_01",
    enabled: true,
    cadence: "EVERY_DAY",
    prompts: [
      {
        prompt_id: "emerging-topics",
        text: "Find emerging AI engineering topics relevant to this channel",
        enabled: true,
        use_broad_web_search: true,
        preferred_sources: [],
      },
    ],
    last_run_at: null,
    next_run_at: "2026-08-29T00:00:00Z",
    updated_at: "2026-08-28T00:00:00Z",
  };
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
        name: "Croviq",
        created_at: "2026-08-26T00:00:00Z",
        updated_at: "2026-08-26T00:00:00Z",
      }),
    });
  });

  await page.route("**/api/channels/sample/dashboard?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        channel: {
          channel_id: "croviq_syn_ai_eng_01",
          source_type: "synthetic",
          title: "Modern AI Engineering",
          description: "Sample channel",
          avatar_url: null,
          subscriber_count: 51317,
          video_count: 100,
        },
        period_days: 28,
        period_end: "2026-08-26",
        kpis: [
          { metric: "views", current_value: 42100, previous_value: 35600, change_percentage: 18.3 },
          {
            metric: "watch_time_hours",
            current_value: 3180,
            previous_value: 2900,
            change_percentage: 9.7,
          },
          {
            metric: "net_subscribers",
            current_value: 184,
            previous_value: 128,
            change_percentage: 43.8,
          },
          {
            metric: "average_retention",
            current_value: 58.4,
            previous_value: 54.1,
            change_percentage: 7.9,
          },
        ],
        trend: Array.from({ length: 28 }, (_, i) => {
          const day = i + 1;
          const dateStr = `2026-08-${String(day).padStart(2, "0")}`;
          return {
            date: dateStr,
            views: 1400 + Math.round(Math.sin(i / 3) * 350 + i * 20),
            previous_views: 1200 + Math.round(Math.cos(i / 3) * 200 + i * 15),
            watch_time_hours: 90 + Math.round(i * 1.8),
            previous_watch_time_hours: 80 + Math.round(i * 1.5),
            net_subscribers: 6 + Math.round(Math.sin(i / 2) * 3),
            previous_net_subscribers: 5 + Math.round(Math.cos(i / 2) * 2),
          };
        }),
        latest_video: {
          video_id: "vid_syn_100",
          title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
          published_at: "2026-08-13T04:00:00Z",
          views: 23314,
          watch_time_hours: 1258.9,
          subscribers_gained: 334,
          subscribers_lost: 31,
          net_subscribers: 303,
          view_delta_percentage: 18,
          subscriber_conversion_delta_percentage: -2.84,
          retention_percentage: 54.8,
          retention_delta_points: -25.61,
        },
        video_performance: [
          {
            video_id: "vid_syn_100",
            title: "Google GenAI SDK Tutorial (Part 5)",
            views: 23314,
            ctr_percentage: 4.8,
            average_retention: 54.8,
            subscribers_gained: 303,
            content_pillar: "Gemini & Vertex AI",
          },
          {
            video_id: "vid_syn_99",
            title: "LangGraph Multi-Agent Architecture",
            views: 18400,
            ctr_percentage: 6.2,
            average_retention: 61.2,
            subscribers_gained: 240,
            content_pillar: "Agent Architecture",
          },
          {
            video_id: "vid_syn_98",
            title: "FastAPI + WebSockets Production Guide",
            views: 15200,
            ctr_percentage: 5.1,
            average_retention: 52.0,
            subscribers_gained: 180,
            content_pillar: "Backend Systems",
          },
          {
            video_id: "vid_syn_97",
            title: "Llama 3 Fine-Tuning on Custom Dataset",
            views: 29800,
            ctr_percentage: 7.4,
            average_retention: 58.5,
            subscribers_gained: 410,
            content_pillar: "Open Source LLMs",
          },
          {
            video_id: "vid_syn_96",
            title: "Vite + React 19 Performance Secrets",
            views: 12100,
            ctr_percentage: 3.9,
            average_retention: 46.2,
            subscribers_gained: 95,
            content_pillar: "Frontend Engineering",
          },
        ],
        topic_clusters: [],
        traffic_sources: [
          { source: "suggested_videos", views: 15200, percentage: 36.1 },
          { source: "youtube_search", views: 13100, percentage: 31.1 },
          { source: "browse_features", views: 9800, percentage: 23.3 },
          { source: "external", views: 2400, percentage: 5.7 },
          { source: "direct_or_other", views: 1600, percentage: 3.8 },
        ],
        insights: [
          {
            insight_id: "insight-1",
            channel_id: "croviq_syn_ai_eng_01",
            type: "RETENTION",
            title: "First demonstration timing tracks retention",
            statement:
              "Across 100 videos, first-demo timing and average retention have a negative correlation.",
            evidence: [
              {
                kind: "FACT",
                statement: "Pearson correlation calculated across 100 videos.",
                metric_refs: ["video:firstDemoSeconds"],
                citation_urls: [],
              },
            ],
            confidence: 0.9,
            recommended_action: "Test the first practical demonstration before 00:30.",
            created_at: "2026-08-26T00:00:00Z",
            expires_at: null,
          },
        ],
        active_experiment: null,
        proposed_experiment: {
          experiment_id: "experiment-1",
          channel_id: "croviq_syn_ai_eng_01",
          hypothesis:
            "Showing the first practical demonstration before 00:30 improves average retention.",
          primary_metric: "averageViewPercentage",
          baseline_value: 59.01,
          expected_direction: "INCREASE",
          status: "PROPOSED",
          started_at: null,
          completed_at: null,
          video_ids: [],
          result: null,
          effect_size: null,
          confidence_summary:
            "Proposed from a historical correlation; causality is not established.",
          created_by: "alex",
        },
        is_sample_modeled_timeseries: true,
      }),
    });
  });

  await page.route("**/api/workspace/agent-settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        alex_prompt: {
          agent_id: "alex",
          prompt_text: "You are Alex. Separate facts, inferences, research, and recommendations.",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "Leo",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        maya_prompt: {
          agent_id: "maya",
          prompt_text: "Maya",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        voice_settings: {
          narration_mode: "original",
          selected_voice: "Puck",
          language: "en-US",
          updated_at: "2026-08-28T00:00:00Z",
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
        channel_title: "AI Engineering & Agent Systems",
        style_guide: "Evidence-backed technical tutorials",
        creator_preferences: [],
        lessons: [
          {
            topic: "Retention",
            content: "Earlier practical demonstrations correlate with stronger retention.",
            learned_from: "100-video sample analysis",
          },
        ],
      }),
    });
  });
  await page.route("**/api/channels/research/config", async (route) => {
    if (route.request().method() === "PUT") {
      Object.assign(researchConfig, JSON.parse(route.request().postData() ?? "{}"), {
        updated_at: "2026-08-28T00:05:00Z",
      });
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(researchConfig),
    });
  });
  await page.route("**/api/channels/youtube/connection", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        connected: false,
        channel_id: null,
        channel_title: null,
        avatar_url: null,
        subscriber_count: null,
        last_sync_at: null,
        has_monetary_access: false,
      }),
    });
  });

  await page.route("**/api/channels/research/findings*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          finding_id: "fnd_gemini_37_01",
          run_id: "run_test_01",
          channel_id: "croviq_syn_ai_eng_01",
          category: "Foundation Models",
          title: "Gemini 3.7 Flash Hybrid Reasoning and Multimodal Agent Capabilities",
          summary:
            "Google released Gemini 3.7 Flash featuring dynamic thinking budgets and tool grounding.",
          why_it_matters:
            "Your tutorial videos on LLM agent architectures historically outperform baseline by 28%.",
          relevance_score: 0.95,
          freshness_score: 0.96,
          opportunity_score: 0.95,
          source_citations: [
            {
              url: "https://ai.google.dev/gemini-api/docs",
              title: "Google AI Documentation",
              domain: "ai.google.dev",
              published_at: "2026-08-28T00:00:00Z",
              grounding_metadata: {},
            },
          ],
          topic_fingerprint: "fp_gemini_37",
          discovered_at: "2026-08-28T00:00:00Z",
          updated_at: "2026-08-28T00:00:00Z",
          lifecycle: "NEW",
        },
      ]),
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
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          productions,
          total: productions.length,
        }),
      });
    } else {
      await route.continue();
    }
  });

  await page.route("**/api/productions/**", async (route) => {
    if (route.request().method() === "DELETE") {
      const url = route.request().url();
      const parts = url.split("/api/productions/");
      const prodId = parts[1]?.split("/")[0] || "prod_f0b41bfd429e";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "deleted",
          production_id: prodId,
          deleted_storage_objects_count: 2,
          deleted_at: new Date().toISOString(),
        }),
      });
      return;
    }
    if (route.request().method() === "GET") {
      const url = route.request().url();
      if (url.endsWith("/renders")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            production_id: "prod_test_001",
            renders: [],
          }),
        });
        return;
      }
      if (url.endsWith("/playback")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            production_id: "prod_test_001",
            playback_url: "http://localhost:8080/mock-storage/source.mp4",
            expires_at: new Date(Date.now() + 3600000).toISOString(),
          }),
        });
        return;
      }
      if (url.endsWith("/transcript") || url.endsWith("/editorial-run") || url.endsWith("/edl")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(null),
        });
        return;
      }
      if (
        url.endsWith("/transcribe") ||
        url.endsWith("/analyze") ||
        url.endsWith("/renders/preview")
      ) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "completed" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        body: JSON.stringify({
          production_id: "prod_test_001",
          workspace_id: "ws_demo",
          channel_id: "croviq_syn_ai_eng_01",
          owner_user_id: "demo_user_123",
          status: "uploaded",
          source_media: {
            upload_id: "upl_test_001",
            original_filename: "raw_tutorial.mp4",
            content_type: "video/mp4",
            size_bytes: 1048576,
            gcs_bucket: "croviq-506602-croviq-media-raw",
            gcs_object:
              "workspaces/ws_demo/productions/prod_test_001/source/upl_test_001/raw_tutorial.mp4",
            status: "uploaded",
            created_at: new Date().toISOString(),
            uploaded_at: new Date().toISOString(),
          },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }
    await route.continue();
  });
};

const login = async (page: Page, openNewProject = true) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("/app");
  if (openNewProject) {
    await page.getByRole("button", { name: "New Project" }).click();
    await page.waitForURL("/projects/new");
  }
};

test.describe("Product Home and Creator Flow", () => {
  test("renders clean creator-facing Product Home with minimal header and no debug/engineering clutter", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page, false);

    await expect(page.getByRole("banner").getByRole("img", { name: "Croviq" })).toBeVisible();
    await expect(page.getByText(DEMO_EMAIL)).toBeVisible();
    await expect(page.getByRole("button", { name: "Logout" })).toBeVisible();
    await expect(page.getByRole("button", { name: "New Project" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Modern AI Engineering" })).toBeVisible();
    await expect(page.getByText("Sample channel", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("51,317 subscribers · 100 videos")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Here's what changed" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Channel Performance" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Alex" })).toBeVisible();
    await expect(page.getByText("Worth watching")).toBeVisible();
    await expect(page.getByText("Since your last upload")).toBeVisible();
    await expect(page.getByText("Active Hypothesis & Experiment")).toBeVisible();
    // DOM Regression Guards (Negative Assertions)
    await expect(page.getByText("Alex Briefing")).toHaveCount(0);
    await expect(page.getByText("Evidence-backed channel intelligence")).toHaveCount(0);
    await expect(page.getByText("Grounded")).toHaveCount(0);
    await expect(page.getByText("thumbnail_ctr")).toHaveCount(0);
    await expect(page.getByText("Alex memory")).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "Sidebar navigation" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Upload raw footage" })).toHaveCount(0);
    await expect(page.getByText("Owner User ID")).toHaveCount(0);
    await expect(page.getByText("Git SHA")).toHaveCount(0);

    // Verify Alex rail default view does not show raw FACT / INFERENCE tags
    const alexRail = page.getByRole("complementary");
    await expect(alexRail.getByText("FACT")).toHaveCount(0);
    await expect(alexRail.getByText("INFERENCE")).toHaveCount(0);

    // Verify progressive disclosure: View Evidence opens modal with FACT/INFERENCE
    await page.getByRole("button", { name: "View evidence" }).first().click();
    const evidenceModal = page
      .getByRole("dialog", { name: "Evidence Analysis" })
      .or(page.locator("div.fixed.inset-0"));
    await expect(evidenceModal).toBeVisible();
    await expect(page.getByText("Supporting Evidence")).toBeVisible();
    await page.getByRole("button", { name: "Close" }).last().click();
    await expect(page.getByText("Supporting Evidence")).toHaveCount(0);
    await page.waitForTimeout(300);

    // Capture Evidence Screenshots at 1600x900, 1440x900, and 1280x800 (Top and Scrolled)
    await page.setViewportSize({ width: 1600, height: 900 });
    await page.screenshot({ path: "e2e/screenshots/channel-intelligence-1600x900-top.png" });
    await page.evaluate(() => window.scrollTo(0, 450));
    await page.waitForTimeout(200);
    await page.screenshot({ path: "e2e/screenshots/channel-intelligence-1600x900-scrolled.png" });

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.screenshot({
      path: "e2e/screenshots/channel-intelligence-after-rework-1440x900.png",
    });
    await page.screenshot({ path: "e2e/screenshots/channel-intelligence-1440x900.png" });
    await page.screenshot({ path: "e2e/screenshots/production-home-top-1440x900.png" });
    await page.evaluate(() => window.scrollTo(0, 450));
    await page.waitForTimeout(200);
    await page.screenshot({ path: "e2e/screenshots/production-home-scrolled-1440x900.png" });

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: "e2e/screenshots/channel-intelligence-fullpage.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.screenshot({
      path: "e2e/screenshots/channel-intelligence-after-rework-1280x800.png",
    });
    await page.screenshot({ path: "e2e/screenshots/channel-intelligence-1280x800.png" });
    await page.screenshot({ path: "e2e/screenshots/production-home-top-1280x800.png" });
    await page.evaluate(() => window.scrollTo(0, 450));
    await page.waitForTimeout(200);
    await page.screenshot({ path: "e2e/screenshots/production-home-scrolled-1280x800.png" });

    expect(consoleErrors).toEqual([]);
  });

  test("persists Alex research schedule and custom public sources", async ({ page }) => {
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page, false);

    await page.getByRole("button", { name: "Open Alex settings" }).click();
    await expect(page.getByRole("dialog", { name: "Alex settings" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Tools" })).toHaveCount(0);
    await page.getByRole("button", { name: "research", exact: true }).click();
    await page.getByLabel("Schedule").selectOption("EVERY_6_HOURS");
    await page.getByPlaceholder("domain or full public URL").fill("ai.google.dev");
    await page.getByRole("button", { name: "Add preferred source" }).click();
    await page.getByRole("button", { name: "Save research settings" }).click();
    await expect(page.getByText("Research schedule saved")).toBeVisible();
    await page.getByRole("button", { name: "Close Alex settings" }).click();

    await page.getByRole("button", { name: "Open Alex settings" }).click();
    await page.getByRole("button", { name: "research", exact: true }).click();
    await expect(page.getByLabel("Schedule")).toHaveValue("EVERY_6_HOURS");
    await expect(page.getByRole("button", { name: /ai\.google\.dev/ })).toBeVisible();
  });

  test("allows creator to connect and switch to real YouTube channel", async ({ page }) => {
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);

    await page.route("**/api/channels/youtube/auth-url", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          auth_url: "https://accounts.google.com/o/oauth2/v2/auth?client_id=test",
          state_token: "test_state_12345",
          scopes: [
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
          ],
        }),
      });
    });

    await page.route("**/api/channels/youtube/callback", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          connected: true,
          channel_id: "UC_alex_real_01",
          channel_title: "Alex River Engineering",
          avatar_url: "",
          subscriber_count: 52300,
          last_sync_at: "2026-08-28T00:00:00Z",
          has_monetary_access: false,
        }),
      });
    });

    await login(page, false);

    await page.getByRole("button", { name: "Select channel" }).click();
    await page.getByRole("button", { name: "Connect YouTube Channel" }).click();
    await expect(page.getByRole("heading", { name: "Connect YouTube Channel" })).toBeVisible();
    await page.getByRole("button", { name: "Authorize Channel" }).click();

    await expect(page.getByText("Connected YouTube")).toBeVisible();
  });

  test("verifies New Project route is focused on raw footage upload without Recent Productions clutter", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const txt = msg.text();
        if (
          !txt.includes("401") &&
          !txt.includes("502") &&
          !txt.includes("Failed to load resource")
        ) {
          consoleErrors.push(txt);
        }
      }
    });

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page, true);

    // Verify New Project Shell
    await expect(page.getByRole("banner").getByRole("img", { name: "Croviq" })).toBeVisible();
    await expect(page.getByRole("banner").getByText("New Project")).toBeVisible();
    await expect(page.getByText("Croviq Sample Channel")).toBeVisible();

    // Verify focused upload card & recent projects
    await expect(page.getByRole("heading", { name: "New Project" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent projects" })).toBeVisible();
    await expect(page.getByText("Start from raw footage")).toBeVisible();

    // Regressions: old giant floating pill MUST be absent
    await expect(page.getByText("Recent Productions", { exact: true })).toHaveCount(0);
    expect(consoleErrors).toEqual([]);
  });

  test("executes end-to-end direct storage upload and records production", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const txt = msg.text();
        if (
          !txt.includes("401") &&
          !txt.includes("404") &&
          !txt.includes("502") &&
          !txt.includes("Failed to load resource")
        ) {
          consoleErrors.push(txt);
        }
      }
    });

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);

    // Mock upload initiation endpoint
    await page.route("**/api/productions/upload", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: "prod_test_001",
          upload_id: "upl_test_001",
          upload_url: "http://localhost:8080/mock-storage/test.mp4?signed=1",
          method: "PUT",
          required_headers: { "Content-Type": "video/mp4" },
          expires_at: new Date(Date.now() + 1800000).toISOString(),
        }),
      });
    });

    // Mock direct-to-storage PUT
    await page.route("http://localhost:8080/mock-storage/**", async (route) => {
      await route.fulfill({
        status: 200,
        body: "",
      });
    });

    // Mock verify-upload endpoint
    await page.route("**/api/productions/prod_test_001/verify-upload", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "uploaded",
          production_id: "prod_test_001",
        }),
      });
    });

    await login(page, true);

    // Select a video file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "raw_tutorial.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.from("mock-video-bytes-for-test"),
    });

    // File selected state
    await expect(page.getByText("raw_tutorial.mp4")).toBeVisible();
    const startBtn = page.getByRole("button", { name: "Start production" });
    await expect(startBtn).toBeVisible();

    // Click upload
    await startBtn.click();

    // Upload completion takes the creator straight into the production Editor.
    await expect(page).toHaveURL(/\/productions\/prod_test_001\/editor/, { timeout: 6000 });
    expect(consoleErrors).toEqual([]);
  });
  test("renders responsive Product Home at mobile viewport (390px)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page, false);

    await expect(page.getByRole("banner").getByRole("img", { name: "Croviq" })).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/studio-cockpit-390px.png", fullPage: true });
  });
  test("rejects invalid media format with clear error", async ({ page }) => {
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page);

    const fileInput = page.locator("input[type='file']");
    await fileInput.setInputFiles({
      name: "document.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("pdf-data"),
    });

    await expect(
      page.getByText("Please select a valid video file (.mp4, .mov, .webm, or .mkv)"),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Start production" })).toHaveCount(0);
  });

  test("verifies New Project shares app shell and removes Recent Productions", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page, []);
    await login(page);

    // 1. Header is continuous with /app
    await expect(page.getByRole("banner").getByRole("img", { name: "Croviq" })).toBeVisible();
    await expect(page.getByRole("banner").getByText("New Project")).toBeVisible();
    await expect(page.getByText("Croviq Sample Channel")).toBeVisible();

    // 2. Focused Upload Card & Recent Projects
    await expect(page.getByRole("heading", { name: "New Project" })).toBeVisible();
    await expect(page.getByText("Start from raw footage")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent projects" })).toBeVisible();

    // 3. Regressions: old floating pill MUST be absent
    await expect(page.getByText("Recent Productions", { exact: true })).toHaveCount(0);
    await page.screenshot({ path: "e2e/screenshots/new-project-1440x900.png" });
  });
});
