import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEMO_EMAIL = "demo@croviq.app";
const BASE_URL = "https://app.croviq.app";
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
    primary_entity: "Gemini 3.7",
    title: "Gemini 3.7 Flash Hybrid Reasoning and Multimodal Agent Capabilities",
    summary:
      "Google released Gemini 3.7 Flash featuring dynamic thinking budgets, native multimodal reasoning, and Python code execution tool grounding for real-time applications.",
    why_it_matters:
      "Your tutorial videos on LLM agent architectures and Gemini tooling historically outperform channel baseline retention by 28%.",
    relevance_score: 0.95,
    freshness_score: 0.96,
    opportunity_score: 0.95,
    topic_cluster: "foundation-models",
    source_citations: [
      {
        url: "https://ai.google.dev/gemini-api/docs/models/gemini",
        title: "Gemini Models & Capabilities Overview — Google AI Developers",
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
    primary_entity: "Agent Evaluation",
    title: "Production Agent Evaluation Frameworks for Multi-Turn Tooling",
    summary:
      "Emerging benchmarks for multi-agent tool execution evaluate deterministic schema adherence, latency budgets, and cut-safety in continuous media processing.",
    why_it_matters:
      "Engineering audiences on your channel show 43% higher subscriber conversion on architectural deep-dives with reproducible benchmarks.",
    relevance_score: 0.9,
    freshness_score: 0.88,
    opportunity_score: 0.89,
    topic_cluster: "agent-workflows",
    source_citations: [
      {
        url: "https://cloud.google.com/products/agent-builder",
        title: "Google Cloud Agent Builder and Evaluation Standards",
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
    primary_entity: "WebCodecs",
    title: "WebCodecs Real-Time Streaming Video Pipeline for AI Media Workflows",
    summary:
      "Hardware-accelerated browser video frame decoding with WebCodecs enables real-time LLM video frame sampling and zero-latency timeline previews.",
    why_it_matters:
      "Video creator workflows combining high-speed browser rendering with AI models drive high engagement and retention on deep-dive tutorials.",
    relevance_score: 0.88,
    freshness_score: 0.92,
    opportunity_score: 0.9,
    topic_cluster: "multimodal-systems",
    source_citations: [
      {
        url: "https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API",
        title: "WebCodecs API Standards — MDN Web Docs",
        domain: "developer.mozilla.org",
      },
    ],
    topic_fingerprint: "fp_3",
    discovered_at: "2026-08-28T06:00:00Z",
    lifecycle: "NEW",
  },
];

const MOCK_DASHBOARD = {
  channel: {
    channel_id: "croviq_syn_ai_eng_01",
    title: "Croviq",
    custom_url: "@croviq",
    subscriber_count: 51317,
    video_count: 100,
    view_count: 12450000,
    thumbnail_url: "https://placehold.co/128x128/1e293b/f8fafc?text=AI",
  },
  period_days: 28,
  kpis: [
    { metric: "views", current_value: 421500, previous_value: 385000, change_percentage: 9.48 },
    {
      metric: "watch_time_hours",
      current_value: 32400.5,
      previous_value: 29800.0,
      change_percentage: 8.73,
    },
    {
      metric: "net_subscribers",
      current_value: 3420,
      previous_value: 2950,
      change_percentage: 15.93,
    },
    {
      metric: "average_retention",
      current_value: 58.4,
      previous_value: 54.2,
      change_percentage: 7.75,
    },
  ],
  trend: [
    { date: "2026-08-01", views: 12400, net_subscribers: 95, average_retention: 56.2 },
    { date: "2026-08-07", views: 14100, net_subscribers: 110, average_retention: 57.8 },
    { date: "2026-08-14", views: 16800, net_subscribers: 140, average_retention: 59.1 },
    { date: "2026-08-21", views: 18200, net_subscribers: 155, average_retention: 60.4 },
    { date: "2026-08-28", views: 21500, net_subscribers: 180, average_retention: 61.2 },
  ],
  latest_video: {
    video_id: "vid_086",
    title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
    published_at: "2026-08-26T14:00:00Z",
    views: 23300,
    net_subscribers: 412,
    retention_percentage: 64.2,
    view_delta_percentage: 18.0,
    subscriber_conversion_delta_percentage: 24.5,
  },
  video_performance: [
    {
      video_id: "v1",
      title: "Google GenAI SDK Tutorial for Beginners (Part 5)",
      views: 23300,
      ctr_percentage: 9.1,
      discovery_metric: "search",
      discovery_value: 45.0,
      average_retention: 64.2,
      subscribers_gained: 412,
      content_pillar: "Agent Engineering",
    },
    {
      video_id: "v2",
      title: "Agent Memory Tutorial — LangGraph & PostgreSQL Store",
      views: 19800,
      ctr_percentage: 7.8,
      discovery_metric: "suggested",
      discovery_value: 52.0,
      average_retention: 68.4,
      subscribers_gained: 345,
      content_pillar: "Agent Engineering",
    },
    {
      video_id: "v3",
      title: "Vertex AI Deployment Architecture & Cloud Run CI/CD",
      views: 16400,
      ctr_percentage: 6.4,
      discovery_metric: "search",
      discovery_value: 60.0,
      average_retention: 61.2,
      subscribers_gained: 280,
      content_pillar: "Cloud & DevOps",
    },
    {
      video_id: "v4",
      title: "WebCodecs Video Editor in Browser with WebAssembly",
      views: 14200,
      ctr_percentage: 8.2,
      discovery_metric: "browse",
      discovery_value: 38.0,
      average_retention: 57.5,
      subscribers_gained: 215,
      content_pillar: "Multimodal Systems",
    },
    {
      video_id: "v5",
      title: "OpenTelemetry Distributed Tracing for Multi-Agent Loops",
      views: 11900,
      ctr_percentage: 5.9,
      discovery_metric: "search",
      discovery_value: 48.0,
      average_retention: 59.8,
      subscribers_gained: 190,
      content_pillar: "Evaluation & Observability",
    },
    {
      video_id: "v6",
      title: "Gemini API Basics — Quickstart & Python Setup",
      views: 9800,
      ctr_percentage: 8.5,
      discovery_metric: "browse",
      discovery_value: 41.0,
      average_retention: 42.1,
      subscribers_gained: 85,
      content_pillar: "Developer Tooling",
    },
  ],
  topic_clusters: [
    {
      cluster_id: "c1",
      label: "Agent Engineering",
      video_count: 28,
      total_views: 480000,
      average_retention: 62.4,
      performance_ratio: 1.25,
    },
    {
      cluster_id: "c2",
      label: "Multimodal Systems",
      video_count: 18,
      total_views: 310000,
      average_retention: 58.1,
      performance_ratio: 1.12,
    },
  ],
  traffic_sources: [
    { source: "youtube_search", views: 185000, percentage: 43.9, conversion_rate: 0.042 },
    { source: "suggested_videos", views: 142000, percentage: 33.7, conversion_rate: 0.038 },
    { source: "browse_features", views: 64000, percentage: 15.2, conversion_rate: 0.029 },
    { source: "direct_or_other", views: 30500, percentage: 7.2, conversion_rate: 0.021 },
  ],
  insights: [
    {
      insight_id: "ins_1",
      channel_id: "croviq_syn_ai_eng_01",
      type: "RETENTION",
      title: "First-Demonstration Timing Drives 28% Retention Gain",
      statement:
        "Videos showing practical code execution before 00:30 achieve 68.4% average retention compared to 42.1% when demos start after 01:30.",
      confidence: 0.94,
      recommended_action:
        "Place working UI / execution within the opening 20 seconds of your next video.",
      evidence: [
        {
          kind: "CORRELATION",
          statement:
            "Strong negative correlation (r = -0.92) between demo start latency and audience drop-off.",
        },
      ],
      created_at: "2026-08-28T06:00:00Z",
    },
  ],
  active_experiment: null,
  proposed_experiment: {
    experiment_id: "exp_1",
    channel_id: "croviq_syn_ai_eng_01",
    hypothesis:
      "Showing the first practical demonstration before 00:30 improves average retention on technical deep-dive videos.",
    primary_metric: "averageViewPercentage",
    baseline_value: 58.4,
    expected_direction: "INCREASE",
    status: "PROPOSED",
    started_at: null,
    completed_at: null,
    video_ids: [],
    result: null,
    created_by: "alex",
    confidence_summary:
      "94% statistical confidence based on historical retention curves across 28 tutorial videos.",
  },
};

async function main() {
  console.log("Launching headless browser for live production verification...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  const consoleLogs = [];
  const failedRequests = [];

  page.on("console", (msg) => {
    console.log(`[Browser Console ${msg.type()}]:`, msg.text());
    if (msg.type() === "error") {
      consoleLogs.push(msg.text());
    }
  });
  page.on("pageerror", (err) => {
    console.log("[Browser Page Error]:", err.message, err.stack);
    consoleLogs.push(err.message);
  });

  page.on("requestfailed", (req) => {
    console.log(`[Failed Request]: ${req.method()} ${req.url()} (${req.failure()?.errorText})`);
    failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText})`);
  });

  // Mock identity platform verifyPassword & lookup responses
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

  // Intercept backend APIs for authenticated UI rendering on live production
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

  await page.route("**/api/channels/sample/dashboard*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_DASHBOARD),
    });
  });

  await page.route("**/api/channels/youtube/connection", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ connected: false, channel_id: null, channel_title: null }),
    });
  });

  await page.route("**/api/channels/research/findings*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_FINDINGS),
    });
  });

  console.log("Navigating to login page on live production:", `${BASE_URL}/login`);
  await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill("valid-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  console.log("Waiting for navigation to /app on live production...");
  await page.waitForURL("**/app*", { timeout: 20000 });
  await page.waitForTimeout(2000);

  const outDir = path.resolve("e2e/screenshots/production");
  fs.mkdirSync(outDir, { recursive: true });

  // 1. Live Overview (1440)
  console.log("Waiting for Overview heading...");
  await page.getByRole("heading", { name: "Croviq" }).waitFor({ state: "visible" });
  await page.waitForTimeout(1000);
  console.log("Capturing live overview screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-overview-1440.png"), fullPage: false });

  // 2. Live Performance (1440)
  console.log("Navigating to Performance tab...");
  await page.locator('nav[aria-label="Dashboard sections"]').getByText("Performance").click();
  await page.waitForTimeout(2000);
  console.log("Capturing live performance screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-performance-1440.png"), fullPage: false });

  // 3. Live Experiments (1440)
  console.log("Navigating to Experiments tab...");
  await page.locator('nav[aria-label="Dashboard sections"]').getByText("Experiments").click();
  await page.waitForTimeout(2000);
  console.log("Capturing live experiments screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-experiments-1440.png"), fullPage: false });
  console.log("Navigating to /projects/new via New Project button...");
  await page.getByRole("button", { name: "New Project" }).click();
  await page.waitForTimeout(1500);
  console.log("Capturing live new project screenshot (1440)...");
  await page.screenshot({ path: path.join(outDir, "live-new-project-1440.png"), fullPage: false });

  // 5. Live New Project 1280
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(1000);
  console.log("Capturing live new project screenshot (1280)...");
  await page.screenshot({ path: path.join(outDir, "live-new-project-1280.png"), fullPage: false });

  // 6. Live Release Gate (1600)
  console.log("Navigating to live /productions/prod_0b7657f515ae/release...");
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.evaluate(() => {
    window.history.pushState(null, "", "/productions/prod_0b7657f515ae/release");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await page.waitForSelector("[data-testid='release-workspace']", { timeout: 15000 });
  await page.waitForTimeout(2000);
  console.log("Capturing live release QA screenshot...");
  await page.screenshot({ path: path.join(outDir, "live-release-qa-1600.png"), fullPage: false });

  console.log("Live Console Errors:", consoleLogs);
  console.log("Live Failed Requests:", failedRequests);

  await browser.close();
  console.log("LIVE PRODUCTION SCREENSHOTS CAPTURED SUCCESSFULLY!");
}

main().catch((err) => {
  console.error("Failed to capture live screenshots:", err);
  process.exit(1);
});
