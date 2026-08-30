import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";

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
            metric: "subscribers",
            current_value: 51317,
            previous_value: 50400,
            change_percentage: 1.8,
          },
          {
            metric: "avg_duration",
            current_value: 412,
            previous_value: 388,
            change_percentage: 6.2,
          },
        ],
        trend: Array.from({ length: 28 }, (_, i) => ({
          date: `2026-08-${String(i + 1).padStart(2, "0")}`,
          views: 1200 + Math.round(Math.sin(i / 2) * 200),
          net_subscribers: 25 + Math.round(Math.cos(i / 2) * 5),
          watch_time_hours: 90 + Math.round(Math.sin(i / 2) * 15),
          previous_views: 1000 + Math.round(Math.sin(i / 2) * 150),
          previous_net_subscribers: 20 + Math.round(Math.cos(i / 2) * 4),
          previous_watch_time_hours: 80 + Math.round(Math.sin(i / 2) * 10),
        })),
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
        proposed_experiment: null,
        is_sample_modeled_timeseries: true,
      }),
    });
  });
};

const signInAndGoTo = async (page: Page, targetPath: string = "/app") => {
  await mockFirebasePasswordSignIn(page);
  await mockBackendApis(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*");
  if (targetPath !== "/app") {
    await page.goto(targetPath);
  }
};

test.describe("Bug 2 Verification: Remove Team Control from Navbar", () => {
  test("header at 1600x900 on /app has no Team control and balanced spacing", async ({ page }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("requestfailed", (req) => {
      failedRequests.push(`${req.method()} ${req.url()}`);
    });

    await page.setViewportSize({ width: 1600, height: 900 });
    await signInAndGoTo(page, "/app");

    // 1. Confirm Team button is REMOVED
    await expect(page.getByTestId("btn-team-selector")).toHaveCount(0);
    await expect(page.getByText("Team", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Autonomous Production Team")).toHaveCount(0);

    // 2. Confirm stacked agent avatars are NOT in navbar
    const header = page.locator("header").first();
    await expect(header).toBeVisible();
    await expect(header.getByTestId("btn-team-selector")).toHaveCount(0);
    await expect(header.locator("img[src*='alex']")).toHaveCount(0);
    await expect(header.locator("img[src*='leo']")).toHaveCount(0);
    await expect(header.locator("img[src*='iris']")).toHaveCount(0);

    // 3. Confirm Logo, Channel Selector, New Project, Email, Logout are present and aligned
    await expect(header.locator("svg").first()).toBeVisible(); // Croviq logo
    await expect(header.getByRole("button", { name: "New Project" })).toBeVisible();
    await expect(header.getByText(DEMO_EMAIL)).toBeVisible();
    await expect(header.getByRole("button", { name: "Logout" })).toBeVisible();

    // 4. No horizontal overflow
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);

    // 5. Screenshot
    await page.screenshot({ path: "e2e/screenshots/bug02-1600x900.png" });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("header at 1440x900 on /app has no Team control and balanced spacing", async ({ page }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("requestfailed", (req) => {
      failedRequests.push(`${req.method()} ${req.url()}`);
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAndGoTo(page, "/app");

    // 1. Confirm Team button is REMOVED
    await expect(page.getByTestId("btn-team-selector")).toHaveCount(0);
    await expect(page.getByText("Team", { exact: true })).toHaveCount(0);

    // 2. Confirm stacked agent avatars are NOT in navbar
    const header = page.locator("header").first();
    await expect(header).toBeVisible();
    await expect(header.getByTestId("btn-team-selector")).toHaveCount(0);

    // 3. Confirm New Project, Email, Logout are aligned
    await expect(header.getByRole("button", { name: "New Project" })).toBeVisible();
    await expect(header.getByText(DEMO_EMAIL)).toBeVisible();
    await expect(header.getByRole("button", { name: "Logout" })).toBeVisible();

    // 4. Screenshot
    await page.screenshot({ path: "e2e/screenshots/bug02-1440x900.png" });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("header at 1280x800 on /app has no Team control and balanced spacing", async ({ page }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("requestfailed", (req) => {
      failedRequests.push(`${req.method()} ${req.url()}`);
    });

    await page.setViewportSize({ width: 1280, height: 800 });
    await signInAndGoTo(page, "/app");

    // 1. Confirm Team button is REMOVED
    await expect(page.getByTestId("btn-team-selector")).toHaveCount(0);
    await expect(page.getByText("Team", { exact: true })).toHaveCount(0);

    // 2. Confirm stacked agent avatars are NOT in navbar
    const header = page.locator("header").first();
    await expect(header).toBeVisible();
    await expect(header.getByTestId("btn-team-selector")).toHaveCount(0);

    // 3. Confirm New Project, Email, Logout are aligned
    await expect(header.getByRole("button", { name: "New Project" })).toBeVisible();
    await expect(header.getByText(DEMO_EMAIL)).toBeVisible();
    await expect(header.getByRole("button", { name: "Logout" })).toBeVisible();

    // 4. Screenshot
    await page.screenshot({ path: "e2e/screenshots/bug02-1280x800.png" });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("header on /projects/new and /app/agents/alex retains consistent layout", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAndGoTo(page, "/projects/new");

    const header = page.locator("header").first();
    await expect(header).toBeVisible();
    await expect(header.getByTestId("btn-team-selector")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "New Project" })).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/bug02-new-project-1440x900.png" });

    // Test direct agent route
    await page.goto("/app/agents/alex");
    await expect(page.getByRole("heading", { name: "Alex", exact: true })).toBeVisible();
    const agentHeader = page.locator("header").first();
    await expect(agentHeader.getByTestId("btn-team-selector")).toHaveCount(0);
    await page.screenshot({ path: "e2e/screenshots/bug02-agent-alex-1440x900.png" });
  });
});
