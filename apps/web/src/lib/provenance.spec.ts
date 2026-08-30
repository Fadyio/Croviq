import { expect, test } from "@playwright/test";
import { classifyUrlRole, getResolvedProvenance, type ResearchFinding } from "./provenance";

test.describe("Research Provenance Resolution & Classification", () => {
  test("classifies Reddit URLs as COMMUNITY_SIGNAL", () => {
    const res = classifyUrlRole(
      "https://www.reddit.com/r/LocalLLaMA/comments/1vllm_benchmarks",
      "Speculative Decoding Benchmarks — r/LocalLLaMA"
    );
    expect(res.role).toBe("COMMUNITY_SIGNAL");
    expect(res.sourceType).toBe("Reddit");
  });

  test("classifies Hacker News URLs as COMMUNITY_SIGNAL", () => {
    const res = classifyUrlRole(
      "https://news.ycombinator.com/item?id=42300010",
      "Discussion: Production Security for MCP Agent Servers"
    );
    expect(res.role).toBe("COMMUNITY_SIGNAL");
    expect(res.sourceType).toBe("Hacker News");
  });

  test("classifies GitHub repositories as PRIMARY", () => {
    const res = classifyUrlRole(
      "https://github.com/google-github-actions/deploy-cloudrun",
      "Deploy to Cloud Run GitHub Action"
    );
    expect(res.role).toBe("PRIMARY");
    expect(res.sourceType).toBe("GitHub Repository");
  });

  test("classifies official documentation and specs as PRIMARY", () => {
    const mcp = classifyUrlRole(
      "https://modelcontextprotocol.io/specification/architecture",
      "Model Context Protocol Architecture and Transports Specification"
    );
    expect(mcp.role).toBe("PRIMARY");
    expect(mcp.sourceType).toBe("Official Specification");

    const gemini = classifyUrlRole(
      "https://ai.google.dev/gemini-api/docs/models/gemini",
      "Gemini Models — Google AI"
    );
    expect(gemini.role).toBe("PRIMARY");
    expect(gemini.sourceType).toBe("Official Documentation");
  });

  test("classifies independent blogs and benchmarks as SUPPORTING, not PRIMARY", () => {
    const particula = classifyUrlRole(
      "https://particula.tech/blog/sglang-vs-vllm",
      "SGLang vs vLLM in 2026: Benchmarks and When to Use Each"
    );
    expect(particula.role).toBe("SUPPORTING");
    expect(particula.sourceType).toBe("Independent Benchmark");

    const spheron = classifyUrlRole(
      "https://spheron.network/blog/vllm-vs-sglang-benchmarks",
      "vLLM vs SGLang Benchmarks: Architecture Analysis"
    );
    expect(spheron.role).toBe("SUPPORTING");
    expect(spheron.sourceType).toBe("Independent Benchmark");

    const tds = classifyUrlRole(
      "https://towardsdatascience.com/scaling-agentic-tools-with-model-context-protocol",
      "Scaling Complex Agentic Tool Plumbing"
    );
    expect(tds.role).toBe("SUPPORTING");
    expect(tds.sourceType).toBe("Independent Analysis");
  });

  test("resolves provenance truthfully for findings with explicit typed provenance", () => {
    const finding: ResearchFinding = {
      finding_id: "fnd_test_01",
      run_id: "run_01",
      channel_id: "croviq_syn_ai_eng_01",
      category: "Foundation Models",
      title: "vLLM Speculative Decoding Benchmarks",
      summary: "Evaluations on vLLM",
      why_it_matters: "Channel audience fit",
      relevance_score: 0.95,
      freshness_score: 0.9,
      opportunity_score: 0.93,
      topic_fingerprint: "fp_vllm_01",
      discovered_at: "2026-08-30T10:00:00Z",
      lifecycle: "NEW",
      source_citations: [
        {
          url: "https://github.com/vllm-project/vllm",
          title: "vLLM GitHub Repo",
          domain: "github.com",
        },
        {
          url: "https://news.ycombinator.com/item?id=42300010",
          title: "Discussion on HN",
          domain: "news.ycombinator.com",
        },
      ],
      provenance: {
        discovery_signal: {
          source_type: "Hacker News",
          title: "Discussion on HN",
          url: "https://news.ycombinator.com/item?id=42300010",
          domain: "news.ycombinator.com",
        },
        primary_sources: [
          {
            title: "vLLM GitHub Repo",
            url: "https://github.com/vllm-project/vllm",
            domain: "github.com",
          },
        ],
        supporting_sources: [],
      },
    };

    const prov = getResolvedProvenance(finding);
    expect(prov.discovery_signal).toEqual({
      source_type: "Hacker News",
      title: "Discussion on HN",
      url: "https://news.ycombinator.com/item?id=42300010",
      domain: "news.ycombinator.com",
    });
    expect(prov.primary_sources).toHaveLength(1);
    expect(prov.primary_sources[0].domain).toBe("github.com");
  });

  test("degrades legacy findings without typed provenance truthfully", () => {
    const legacyFinding: ResearchFinding = {
      finding_id: "fnd_legacy_02",
      run_id: "run_legacy",
      channel_id: "croviq_syn_ai_eng_01",
      category: "Foundation Models",
      title: "SGLang vs vLLM: RadixAttention Benchmarks",
      summary: "Inference benchmark comparison",
      why_it_matters: "Channel audience fit",
      relevance_score: 0.94,
      freshness_score: 0.91,
      opportunity_score: 0.93,
      topic_fingerprint: "fp_sglang_legacy",
      discovered_at: "2026-08-30T10:00:00Z",
      lifecycle: "NEW",
      source_citations: [
        {
          url: "https://particula.tech/blog/sglang-vs-vllm",
          title: "SGLang vs vLLM Benchmarks",
          domain: "particula.tech",
        },
        {
          url: "https://spheron.network/blog/vllm-vs-sglang-benchmarks",
          title: "vLLM vs SGLang Benchmarks",
          domain: "spheron.network",
        },
      ],
    };

    const prov = getResolvedProvenance(legacyFinding);
    // Non-reddit domain cannot be a discovery signal
    expect(prov.discovery_signal).toBeNull();
    // Non-primary domains cannot be primary
    expect(prov.primary_sources).toHaveLength(0);
    // Both are correctly placed in supporting sources
    expect(prov.supporting_sources).toHaveLength(2);
    expect(prov.supporting_sources[0].domain).toBe("particula.tech");
    expect(prov.supporting_sources[1].domain).toBe("spheron.network");
  });
});
