import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const DEMO_EMAIL = "demo@croviq.app";
const SCREENSHOT_DIR = path.resolve("../../docs/screenshots");

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
      body: JSON.stringify({
        workspace_id: "ws_demo",
        owner_user_id: APPROVED_USER.user_id,
        name: "Croviq",
        created_at: "2026-08-26T00:00:00Z",
        updated_at: "2026-08-26T00:00:00Z",
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

  await page.route("**/api/channels/research/config", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workspace_id: "ws_demo",
        channel_id: "croviq_syn_ai_eng_01",
        enabled: true,
        cadence: "EVERY_HOUR",
        prompts: [],
        last_run_at: new Date(Date.now() - 3600000).toISOString(),
        next_run_at: new Date(Date.now() + 3600000).toISOString(),
        updated_at: new Date().toISOString(),
      }),
    });
  });

  await page.route("**/api/channels/*/dashboard*", async (route) => {
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
        period_end: "2026-08-26",
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
            current_value: 340,
            previous_value: 280,
            change_percentage: 21.4,
          },
          {
            metric: "average_retention",
            current_value: 54.2,
            previous_value: 48.9,
            change_percentage: 10.8,
          },
        ],
        trend: Array.from({ length: 28 }, (_, i) => ({
          date: `2026-08-${String(i + 1).padStart(2, "0")}`,
          views: 1200 + i * 25 + (i % 3 === 0 ? 300 : -100),
          previous_views: 1000 + i * 20,
          watch_time_hours: 80 + i * 1.5,
          previous_watch_time_hours: 70 + i * 1.2,
          net_subscribers: 10 + (i % 4),
          previous_net_subscribers: 8 + (i % 3),
        })),
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
            channel_id: "croviq_syn_ai_eng_01",
            type: "RETENTION",
            title: "First demonstration timing tracks retention",
            statement:
              "Videos reaching the first demonstration before 00:30 retain 14.3 percentage points more viewers across n=42 videos.",
            evidence: [
              {
                kind: "FACT",
                statement:
                  "MEASUREMENT: Videos with early demonstrations (<=00:30) average 58.4% retention vs 44.1% for later demonstrations across n=42 videos.",
                metric_refs: ["video:firstDemoSeconds", "video:averageViewPercentage"],
                citation_urls: [],
              },
              {
                kind: "INFERENCE",
                statement:
                  "INTERPRETATION: The association between early demonstration and viewer retention is strong (r=-0.62), but observational rather than established causal certainty.",
                metric_refs: ["analysis:first-demo-retention-correlation"],
                citation_urls: [],
              },
            ],
            confidence: 0.92,
            recommended_action:
              "ACTION: For the next upload, reach the first usable demonstration by 00:25 while holding topic and format stable.",
            created_at: "2026-08-26T00:00:00Z",
          },
        ],
        active_experiment: null,
        proposed_experiment: {
          experiment_id: "exp_1",
          channel_id: "croviq_syn_ai_eng_01",
          hypothesis:
            "Showing the first practical demonstration before 00:30 improves average retention.",
          primary_metric: "averageViewPercentage",
          baseline_value: 48.9,
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
        video_performance: [],
        topic_clusters: [],
        traffic_sources: [],
        is_sample_modeled_timeseries: true,
      }),
    });
  });

  await page.route("**/api/channels/*/findings*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          finding_id: "find_1",
          category: "Foundation Models",
          primary_entity: "Gemini 3.7",
          title: "Gemini 3.7 Flash Hybrid Reasoning and Multimodal Agent Capabilities",
          summary:
            "Gemini 3.7 Flash introduces dynamic thinking budgets for real-time agent loops.",
          why_it_matters:
            "Directly aligns with channel interest in technical architecture walkthroughs.",
          discovered_at: new Date(Date.now() - 3600000).toISOString(),
          source_citations: [
            {
              url: "https://blog.google/technology/ai/gemini-3-7-flash",
              domain: "blog.google",
              title: "Gemini 3.7 Flash Announcement",
            },
          ],
        },
        {
          finding_id: "find_2",
          category: "Agent Workflows",
          primary_entity: "Agent Evaluation",
          title: "Production Agent Evaluation Frameworks for Multi-Turn Tooling",
          summary: "Emerging benchmarks evaluate deterministic tool execution and latency budgets.",
          why_it_matters: "High subscriber conversion topic on DevOps and agent reliability.",
          discovered_at: new Date(Date.now() - 7200000).toISOString(),
          source_citations: [
            {
              url: "https://arxiv.org/abs/2402.00001",
              domain: "arxiv.org",
              title: "Multi-Turn Agent Evaluation",
            },
          ],
        },
      ]),
    });
  });

  await page.route("**/api/workspace/agents/*/chat", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ agent_id: "alex", messages: [] }),
      });
      return;
    }
    const postData = JSON.parse(route.request().postData() || "{}");
    const msg = postData.message || "";
    let reply = "I analyzed your channel data across all 100 historical videos.";
    if (msg.includes("last video")) {
      reply =
        "Your latest upload 'Google GenAI SDK Tutorial for Beginners (Part 5)' achieved 4,500 views (85th percentile) and 58.4% retention (+9.5 percentage points vs channel baseline).";
    } else if (msg.includes("unusual")) {
      reply =
        "Across your last 10 videos, videos with terminal demonstrations within 00:30 retained +14.3 percentage points more viewers compared to slide-heavy intros.";
    } else if (msg.includes("what should I make")) {
      reply =
        "I recommend an architecture deep-dive on 'Gemini 3.7 Flash Dynamic Thinking Budgets'—this aligns with your top content pillar and has high topical demand.";
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        message_id: `msg_${Date.now()}`,
        role: "assistant",
        content: reply,
        tool_executions: [
          {
            tool_name: "channel_analytics_inspection",
            goal: "Query historical video catalog and retention curves",
          },
        ],
        created_at: new Date().toISOString(),
      }),
    });
  });
};

test.describe("Foundation Verification & Visual Journey", () => {
  test("executes complete foundation visual review and user journey", async ({ page }) => {
    if (!fs.existsSync(SCREENSHOT_DIR)) {
      fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    }

    await mockFirebasePasswordSignIn(page);
    await mockBackendApis(page);

    // 1. Sign In via /login
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/app*");
    await page.waitForSelector('[aria-label="Channel KPIs"]', { timeout: 15000 });
    await page.waitForTimeout(500);

    // 2. Viewport Screenshots (1600, 1440, 1280)
    await page.setViewportSize({ width: 1600, height: 900 });
    await page.waitForTimeout(500);
    const path1600 = path.join(SCREENSHOT_DIR, "home_1600x900.png");
    await page.screenshot({ path: path1600 });
    expect(fs.existsSync(path1600)).toBe(true);

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(500);
    const path1440 = path.join(SCREENSHOT_DIR, "home_1440x900.png");
    await page.screenshot({ path: path1440 });
    expect(fs.existsSync(path1440)).toBe(true);

    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForTimeout(500);
    const path1280 = path.join(SCREENSHOT_DIR, "home_1280x800.png");
    await page.screenshot({ path: path1280 });
    expect(fs.existsSync(path1280)).toBe(true);

    // Reset to 1440x900
    await page.setViewportSize({ width: 1440, height: 900 });

    // 3. Ask Alex: 3 Questions
    const alexBtn = page.getByTestId("btn-agent-menu-alex");
    await alexBtn.click();
    await page.getByTestId("action-chat-alex").click();
    await page.waitForSelector('[data-testid="input-chat-message"]', { timeout: 8000 });

    // Q1
    await page.fill('[data-testid="input-chat-message"]', "How did my last video perform?");
    await page.click('[data-testid="btn-send-chat"]');
    await page.waitForTimeout(800);

    // Q2
    await page.fill(
      '[data-testid="input-chat-message"]',
      "What is unusual about my last 10 videos?",
    );
    await page.click('[data-testid="btn-send-chat"]');
    await page.waitForTimeout(800);

    // Q3
    await page.fill('[data-testid="input-chat-message"]', "What should I make next and why?");
    await page.click('[data-testid="btn-send-chat"]');
    await page.waitForTimeout(800);

    // Close Alex chat
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);

    // 4. Open Ideas Worth Making
    const ideasSection = page.locator('h3:has-text("Ideas Worth Making")');
    await expect(ideasSection).toBeVisible();

    // 5. New Project & Upload Flow
    const newProjectBtn = page
      .locator('button:has-text("Upload video"), a[href*="/new"], button:has-text("New Project")')
      .first();
    await newProjectBtn.click();
    await page.waitForURL("**/new");

    // Mock upload endpoints for clean browser test
    await page.route("**/api/uploads", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: "prod_foundation_001",
          upload_id: "upl_foundation_001",
          upload_url: "http://127.0.0.1:5173/mock-gcs/upload.mp4",
          expires_at: new Date(Date.now() + 1800000).toISOString(),
        }),
      });
    });

    await page.route("http://127.0.0.1:5173/mock-gcs/**", async (route) => {
      await route.fulfill({ status: 200, body: "" });
    });

    await page.route("**/api/uploads/upl_foundation_001/complete", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          production_id: "prod_foundation_001",
          status: "uploaded",
        }),
      });
    });

    // Select a video file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "raw_tutorial.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.from("mock-video-bytes-for-test"),
    });

    await expect(page.getByText("raw_tutorial.mp4")).toBeVisible();
    const startBtn = page.getByRole("button", { name: "Start production" });
    await expect(startBtn).toBeVisible();
    await startBtn.click();

    // Verify it transitions to Editor
    await expect(page).toHaveURL(/\/productions\/prod_foundation_001\/editor/, { timeout: 10000 });
  });
});
