import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";
import * as fs from "fs";

const setupPageRoutes = async (page: Page) => {
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
          localId: APPROVED_USER.user_id,
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
              localId: APPROVED_USER.user_id,
              email: DEMO_EMAIL,
              emailVerified: true,
              displayName: APPROVED_USER.display_name,
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
        access_token: "fake-access-token",
        expires_in: "3600",
        token_type: "Bearer",
        refresh_token: "fake-refresh-token",
        id_token: FIREBASE_ID_TOKEN,
        user_id: APPROVED_USER.user_id,
        project_id: "croviq-506602",
      }),
    });
  });

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(APPROVED_USER),
    });
  });

  await page.route("**/api/workspaces/current", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(WORKSPACE),
    });
  });

  await page.route("**/api/channels/research/findings*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });

  await page.route("**/api/channels/research/config*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workspace_id: "ws_demo",
        channel_id: "croviq_syn_ai_eng_01",
        enabled: true,
        cadence: "EVERY_HOUR",
        prompts: [],
      }),
    });
  });
};

const loginAndNavigateToApp = async (page: Page) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*");
};

const SAMPLE_DASHBOARD = {
  channel: {
    channel_id: "croviq_syn_ai_eng_01",
    source_type: "synthetic",
    title: "Croviq",
    description:
      "Deep-dive technical tutorials, architecture walkthroughs, and production benchmarks for AI engineers.",
    custom_url: "@croviq",
    subscriber_count: 51317,
    video_count: 100,
    total_views: 3501567,
    avatar_url: null,
  },
  period_days: 28,
  start_date: "2026-08-01",
  end_date: "2026-08-28",
  kpis: [
    {
      metric: "views",
      label: "Views",
      current_value: 389420,
      previous_value: 342100,
      change_percentage: 13.8,
    },
    {
      metric: "watch_time_hours",
      label: "Watch time",
      current_value: 48920.0,
      previous_value: 43200.0,
      change_percentage: 13.2,
    },
    {
      metric: "net_subscribers",
      label: "Net subscribers",
      current_value: 5120,
      previous_value: 4300,
      change_percentage: 19.1,
    },
    {
      metric: "average_retention",
      label: "Average retention",
      current_value: 54.8,
      previous_value: 52.0,
      change_percentage: 2.8,
    },
  ],
  latest_video: {
    channel_id: "croviq_syn_ai_eng_01",
    video_id: "vid_sample_01",
    title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
    published_at: "2026-08-26T14:00:00Z",
    views: 45200,
    watch_time_hours: 320.0,
    subscribers_gained: 340,
    subscribers_lost: 37,
    net_subscribers: 303,
    view_delta_percentage: 18.0,
    subscriber_conversion_delta_percentage: -2.84,
    retention_percentage: 54.8,
    retention_delta_points: -25.61,
    views_percentile: 50.0,
    retention_percentile: 50.0,
    ctr_percentile: 10.1,
    subscriber_conversion_per_1k_views: 6.7,
    comparison_window: "lifetime catalog baseline",
    baseline_sample_size: 99,
    median_views: 38300.0,
    median_retention: 58.4,
    median_ctr: 7.8,
    ctr: 7.9,
    retention: 54.8,
    subscriber_gain: 340,
  },
  recent_videos: [
    {
      video_id: "vid_sample_01",
      title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
      published_at: "2026-08-26T14:00:00Z",
      views: 45200,
      views_delta_percentage: 18.0,
      average_retention: 54.8,
      retention_delta_points: -25.61,
      ctr_percentage: 7.9,
      ctr_delta_points: 0.1,
      subscribers_gained: 340,
      subscribers_lost: 37,
      net_subscribers: 303,
      subs_per_1k: 6.7,
      subs_per_1k_delta_percentage: -2.84,
      is_latest: true,
      alex_interpretation: null,
      alex_next_action: null,
    },
  ],
  trend: [],
  insights: [],
};

const LIVE_DASHBOARD = {
  channel: {
    channel_id: "UC_live_creator_channel_99",
    source_type: "youtube",
    title: "Alex Tech Engineering",
    description: "Authentic YouTube Channel Data",
    custom_url: "@alextecheng",
    subscriber_count: 84200,
    video_count: 42,
    total_views: 1250000,
    avatar_url: null,
  },
  period_days: 28,
  start_date: "2026-08-01",
  end_date: "2026-08-28",
  kpis: [
    {
      metric: "views",
      label: "Views",
      current_value: 124500,
      previous_value: 110000,
      delta_percentage: 13.2,
      delta_percentage_points: null,
      unit: "count",
      status: "POSITIVE",
      display_order: 1,
    },
    {
      metric: "watch_time_hours",
      label: "Watch time",
      current_value: 15400.0,
      previous_value: 14000.0,
      delta_percentage: 10.0,
      delta_percentage_points: null,
      unit: "hours",
      status: "POSITIVE",
      display_order: 2,
    },
    {
      metric: "net_subscribers",
      label: "Net subscribers",
      current_value: 1420,
      previous_value: 1200,
      delta_percentage: 18.3,
      delta_percentage_points: null,
      unit: "count",
      status: "POSITIVE",
      display_order: 3,
    },
    {
      metric: "average_retention",
      label: "Average retention",
      current_value: 51.2,
      previous_value: 48.0,
      delta_percentage: 6.7,
      delta_percentage_points: 3.2,
      unit: "percentage",
      status: "POSITIVE",
      display_order: 4,
    },
  ],
  recent_videos: [
    {
      video_id: "vid_live_01",
      title: "Building Production Multi-Agent Systems on Cloud Run (Live Take)",
      published_at: "2026-08-27T10:00:00Z",
      views: 14200,
      watch_time_minutes: 89000.0,
      average_retention: 54.1,
      subscribers_gained: 180,
      subscribers_lost: 8,
      net_subscribers: 172,
      likes: 850,
      comments: 64,
      shares: 42,
      ctr_percentage: 7.9,
      subs_per_1k: 12.1,
      retention_delta_pts: null,
      ctr_delta_pts: null,
      subs_delta_pct: null,
      views_delta_percentage: null,
      retention_delta_points: null,
      subs_per_1k_delta_percentage: null,
      is_latest: true,
      alex_interpretation: null,
      alex_next_action: null,
    },
  ],
  latest_video: {
    channel_id: "UC_live_creator_channel_99",
    video_id: "vid_live_01",
    title: "Building Production Multi-Agent Systems on Cloud Run (Live Take)",
    published_at: "2026-08-27T10:00:00Z",
    views: 14200,
    watch_time_hours: 1483.3,
    subscribers_gained: 180,
    subscribers_lost: 8,
    net_subscribers: 172,
    view_delta_percentage: null,
    subscriber_conversion_delta_percentage: null,
    retention_percentage: 54.1,
    retention_delta_points: null,
    views_percentile: 50.0,
    retention_percentile: 50.0,
    ctr_percentile: null,
    subscriber_conversion_per_1k_views: 12.1,
    comparison_window: "lifetime catalog baseline",
    baseline_sample_size: 1,
    median_views: 0.0,
    median_retention: 0.0,
    median_ctr: null,
    ctr: null,
    retention: 54.1,
    subscriber_gain: 180,
  },
  trend: [],
  insights: [],
};

const LIVE_DASHBOARD_NORMAL_DELTAS = {
  ...LIVE_DASHBOARD,
  recent_videos: [
    {
      ...LIVE_DASHBOARD.recent_videos[0],
      views_delta_percentage: 18.0,
      subs_per_1k_delta_percentage: -2.84,
      retention_delta_points: 2.5,
      subs_delta_pct: -2.84,
      retention_delta_pts: 2.5,
    },
  ],
  latest_video: {
    ...LIVE_DASHBOARD.latest_video,
    view_delta_percentage: 18.0,
    subscriber_conversion_delta_percentage: -2.84,
    retention_delta_points: 2.5,
  },
};

test.describe("BUG 10 — Nullable Comparison Metrics Regression", () => {
  test("Live YouTube dashboard renders truthfully with null deltas without crashing (1600x900)", async ({
    page,
  }) => {
    fs.mkdirSync("e2e/screenshots", { recursive: true });
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await setupPageRoutes(page);
    await page.setViewportSize({ width: 1600, height: 900 });

    let isConnected = true;

    await page.route("**/api/channels/youtube/connection", async (route) => {
      if (isConnected) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            connected: true,
            status: "connected",
            channel_id: "UC_live_creator_channel_99",
            channel_title: "Alex Tech Engineering",
            subscriber_count: 84200,
            avatar_url: null,
            scopes: [
              "https://www.googleapis.com/auth/youtube.readonly",
              "https://www.googleapis.com/auth/yt-analytics.readonly",
            ],
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ connected: false, status: "disconnected" }),
        });
      }
    });

    await page.route("**/api/channels/youtube/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(LIVE_DASHBOARD),
      });
    });

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SAMPLE_DASHBOARD),
      });
    });

    await page.route("**/api/channels/youtube/disconnect", async (route) => {
      isConnected = false;
      await route.fulfill({ status: 204 });
    });

    await loginAndNavigateToApp(page);

    // 1. Dashboard and channel title load
    await expect(
      page.getByRole("heading", { name: "Alex Tech Engineering", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Connected YouTube", { exact: true })).toBeVisible();
    await expect(page.getByText("84,200 subscribers · 42 videos")).toBeVisible();

    // 2. Real available KPIs render
    await expect(page.getByLabel("Channel KPIs")).toBeVisible();
    await expect(page.getByText("124.5K")).toBeVisible(); // Views
    await expect(page.getByText("15.4K hours")).toBeVisible(); // Watch time
    await expect(page.getByText("+1.4K")).toBeVisible(); // Net subscribers
    await expect(page.getByText("51.2%")).toBeVisible(); // Average retention

    // 3. Latest video section renders with real views and truthful unavailable comparison
    await expect(
      page.getByText("Building Production Multi-Agent Systems on Cloud Run (Live Take)"),
    ).toBeVisible();
    await expect(page.getByText("14.2K")).toBeVisible(); // Real views
    await expect(page.getByText("Comparison unavailable").first()).toBeVisible(); // Truthful unavailable state

    // 4. No raw Pydantic errors or reconnect alerts
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.getByText(/validation error/i)).toHaveCount(0);
    await expect(page.getByText(/input_value=None/i)).toHaveCount(0);

    // 5. No sample data leaks
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toHaveCount(0);
    await expect(page.getByText("51,317 subscribers")).toHaveCount(0);

    // 6. Switch date range (90 days) and verify it does not crash
    await page.getByLabel("Time range").selectOption("90");
    await expect(
      page.getByText("Building Production Multi-Agent Systems on Cloud Run (Live Take)"),
    ).toBeVisible();
    await expect(page.getByText("Comparison unavailable").first()).toBeVisible();

    // 7. Switch date range (365 days) and verify it does not crash
    await page.getByLabel("Time range").selectOption("365");
    await expect(
      page.getByText("Building Production Multi-Agent Systems on Cloud Run (Live Take)"),
    ).toBeVisible();

    // Take AFTER screenshot at 1600x900
    await page.screenshot({ path: "e2e/screenshots/bug10-after-1600x900.png", fullPage: true });

    // Verify 0 unexpected console errors
    expect(consoleErrors).toHaveLength(0);
  });

  test("Live YouTube dashboard renders at 1440x900 and 1280x800", async ({ page }) => {
    fs.mkdirSync("e2e/screenshots", { recursive: true });
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await setupPageRoutes(page);

    let isConnected = true;

    await page.route("**/api/channels/youtube/connection", async (route) => {
      if (isConnected) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            connected: true,
            status: "connected",
            channel_id: "UC_live_creator_channel_99",
            channel_title: "Alex Tech Engineering",
            subscriber_count: 84200,
            avatar_url: null,
            scopes: [
              "https://www.googleapis.com/auth/youtube.readonly",
              "https://www.googleapis.com/auth/yt-analytics.readonly",
            ],
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ connected: false, status: "disconnected" }),
        });
      }
    });

    await page.route("**/api/channels/youtube/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(LIVE_DASHBOARD),
      });
    });

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SAMPLE_DASHBOARD),
      });
    });

    // Viewport 1440x900
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAndNavigateToApp(page);

    await expect(
      page.getByRole("heading", { name: "Alex Tech Engineering", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Comparison unavailable").first()).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/bug10-after-1440x900.png", fullPage: true });

    // Viewport 1280x800
    await page.setViewportSize({ width: 1280, height: 800 });
    await expect(
      page.getByRole("heading", { name: "Alex Tech Engineering", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Comparison unavailable").first()).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/bug10-after-1280x800.png", fullPage: true });

    expect(consoleErrors).toHaveLength(0);
  });

  test("Live YouTube dashboard renders normal case when deltas exist", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await setupPageRoutes(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    let isConnected = true;

    await page.route("**/api/channels/youtube/connection", async (route) => {
      if (isConnected) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            connected: true,
            status: "connected",
            channel_id: "UC_live_creator_channel_99",
            channel_title: "Alex Tech Engineering",
            subscriber_count: 84200,
            avatar_url: null,
            scopes: [
              "https://www.googleapis.com/auth/youtube.readonly",
              "https://www.googleapis.com/auth/yt-analytics.readonly",
            ],
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ connected: false, status: "disconnected" }),
        });
      }
    });

    await page.route("**/api/channels/youtube/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(LIVE_DASHBOARD_NORMAL_DELTAS),
      });
    });

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SAMPLE_DASHBOARD),
      });
    });

    await loginAndNavigateToApp(page);

    await expect(
      page.getByRole("heading", { name: "Alex Tech Engineering", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Building Production Multi-Agent Systems on Cloud Run (Live Take)"),
    ).toBeVisible();
    await expect(page.getByText("↑ 18% vs channel median")).toBeVisible();
    expect(consoleErrors).toHaveLength(0);
  });
});
