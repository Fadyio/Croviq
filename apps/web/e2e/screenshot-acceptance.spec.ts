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

test.describe("Visual Screenshot Acceptance", () => {
  test("overview-1600x900.png", async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("valid-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/app*");

    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("Here's what changed")).toBeVisible();
    await page.waitForTimeout(500);

    await page.screenshot({ path: "e2e/screenshots/overview-1600x900.png" });
  });

  test("overview-1440x900.png", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("valid-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/app*");

    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await page.waitForTimeout(500);

    await page.screenshot({ path: "e2e/screenshots/overview-1440x900.png" });
    await page.screenshot({ path: "e2e/screenshots/home-1440x900.png" });
  });

  test("performance-1440x900.png", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("valid-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/app*");

    await page.goto("/app/performance");
    await expect(page.getByRole("heading", { name: "Video Performance" })).toBeVisible();
    await page.waitForTimeout(500);

    await page.screenshot({ path: "e2e/screenshots/performance-1440x900.png" });
  });

  test("experiments-1440x900.png", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("valid-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/app*");

    await page.goto("/app/experiments");
    await expect(page.getByRole("heading", { name: "Proposed Experiments" })).toBeVisible();
    await page.waitForTimeout(500);

    await page.screenshot({ path: "e2e/screenshots/experiments-1440x900.png" });
  });

  test("new-project-1440x900.png", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("valid-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/app*");

    await page.goto("/projects/new");
    await expect(page.getByRole("heading", { name: "New Project" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent projects" })).toBeVisible();
    await page.waitForTimeout(500);

    await page.screenshot({ path: "e2e/screenshots/new-project-1440x900.png" });
  });

  test("new-project-1280x800.png", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("valid-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/app*");

    await page.goto("/projects/new");
    await expect(page.getByRole("heading", { name: "New Project" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent projects" })).toBeVisible();
    await page.waitForTimeout(500);

    await page.screenshot({ path: "e2e/screenshots/new-project-1280x800.png" });
  });
});
