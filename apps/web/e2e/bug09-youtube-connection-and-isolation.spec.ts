import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";

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
      delta_percentage: 13.8,
      delta_percentage_points: null,
      unit: "count",
      status: "POSITIVE",
      display_order: 1,
    },
    {
      metric: "watch_time_hours",
      label: "Watch time",
      current_value: 48912.4,
      previous_value: 43200.0,
      delta_percentage: 13.2,
      delta_percentage_points: null,
      unit: "hours",
      status: "POSITIVE",
      display_order: 2,
    },
    {
      metric: "net_subscribers",
      label: "Net subscribers",
      current_value: 5812,
      previous_value: 5120,
      delta_percentage: 13.5,
      delta_percentage_points: null,
      unit: "count",
      status: "POSITIVE",
      display_order: 3,
    },
    {
      metric: "average_retention",
      label: "Average retention",
      current_value: 58.4,
      previous_value: 52.1,
      delta_percentage: 12.1,
      delta_percentage_points: 6.3,
      unit: "percentage",
      status: "POSITIVE",
      display_order: 4,
    },
  ],
  recent_videos: [
    {
      video_id: "vid_sample_01",
      title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
      published_at: "2026-08-23T14:30:00Z",
      views: 23314,
      watch_time_minutes: 149800.0,
      average_retention: 64.2,
      subscribers_gained: 334,
      subscribers_lost: 12,
      net_subscribers: 322,
      likes: 1240,
      comments: 118,
      shares: 95,
      ctr_percentage: 8.4,
      subs_per_1k: 13.8,
      retention_delta_pts: 5.8,
      ctr_delta_pts: 0.8,
      subs_delta_pct: 18.2,
      is_latest: true,
      alex_interpretation: "Retention was 64.2%, tracking +5.8 pts above channel median.",
      alex_next_action: "Test terminal demos within the first 25s.",
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
      retention_delta_pts: 2.9,
      ctr_delta_pts: 0.5,
      subs_delta_pct: 12.0,
      is_latest: true,
      alex_interpretation: "Live retention tracked at 54.1%.",
      alex_next_action: "Continue deep-dive format.",
    },
  ],
  trend: [],
  insights: [],
};

test.describe("Bug 9 Contract & Isolation Verification: YouTube Channel Connection", () => {
  test("Step 7 & 10: Sample mode displays truthful metadata and visible Sample label (1440x900)", async ({
    page,
  }) => {
    await setupPageRoutes(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.route("**/api/channels/youtube/connection", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ connected: false, status: "disconnected" }),
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

    // 1. Verify Sample Header
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("Sample channel", { exact: true })).toBeVisible();
    await expect(page.getByText("51,317 subscribers · 100 videos")).toBeVisible();

    // 2. Verify Sample Video
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toBeVisible();

    // 3. Verify Channel Selector Dropdown
    const selectorBtn = page.getByRole("button", { name: "Select channel" });
    await expect(selectorBtn).toBeVisible();
    await expect(selectorBtn).toContainText("Croviq");
    await expect(selectorBtn).toContainText("Sample");

    await selectorBtn.click();
    await expect(page.getByText("Deterministic sample dataset")).toBeVisible();
    await expect(page.getByText("Connect YouTube Channel")).toBeVisible();

    // Capture screenshot
    await page.screenshot({ path: "e2e/screenshots/bug09-sample-mode-1440x900.png" });
  });

  test("Step 3, 4: Connect button opens modal and generates truthful auth URL with server state", async ({
    page,
  }) => {
    await setupPageRoutes(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.route("**/api/channels/youtube/connection", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ connected: false, status: "disconnected" }),
      });
    });

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SAMPLE_DASHBOARD),
      });
    });

    let authUrlRequested = false;
    await page.route("**/api/channels/youtube/auth-url", async (route) => {
      authUrlRequested = true;
      const requestData = route.request().postDataJSON();
      expect(requestData.redirect_uri).toContain("/app");

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          auth_url:
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=test-client-id&redirect_uri=http%3A%2F%2Flocalhost%3A5173%2Fapp&response_type=code&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyt-analytics.readonly&access_type=offline&prompt=consent&state=server_generated_csrf_state_token_12345",
          state_token: "server_generated_csrf_state_token_12345",
          scopes: [
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
          ],
        }),
      });
    });

    await loginAndNavigateToApp(page);

    // Open channel selector
    await page.getByRole("button", { name: "Select channel" }).click();
    await page.getByText("Connect YouTube Channel").click();

    // Verify modal is open
    const modalTitle = page.getByRole("heading", { name: "Connect YouTube Channel" });
    await expect(modalTitle).toBeVisible();
    await expect(
      page.getByText("youtube.readonly (channel metadata & video catalog)"),
    ).toBeVisible();
    await expect(
      page.getByText("yt-analytics.readonly (retention & views analytics)"),
    ).toBeVisible();

    await page.screenshot({ path: "e2e/screenshots/bug09-connect-modal-1440x900.png" });

    // Click Authorize Channel
    await page.getByRole("button", { name: "Authorize Channel" }).click();
    expect(authUrlRequested).toBe(true);
  });

  test("Step 8, 9, 10, 11: Live mode switches cleanly, isolates recent videos, and handles mode toggle", async ({
    page,
  }) => {
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

    // 1. Verify Live Mode Dashboard is loaded
    await expect(
      page.getByRole("heading", { name: "Alex Tech Engineering", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Connected YouTube", { exact: true })).toBeVisible();
    await expect(page.getByText("84,200 subscribers · 42 videos")).toBeVisible();

    // 2. Step 11: Verify Recent Videos Isolation (Live title is visible, Sample title is NOT visible)
    await expect(
      page.getByText("Building Production Multi-Agent Systems on Cloud Run (Live Take)"),
    ).toBeVisible();
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toHaveCount(0);

    await page.screenshot({ path: "e2e/screenshots/bug09-live-mode-1440x900.png" });

    // 3. Step 9: Switch from Live to Sample Mode via Channel Selector
    const selectorBtn = page.getByRole("button", { name: "Select channel" });
    await selectorBtn.click();
    await page.getByRole("button", { name: /Croviq.*Deterministic sample dataset/i }).click();

    // 4. Verify Sample Mode is now active
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("Sample channel", { exact: true })).toBeVisible();
    await expect(page.getByText("51,317 subscribers · 100 videos")).toBeVisible();

    // 5. Verify Sample Video is now visible and Live Video is NOT visible
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toBeVisible();
    await expect(
      page.getByText("Building Production Multi-Agent Systems on Cloud Run (Live Take)"),
    ).toHaveCount(0);

    // 6. Switch back to Live Mode
    await selectorBtn.click();
    await page.getByRole("button", { name: /Alex Tech Engineering.*84,200 subscribers/i }).click();

    // 7. Verify Live Mode restored without stale Sample titles
    await expect(
      page.getByRole("heading", { name: "Alex Tech Engineering", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Building Production Multi-Agent Systems on Cloud Run (Live Take)"),
    ).toBeVisible();
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toHaveCount(0);

    // 8. Step 13: Test Disconnect
    await selectorBtn.click();
    await page.getByRole("button", { name: "Disconnect YouTube channel" }).click();

    // Verify after disconnect, it cleanly resets to Sample Mode
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("Sample channel", { exact: true })).toBeVisible();
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toBeVisible();
    await expect(
      page.getByText("Building Production Multi-Agent Systems on Cloud Run (Live Take)"),
    ).toHaveCount(0);

    await page.screenshot({ path: "e2e/screenshots/bug09-after-disconnect-1440x900.png" });
  });

  test("Step 14: Error states in live mode show truthful error without falling back to sample (1280x800)", async ({
    page,
  }) => {
    await setupPageRoutes(page);
    await page.setViewportSize({ width: 1280, height: 800 });

    await page.route("**/api/channels/youtube/connection", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          connected: true,
          status: "reauth_required",
          channel_id: "UC_live_creator_channel_99",
          channel_title: "Alex Tech Engineering",
          subscriber_count: 84200,
        }),
      });
    });

    await page.route("**/api/channels/youtube/dashboard*", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "YouTube authorization expired or invalid: token revoked" }),
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

    // Verify error banner is displayed
    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("YouTube authorization expired or invalid: token revoked");
    await expect(page.getByRole("button", { name: "Reconnect YouTube" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Switch to Sample" })).toBeVisible();

    // Verify ZERO sample data is shown while in failed live mode
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toHaveCount(0);

    // Verify clicking "Switch to Sample" recovers to Sample mode
    await page.getByRole("button", { name: "Switch to Sample" }).click();
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
    await expect(page.getByText("Sample channel", { exact: true })).toBeVisible();
    await expect(page.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)")).toBeVisible();

    await page.screenshot({ path: "e2e/screenshots/bug09-error-recovery-1280x800.png" });
  });
});
