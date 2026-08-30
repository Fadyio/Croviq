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

  await page.route("**/api/productions", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
};

const signInAndGoToHome = async (page: Page) => {
  await page.goto("/login");
  await page.fill('input[type="email"]', DEMO_EMAIL);
  await page.fill('input[type="password"]', "password123");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/app**", { timeout: 10000 });
};

test.describe("Bug 11 — Recent Video Performance Must Be One Consistent Grounded Analysis", () => {
  test("Sample Mode Home Dashboard renders canonical Recent Video Performance across resolutions", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await setupPageRoutes(page);
    await signInAndGoToHome(page);

    const recentSection = page.locator('[aria-labelledby="recent-videos-title"]');
    await expect(recentSection).toBeVisible();

    // 1. Verify Header & Subtitle
    await expect(
      recentSection.getByRole("heading", { name: "Recent video performance" }),
    ).toBeVisible();
    await expect(
      recentSection.getByText("Compared with your channel's historical median (100 videos)"),
    ).toBeVisible();

    // 2. Verify Latest Upload Badge on First Video Only
    const latestBadges = recentSection.locator('text="Latest Upload"');
    await expect(latestBadges).toHaveCount(1);

    // 3. Verify Latest Video (vid_syn_100) Identity and Metrics
    const firstArticle = recentSection.locator("article").first();
    await expect(
      firstArticle.getByRole("heading", {
        name: "Google GenAI SDK Tutorial for Beginners (Part 5)",
      }),
    ).toBeVisible();
    await expect(firstArticle.getByText("Aug 13, 2026")).toBeVisible();

    // Views
    await expect(firstArticle.getByText("23.3K")).toBeVisible();
    await expect(firstArticle.getByText("↓ 22% vs channel median")).toBeVisible();

    // Retention
    await expect(firstArticle.getByText("33.4%")).toBeVisible();
    await expect(firstArticle.getByText("↓ 25.6 pts vs channel median")).toBeVisible();

    // Thumbnail CTR
    await expect(firstArticle.getByText("4.3%")).toBeVisible();
    await expect(firstArticle.getByText("↓ 3.5 pts vs channel median")).toBeVisible();

    // Subs / 1K views
    await expect(firstArticle.getByText("14.3")).toBeVisible();
    await expect(firstArticle.getByText("+303 net")).toBeVisible();
    await expect(firstArticle.getByText("↓ 2.4% vs channel median")).toBeVisible();
    // Alex Interpretation & Next Action
    await expect(
      firstArticle.getByText(
        "Retention is the main weakness here. The video is 25.6 points below your channel median.",
      ),
    ).toBeVisible();
    await expect(
      firstArticle.getByText("Inspect the first 30 seconds for delayed demonstration or setup."),
    ).toBeVisible();

    // 4. Capture screenshots for acceptance
    fs.mkdirSync("e2e/screenshots", { recursive: true });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.screenshot({ path: "e2e/screenshots/bug11-after-1440x900.png" });

    // 5. Verify no console errors
    expect(consoleErrors).toHaveLength(0);
  });

  test("CASE A: Poor retention with normal CTR produces grounded retention diagnosis", async ({
    page,
  }) => {
    await setupPageRoutes(page);

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel: {
            channel_id: "croviq_syn_ai_eng_01",
            title: "Croviq",
            subscriber_count: 51317,
            source_type: "synthetic",
          },
          period_days: 28,
          period_end: "2026-08-26",
          kpis: [],
          trend: [],
          latest_video: null,
          recent_videos: [
            {
              video_id: "vid_case_a",
              title: "Testing Case A Poor Retention",
              published_at: "2026-08-20T10:00:00Z",
              views: 24000,
              views_delta_percentage: -5.0,
              average_retention: 35.0,
              retention_delta_points: -24.0,
              ctr_percentage: 7.6,
              ctr_delta_points: -0.2,
              subscribers_gained: 350,
              subscribers_lost: 20,
              net_subscribers: 330,
              subs_per_1k: 14.5,
              subs_per_1k_delta_percentage: -1.2,
              is_latest: true,
              alex_interpretation:
                "Retention is the main weakness here. The video is 24.0 points below your channel median.",
              alex_next_action: "Inspect the first 30 seconds for delayed demonstration or setup.",
            },
          ],
          channel_baselines: {
            median_views: 25200.0,
            median_retention: 59.0,
            median_ctr: 7.8,
            median_subs_per_1k: 14.7,
            sample_size: 50,
          },
          video_performance: [],
          topic_clusters: [],
          traffic_sources: [],
          insights: [],
          active_experiment: null,
          proposed_experiment: null,
          is_sample_modeled_timeseries: true,
        }),
      });
    });

    await signInAndGoToHome(page);

    const firstArticle = page.locator("article").first();
    await expect(firstArticle.getByText("Testing Case A Poor Retention")).toBeVisible();
    await expect(firstArticle.getByText("35.0%")).toBeVisible();
    await expect(firstArticle.getByText("↓ 24.0 pts vs channel median")).toBeVisible();
    await expect(
      firstArticle.getByText(
        "Retention is the main weakness here. The video is 24.0 points below your channel median.",
      ),
    ).toBeVisible();
    await expect(
      firstArticle.getByText("Inspect the first 30 seconds for delayed demonstration or setup."),
    ).toBeVisible();
  });

  test("CASE B: Strong retention with weak views diagnoses distribution bottleneck", async ({
    page,
  }) => {
    await setupPageRoutes(page);

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel: {
            channel_id: "croviq_syn_ai_eng_01",
            title: "Croviq",
            subscriber_count: 51317,
            source_type: "synthetic",
          },
          period_days: 28,
          period_end: "2026-08-26",
          kpis: [],
          trend: [],
          latest_video: null,
          recent_videos: [
            {
              video_id: "vid_case_b",
              title: "Testing Case B Strong Retention Weak Reach",
              published_at: "2026-08-20T10:00:00Z",
              views: 12000,
              views_delta_percentage: -52.0,
              average_retention: 65.4,
              retention_delta_points: 6.4,
              ctr_percentage: 4.1,
              ctr_delta_points: -3.7,
              subscribers_gained: 200,
              subscribers_lost: 10,
              net_subscribers: 190,
              subs_per_1k: 16.6,
              subs_per_1k_delta_percentage: 13.0,
              is_latest: true,
              alex_interpretation:
                "Viewer engagement is strong with retention +6.4 pts vs median, but packaging is limiting reach with CTR -3.7 pts vs median.",
              alex_next_action:
                "Test alternative thumbnail compositions and high-contrast title variations to match packaging to content quality.",
            },
          ],
          channel_baselines: {
            median_views: 25000.0,
            median_retention: 59.0,
            median_ctr: 7.8,
            median_subs_per_1k: 14.7,
            sample_size: 50,
          },
          video_performance: [],
          topic_clusters: [],
          traffic_sources: [],
          insights: [],
          active_experiment: null,
          proposed_experiment: null,
          is_sample_modeled_timeseries: true,
        }),
      });
    });

    await signInAndGoToHome(page);

    const firstArticle = page.locator("article").first();
    await expect(
      firstArticle.getByText("Testing Case B Strong Retention Weak Reach"),
    ).toBeVisible();
    await expect(firstArticle.getByText("65.4%")).toBeVisible();
    await expect(firstArticle.getByText("↑ 6.4 pts vs channel median")).toBeVisible();
    await expect(firstArticle.getByText("4.1%")).toBeVisible();
    await expect(firstArticle.getByText("↓ 3.7 pts vs channel median")).toBeVisible();
    await expect(
      firstArticle.getByText(
        "Viewer engagement is strong with retention +6.4 pts vs median, but packaging is limiting reach with CTR -3.7 pts vs median.",
      ),
    ).toBeVisible();
    await expect(
      firstArticle.getByText(
        "Test alternative thumbnail compositions and high-contrast title variations to match packaging to content quality.",
      ),
    ).toBeVisible();
  });

  test("CASE C: Missing CTR renders truthfully without fake values or ungrounded CTR commentary", async ({
    page,
  }) => {
    await setupPageRoutes(page);

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel: {
            channel_id: "croviq_syn_ai_eng_01",
            title: "Croviq",
            subscriber_count: 51317,
            source_type: "synthetic",
          },
          period_days: 28,
          period_end: "2026-08-26",
          kpis: [],
          trend: [],
          latest_video: null,
          recent_videos: [
            {
              video_id: "vid_case_c",
              title: "Testing Case C Missing CTR",
              published_at: "2026-08-20T10:00:00Z",
              views: 30000,
              views_delta_percentage: 1.2,
              average_retention: 59.2,
              retention_delta_points: 0.2,
              ctr_percentage: null,
              ctr_delta_points: null,
              subscribers_gained: 440,
              subscribers_lost: 30,
              net_subscribers: 410,
              subs_per_1k: 14.6,
              subs_per_1k_delta_percentage: -0.5,
              is_latest: true,
              alex_interpretation:
                "Performance across views, retention, and subscriber conversion aligns closely with your channel median.",
              alex_next_action: "Maintain format consistency and pacing across upcoming uploads.",
            },
          ],
          channel_baselines: {
            median_views: 29700.0,
            median_retention: 59.0,
            median_ctr: null,
            median_subs_per_1k: 14.7,
            sample_size: 20,
          },
          video_performance: [],
          topic_clusters: [],
          traffic_sources: [],
          insights: [],
          active_experiment: null,
          proposed_experiment: null,
          is_sample_modeled_timeseries: true,
        }),
      });
    });

    await signInAndGoToHome(page);

    const firstArticle = page.locator("article").first();
    await expect(firstArticle.getByText("Testing Case C Missing CTR")).toBeVisible();
    await expect(firstArticle.getByText("Unavailable")).toBeVisible();
    await expect(firstArticle.getByText("No CTR recorded")).toBeVisible();
    await expect(
      firstArticle.getByText(
        "Performance across views, retention, and subscriber conversion aligns closely with your channel median.",
      ),
    ).toBeVisible();
  });

  test("CASE D: Zero / undefined comparison baseline renders truthfully without NaN or crashes", async ({
    page,
  }) => {
    await setupPageRoutes(page);

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel: {
            channel_id: "croviq_syn_ai_eng_01",
            title: "Croviq",
            subscriber_count: 10,
            source_type: "synthetic",
          },
          period_days: 28,
          period_end: "2026-08-26",
          kpis: [],
          trend: [],
          latest_video: null,
          recent_videos: [
            {
              video_id: "vid_case_d",
              title: "First Upload on New Channel",
              published_at: "2026-08-20T10:00:00Z",
              views: 120,
              views_delta_percentage: null,
              average_retention: 40.0,
              retention_delta_points: null,
              ctr_percentage: null,
              ctr_delta_points: null,
              subscribers_gained: 2,
              subscribers_lost: 0,
              net_subscribers: 2,
              subs_per_1k: 16.7,
              subs_per_1k_delta_percentage: null,
              is_latest: true,
              alex_interpretation:
                "Catalog baseline is insufficient for comparative performance analysis.",
              alex_next_action:
                "Publish additional uploads to establish statistically reliable channel medians.",
            },
          ],
          channel_baselines: {
            median_views: 0.0,
            median_retention: 0.0,
            median_ctr: null,
            median_subs_per_1k: null,
            sample_size: 1,
          },
          video_performance: [],
          topic_clusters: [],
          traffic_sources: [],
          insights: [],
          active_experiment: null,
          proposed_experiment: null,
          is_sample_modeled_timeseries: true,
        }),
      });
    });

    await signInAndGoToHome(page);

    const firstArticle = page.locator("article").first();
    await expect(firstArticle.getByText("First Upload on New Channel")).toBeVisible();
    await expect(firstArticle.getByText("Comparison unavailable").first()).toBeVisible();
    await expect(
      firstArticle.getByText(
        "Catalog baseline is insufficient for comparative performance analysis.",
      ),
    ).toBeVisible();
    await expect(
      firstArticle.getByText(
        "Publish additional uploads to establish statistically reliable channel medians.",
      ),
    ).toBeVisible();

    // Verify zero NaNs or Infinities in the entire section
    const sectionText = await page.locator('[aria-labelledby="recent-videos-title"]').innerText();
    expect(sectionText).not.toContain("NaN");
    expect(sectionText).not.toContain("Infinity");
    expect(sectionText).not.toContain("undefined");
  });

  test("CASE E & F: Ordering and independent video metrics without cross-video contamination", async ({
    page,
  }) => {
    await setupPageRoutes(page);

    await page.route("**/api/channels/sample/dashboard*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel: {
            channel_id: "croviq_syn_ai_eng_01",
            title: "Croviq",
            subscriber_count: 51317,
            source_type: "synthetic",
          },
          period_days: 28,
          period_end: "2026-08-26",
          kpis: [],
          trend: [],
          latest_video: null,
          recent_videos: [
            {
              video_id: "vid_newest_01",
              title: "Newest Video 01",
              published_at: "2026-08-20T10:00:00Z",
              views: 15000,
              views_delta_percentage: -40.0,
              average_retention: 25.0,
              retention_delta_points: -34.0,
              ctr_percentage: 5.0,
              ctr_delta_points: -2.8,
              subscribers_gained: 150,
              subscribers_lost: 10,
              net_subscribers: 140,
              subs_per_1k: 10.0,
              subs_per_1k_delta_percentage: -32.0,
              is_latest: true,
              alex_interpretation:
                "Retention is the main weakness here. The video is 34.0 points below your channel median.",
              alex_next_action: "Inspect the first 30 seconds for delayed demonstration or setup.",
            },
            {
              video_id: "vid_older_02",
              title: "Older Video 02",
              published_at: "2026-08-10T10:00:00Z",
              views: 50000,
              views_delta_percentage: 100.0,
              average_retention: 65.0,
              retention_delta_points: 6.0,
              ctr_percentage: 9.5,
              ctr_delta_points: 1.7,
              subscribers_gained: 800,
              subscribers_lost: 40,
              net_subscribers: 760,
              subs_per_1k: 16.0,
              subs_per_1k_delta_percentage: 8.8,
              is_latest: false,
              alex_interpretation: null,
              alex_next_action: null,
            },
          ],
          channel_baselines: {
            median_views: 25000.0,
            median_retention: 59.0,
            median_ctr: 7.8,
            median_subs_per_1k: 14.7,
            sample_size: 50,
          },
          video_performance: [],
          topic_clusters: [],
          traffic_sources: [],
          insights: [],
          active_experiment: null,
          proposed_experiment: null,
          is_sample_modeled_timeseries: true,
        }),
      });
    });

    await signInAndGoToHome(page);

    const recentSection = page.locator('[aria-labelledby="recent-videos-title"]');
    await expect(recentSection).toBeVisible();
    const articles = recentSection.locator('[data-testid^="recent-video-"]');
    await expect(articles).toHaveCount(2);

    // Verify Latest Upload badge is only on the first video
    await expect(articles.nth(0).getByText("Latest Upload")).toBeVisible();
    await expect(articles.nth(1).getByText("Latest Upload")).toHaveCount(0);

    // Verify first video metrics
    await expect(articles.nth(0).getByText("Newest Video 01")).toBeVisible();
    await expect(articles.nth(0).getByText("15K")).toBeVisible();
    await expect(articles.nth(0).getByText("25.0%")).toBeVisible();
    await expect(articles.nth(0).getByText("Alex:")).toBeVisible();

    // Verify second video metrics are completely distinct and not overwritten by video 1
    await expect(articles.nth(1).getByText("Older Video 02")).toBeVisible();
    await expect(articles.nth(1).getByText("50K")).toBeVisible();
    await expect(articles.nth(1).getByText("65.0%")).toBeVisible();
    await expect(articles.nth(1).getByText("↑ 100% vs channel median")).toBeVisible();
    await expect(articles.nth(1).getByText("↑ 6.0 pts vs channel median")).toBeVisible();
    await expect(articles.nth(1).getByText("Alex:")).toHaveCount(0);
  });
});
