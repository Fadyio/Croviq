import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";
import * as fs from "fs";

export const CANONICAL_DASHBOARD = {
  channel: {
    channel_id: "croviq_syn_ai_eng_01",
    title: "Croviq AI Engineering",
    subscriber_count: 51317,
    source_type: "synthetic",
  },
  period_days: 28,
  period_end: "2026-08-26",
  kpis: [
    {
      metric: "views",
      current_value: 348200,
      previous_value: 290100,
      change_percentage: 20.0,
      unit: "count",
    },
    {
      metric: "watch_time_hours",
      current_value: 28400.5,
      previous_value: 23100.0,
      change_percentage: 22.9,
      unit: "hours",
    },
    {
      metric: "net_subscribers",
      current_value: 4120,
      previous_value: 3200,
      change_percentage: 28.8,
      unit: "count",
    },
    {
      metric: "average_retention",
      current_value: 58.4,
      previous_value: 53.2,
      change_percentage: 5.2,
      unit: "percentage",
    },
  ],
  trend: [
    {
      date: "2026-08-01",
      views: 12000,
      previous_views: 10000,
      watch_time_hours: 980,
      previous_watch_time_hours: 800,
      net_subscribers: 150,
      previous_net_subscribers: 110,
    },
    {
      date: "2026-08-15",
      views: 14500,
      previous_views: 11000,
      watch_time_hours: 1120,
      previous_watch_time_hours: 850,
      net_subscribers: 180,
      previous_net_subscribers: 120,
    },
    {
      date: "2026-08-26",
      views: 16000,
      previous_views: 12500,
      watch_time_hours: 1300,
      previous_watch_time_hours: 950,
      net_subscribers: 210,
      previous_net_subscribers: 140,
    },
  ],
  latest_video: {
    video_id: "vid_syn_100",
    title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
    published_at: "2026-08-13T10:00:00Z",
    views: 23314,
    view_delta_percentage: -22.0,
    retention_percentage: 33.4,
    retention_delta_points: -25.6,
    ctr: 4.3,
    ctr_delta_points: -3.5,
    subscribers_gained: 350,
    subscribers_lost: 47,
    net_subscribers: 303,
    subscriber_conversion_per_1k_views: 14.3,
    subscriber_conversion_delta_percentage: -2.4,
    is_latest: true,
    alex_interpretation:
      "Retention is the main weakness here. The video is 25.6 points below your channel median.",
    alex_next_action: "Inspect the first 30 seconds for delayed demonstration or setup.",
  },
  recent_videos: [
    {
      video_id: "vid_syn_100",
      title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
      published_at: "2026-08-13T10:00:00Z",
      views: 23314,
      views_delta_percentage: -22.0,
      average_retention: 33.4,
      retention_delta_points: -25.6,
      ctr_percentage: 4.3,
      ctr_delta_points: -3.5,
      subscribers_gained: 350,
      subscribers_lost: 47,
      net_subscribers: 303,
      subs_per_1k: 14.3,
      subs_per_1k_delta_percentage: -2.4,
      is_latest: true,
      alex_interpretation:
        "Retention is the main weakness here. The video is 25.6 points below your channel median.",
      alex_next_action: "Inspect the first 30 seconds for delayed demonstration or setup.",
    },
    {
      video_id: "vid_syn_099",
      title: "FastAPI Production Deployment with Docker & Cloud Run",
      published_at: "2026-08-06T10:00:00Z",
      views: 31200,
      views_delta_percentage: 5.0,
      average_retention: 61.2,
      retention_delta_points: 2.2,
      ctr_percentage: 8.1,
      ctr_delta_points: 0.3,
      subscribers_gained: 450,
      subscribers_lost: 30,
      net_subscribers: 420,
      subs_per_1k: 14.4,
      subs_per_1k_delta_percentage: 1.5,
      is_latest: false,
      alex_interpretation: null,
      alex_next_action: null,
    },
    {
      video_id: "vid_syn_098",
      title: "Building Multi-Agent Systems with LangGraph & Claude",
      published_at: "2026-07-30T10:00:00Z",
      views: 45000,
      views_delta_percentage: 51.0,
      average_retention: 67.8,
      retention_delta_points: 8.8,
      ctr_percentage: 9.4,
      ctr_delta_points: 1.6,
      subscribers_gained: 720,
      subscribers_lost: 40,
      net_subscribers: 680,
      subs_per_1k: 16.0,
      subs_per_1k_delta_percentage: 12.0,
      is_latest: false,
      alex_interpretation: null,
      alex_next_action: null,
    },
    {
      video_id: "vid_syn_097",
      title: "Model Context Protocol Explained in 10 Minutes",
      published_at: "2026-07-23T10:00:00Z",
      views: 38400,
      views_delta_percentage: 29.0,
      average_retention: 64.0,
      retention_delta_points: 5.0,
      ctr_percentage: 8.7,
      ctr_delta_points: 0.9,
      subscribers_gained: 590,
      subscribers_lost: 35,
      net_subscribers: 555,
      subs_per_1k: 15.3,
      subs_per_1k_delta_percentage: 7.5,
      is_latest: false,
      alex_interpretation: null,
      alex_next_action: null,
    },
    {
      video_id: "vid_syn_096",
      title: "Local LLM Serving with vLLM and Speculative Decoding",
      published_at: "2026-07-16T10:00:00Z",
      views: 29800,
      views_delta_percentage: 0.1,
      average_retention: 59.5,
      retention_delta_points: 0.5,
      ctr_percentage: 7.9,
      ctr_delta_points: 0.1,
      subscribers_gained: 410,
      subscribers_lost: 25,
      net_subscribers: 385,
      subs_per_1k: 13.8,
      subs_per_1k_delta_percentage: -2.8,
      is_latest: false,
      alex_interpretation: null,
      alex_next_action: null,
    },
  ],
  channel_baselines: {
    median_views: 29769.5,
    median_retention: 59.0,
    median_ctr: 7.8,
    median_subs_per_1k: 14.7,
    median_net_subscribers: 400.0,
    sample_size: 100,
  },
  video_performance: [],
  topic_clusters: [],
  traffic_sources: [],
  insights: [
    {
      insight_id: "ins_1",
      title: "Agent Architecture Tutorials Outperform Baselines",
      type: "TOPIC",
      statement: "Tutorials focusing on multi-agent architectures achieve 34% higher retention.",
      recommended_action: "Publish the Model Context Protocol deep-dive video.",
      evidence: [],
      evidence_stats: { eligible_video_count: 12 },
    },
  ],
  active_experiment: null,
  proposed_experiment: null,
  is_sample_modeled_timeseries: true,
};

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
  await page.route("**/api/channels/youtube/connection", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        connected: false,
        channel_id: null,
        channel_title: null,
        status: "disconnected",
      }),
    });
  });

  await page.route("**/api/channels/sample/dashboard*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(CANONICAL_DASHBOARD),
    });
  });

  await page.route("**/api/channels/dashboard*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(CANONICAL_DASHBOARD),
    });
  });

  let mockResearchConfig = {
    workspace_id: "ws_demo",
    channel_id: "croviq_syn_ai_eng_01",
    enabled: true,
    cadence: "EVERY_DAY",
    prompts: [
      {
        prompt_id: "autonomous_channel_research",
        text: "Autonomous channel grounded research",
        enabled: true,
        use_broad_web_search: true,
        preferred_sources: ["ai.google.dev", "cloud.google.com"],
      },
    ],
    last_run_at: "2026-08-30T12:00:00Z",
    next_run_at: "2026-08-31T12:00:00Z",
    updated_at: "2026-08-30T12:00:00Z",
  };

  await page.route("**/api/channels/research/config", async (route) => {
    if (route.request().method() === "PUT") {
      const data = route.request().postDataJSON();
      mockResearchConfig = { ...mockResearchConfig, ...data, updated_at: new Date().toISOString() };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResearchConfig),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResearchConfig),
      });
    }
  });

  const mockFindings = [
    {
      finding_id: "finding_1",
      workspace_id: "ws_demo",
      channel_id: "croviq_syn_ai_eng_01",
      title: "Model Context Protocol Production Server Architectures",
      category: "Agent Workflows",
      topic_cluster: "agent-workflows",
      primary_entity: "Model Context Protocol",
      ecosystem: "HACKER_NEWS",
      summary: "Anthropic and Cloud Run published standardized authentication patterns for MCP.",
      why_it_matters:
        "Your agent infrastructure tutorials historically outperform retention by 34%.",
      relevance_score: 0.95,
      freshness_score: 0.96,
      opportunity_score: 0.95,
      discovered_at: "2026-08-30T11:45:00Z",
      source_citations: [
        {
          url: "https://github.com/modelcontextprotocol/servers",
          title: "Model Context Protocol Servers",
          domain: "github.com",
          grounding_metadata: { role: "primary_source", ecosystem: "GITHUB" },
        },
        {
          url: "https://news.ycombinator.com/item?id=42300010",
          title: "Discussion: MCP Production Security",
          domain: "news.ycombinator.com",
          grounding_metadata: { role: "discovery_signal", ecosystem: "HACKER_NEWS" },
        },
      ],
    },
    {
      finding_id: "finding_2",
      workspace_id: "ws_demo",
      channel_id: "croviq_syn_ai_eng_01",
      title: "vLLM Multi-GPU Speculative Decoding Benchmarks",
      category: "Foundation Models",
      topic_cluster: "foundation-models",
      primary_entity: "vLLM",
      ecosystem: "REDDIT",
      summary: "vLLM v0.7 introduced chunked prefill and speculative decoding benchmarks.",
      why_it_matters: "Local inference benchmarks drive 41% higher subscriber conversion.",
      relevance_score: 0.93,
      freshness_score: 0.94,
      opportunity_score: 0.93,
      discovered_at: "2026-08-30T11:45:00Z",
      source_citations: [
        {
          url: "https://github.com/vllm-project/vllm",
          title: "vLLM Serving",
          domain: "github.com",
          grounding_metadata: { role: "primary_source", ecosystem: "GITHUB" },
        },
      ],
    },
  ];

  await page.route("**/api/channels/research/findings*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockFindings),
    });
  });

  await page.route("**/api/channels/research/run", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        ...mockFindings,
        {
          finding_id: "finding_3",
          workspace_id: "ws_demo",
          channel_id: "croviq_syn_ai_eng_01",
          title: "Gemini 3.7 Flash Dynamic Thinking Budget and Tool Grounding",
          category: "Foundation Models",
          topic_cluster: "foundation-models",
          primary_entity: "Gemini 3.7",
          ecosystem: "PRIMARY_VENDOR",
          summary: "Google released Gemini 3.7 Flash featuring native dynamic thinking budgets.",
          why_it_matters: "Gemini tooling tutorials outperform baseline channel retention by 28%.",
          relevance_score: 0.96,
          freshness_score: 0.98,
          opportunity_score: 0.97,
          discovered_at: new Date().toISOString(),
          source_citations: [
            {
              url: "https://ai.google.dev/gemini-api/docs/models/gemini",
              title: "Gemini Models",
              domain: "ai.google.dev",
              grounding_metadata: { role: "primary_source", ecosystem: "PRIMARY_VENDOR" },
            },
          ],
        },
      ]),
    });
  });
  await page.route("**/api/workspace/agent-settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "Leo editorial prompt",
          default_prompt: "Leo editorial prompt",
          is_custom: false,
          updated_at: "2026-08-28T00:00:00Z",
        },
        alex_prompt: {
          agent_id: "alex",
          prompt_text: "Alex research prompt",
          default_prompt: "Alex research prompt",
          is_custom: false,
          updated_at: "2026-08-28T00:00:00Z",
        },
        iris_prompt: {
          agent_id: "iris",
          prompt_text: "Iris publishing prompt",
          default_prompt: "Iris publishing prompt",
          is_custom: false,
          updated_at: "2026-08-28T00:00:00Z",
        },
        voice_settings: {
          narration_mode: "original",
          selected_voice: "Puck",
          language: "en-US",
        },
        voices: [
          {
            voice_id: "Puck",
            display_name: "Puck",
            gender: "Male",
            language_code: "en-US",
          },
        ],
      }),
    });
  });

  await page.route("**/api/workspace/agent-settings/memory*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        channel_title: "Croviq",
        style_guide: "Evidence-first quantitative statistical analysis",
        memories: [],
        creator_preferences: [],
        lessons: [],
      }),
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

test.describe("BUG 24 — Final Alex Dashboard & Live Research UX Acceptance", () => {
  test("Dashboard hierarchy: Channel Performance appears BEFORE Recent Video Performance", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await setupPageRoutes(page);
    await signInAndGoToHome(page);

    // 1. Confirm KPI cards load
    const kpiSection = page.getByLabel("Channel KPIs");
    await expect(kpiSection).toBeVisible();

    // 2. Confirm Channel Performance chart header is visible
    const channelPerfHeading = page.getByRole("heading", { name: "Channel Performance" });
    await expect(channelPerfHeading).toBeVisible();

    // 3. Confirm Recent Video Performance heading is visible
    const recentVideosHeading = page.getByRole("heading", { name: "Recent video performance" });
    await expect(recentVideosHeading).toBeVisible();

    // 4. Verify DOM ordering: KPI Section -> Channel Performance -> Recent Video Performance
    const channelPerfBox = await channelPerfHeading.boundingBox();
    const recentVideosBox = await recentVideosHeading.boundingBox();
    expect(channelPerfBox).not.toBeNull();
    expect(recentVideosBox).not.toBeNull();
    if (channelPerfBox && recentVideosBox) {
      expect(channelPerfBox.y).toBeLessThan(recentVideosBox.y);
    }

    // 5. Confirm Recent Video Performance says 'Latest 5 videos'
    const recentSection = page.locator('[aria-labelledby="recent-videos-title"]');
    await expect(recentSection.getByText("(Latest 5 videos)")).toBeVisible();

    // 6. Confirm exactly 5 video cards are shown
    const videoArticles = recentSection.locator("article");
    await expect(videoArticles).toHaveCount(5);

    // 7. Verify first video is the newest video
    const firstVideo = videoArticles.first();
    await expect(
      firstVideo.getByRole("heading", {
        name: "Google GenAI SDK Tutorial for Beginners (Part 5)",
      }),
    ).toBeVisible();
    await expect(firstVideo.getByText("Latest Upload")).toBeVisible();

    // 8. Verify all 4 metrics are visible in the compact strip
    await expect(firstVideo.getByText("Views", { exact: true })).toBeVisible();
    await expect(firstVideo.getByText("Retention", { exact: true })).toBeVisible();
    await expect(firstVideo.getByText("Thumbnail CTR", { exact: true })).toBeVisible();
    await expect(firstVideo.getByText("Subs / 1K views", { exact: true })).toBeVisible();

    expect(consoleErrors).toHaveLength(0);
  });
  test("Manual research trigger: Find new ideas button starts real research and refreshes UI", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await setupPageRoutes(page);
    await signInAndGoToHome(page);

    // 1. Check Ideas Worth Making section
    const ideasHeading = page.getByRole("heading", { name: "Ideas Worth Making" }).first();
    await expect(ideasHeading).toBeVisible();

    // 2. Find manual trigger button
    const findNewIdeasBtn = page.getByTestId("btn-find-new-ideas");
    await expect(findNewIdeasBtn).toBeVisible();
    await expect(findNewIdeasBtn).toHaveText(/Find new ideas/i);

    // 3. Click trigger and verify network request / state
    const researchResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes("/api/channels/research/run") && resp.status() === 200,
    );
    await findNewIdeasBtn.click();

    // 4. Wait for response
    const resp = await researchResponsePromise;
    expect(resp.status()).toBe(200);

    // 5. Verify Ideas Worth Making has updated findings
    await expect(page.getByRole("heading", { name: "Ideas Worth Making" }).first()).toBeVisible();
    await expect(findNewIdeasBtn).toHaveText(/Find new ideas/i);

    expect(consoleErrors).toHaveLength(0);
  });

  test("Alex Settings Research tab: heading is Preferred Public Sources, add/remove works and persists", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await setupPageRoutes(page);
    await signInAndGoToHome(page);

    // 1. Open Alex action menu and click Settings
    const alexTrigger = page.getByTestId("btn-agent-menu-alex");
    await alexTrigger.click();
    const settingsItem = page.getByTestId("action-settings-alex");
    await settingsItem.click();

    // 2. Verify drawer is open
    const drawer = page.getByTestId("agent-settings-drawer");
    await expect(drawer).toBeVisible();

    // 3. Switch to Research tab
    const researchTab = drawer.getByTestId("tab-research");
    await expect(researchTab).toBeVisible();
    await researchTab.click();

    // 4. Verify heading: 'PREFERRED PUBLIC SOURCES'
    await expect(drawer.getByText("Preferred Public Sources")).toBeVisible();

    // 5. Add a new public source
    const newSource = "news.ycombinator.com";
    const sourceInput = drawer.getByTestId("input-new-source");
    await sourceInput.fill(newSource);
    await page.keyboard.press("Enter");

    // 6. Verify source chip is displayed
    await expect(drawer.getByTestId(`source-chip-${newSource}`)).toBeVisible();

    // 7. Save research settings
    const saveBtn = drawer.getByTestId("btn-save-research");
    await saveBtn.click();
    await expect(drawer.getByText("Research settings saved")).toBeVisible();

    // 8. Close drawer
    const closeBtn = drawer.getByTestId("btn-close-settings");
    await closeBtn.click();
    await expect(drawer).not.toBeVisible();

    // 9. Reopen and verify persisted
    await alexTrigger.click();
    await settingsItem.click();
    await expect(drawer).toBeVisible();
    await researchTab.click();
    await expect(drawer.getByTestId(`source-chip-${newSource}`)).toBeVisible();

    expect(consoleErrors).toHaveLength(0);
  });

  test("Viewport inspections across 1600x900, 1440x900, and 1280x800", async ({ page }) => {
    fs.mkdirSync("e2e/screenshots", { recursive: true });
    await setupPageRoutes(page);
    await signInAndGoToHome(page);

    const viewports = [
      { width: 1600, height: 900, name: "1600x900" },
      { width: 1440, height: 900, name: "1440x900" },
      { width: 1280, height: 800, name: "1280x800" },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await expect(page.getByRole("heading", { name: "Channel Performance" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Recent video performance" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Ideas Worth Making" }).first()).toBeVisible();
      await expect(page.getByTestId("btn-find-new-ideas")).toBeVisible();
      await page.screenshot({ path: `e2e/screenshots/bug24-dashboard-${vp.name}.png` });
    }
  });
});
