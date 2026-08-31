import { expect, test, type Page } from "@playwright/test";

import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";

const MOCK_PROMPT_CONFIG = {
  agent_id: "alex",
  prompt_text: "You are Alex, Croviq's senior Channel Data Scientist and research partner.",
  is_custom: false,
  version: 1,
  updated_at: "2026-08-26T00:00:00Z",
};

const MOCK_MEMORIES = [
  {
    name: "projects/705994694330/locations/us-central1/reasoningEngines/9001435065032376320/memories/4328572563232915456",
    memory_id: "4328572563232915456",
    fact: "Introduce live code or terminal demonstration within the first 30 seconds.\nVideos featuring early demonstrations (<=00:30) achieve 58.4% mean retention vs 44.1% for late demos.",
    scope: { channel_id: "croviq_syn_ai_eng_01" },
    provenance: "Channel analytics",
    created_at: "2026-08-26T00:59:03.850983Z",
    updated_at: "2026-08-26T00:59:03.850983Z",
  },
  {
    name: "projects/705994694330/locations/us-central1/reasoningEngines/9001435065032376320/memories/8940258581660303360",
    memory_id: "8940258581660303360",
    fact: "Lead with outcome-focused titles and concrete tool names rather than generic beginner labels.\nOutcome-focused titles achieved an average CTR of 8.6% compared to 4.8% for generic tutorial phrasing.",
    scope: { channel_id: "croviq_syn_ai_eng_01" },
    provenance: "Packaging analytics",
    created_at: "2026-08-26T00:59:04.776470Z",
    updated_at: "2026-08-26T00:59:04.776470Z",
  },
];

const MOCK_RESEARCH_CONFIG = {
  workspace_id: "ws_demo",
  channel_id: "croviq_syn_ai_eng_01",
  enabled: true,
  cadence: "EVERY_HOUR",
  prompts: [
    {
      prompt_id: "emerging-opportunities",
      text: "Discover high-conviction video opportunities and emerging technical breakthroughs for this channel",
      enabled: true,
      use_broad_web_search: true,
      preferred_sources: [],
    },
  ],
  last_run_at: "2026-08-29T08:00:00Z",
  next_run_at: "2026-08-29T09:00:00Z",
  updated_at: "2026-08-29T08:00:00Z",
};

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
    primary_entity: "Gemini 3.7",
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
    primary_entity: "Agent Evaluation",
    source_citations: [
      {
        url: "https://news.ycombinator.com/item?id=39501234",
        title: "Discussion on Agent Evaluation — Hacker News",
        domain: "news.ycombinator.com",
      },
    ],
    topic_fingerprint: "fp_2",
    discovered_at: "2026-08-28T07:30:00Z",
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
        id_token: FIREBASE_ID_TOKEN,
        refresh_token: "fake-refresh-token",
        expires_in: "3600",
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
      body: JSON.stringify({ productions: [], total: 0 }),
    });
  });

  await page.route("**/api/channels/sample/dashboard?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        channel: {
          channel_id: "croviq_syn_ai_eng_01",
          title: "Croviq",
          custom_url: "@croviq",
          description: "Production intelligence for engineering creators.",
          subscriber_count: 51317,
          video_count: 100,
          view_count: 3501567,
          avatar_url: null,
          banner_url: null,
          published_at: "2025-01-01T00:00:00Z",
          country: "US",
          primary_language: "en",
          topic_categories: ["AI", "Software Engineering"],
          keywords: ["ai", "agents"],
          status: "active",
        },
        period_days: 28,
        kpis: [
          {
            metric: "views",
            label: "Views",
            current_value: 431400,
            previous_value: 390700,
            change_percentage: 10.4,
            trend: "up",
          },
          {
            metric: "watch_time_hours",
            label: "Watch time",
            current_value: 52000,
            previous_value: 49480,
            change_percentage: 5.1,
            trend: "up",
          },
          {
            metric: "net_subscribers",
            label: "Net subscribers",
            current_value: 5600,
            previous_value: 4940,
            change_percentage: 13.3,
            trend: "up",
          },
          {
            metric: "average_retention",
            label: "Average retention",
            current_value: 55.2,
            previous_value: 56.1,
            change_percentage: -1.6,
            trend: "down",
          },
        ],
        chart_series: [],
        trend: [
          {
            date: "2026-08-01",
            views: 14200,
            views_previous_period: 12100,
            watch_time_hours: 1800,
            net_subscribers: 180,
            average_retention: 54.2,
          },
          {
            date: "2026-08-15",
            views: 18500,
            views_previous_period: 15300,
            watch_time_hours: 2200,
            net_subscribers: 240,
            average_retention: 58.1,
          },
          {
            date: "2026-08-28",
            views: 21000,
            views_previous_period: 17200,
            watch_time_hours: 2600,
            net_subscribers: 310,
            average_retention: 59.4,
          },
        ],
        latest_video: {
          video_id: "vid_syn_100",
          title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
          published_at: "2026-08-24T10:00:00Z",
          views: 4500,
          watch_time_hours: 320.5,
          subscribers_gained: 52,
          subscribers_lost: 4,
          net_subscribers: 48,
          view_delta_percentage: 22.4,
          subscriber_conversion_delta_percentage: 18.2,
          retention_percentage: 58.4,
          retention_delta_points: 9.5,
          views_percentile: 85.0,
          retention_percentile: 78.0,
          ctr_percentile: 82.0,
          subscriber_conversion_per_1k_views: 11.5,
          comparison_window: "lifetime catalog baseline",
        },
        insights: [
          {
            insight_id: "ins_1",
            type: "Retention Pattern",
            title: "Early terminal demonstration tracks +28% retention",
            statement:
              "Videos placing code demonstrations before 00:30 achieve 58.4% mean retention vs 44.1% for late demos.",
            confidence: 0.92,
            recommended_action:
              "Introduce terminal demonstration within the first 25 seconds of your next production.",
            evidence: [
              {
                kind: "FACT",
                statement: "MEASUREMENT: Early demos achieve 58.4% mean retention.",
                metric_refs: [],
                citation_urls: [],
              },
            ],
            created_at: "2026-08-28T00:00:00Z",
          },
        ],
        proposed_experiment: {
          experiment_id: "exp_1",
          channel_id: "croviq_syn_ai_eng_01",
          hypothesis: "Showing early demos improves retention",
          primary_metric: "averageViewPercentage",
          baseline_value: 48.9,
          expected_direction: "INCREASE",
          status: "PROPOSED",
          started_at: null,
          completed_at: null,
          video_ids: [],
          result: null,
          created_by: "alex",
          confidence_summary: "Strong statistical confidence.",
        },
        is_sample_modeled_timeseries: true,
      }),
    });
  });

  await page.route("**/api/channels/youtube/connection", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ connected: false }),
    });
  });

  await page.route("**/api/workspace/agent-settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        leo_prompt: { ...MOCK_PROMPT_CONFIG, agent_id: "leo" },
        alex_prompt: MOCK_PROMPT_CONFIG,
        iris_prompt: { ...MOCK_PROMPT_CONFIG, agent_id: "iris" },
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

  await page.route("**/api/workspace/agent-settings/prompts/*", async (route) => {
    if (route.request().method() === "PUT") {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...MOCK_PROMPT_CONFIG,
          prompt_text: data.prompt_text,
          is_custom: true,
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PROMPT_CONFIG),
      });
    }
  });

  await page.route("**/api/workspace/agent-settings/memory*", async (route) => {
    if (route.request().method() === "POST") {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          name: `projects/demo/locations/us-central1/reasoningEngines/1/memories/new_${Date.now()}`,
          memory_id: `new_${Date.now()}`,
          fact: data.fact,
          scope: { channel_id: "croviq_syn_ai_eng_01" },
          provenance: data.provenance || "Creator instruction",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
    } else if (route.request().method() === "DELETE") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deleted: true }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel_title: "Croviq",
          style_guide: "Evidence-first quantitative statistical analysis",
          memories: MOCK_MEMORIES,
          creator_preferences: [],
          lessons: [],
        }),
      });
    }
  });

  await page.route("**/api/channels/research/config", async (route) => {
    if (route.request().method() === "PUT") {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...MOCK_RESEARCH_CONFIG,
          ...data,
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_RESEARCH_CONFIG),
      });
    }
  });

  await page.route("**/api/channels/research/findings*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FINDINGS),
    });
  });

  let dynamicMessages: Array<{
    message_id: string;
    role: "user" | "assistant";
    content: string;
    tool_executions?: Array<Record<string, unknown>>;
    created_at: string;
  }> = [
    {
      message_id: "msg_1",
      role: "user",
      content: "hi",
      created_at: "2026-08-29T08:00:00Z",
    },
    {
      message_id: "msg_2",
      role: "assistant",
      content: "Hello! I am Alex, your Channel Data Scientist.",
      tool_executions: [],
      created_at: "2026-08-29T08:00:01Z",
    },
  ];

  await page.route("**/api/workspace/agents/*/chat", async (route) => {
    if (route.request().method() === "DELETE") {
      dynamicMessages = [];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          agent_id: "alex",
          messages: [],
        }),
      });
    } else if (route.request().method() === "POST") {
      const data = route.request().postDataJSON();
      const msg = data.message || "";
      let content = "";
      if (msg.includes("table")) {
        content =
          "Here is the cohort breakdown:\n\n| Video Title | Views | Retention | Conversion |\n| :--- | :--- | :--- | :--- |\n| Google GenAI SDK (Part 5) | 23,314 | 64.2% | +334 |\n| Agent Benchmarks | 19,450 | 58.1% | +210 |\n| LangGraph Deep Dive | 27,800 | 61.5% | +380 |\n\n**Key Takeaway**: Agent and developer tooling videos consistently convert higher.";
      } else if (msg.includes("perform") || msg.includes("last video")) {
        content =
          "Here is the performance analysis for your latest published video **Google GenAI SDK Tutorial for Beginners (Part 5)**:\n\n- **Views**: 23,314 (+31.2% vs lifetime channel median of 17,760)\n- **Retention**: 64.2% (+5.8 points vs lifetime channel median of 58.4%)\n- **Subscribers Gained**: +334\n- **CTR**: 8.4%\n\n**Data Scientist Assessment**: Retention was 64.2%, tracking well above channel baseline. Subscriber conversion remained strong at +334 net subscribers.\n\n**Recommendation**: The audience engagement indicates the demonstration structure in this video resonated well. Maintain this hook pacing in your upcoming production.";
      } else {
        content = `Here is my data science analysis for '${msg}':\n\n- **Metric**: Retention correlation r=0.62\n- **Sample Size**: 100 historical videos\n\n**Recommendation**: Test terminal demos within 25s.`;
      }
      const newMsg = {
        message_id: `msg_${Date.now()}`,
        role: "assistant" as const,
        content,
        tool_executions: [
          {
            tool_name: "channel_analytics_inspection",
            goal: "Inspect metrics for latest upload",
            video_id: "vid_syn_100",
            published_at: "2026-08-23T14:30:00Z",
          },
        ],
        created_at: new Date().toISOString(),
      };
      dynamicMessages.push({
        message_id: `msg_u_${Date.now()}`,
        role: "user" as const,
        content: msg,
        created_at: new Date().toISOString(),
      });
      dynamicMessages.push(newMsg);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(newMsg),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          agent_id: "alex",
          messages: dynamicMessages,
        }),
      });
    }
  });
};

const signInAndGoTo = async (page: Page, path: string = "/app") => {
  await mockFirebasePasswordSignIn(page);
  await mockBackendApis(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*");
  await expect(page.locator('[aria-label="Channel KPIs"]')).toBeVisible({ timeout: 15000 });
  if (path !== "/app" && !page.url().endsWith(path)) {
    await page.goto(path);
  }
};

test.describe("Canonical Agent Architecture, Settings, and Ideas Worth Making", () => {
  test("Alex action menu opens and offers Chat and Settings options", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAndGoTo(page, "/app");

    // Click Alex in rail
    const alexBtn = page.getByTestId("btn-agent-menu-alex");
    await expect(alexBtn).toBeVisible();
    await alexBtn.click();

    // Verify Action Menu
    const menu = page.getByTestId("menu-agent-actions-alex");
    await expect(menu).toBeVisible();
    await expect(page.getByTestId("action-chat-alex")).toBeVisible();
    await expect(page.getByTestId("action-settings-alex")).toBeVisible();

    await page.screenshot({ path: "e2e/screenshots/alex-menu-1440x900.png" });
  });

  test("Chat with Alex renders Markdown, tables, and supports Clear Conversation", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAndGoTo(page, "/app");

    // Open chat from Alex rail menu
    await page.getByTestId("btn-agent-menu-alex").click();
    await page.getByTestId("action-chat-alex").click();

    // Verify Chat Drawer
    const chatDrawer = page.getByTestId("agent-chat-drawer");
    await expect(chatDrawer).toBeVisible();
    await expect(page.getByText("Chat with Alex")).toBeVisible();

    // 1. Short answer / latest video question
    const chatInput = page.getByTestId("input-chat-message");
    await chatInput.fill("How did my last video perform?");
    await page.getByTestId("btn-send-chat").click();

    // Assert Markdown bolding, list rendering, and latest video title
    await expect(
      chatDrawer.getByText("Google GenAI SDK Tutorial for Beginners (Part 5)"),
    ).toBeVisible();
    await expect(page.getByText("Data Scientist Assessment")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/alex-chat-short-answer.png" });
    await page.screenshot({ path: "e2e/screenshots/alex-chat-1440x900.png" });

    // 2. In-depth analysis question
    await chatInput.fill("What is unusual about my last 10 videos?");
    await page.getByTestId("btn-send-chat").click();
    await expect(page.getByText("data science analysis")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/alex-chat-analysis.png" });

    // 3. Markdown table rendering
    await chatInput.fill("Show me a comparison table");
    await page.getByTestId("btn-send-chat").click();
    await expect(page.locator("table")).toBeVisible();
    await expect(page.getByText("LangGraph Deep Dive")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/alex-chat-markdown-table.png" });

    // 4. Clear chat conversation
    const clearBtn = page.getByTestId("btn-clear-chat");
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();

    const confirmBtn = page.getByTestId("btn-confirm-clear-chat");
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // Confirm conversation is empty and starter prompts are shown
    await expect(page.getByText("Suggested Prompts")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/alex-chat-cleared.png" });

    // Close chat
    await page.getByTestId("btn-close-chat").click();
    await expect(chatDrawer).not.toBeVisible();
  });
  test("Alex Settings drawer renders Prompt, Memory, and Research tabs without UI artifacts", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAndGoTo(page, "/app");

    // Open settings from Alex rail menu
    await page.getByTestId("btn-agent-menu-alex").click();
    await page.getByTestId("action-settings-alex").click();

    const drawer = page.getByTestId("agent-settings-drawer");
    await expect(drawer).toBeVisible();
    await expect(page.getByText("Alex settings")).toBeVisible();

    // 1. Prompt Tab verification
    await expect(page.getByTestId("tab-prompt")).toBeVisible();
    await expect(page.getByText("Working prompt")).toBeVisible();
    await expect(page.getByTestId("agent-prompt-textarea")).toBeVisible();
    await expect(page.getByTestId("btn-save-prompt")).toBeVisible();
    await expect(page.getByTestId("btn-reset-prompt")).toBeVisible();

    // Ensure no implementation artifacts like 'v1' or 'Custom: True'
    await expect(drawer.getByText("v1")).not.toBeVisible();
    await expect(drawer.getByText("Custom: True")).not.toBeVisible();

    await page.screenshot({ path: "e2e/screenshots/alex-settings-prompt-1440x900.png" });

    // 2. Memory Tab verification (Canonical Google Memory Bank)
    await page.getByTestId("tab-memory").click();
    await expect(page.getByText("Memory Bank")).toBeVisible();
    await expect(page.getByTestId("input-memory-search")).toBeVisible();
    await expect(page.getByTestId("btn-add-memory-toggle")).toBeVisible();
    await expect(page.getByTestId("memory-card").first()).toBeVisible();

    // Ensure no fake 'historical_analysis.mp4'
    await expect(drawer.getByText("historical_analysis.mp4")).not.toBeVisible();

    await page.screenshot({ path: "e2e/screenshots/alex-settings-memory-1440x900.png" });

    // 3. Research Tab verification
    await page.getByTestId("tab-research").click();
    await expect(page.getByText("Background research")).toBeVisible();
    await expect(page.getByTestId("select-research-cadence")).toBeVisible();
    await expect(page.getByTestId("checkbox-research-enabled")).toBeVisible();
    await expect(page.getByTestId("btn-save-research")).toBeVisible();

    await page.screenshot({ path: "e2e/screenshots/alex-settings-research-1440x900.png" });

    // Close settings
    await page.getByTestId("btn-close-settings").click();
    await expect(drawer).not.toBeVisible();
  });

  test("Captures full Home viewport screenshot at 1600x900", async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 900 });
    await signInAndGoTo(page, "/app");
    await expect(page.getByRole("heading", { name: "Channel Performance" })).toBeVisible();
    await expect(page.getByText("Ideas Worth Making")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/home-1600x900.png" });
  });

  test("Captures full Home viewport screenshot at 1440x900", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAndGoTo(page, "/app");
    await expect(page.getByRole("heading", { name: "Channel Performance" })).toBeVisible();
    await expect(page.getByText("Ideas Worth Making")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/home-1440x900.png" });
  });

  test("Captures full Home viewport screenshot at 1280x800", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await signInAndGoTo(page, "/app");
    await expect(page.getByRole("heading", { name: "Channel Performance" })).toBeVisible();
    await expect(page.getByText("Ideas Worth Making")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/home-1280x800.png" });
  });
});
