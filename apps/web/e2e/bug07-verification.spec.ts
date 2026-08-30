import { expect, test, type Page } from "@playwright/test";
import { APPROVED_USER, DEMO_EMAIL, FIREBASE_ID_TOKEN, WORKSPACE } from "./test-auth-fixtures";

const BUG07_PROVENANCE_FINDINGS = [
  {
    finding_id: "fnd_pydantic_01",
    run_id: "ws_demo_user_123:croviq_syn_ai_eng_01:2026-08-30T07:18:29.726229+00:00",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Agent Workflows",
    title: "PydanticAI v2.35: Type-Safe Production Agent Architecture & Native MCP Integration",
    summary:
      "Pydantic released PydanticAI v2.35, providing typed end-to-end agent loops, first-class Model Context Protocol (MCP) capability injection, dynamic dependency injection, and integrated Logfire OpenTelemetry tracing.",
    why_it_matters:
      "Directly addresses developer pain points with untyped dictionaries in multi-agent orchestration, matching channel benchmarks for production backend frameworks.",
    relevance_score: 0.96,
    freshness_score: 0.94,
    opportunity_score: 0.95,
    topic_cluster: "agent-architecture",
    primary_entity: "Pydantic",
    source_citations: [
      {
        url: "https://github.com/pydantic/pydantic-ai",
        title: "pydantic/pydantic-ai: Type-safe Agent Framework",
        domain: "github.com",
        grounding_metadata: { role: "primary_source", ecosystem: "GITHUB" },
      },
      {
        url: "https://pydantic.dev/articles/pydantic-ai-overview",
        title: "PydanticAI Architecture Overview",
        domain: "pydantic.dev",
        grounding_metadata: { role: "supporting_source", ecosystem: "GENERAL_WEB" },
      },
    ],
    provenance: {
      discovery_signal: null,
      primary_sources: [
        {
          title: "pydantic/pydantic-ai: Type-safe Agent Framework",
          url: "https://github.com/pydantic/pydantic-ai",
          domain: "github.com",
        },
      ],
      supporting_sources: [
        {
          title: "PydanticAI Architecture Overview",
          url: "https://pydantic.dev/articles/pydantic-ai-overview",
          domain: "pydantic.dev",
          source_type: "Independent Analysis",
        },
      ],
    },
    topic_fingerprint: "fp_pydantic_01",
    discovered_at: "2026-08-30T07:18:29.000000Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_mcp_02",
    run_id: "ws_demo_user_123:croviq_syn_ai_eng_01:2026-08-30T07:18:29.726229+00:00",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Agent Workflows",
    title:
      "Architecting Centralized Tool Registries: MCP Streamable HTTP (SSE) vs Stdio in FastAPI",
    summary:
      "The Model Context Protocol specification clarifies architectural boundaries between local Stdio transport and remote Streamable HTTP (Server-Sent Events) transports, enabling engineers to centralize shared tool registries across multiple distributed agents.",
    why_it_matters:
      "Resolves a core friction point for senior backend developers building multi-agent systems in LangGraph and FastAPI: eliminating repetitive tool definition maintenance across isolated sub-agents.",
    relevance_score: 0.95,
    freshness_score: 0.92,
    opportunity_score: 0.94,
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
        grounding_metadata: { role: "supporting_source", ecosystem: "GENERAL_WEB" },
      },
    ],
    provenance: {
      discovery_signal: null,
      primary_sources: [
        {
          title: "Model Context Protocol Architecture and Transports Specification",
          url: "https://modelcontextprotocol.io/specification/architecture",
          domain: "modelcontextprotocol.io",
        },
      ],
      supporting_sources: [
        {
          title: "Scaling Complex Agentic Tool Plumbing with Model Context Protocol",
          url: "https://towardsdatascience.com/scaling-agentic-tools-with-model-context-protocol",
          domain: "towardsdatascience.com",
          source_type: "Independent Analysis",
        },
      ],
    },
    topic_fingerprint: "fp_mcp_02",
    discovered_at: "2026-08-30T07:18:29.000000Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_vllm_03",
    run_id: "ws_demo_user_123:croviq_syn_ai_eng_01:2026-08-30T07:18:29.726229+00:00",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Foundation Models",
    title: "vLLM Multi-GPU Speculative Decoding and Chunked Prefill Benchmarks",
    summary:
      "vLLM released comprehensive benchmark data and architecture patterns for draft-and-verify speculative decoding, evaluating Native MTP, Gemma 4 MTP, and EAGLE-3.",
    why_it_matters:
      "Engineering viewers on your channel show 41% higher subscriber conversion on architectural deep-dives with reproducible local inference benchmarks.",
    relevance_score: 0.94,
    freshness_score: 0.91,
    opportunity_score: 0.93,
    topic_cluster: "inference-engines",
    primary_entity: "vLLM",
    source_citations: [
      {
        url: "https://github.com/vllm-project/vllm",
        title: "vLLM: High-Throughput and Memory-Efficient LLM Serving",
        domain: "github.com",
        grounding_metadata: { role: "primary_source", ecosystem: "GITHUB" },
      },
      {
        url: "https://news.ycombinator.com/item?id=42300010",
        title: "Discussion: Speculative Decoding and Serving Throughput in vLLM — Hacker News",
        domain: "news.ycombinator.com",
        grounding_metadata: { role: "discovery_signal", ecosystem: "HACKER_NEWS" },
      },
      {
        url: "https://particula.tech/blog/sglang-vs-vllm",
        title: "SGLang vs vLLM in 2026: Benchmarks and When to Use Each",
        domain: "particula.tech",
        grounding_metadata: { role: "supporting_source", ecosystem: "GENERAL_WEB" },
      },
    ],
    provenance: {
      discovery_signal: {
        source_type: "Hacker News",
        title: "Discussion: Speculative Decoding and Serving Throughput in vLLM — Hacker News",
        url: "https://news.ycombinator.com/item?id=42300010",
        domain: "news.ycombinator.com",
      },
      primary_sources: [
        {
          title: "vLLM: High-Throughput and Memory-Efficient LLM Serving",
          url: "https://github.com/vllm-project/vllm",
          domain: "github.com",
        },
      ],
      supporting_sources: [
        {
          title: "SGLang vs vLLM in 2026: Benchmarks and When to Use Each",
          url: "https://particula.tech/blog/sglang-vs-vllm",
          domain: "particula.tech",
          source_type: "Independent Benchmark",
        },
      ],
    },
    topic_fingerprint: "fp_vllm_03",
    discovered_at: "2026-08-30T07:18:29.000000Z",
    lifecycle: "NEW",
  },
  {
    finding_id: "fnd_sglang_04",
    run_id: "ws_demo_user_123:croviq_syn_ai_eng_01:2026-08-30T07:18:29.726229+00:00",
    channel_id: "croviq_syn_ai_eng_01",
    category: "Foundation Models",
    title: "SGLang RadixAttention: Production Benchmarks for Multi-Agent Loops and Agentic RAG",
    summary:
      "Production benchmarks highlight SGLang's RadixAttention delivering throughput and TTFT gains over traditional PagedAttention in prefix-heavy multi-agent loops.",
    why_it_matters:
      "Channel tool comparisons consistently generate peak audience retention (60%+). Engineers need empirical data to decide serving stack migrations.",
    relevance_score: 0.93,
    freshness_score: 0.9,
    opportunity_score: 0.92,
    topic_cluster: "inference-engines",
    primary_entity: "SGLang",
    source_citations: [
      {
        url: "https://github.com/sgl-project/sglang",
        title: "SGLang: Fast and Expressive Serving Framework for LLMs",
        domain: "github.com",
        grounding_metadata: { role: "primary_source", ecosystem: "GITHUB" },
      },
      {
        url: "https://www.reddit.com/r/LocalLLaMA/comments/1vllm_benchmarks",
        title: "RadixAttention Benchmarks Discussion — r/LocalLLaMA",
        domain: "reddit.com",
        grounding_metadata: { role: "discovery_signal", ecosystem: "REDDIT" },
      },
      {
        url: "https://spheron.network/blog/vllm-vs-sglang-benchmarks",
        title: "vLLM vs SGLang Benchmarks: Architecture Analysis",
        domain: "spheron.network",
        grounding_metadata: { role: "supporting_source", ecosystem: "GENERAL_WEB" },
      },
    ],
    provenance: {
      discovery_signal: {
        source_type: "Reddit",
        title: "RadixAttention Benchmarks Discussion — r/LocalLLaMA",
        url: "https://www.reddit.com/r/LocalLLaMA/comments/1vllm_benchmarks",
        domain: "reddit.com",
      },
      primary_sources: [
        {
          title: "SGLang: Fast and Expressive Serving Framework for LLMs",
          url: "https://github.com/sgl-project/sglang",
          domain: "github.com",
        },
      ],
      supporting_sources: [
        {
          title: "vLLM vs SGLang Benchmarks: Architecture Analysis",
          url: "https://spheron.network/blog/vllm-vs-sglang-benchmarks",
          domain: "spheron.network",
          source_type: "Independent Benchmark",
        },
      ],
    },
    topic_fingerprint: "fp_sglang_04",
    discovered_at: "2026-08-30T07:18:29.000000Z",
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
      body: JSON.stringify(BUG07_PROVENANCE_FINDINGS),
    });
  });
};

test.describe("Bug 7 Verification: Truthful Research Source Provenance & Evidence Contract", () => {
  test("1440x900: AlexRail cards and Findings Drawer render canonical human copy provenance without raw enums or fake community signals", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    page.on("requestfailed", (request) => {
      failedRequests.push(`${request.method()} ${request.url()} - ${request.failure()?.errorText}`);
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await setupPageRoutes(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(DEMO_EMAIL);
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("**/app*");
    await page.waitForSelector("aside");

    // Wait for App to mount and Ideas Worth Making section to appear
    await expect(page.getByText("Ideas Worth Making").first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("heading", { name: /PydanticAI v2\.35/i })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Architecting Centralized Tool Registries/i }),
    ).toBeVisible();
    // 1. Verify Card Source Pills:
    // Finding 1 (PydanticAI) has GitHub primary + pydantic.dev supporting -> lead source is github.com (+1) (NOT fake Reddit/HN)
    await expect(page.getByText("github.com (+1)").first()).toBeVisible();

    // Finding 3 (vLLM) has Hacker News discovery signal -> lead source is Spotted on Hacker News (+2)
    await expect(page.getByText("Spotted on Hacker News (+2)")).toBeVisible();

    // 2. Open popover on PydanticAI card
    await page.getByText("github.com (+1)").first().click();
    await expect(page.getByText("Primary Source").first()).toBeVisible();
    await expect(page.getByText("Supporting Evidence").first()).toBeVisible();
    // Take screenshot of AlexRail with open source popover at 1440x900
    await page.screenshot({
      path: "e2e/screenshots/bug07-ideas-worth-making-1440x900.png",
      fullPage: false,
    });

    // 3. Open "View all 4 findings" drawer
    await page.getByText("View all 4 findings").click();

    // Wait for drawer to open
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(
      page.getByRole("dialog").getByRole("heading", { name: "Ideas Worth Making" }),
    ).toBeVisible();
    // Verify structured sections in drawer:
    // - "Discovered via Hacker News" on vLLM finding
    await expect(page.getByText("Discovered via Hacker News")).toBeVisible();
    // - "Discovered via Reddit" on SGLang finding
    await expect(page.getByText("Discovered via Reddit")).toBeVisible();
    // - "Primary Source" on findings
    await expect(page.getByText("Primary Source").first()).toBeVisible();
    // - "Supporting Evidence" on findings
    await expect(page.getByText("Supporting Evidence").first()).toBeVisible();

    // Verify NO raw taxonomy enums are rendered anywhere in the DOM
    const bodyText = await page.innerText("body");
    expect(bodyText).not.toContain("COMMUNITY_SIGNAL");
    expect(bodyText).not.toContain("PRIMARY_VENDOR");
    expect(bodyText).not.toContain("ENGINEERING_DOCS");

    // Take screenshot of Findings Drawer at 1440x900
    await page.screenshot({
      path: "e2e/screenshots/bug07-findings-drawer-1440x900.png",
      fullPage: false,
    });

    // Close drawer via close button
    await page.getByLabel("Close research findings").click();
    await expect(page.getByRole("dialog")).not.toBeVisible();

    // Verify Clean Console and Clean Network
    expect(consoleErrors).toHaveLength(0);
    expect(failedRequests).toHaveLength(0);
  });
});
