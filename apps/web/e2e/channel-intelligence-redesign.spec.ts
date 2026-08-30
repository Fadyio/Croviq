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

  const chatHistory: Record<string, Record<string, unknown>[]> = {
    alex: [],
    leo: [],
    iris: [],
  };

  await page.route("**/api/workspace/agents/*/chat", async (route) => {
    const url = route.request().url();
    const match = url.match(/\/agents\/(alex|leo|iris)\/chat/);
    const agent = match ? match[1] : "alex";

    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          agent_id: agent,
          messages: chatHistory[agent] || [],
        }),
      });
      return;
    }

    const reqBody = route.request().postDataJSON();
    const userText = reqBody?.message || "";
    const userMsg = {
      message_id: `msg_user_${Date.now()}`,
      role: "user",
      content: userText,
      created_at: new Date().toISOString(),
    };
    chatHistory[agent].push(userMsg);

    let assistantReply = "";
    let toolExecutions: Record<string, unknown>[] = [];
    let artifact: Record<string, unknown> | null = null;

    if (agent === "alex") {
      if (
        userText.toLowerCase().includes("correlation") ||
        userText.toLowerCase().includes("calculate")
      ) {
        toolExecutions = [
          {
            tool_name: "python_code_execution",
            goal: "Calculate Pearson correlation between demo timing and retention",
          },
        ];
        artifact = {
          type: "statistical_analysis",
          metrics: {
            sample_size: 100,
            correlation_r: -0.68,
            baseline_retention: "58.4%",
          },
        };
        assistantReply =
          "I executed the statistical correlation calculation across your 100-video history. Demonstrations starting within 00:30 correlate with +14.3% retention advantage (r = -0.68).";
      } else {
        toolExecutions = [
          {
            tool_name: "channel_analytics_inspection",
            goal: "Query latest upload performance and subscriber conversion",
          },
        ];
        artifact = {
          type: "video_summary",
          metrics: {
            views: "23,314",
            retention: "54.8%",
            subscribers: "+303",
          },
        };
        assistantReply =
          "Your latest upload **Google GenAI SDK Tutorial (Part 5)** achieved 23,314 views with 54.8% retention and +303 subscribers.";
      }
    } else if (agent === "leo") {
      toolExecutions = [
        {
          tool_name: "dialogue_decision_inspector",
          goal: "Inspect timeline cuts and audio phrasing",
        },
      ];
      assistantReply =
        "I analyzed the timeline dialogue cuts. We can tighten the introduction at 00:18 and preserve the strongest explanation from 01:12 to 01:45.";
    } else {
      toolExecutions = [
        {
          tool_name: "quality_control_verifier",
          goal: "Verify audio loudness (-16 LUFS) and caption timing",
        },
      ];
      assistantReply =
        "I verified the rendered master. Target loudness is -16.1 LUFS, speech captions are synchronized with zero frame gaps, and all release criteria pass.";
    }

    const assistantMsg = {
      message_id: `msg_asst_${Date.now()}`,
      role: "assistant",
      content: assistantReply,
      tool_executions: toolExecutions,
      structured_artifact: artifact,
      created_at: new Date().toISOString(),
    };
    chatHistory[agent].push(assistantMsg);

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(assistantMsg),
    });
  });

  let alexPromptText = "You are Alex, Croviq's senior Channel Data Scientist and research partner.";

  await page.route("**/api/workspace/agent-settings/prompt/*", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/reset")) {
      alexPromptText = "You are Alex, Croviq's senior Channel Data Scientist and research partner.";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          agent_id: "alex",
          prompt_text: alexPromptText,
          version: 1,
          updated_at: new Date().toISOString(),
          is_custom: false,
        }),
      });
      return;
    }
    const body = route.request().postDataJSON();
    alexPromptText = body?.prompt_text || alexPromptText;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        agent_id: "alex",
        prompt_text: alexPromptText,
        version: 2,
        updated_at: new Date().toISOString(),
        is_custom: true,
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
          prompt_text: alexPromptText,
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        leo_prompt: {
          agent_id: "leo",
          prompt_text: "You are Leo, Croviq's Video Editor.",
          version: 1,
          updated_at: "2026-08-28T00:00:00Z",
          is_custom: false,
        },
        iris_prompt: {
          agent_id: "iris",
          prompt_text: "You are Iris, Croviq's Quality Control gatekeeper.",
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

  await page.route("**/api/workspace/agent-settings/memory*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        channel_title: "Croviq",
        style_guide: "Evidence-first quantitative statistical analysis.",
        creator_preferences: [
          "Prefers early demonstrations in the first 30 seconds.",
          "Track subscriber conversion per 1,000 views.",
        ],
        lessons: [
          {
            topic: "Early demonstration timing tracks viewer retention",
            content:
              "Videos with technical demonstrations in the first 30 seconds average 58.4% retention.",
            learned_from: "100-video historical channel dataset",
          },
          {
            topic: "DevOps & Tooling tutorial subscriber conversion",
            content:
              "Hands-on workflow architectures drive +43% higher conversion than theoretical explanations.",
            learned_from: "Audience analytics audit",
          },
        ],
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
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/app*");
  if (path !== "/app" && !page.url().endsWith(path)) {
    await page.goto(path);
  }
};

test.describe("Home / Channel Intelligence Redesign", () => {
  test("Single unified Home dashboard on /app renders KPIs, dominant trend chart, and Alex rail", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");

    // Check header & channel title
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();

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

    // Check dominant trend chart
    await expect(page.getByRole("heading", { name: "Channel Performance" })).toBeVisible();

    // Check Alex rail is present on the right
    await expect(page.getByRole("heading", { name: "Alex", exact: true })).toBeVisible();
    await expect(page.getByRole("complementary").getByText("Data Scientist")).toBeVisible();
    await expect(page.getByText("Ideas Worth Making")).toBeVisible();
  });

  test("Legacy /app/performance and /app/experiments routes redirect cleanly to canonical /app", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");
    await expect(page).toHaveURL(/\/app$/);

    await page.goto("/app/performance");
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();

    await page.goto("/app/experiments");
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByRole("heading", { name: "Croviq", exact: true })).toBeVisible();
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
  test("Ideas Worth Making feed shows max 3 default cards and opens all findings drawer", async ({
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
    await expect(page.getByRole("heading", { name: "Ideas Worth Making" }).last()).toBeVisible();
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

  test("agent workspaces provide real chat with tool execution telemetry, artifacts, and persistence across refresh", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app");

    // Open Alex chat
    await page.getByTestId("btn-team-selector").click();
    await page
      .getByText("Autonomous Production Team", { exact: true })
      .locator("..")
      .getByRole("button", { name: /^Alex / })
      .click();

    await expect(page).toHaveURL(/\/app\/agents\/alex$/);
    await expect(page.getByRole("heading", { name: "Alex", exact: true })).toBeVisible();

    // Send analytical message
    const chatInput = page.getByPlaceholder(/Ask Alex a question/i);
    await chatInput.fill("How did my last video perform?");
    await page.getByRole("button", { name: "Send" }).click();

    // Verify real agent response with tool telemetry and artifact
    await expect(page.getByText("Google GenAI SDK Tutorial (Part 5)")).toBeVisible();
    await expect(page.getByText("channel_analytics_inspection")).toBeVisible();
    await expect(page.getByText("Analytical Artifact: video_summary")).toBeVisible();

    // Send Python calculation query
    await chatInput.fill("Calculate the correlation between demo timing and retention.");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(page.getByText("python_code_execution")).toBeVisible();
    await expect(page.getByText("correlation r")).toBeVisible();

    // Refresh and verify conversation persists
    await page.reload();
    await expect(page).toHaveURL(/\/app\/agents\/alex$/);
    await expect(page.getByText("python_code_execution")).toBeVisible();

    // Switch to Leo
    await page.getByTestId("btn-team-selector").click();
    await page
      .getByText("Autonomous Production Team", { exact: true })
      .locator("..")
      .getByRole("button", { name: /^Leo / })
      .click();

    await expect(page).toHaveURL(/\/app\/agents\/leo$/);
    await expect(page.getByRole("heading", { name: "Leo", exact: true })).toBeVisible();
    const leoInput = page.getByPlaceholder(/Ask Leo a question/i);
    await leoInput.fill("Where is the strongest hook?");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.getByText("dialogue_decision_inspector")).toBeVisible();

    // Switch to Iris
    await page.getByTestId("btn-team-selector").click();
    await page
      .getByText("Autonomous Production Team", { exact: true })
      .locator("..")
      .getByRole("button", { name: /^Iris / })
      .click();

    await expect(page).toHaveURL(/\/app\/agents\/iris$/);
    await expect(page.getByRole("heading", { name: "Iris", exact: true })).toBeVisible();
    const irisInput = page.getByPlaceholder(/Ask Iris a question/i);
    await irisInput.fill("Is this video ready for release?");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.getByText("quality_control_verifier")).toBeVisible();
  });

  test("agent workspace settings provides memory search, custom prompt propagation, and reset", async ({
    page,
  }) => {
    await signInAndGoTo(page, "/app/agents/alex");
    await expect(page.getByRole("heading", { name: "Alex", exact: true })).toBeVisible();

    // 1. Open Settings & Memory tab
    await page.getByRole("tab", { name: "Settings & Memory" }).click();
    await expect(page.getByTestId("agent-settings-drawer")).toBeVisible();

    // 2. Switch to Memory view and test search
    await page.getByTestId("tab-memory").click();
    await expect(page.getByTestId("settings-memory-view")).toBeVisible();
    await expect(page.getByTestId("input-memory-search")).toBeVisible();

    // Search for demonstration lessons
    await page.getByTestId("input-memory-search").fill("demonstration");
    await expect(page.getByText(/demonstration/i).first()).toBeVisible();

    // 3. Switch to Prompt view, update prompt, save, and reset
    await page.getByTestId("tab-prompt").click();
    const promptInput = page.getByTestId("agent-prompt-textarea");
    await promptInput.fill("Focus specifically on edge computing and small vision models.");
    await page.getByTestId("btn-save-prompt").click();
    await expect(page.getByText("Saved")).toBeVisible();

    // Reset prompt to default
    await page.getByTestId("btn-reset-prompt").click();
    await expect(page.getByText(/Data Scientist/i).first()).toBeVisible();
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
