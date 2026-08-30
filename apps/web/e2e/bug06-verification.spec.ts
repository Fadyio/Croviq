import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";

const REAL_ACCEPTED_FINDINGS = [
  {
    finding_id: "fnd_mcp_01",
    run_id: "ws_demo_user_123:croviq_syn_ai_eng_01:2026-08-30T06:50:58.060801+00:00",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Agent Workflows",
    title:
      "Architecting Centralized Tool Registries: MCP Streamable HTTP (SSE) vs Stdio in FastAPI",
    summary:
      "The Model Context Protocol specification clarifies architectural boundaries between local Stdio transport and remote Streamable HTTP (Server-Sent Events) transports, enabling engineers to centralize shared tool registries across multiple distributed agents.",
    why_it_matters:
      "Directly resolves a core friction point for senior backend developers building multi-agent systems in LangGraph and FastAPI: eliminating repetitive tool definition maintenance across isolated sub-agents.",
    relevance_score: 0.96,
    freshness_score: 0.9,
    opportunity_score: 0.95,
    topic_cluster: "agent-architecture",
    primary_entity: "Model Context Protocol",
    source_citations: [
      {
        url: "https://modelcontextprotocol.io/specification/architecture",
        title: "Model Context Protocol Architecture and Transports Specification",
        domain: "modelcontextprotocol.io",
        grounding_metadata: { role: "primary_source", ecosystem: "ENGINEERING_DOCS" },
      },
      {
        url: "https://towardsdatascience.com/scaling-agentic-tools-with-model-context-protocol",
        title: "Scaling Complex Agentic Tool Plumbing with Model Context Protocol",
        domain: "towardsdatascience.com",
        grounding_metadata: { role: "discovery_signal", ecosystem: "GENERAL_WEB" },
      },
    ],
    topic_fingerprint: "fp_mcp_01",
    discovered_at: "2026-08-30T06:51:24.000000Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_sglang_02",
    run_id: "ws_demo_user_123:croviq_syn_ai_eng_01:2026-08-30T06:50:58.060801+00:00",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Foundation Models",
    title: "SGLang vs vLLM: RadixAttention Benchmarks for Multi-Agent Loops and Agentic RAG",
    summary:
      "Recent production benchmarks highlight SGLang's RadixAttention delivering up to 6.4x throughput and TTFT gains over traditional PagedAttention architectures in prefix-heavy multi-agent loops.",
    why_it_matters:
      "Channel benchmarks and tool comparisons consistently generate peak audience retention (60%+). AI engineers in the channel's 72%+ desktop audience require empirical data to decide serving stack migrations.",
    relevance_score: 0.94,
    freshness_score: 0.91,
    opportunity_score: 0.93,
    topic_cluster: "inference-engines",
    primary_entity: "SGLang",
    source_citations: [
      {
        url: "https://particula.tech/blog/sglang-vs-vllm",
        title: "SGLang vs vLLM in 2026: Benchmarks and When to Use Each",
        domain: "particula.tech",
        grounding_metadata: { role: "primary_source", ecosystem: "REDDIT" },
      },
      {
        url: "https://spheron.network/blog/vllm-vs-sglang-benchmarks",
        title: "vLLM vs SGLang Benchmarks: Architecture and Production Latency Analysis",
        domain: "spheron.network",
        grounding_metadata: { role: "discovery_signal", ecosystem: "GENERAL_WEB" },
      },
    ],
    topic_fingerprint: "fp_sglang_02",
    discovered_at: "2026-08-30T06:51:24.000000Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_gha_03",
    run_id: "ws_demo_user_123:croviq_syn_ai_eng_01:2026-08-30T06:50:58.060801+00:00",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Cloud Infrastructure",
    title:
      "Automated Multi-Stage CI/CD for FastAPI AI Microservices on Cloud Run via GitHub Actions",
    summary:
      "A complete DevOps pipeline walkthrough utilizing the official google-github-actions/deploy-cloudrun action with Workload Identity Federation, automated Docker artifact builds, and canary traffic splitting.",
    why_it_matters:
      "DevOps pipelines represent one of the channel's proven high-performing formats (e.g. 'Autonomous Multi-Agent DevOps Team' hit 60.6% retention).",
    relevance_score: 0.93,
    freshness_score: 0.89,
    opportunity_score: 0.92,
    topic_cluster: "devops-cicd",
    primary_entity: "GitHub Actions",
    source_citations: [
      {
        url: "https://github.com/google-github-actions/deploy-cloudrun",
        title: "Deploy to Cloud Run GitHub Action",
        domain: "github.com",
        grounding_metadata: { role: "primary_source", ecosystem: "PRIMARY_VENDOR" },
      },
      {
        url: "https://fastapicloud.com/docs/deployments/github-actions",
        title: "FastAPI Automated CI/CD Pipelines and GitHub Integration",
        domain: "fastapicloud.com",
        grounding_metadata: { role: "discovery_signal", ecosystem: "GITHUB" },
      },
    ],
    topic_fingerprint: "fp_gha_03",
    discovered_at: "2026-08-30T06:51:24.000000Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_vllm_04",
    run_id: "ws_demo_user_123:croviq_syn_ai_eng_01:2026-08-30T06:50:58.060801+00:00",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Developer Tooling",
    title: "Slashing Agent Latency: Eagle3 Speculative Decoding on vLLM for Code-Heavy Workflows",
    summary:
      "Empirical evaluations demonstrate that integrating Eagle3 speculative decoding head within vLLM achieves a 19.4% cost reduction per 1M tokens and up to 1.8x decode speedup under high concurrency.",
    why_it_matters:
      "Autonomous coding agents frequently stall during sequential token generation steps. A practical engineering deep-dive with terminal latency traces aligns directly with channel benchmarks.",
    relevance_score: 0.91,
    freshness_score: 0.88,
    opportunity_score: 0.9,
    topic_cluster: "inference-optimization",
    primary_entity: "vLLM",
    source_citations: [
      {
        url: "https://redhat.com/en/blog/accelerating-llm-inference-eagle3-speculative-decoding-vllm",
        title: "Accelerating LLM Inference: Benchmarking Eagle3 Speculative Decoding in vLLM",
        domain: "redhat.com",
        grounding_metadata: { role: "primary_source", ecosystem: "HACKER_NEWS" },
      },
    ],
    topic_fingerprint: "fp_vllm_04",
    discovered_at: "2026-08-30T06:51:24.000000Z",
    lifecycle: "NEW",
  },
];

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
    } else if (url.includes("accounts:lookup")) {
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
    } else {
      await route.continue();
    }
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
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(REAL_ACCEPTED_FINDINGS),
    });
  });
};

test.describe("Bug 6 Verification: Diverse Ecosystem Grounded Research in UI", () => {
  test("1600x900: AlexRail renders diverse multi-ecosystem findings cleanly with no console errors", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    page.on("requestfailed", (req) => {
      if (!req.url().includes("favicon")) {
        failedRequests.push(`${req.method()} ${req.url()}`);
      }
    });

    await setupPageRoutes(page);

    await page.setViewportSize({ width: 1600, height: 900 });
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/app*");
    await page.waitForSelector("aside");
    await expect(page.locator("aside article").first()).toBeVisible({ timeout: 10000 });

    // Verify top 3 primary entities are distinct and channel-relevant
    const entities = await page.locator("aside article:has(h4) span.uppercase").allTextContents();
    expect(entities.length).toBe(3);
    const upperEntities = entities.map((e) => e.toUpperCase());
    expect(new Set(upperEntities).size).toBe(3);
    expect(upperEntities).toContain("MODEL CONTEXT PROTOCOL");
    expect(upperEntities).toContain("SGLANG");
    expect(upperEntities).toContain("GITHUB ACTIONS");

    // Verify Why fits and Why now are present
    const whyFits = page.locator("aside article", { hasText: "Why it fits:" });
    await expect(whyFits.first()).toBeVisible();

    const whyNow = page.locator("aside article", { hasText: "Why now:" });
    await expect(whyNow.first()).toBeVisible();

    // Verify sources button is clickable and toggles domain popover
    const sourcesBtn = page
      .locator("aside article button", { hasText: /modelcontextprotocol\.io/i })
      .first();
    await expect(sourcesBtn).toBeVisible();
    await sourcesBtn.click();
    await expect(
      page.locator("aside article a", { hasText: "modelcontextprotocol.io" }).first(),
    ).toBeVisible();

    await page.screenshot({ path: "docs/screenshots/acceptance/home-1600x900.png" });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("1440x900: Drawer opens and renders all multi-ecosystem research findings", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    page.on("requestfailed", (req) => {
      if (!req.url().includes("favicon")) {
        failedRequests.push(`${req.method()} ${req.url()}`);
      }
    });

    await setupPageRoutes(page);

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/app*");
    await page.waitForSelector("aside");

    const viewAllBtn = page.getByRole("button", { name: /View all .* findings/i });
    await expect(viewAllBtn).toBeVisible();
    await viewAllBtn.click();

    const drawer = page.locator('[role="dialog"]');
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("Ideas Worth Making")).toBeVisible();

    // Verify all 4 findings are present in drawer
    await expect(drawer.getByText("Architecting Centralized Tool Registries")).toBeVisible();
    await expect(drawer.getByText("SGLang vs vLLM: RadixAttention Benchmarks")).toBeVisible();
    await expect(
      drawer.getByText("Automated Multi-Stage CI/CD for FastAPI AI Microservices"),
    ).toBeVisible();
    await expect(
      drawer.getByText("Slashing Agent Latency: Eagle3 Speculative Decoding"),
    ).toBeVisible();

    await page.screenshot({ path: "docs/screenshots/acceptance/all-findings-1440x900.png" });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });

  test("1280x800: Responsive layout on compact desktop displays ideas cleanly", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    page.on("requestfailed", (req) => {
      if (!req.url().includes("favicon")) {
        failedRequests.push(`${req.method()} ${req.url()}`);
      }
    });

    await setupPageRoutes(page);

    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/app*");
    await page.waitForSelector("aside");
    await expect(page.locator("aside article:has(h4)").first()).toBeVisible({ timeout: 10000 });
    const findingArticles = page.locator("aside article:has(h4)");
    await expect(findingArticles).toHaveCount(3);
    await page.screenshot({ path: "docs/screenshots/acceptance/home-1280x800.png" });

    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });
});
