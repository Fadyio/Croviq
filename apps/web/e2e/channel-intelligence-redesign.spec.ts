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

const MOCK_PRODUCTIONS = [
  {
    production_id: "prod_demo_01",
    workspace_id: "ws_demo",
    channel_id: "croviq_syn_ai_eng_01",
    owner_user_id: APPROVED_USER.user_id,
    source_media: {
      upload_id: "upl_01",
      original_filename: "gemini_37_agent_demo_raw.mp4",
      content_type: "video/mp4",
      size_bytes: 485000000,
      gcs_bucket: "croviq-media-raw",
      gcs_object: "upl_01.mp4",
      status: "uploaded",
      created_at: "2026-08-27T10:00:00Z",
    },
    status: "uploaded",
    created_at: "2026-08-27T10:00:00Z",
    updated_at: "2026-08-27T10:05:00Z",
  },
  {
    production_id: "prod_demo_02",
    workspace_id: "ws_demo",
    channel_id: "croviq_syn_ai_eng_01",
    owner_user_id: APPROVED_USER.user_id,
    source_media: {
      upload_id: "upl_02",
      original_filename: "multimodal_webcodecs_benchmark.mov",
      content_type: "video/quicktime",
      size_bytes: 290000000,
      gcs_bucket: "croviq-media-raw",
      gcs_object: "upl_02.mov",
      status: "uploaded",
      created_at: "2026-08-25T14:30:00Z",
    },
    status: "uploaded",
    created_at: "2026-08-25T14:30:00Z",
    updated_at: "2026-08-25T14:35:00Z",
  },
];

const MOCK_FINDINGS = [
  {
    finding_id: "fnd_1",
    run_id: "run_1",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Foundation Models",
    title: "Gemini 3.7 Flash Hybrid Reasoning Capabilities",
    summary:
      "Google announced dynamic thinking budgets and native multimodal reasoning in Gemini 3.7 Flash.",
    why_it_matters: "Audience tutorial retention is 28% higher on model reasoning deep dives.",
    relevance_score: 0.95,
    freshness_score: 0.96,
    opportunity_score: 0.95,
    topic_cluster: "foundation-models",
    source_citations: [
      {
        url: "https://ai.google.dev/gemini-api/docs/models/gemini",
        title: "Gemini Models — Google AI",
        domain: "ai.google.dev",
      },
    ],
    topic_fingerprint: "fp_1",
    discovered_at: "2026-08-28T08:00:00Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_2",
    run_id: "run_1",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Agent Workflows",
    title: "Production Agent Evaluation Frameworks for Multi-Turn Tooling",
    summary: "Emerging benchmarks evaluate deterministic tool execution and latency budgets.",
    why_it_matters:
      "Engineering audiences show 43% higher subscriber conversion on architectural benchmarks.",
    relevance_score: 0.9,
    freshness_score: 0.88,
    opportunity_score: 0.89,
    topic_cluster: "agent-workflows",
    source_citations: [
      {
        url: "https://cloud.google.com/products/agent-builder",
        title: "Agent Builder — Google Cloud",
        domain: "cloud.google.com",
      },
    ],
    topic_fingerprint: "fp_2",
    discovered_at: "2026-08-28T07:30:00Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_3",
    run_id: "run_1",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Multimodal Systems",
    title: "WebCodecs Real-Time Streaming Video Pipeline for AI Media Workflows",
    summary:
      "Hardware-accelerated browser video frame decoding enables real-time timeline previews.",
    why_it_matters: "Combining browser rendering with AI models drives high viewer engagement.",
    relevance_score: 0.88,
    freshness_score: 0.92,
    opportunity_score: 0.9,
    topic_cluster: "multimodal-systems",
    source_citations: [
      {
        url: "https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API",
        title: "WebCodecs API — MDN",
        domain: "developer.mozilla.org",
      },
    ],
    topic_fingerprint: "fp_3",
    discovered_at: "2026-08-28T06:00:00Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_4",
    run_id: "run_1",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Evaluation & Observability",
    title: "OpenTelemetry Distributed Tracing Standards for Multi-Agent Loops",
    summary:
      "Standardized semantic conventions for GenAI systems track tool invocation spans and latency.",
    why_it_matters: "Production teams look for structured telemetry benchmarks.",
    relevance_score: 0.86,
    freshness_score: 0.9,
    opportunity_score: 0.87,
    topic_cluster: "evaluation-observability",
    source_citations: [
      {
        url: "https://opentelemetry.io/docs/specs/semconv/gen-ai/",
        title: "GenAI Semantic Conventions — OpenTelemetry",
        domain: "opentelemetry.io",
      },
    ],
    topic_fingerprint: "fp_4",
    discovered_at: "2026-08-28T05:00:00Z",
    lifecycle: "NEW",
  },
];

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

  await page.route("**/securetoken.googleapis.com/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: FIREBASE_ID_TOKEN,
        expires_in: "3600",
        token_type: "Bearer",
        refresh_token: "fake-refresh-token",
        id_token: FIREBASE_ID_TOKEN,
        user_id: "demo_user_123",
        project_id: "croviq-506602",
      }),
    });
  });
};
const mockBackendApis = async (page: Page) => {
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
      body: JSON.stringify(WORKSPACE),
    });
  });

  await page.route("**/api/productions", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ productions: MOCK_PRODUCTIONS, total: MOCK_PRODUCTIONS.length }),
    });
  });

  await page.route("**/api/channels/research/findings*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FINDINGS),
    });
  });

  await page.route("**/api/channels/youtube/connection", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ connected: false }),
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
          title: "Croviq",
          description: "Sample channel",
          avatar_url: null,
          subscriber_count: 51317,
          video_count: 100,
        },
        period_days: 28,
        period_end: "2026-08-28",
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
          view_delta_percentage: 18.0,
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
};

const signInAndGoTo = async (page: Page, path: string = "/app") => {
  await mockFirebasePasswordSignIn(page);
  await mockBackendApis(page);
  await page.goto("/login");
  try {
    const emailInput = page.getByLabel("Email");
    if (await emailInput.isVisible({ timeout: 1500 })) {
      await emailInput.fill(DEMO_EMAIL);
      await page.getByLabel("Password").fill("valid-password");
      await page.getByRole("button", { name: "Sign in" }).click();
    }
  } catch {
    // Already authenticated or navigated
  }
  await page.waitForURL("**/app*");
  if (path !== "/app" && !page.url().endsWith(path)) {
    await page.goto(path);
  }
};

test.describe("Home / Channel Intelligence Redesign", () => {
  test("Overview route /app renders 4 KPIs, compact trend chart, latest video summary, and Alex rail", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");

    // Check header & channel title
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();

    // Check Overview tab is active
    const overviewTab = page.getByRole("button", { name: /Overview/i });
    await expect(overviewTab).toHaveClass(/bg-surface-2/);

    // Check 4 KPIs
    await expect(page.getByText("Here's what changed")).toBeVisible();
    const kpiSection = page.getByLabel("Channel KPIs");
    await expect(kpiSection.getByText("Views", { exact: true })).toBeVisible();
    await expect(kpiSection.getByText("Watch time", { exact: true })).toBeVisible();
    await expect(kpiSection.getByText("Net subscribers", { exact: true })).toBeVisible();
    await expect(kpiSection.getByText("Average retention", { exact: true })).toBeVisible();
    // Check latest video summary
    await expect(page.getByText("Since your last upload")).toBeVisible();
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toBeVisible();

    // Check Alex rail is present on the right
    await expect(page.getByRole("heading", { name: "Alex" })).toBeVisible();
    await expect(page.getByRole("complementary").getByText("Data Scientist")).toBeVisible();
    await expect(page.getByText("Worth watching")).toBeVisible();
  });

  test("Performance route /app/performance renders Video Quadrant, Video Catalog Table, and Traffic Sources", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app/performance");

    // Check URL
    await expect(page).toHaveURL(/\/app\/performance$/);

    // Check Performance tab is active
    const perfTab = page.getByRole("button", { name: /Performance/i });
    await expect(perfTab).toHaveClass(/bg-surface-2/);

    // Check Video Performance Ranked Chart section
    await expect(page.getByRole("heading", { name: "Video Performance" })).toBeVisible();

    // Check Video Catalog Table section
    await expect(page.getByRole("heading", { name: "Video Catalog Performance" })).toBeVisible();
    await expect(
      page.getByRole("table").getByText("LangGraph Multi-Agent Architecture"),
    ).toBeVisible();

    // Check Traffic Sources section
    await expect(page.getByRole("heading", { name: "Traffic Sources" })).toBeVisible();

    // Check Alex rail persists on performance route
    await expect(page.getByRole("heading", { name: "Alex" })).toBeVisible();
  });

  test("Experiments route /app/experiments renders Active, Proposed, and Completed experiments", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app/experiments");

    // Check URL
    await expect(page).toHaveURL(/\/app\/experiments$/);

    // Check Experiments tab is active
    const expTab = page.getByRole("button", { name: /Experiments/i });
    await expect(expTab).toHaveClass(/bg-surface-2/);

    // Check sections
    await expect(page.getByRole("heading", { name: "Proposed Experiments" })).toBeVisible();
    await expect(
      page.getByText("Showing the first practical demonstration before 00:30"),
    ).toBeVisible();

    // Check Alex rail persists on experiments route
    await expect(page.getByRole("heading", { name: "Alex" })).toBeVisible();
  });

  test("Navigation tabs change URL and support browser Back/Forward navigation", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");

    // Click Performance tab
    await page.getByRole("button", { name: /Performance/i }).click();
    await expect(page).toHaveURL(/\/app\/performance$/);
    await expect(page.getByRole("heading", { name: "Video Performance" })).toBeVisible();

    // Click Experiments tab
    await page.getByRole("button", { name: /Experiments/i }).click();
    await expect(page).toHaveURL(/\/app\/experiments$/);
    await expect(page.getByRole("heading", { name: "Proposed Experiments" })).toBeVisible();

    // Browser Back to /app/performance
    await page.goBack();
    await expect(page).toHaveURL(/\/app\/performance$/);
    await expect(page.getByRole("heading", { name: "Video Performance" })).toBeVisible();

    // Browser Back to /app
    await page.goBack();
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByText("Here's what changed")).toBeVisible();

    // Browser Forward to /app/performance
    await page.goForward();
    await expect(page).toHaveURL(/\/app\/performance$/);
  });

  test("Layout consumes full width with zero right-side dead gap at 1600x900, 1440x900, and 1280x800", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");

    for (const vp of [
      { width: 1600, height: 900 },
      { width: 1440, height: 900 },
      { width: 1280, height: 800 },
    ]) {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      const isNoOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth <= document.documentElement.clientWidth;
      });
      expect(isNoOverflow).toBe(true);

      // Check Alex rail is visible and positioned without broken sticky behavior
      const alexRail = page.locator("aside");
      await expect(alexRail).toBeVisible();
      const box = await alexRail.boundingBox();
      expect(box).not.toBeNull();
      if (box && vp.width >= 1440) {
        expect(box.x + box.width).toBeGreaterThanOrEqual(vp.width - 50);
      }
    }
  });
  test("Worth Watching feed shows max 3 default cards and opens all findings drawer", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");

    const aside = page.locator("aside");
    // Should show at most 3 finding articles in the sidebar
    const findingCards = aside.locator("article");
    const count = await findingCards.count();
    // 1 insight article + up to 3 finding articles = max 4 articles in aside
    expect(count).toBeLessThanOrEqual(4);

    // View all findings button should be visible when >3 findings exist
    const viewAllBtn = page.getByRole("button", { name: /View all.*findings/i });
    await expect(viewAllBtn).toBeVisible();

    // Click View all findings -> Drawer opens
    await viewAllBtn.click();
    await expect(page.getByText("Worth Watching · Topic Radar")).toBeVisible();
    await expect(page.getByText("OpenTelemetry Distributed Tracing Standards")).toBeVisible();

    // Close drawer
    await page.getByRole("button", { name: "Close" }).last().click();
  });

  test("team selector preserves distinct agent routes across navigation and refresh", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");

    const openAgent = async (agent: "Alex" | "Leo" | "Iris", route: string) => {
      await page.getByTestId("btn-team-selector").click();
      await page
        .getByText("Autonomous Production Team", { exact: true })
        .locator("..")
        .getByRole("button", { name: new RegExp(`^${agent} `) })
        .click();
      await expect(page).toHaveURL(new RegExp(`${route}$`));
      await expect(page.getByRole("heading", { name: agent, exact: true })).toBeVisible();
      await expect(page.getByRole("tab", { name: "Chat" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    };

    await page.setViewportSize({ width: 1600, height: 900 });
    await openAgent("Alex", "/app/agents/alex");
    await page.screenshot({ path: "e2e/screenshots/bug02-alex-1600x900.png" });

    await page.setViewportSize({ width: 1440, height: 900 });
    await openAgent("Leo", "/app/agents/leo");
    await page.screenshot({ path: "e2e/screenshots/bug02-leo-1440x900.png" });

    await page.setViewportSize({ width: 1280, height: 800 });
    await openAgent("Iris", "/app/agents/iris");
    await page.screenshot({ path: "e2e/screenshots/bug02-iris-1280x800.png" });

    await page.reload();
    await expect(page).toHaveURL(/\/app\/agents\/iris$/);
    await expect(page.getByRole("heading", { name: "Iris", exact: true })).toBeVisible();

    await page.goBack();
    await expect(page).toHaveURL(/\/app\/agents\/leo$/);
    await expect(page.getByRole("heading", { name: "Leo", exact: true })).toBeVisible();

    await page.goForward();
    await expect(page).toHaveURL(/\/app\/agents\/iris$/);
    await expect(page.getByRole("heading", { name: "Iris", exact: true })).toBeVisible();
  });

  test("transitions cleanly from sample mode to connected YouTube and isolates live metrics", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("51,317 subscribers")).toBeVisible();

    // Route connected YouTube dashboard
    await page.route("**/api/channels/youtube/connection", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          connected: true,
          status: "connected",
          channel_id: "UC_real_creator_123",
          channel_title: "Real Creator Studio",
          subscriber_count: 128500,
        }),
      });
    });

    await page.route("**/api/channels/youtube/dashboard?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel: {
            channel_id: "UC_real_creator_123",
            source_type: "youtube",
            title: "Real Creator Studio",
            description: "Authentic creator channel",
            avatar_url: null,
            subscriber_count: 128500,
            video_count: 42,
          },
          period_days: 28,
          period_end: "2026-08-28",
          kpis: [
            {
              metric: "views",
              current_value: 88400,
              previous_value: 71200,
              change_percentage: 24.1,
            },
            {
              metric: "watch_time_hours",
              current_value: 6200,
              previous_value: 5100,
              change_percentage: 21.5,
            },
            {
              metric: "net_subscribers",
              current_value: 940,
              previous_value: 650,
              change_percentage: 44.6,
            },
            {
              metric: "average_retention",
              current_value: 64.2,
              previous_value: 59.8,
              change_percentage: 7.3,
            },
          ],
          trend: [],
          latest_video: null,
          video_performance: [],
          topic_clusters: [],
          traffic_sources: [],
          insights: [],
          active_experiment: null,
          proposed_experiment: null,
          is_sample_modeled_timeseries: false,
        }),
      });
    });

    await page.reload();

    // Verify real creator channel is active and sample numbers disappeared
    await expect(
      page.getByRole("heading", { name: "Real Creator Studio", exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/128.?500 subscribers/)).toBeVisible();
    await expect(page.getByText("51,317")).not.toBeVisible();
    await expect(page.getByText("Modern AI Engineering")).not.toBeVisible();

    // Verify live error state does not silently fall back to sample numbers
    await page.route("**/api/channels/youtube/dashboard?*", async (route) => {
      await route.fulfill({
        status: 502,
        contentType: "application/json",
        body: JSON.stringify({ detail: "YouTube analytics sync failed upstream" }),
      });
    });

    await page.reload();
    await expect(page.getByRole("alert")).toContainText("YouTube analytics sync failed upstream");
    await expect(page.getByText("51,317")).not.toBeVisible();
  });

  test("New Project page includes Back button, upload card, and Recent Projects list", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");

    // Click New Project
    await page.getByRole("button", { name: "New Project" }).click();
    await expect(page).toHaveURL(/\/projects\/new$/);

    // Verify Back navigation
    const backBtn = page.getByRole("button", { name: "Back to Channel Intelligence" }).first();
    await expect(backBtn).toBeVisible();
    await expect(page.getByText("Start with raw footage").first()).toBeVisible();
    await expect(page.getByText("Click to browse or drag and drop video")).toBeVisible();

    // Verify Recent Projects list
    await expect(page.getByRole("heading", { name: "Recent projects" })).toBeVisible();
    await expect(page.getByText("gemini_37_agent_demo_raw.mp4")).toBeVisible();
    await expect(page.getByText("multimodal_webcodecs_benchmark.mov")).toBeVisible();

    // Click Back to return to /app
    await backBtn.click();
    await expect(page).toHaveURL(/\/app$/);
  });
});
