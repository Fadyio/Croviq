import pytest
from datetime import UTC, datetime
from croviq_agents.alex import (
    ALEX_SYSTEM_INSTRUCTION,
    AlexDataScientist,
    ResearchPlanIntent,
    classify_ecosystem,
    generate_channel_research_plan,
    apply_research_diversity_and_dedup,
    is_url_allowed_by_sources,
    normalize_topic_fingerprint,
)
from croviq_domain.channel_intelligence import (
    FindingLifecycle,
    FindingProvenance,
    ResearchCadence,
    ResearchConfig,
    ResearchFinding,
    ResearchPrompt,
    ResearchRunStatus,
    SourceCitation,
    classify_url_provenance_role,
    derive_truthful_provenance_from_citations,
)
from croviq_domain.memory import ChannelLesson, TargetAgent
from croviq_domain.channel_provider import SampleChannelDataProvider



def test_alex_labels_grounded_web_research_provenance_truthfully() -> None:
    assert (
        "web research synthesized by Gemini 3.7 Flash with Google Search Grounding"
        in ALEX_SYSTEM_INSTRUCTION
    )


@pytest.mark.asyncio
async def test_alex_runs_grounded_research_with_citations() -> None:
    alex = AlexDataScientist()
    prompt = ResearchPrompt(
        prompt_id="ai-agents",
        text="Find emerging multimodal agent workflows",
        enabled=True,
        use_broad_web_search=True,
        preferred_sources=["ai.google.dev", "cloud.google.com"],
    )

    run, findings = await alex.run_grounded_research(
        prompts=[prompt],
        workspace_id="ws-test",
        channel_id="croviq_syn_ai_eng_01",
        force_mock=True,
    )

    assert run.status == ResearchRunStatus.COMPLETED
    assert run.findings_count == len(findings)
    assert len(findings) >= 2
    for finding in findings:
        assert finding.lifecycle == FindingLifecycle.NEW
        assert len(finding.source_citations) >= 1
        assert finding.source_citations[0].url.startswith("http")
        assert finding.source_citations[0].domain != ""
        assert finding.topic_fingerprint != ""
        assert finding.why_it_matters != ""


@pytest.mark.asyncio
async def test_alex_deduplicates_existing_findings() -> None:
    alex = AlexDataScientist()
    prompt = ResearchPrompt(
        prompt_id="ai-agents",
        text="Find emerging multimodal agent workflows",
        enabled=True,
    )

    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    fp = normalize_topic_fingerprint("Gemini 3.7 Flash Hybrid Reasoning and Multimodal Agent Capabilities", "ai.google.dev")
    existing = ResearchFinding(
        finding_id="fnd_old_1",
        run_id="old_run",
        channel_id="croviq_syn_ai_eng_01",
        category="Foundation Models",
        title="Gemini 3.7 Flash Hybrid Reasoning and Multimodal Agent Capabilities",
        summary="Old summary",
        why_it_matters="Old why it matters",
        relevance_score=0.9,
        freshness_score=0.9,
        opportunity_score=0.9,
        source_citations=[
            SourceCitation(
                url="https://ai.google.dev/gemini-api/docs/models/gemini",
                title="Google AI",
                domain="ai.google.dev",
            )
        ],
        topic_fingerprint=fp,
        discovered_at=now,
        lifecycle=FindingLifecycle.NEW,
    )

    run, findings = await alex.run_grounded_research(
        prompts=[prompt],
        existing_findings=[existing],
        force_mock=True,
    )

    # Duplicate candidate matching existing history must be rejected, not returned as a new finding
    matched = [f for f in findings if f.topic_fingerprint == fp]
    assert len(matched) == 0
    # Genuinely new candidates from other entities/topics should be returned
    assert len(findings) >= 2
    for f in findings:
        assert f.lifecycle == FindingLifecycle.NEW
        assert f.finding_id != "fnd_old_1"

@pytest.mark.asyncio
async def test_alex_runs_code_execution_analysis() -> None:
    alex = AlexDataScientist()
    dataset = {
        "videos": [
            {"first_demo_seconds": 15, "average_view_percentage": 62.0, "views": 50000, "subscribers_gained": 250},
            {"first_demo_seconds": 25, "average_view_percentage": 58.0, "views": 45000, "subscribers_gained": 200},
            {"first_demo_seconds": 60, "average_view_percentage": 42.0, "views": 30000, "subscribers_gained": 90},
            {"first_demo_seconds": 90, "average_view_percentage": 38.0, "views": 25000, "subscribers_gained": 70},
        ]
    }

    result = await alex.run_code_execution_analysis(
        analysis_goal="Evaluate first demonstration timing effect on retention",
        dataset_summary=dataset,
    )

    assert result["numeric_result"]["sample_size"] == 4
    assert result["numeric_result"]["first_demo_retention_correlation"] < -0.9
    assert result["calculation_performed"] != ""


def test_alex_distills_lesson_for_high_opportunity_finding() -> None:
    alex = AlexDataScientist()
    finding = ResearchFinding(
        finding_id="fnd_1",
        run_id="run_1",
        channel_id="croviq_syn_ai_eng_01",
        category="Architecture",
        title="Dynamic Thinking Budgets",
        summary="Gemini 3.7 Flash allows dynamic thinking budgets per request.",
        why_it_matters="Audience shows 28% higher retention when system internals are shown early.",
        relevance_score=0.95,
        freshness_score=0.95,
        opportunity_score=0.95,
        source_citations=[
            SourceCitation(
                url="https://ai.google.dev/docs",
                title="Google AI",
                domain="ai.google.dev",
            )
        ],
        topic_fingerprint="fp_123",
        discovered_at=datetime.now(UTC),
    )

    lesson = alex.distill_lesson(finding, channel_id="croviq_syn_ai_eng_01")
    assert lesson is not None
    assert lesson.target_agent == TargetAgent.LEO
    assert "Dynamic Thinking Budgets" in lesson.directive
    assert lesson.confidence == 0.95


@pytest.mark.asyncio
async def test_alex_research_diversity_limits_topic_clusters() -> None:
    alex = AlexDataScientist()
    prompt = ResearchPrompt(
        prompt_id="ai-all",
        text="Find emerging topics in AI engineering",
        enabled=True,
    )
    run, findings = await alex.run_grounded_research(
        prompts=[prompt],
        force_mock=True,
    )
    assert len(findings) >= 3
    # Check that findings span multiple categories and no single cluster dominates (> 2)
    clusters: dict[str, int] = {}
    for f in findings:
        c = f.topic_cluster or f.category
        clusters[c] = clusters.get(c, 0) + 1
    for c, count in clusters.items():
        assert count <= 2, f"Cluster '{c}' had {count} items, exceeding diversity limit of 2"


@pytest.mark.asyncio
async def test_alex_research_exact_url_deduplication() -> None:
    alex = AlexDataScientist()
    prompt = ResearchPrompt(prompt_id="p1", text="Search", enabled=True)
    now = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)
    existing_finding = ResearchFinding(
        finding_id="fnd_url_test",
        run_id="old_run",
        channel_id="croviq_syn_ai_eng_01",
        category="Foundation Models",
        title="Gemini 3.7 Flash Hybrid Reasoning and Multimodal Agent Capabilities",
        summary="Existing summary",
        why_it_matters="Existing why it matters",
        relevance_score=0.9,
        freshness_score=0.9,
        opportunity_score=0.9,
        source_citations=[
            SourceCitation(
                url="https://ai.google.dev/gemini-api/docs/models/gemini",
                title="Google AI",
                domain="ai.google.dev",
            )
        ],
        topic_fingerprint="fp_url_test",
        discovered_at=now,
        lifecycle=FindingLifecycle.NEW,
    )
    run, findings = await alex.run_grounded_research(
        prompts=[prompt],
        existing_findings=[existing_finding],
        force_mock=True,
    )
    # The candidate matching this exact URL must be rejected and not duplicated
    matching = [f for f in findings if any(c.url == "https://ai.google.dev/gemini-api/docs/models/gemini" for c in f.source_citations)]
    assert len(matching) == 0
    # Genuinely new distinct opportunities are returned
    assert len(findings) >= 2

@pytest.mark.asyncio
async def test_alex_enforces_primary_entity_diversity_in_top_findings() -> None:
    alex = AlexDataScientist()
    prompt = ResearchPrompt(prompt_id="p1", text="Investigate all AI developments", enabled=True)
    run, findings = await alex.run_grounded_research(
        prompts=[prompt],
        workspace_id="ws-test",
        channel_id="croviq_syn_ai_eng_01",
        force_mock=True,
    )
    assert len(findings) >= 3
    top_3 = findings[:3]
    entities = [f.primary_entity for f in top_3]
    # Ensure top 3 findings have distinct primary entities (max 1 per entity)
    assert len(set(entities)) == len(top_3), f"Top 3 findings must have distinct primary entities: {entities}"


@pytest.mark.asyncio
async def test_alex_research_recency_truth_does_not_fabricate_published_at() -> None:
    alex = AlexDataScientist()
    prompt = ResearchPrompt(
        prompt_id="p_recency",
        text="Investigate emerging foundation models and tooling",
        enabled=True,
        use_broad_web_search=True,
    )
    now_before = datetime.now(UTC)
    run, findings = await alex.run_grounded_research(
        prompts=[prompt],
        workspace_id="ws-test",
        channel_id="croviq_syn_ai_eng_01",
        force_mock=True,
    )
    assert len(findings) > 0
    for finding in findings:
        assert finding.discovered_at >= now_before
        assert finding.lifecycle == FindingLifecycle.NEW
        # Citations without known upstream publish timestamp must be None, not fabricated to now()
        for citation in finding.source_citations:
            assert citation.published_at is None


@pytest.mark.asyncio
async def test_alex_research_multi_lane_and_creator_ecosystem_patterns() -> None:
    alex = AlexDataScientist()
    prompt = ResearchPrompt(
        prompt_id="p_multi",
        text="Comprehensive channel intelligence and creator content ecosystem patterns",
        enabled=True,
        preferred_sources=["support.google.com", "ai.google.dev", "developer.mozilla.org"],
        use_broad_web_search=True,
    )
    run, findings = await alex.run_grounded_research(
        prompts=[prompt],
        workspace_id="ws-test",
        channel_id="croviq_syn_ai_eng_01",
        force_mock=True,
    )
    clusters = {f.topic_cluster for f in findings}
    assert "foundation-models" in clusters
    assert "multimodal-systems" in clusters or "agent-workflows" in clusters
    assert "video-pacing-audience-retention" in clusters


@pytest.mark.parametrize(
    ("url", "allowed_sources"),
    [
        ("https://google.com/search?q=gemini", ["google.com"]),
        ("https://docs.python.org/3/library/urllib.parse.html", ["docs.python.org"]),
        ("https://sub.domain.com/research", ["domain.com"]),
        ("https://sub.domain.com/research", ["HTTPS://DOMAIN.COM:443/preferred/path"]),
    ],
)
def test_url_validator_allows_exact_and_subdomain_sources(
    url: str,
    allowed_sources: list[str],
) -> None:
    assert is_url_allowed_by_sources(url, allowed_sources, allow_broad_web=False) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://unrelated.example/research",
        "https://fake-google.com/research",
        "https://google.com.evil.com/research",
        "https://evil.com/research?source=google.com",
        "https://evil.com/research#google.com",
    ],
)
def test_url_validator_rejects_domains_outside_preferred_sources(url: str) -> None:
    assert is_url_allowed_by_sources(url, ["google.com"], allow_broad_web=False) is False


@pytest.mark.parametrize(
    "url",
    [
        "httpx://google.com/research",
        "javascript:alert('research')",
        "not a url",
        "https://[invalid",
        "https://google.com\n/research",
    ],
)
def test_url_validator_rejects_invalid_urls(url: str) -> None:
    assert is_url_allowed_by_sources(url, ["google.com"], allow_broad_web=False) is False


def test_url_validator_does_not_treat_ip_allowlist_entries_as_parent_domains() -> None:
    assert (
        is_url_allowed_by_sources(
            "https://evil.8.8.8.8/research",
            ["8.8.8.8"],
            allow_broad_web=False,
        )
        is False
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/research",
        "http://localhost/research",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1",
        "http://10.0.0.1/research",
        "http://0.0.0.0/research",
        "http://172.16.0.1/research",
        "http://192.168.0.1/research",
        "http://instance-data/latest/meta-data",
        "http://[::1]/research",
        "http://[fc00::1]/research",
        "http://[fe80::1]/research",
        "http://0x7f.0x0.0x0.0x1/research",
        "http://224.0.0.1/research",
        "http://240.0.0.1/research",
        "http://[ff02::1]/research",
    ],
)
def test_url_validator_rejects_ssrf_hosts(url: str) -> None:
    assert is_url_allowed_by_sources(url, None, allow_broad_web=True) is False


@pytest.mark.asyncio
async def test_alex_research_restricts_citations_to_preferred_sources() -> None:
    alex = AlexDataScientist()
    prompt = ResearchPrompt(
        prompt_id="strict-google-ai",
        text="Research Gemini model capabilities",
        enabled=True,
        preferred_sources=["https://ai.google.dev/gemini-api/docs"],
        use_broad_web_search=False,
    )

    run, findings = await alex.run_grounded_research(
        prompts=[prompt],
        force_mock=True,
    )

    assert run.status == ResearchRunStatus.COMPLETED
    assert [finding.title for finding in findings] == [
        "Gemini 3.7 Flash Hybrid Reasoning and Multimodal Agent Capabilities"
    ]
    assert [
        citation.url
        for finding in findings
        for citation in finding.source_citations
    ] == ["https://ai.google.dev/gemini-api/docs/models/gemini"]


@pytest.mark.asyncio
@pytest.mark.parametrize("environment_variable", ["ENVIRONMENT", "CROVIQ_ENVIRONMENT"])
async def test_alex_research_fails_closed_without_gcp_configuration_in_production(
    environment_variable: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("CROVIQ_ENVIRONMENT", raising=False)
    monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.setenv(environment_variable, "production")
    alex = AlexDataScientist()
    prompt = ResearchPrompt(prompt_id="production", text="Research AI systems", enabled=True)

    with pytest.raises(
        RuntimeError,
        match=(
            "^Alex grounded research cannot use mock/deterministic provider in production "
            "without GCP/Vertex configuration$"
        ),
    ):
        await alex.run_grounded_research(prompts=[prompt], force_mock=True)


@pytest.mark.asyncio
async def test_alex_chat_resolves_latest_video_from_shuffled_list() -> None:
    alex = AlexDataScientist()
    sample_provider = SampleChannelDataProvider()
    videos = await sample_provider.get_videos(limit=100)
    
    # Deliberately reverse and shuffle the video list so vid_syn_100 is at the beginning or middle
    shuffled = list(reversed(videos))
    assert shuffled[0].video_id == "vid_syn_100"
    
    # Put the oldest video first
    shuffled_oldest_first = list(videos)
    assert shuffled_oldest_first[0].video_id == "vid_syn_001"

    res1 = await alex.chat(
        message="How did my last video perform?",
        videos=shuffled,
        channel=await sample_provider.get_channel(),
    )
    res2 = await alex.chat(
        message="How did my last video perform?",
        videos=shuffled_oldest_first,
        channel=await sample_provider.get_channel(),
    )

    # Both must identify vid_syn_100 as the latest published video regardless of array ordering
    tool1 = next(t for t in res1["tool_executions"] if t["tool_name"] == "channel_analytics_inspection")
    tool2 = next(t for t in res2["tool_executions"] if t["tool_name"] == "channel_analytics_inspection")
    assert tool1["video_id"] == "vid_syn_100"
    assert tool2["video_id"] == "vid_syn_100"
    assert "Google GenAI SDK Tutorial for Beginners (Part 5)" in tool1["title"]
    assert "Google GenAI SDK Tutorial for Beginners (Part 5)" in tool2["title"]
    assert "Google GenAI SDK Tutorial for Beginners (Part 5)" in res1["reply"]
    assert "Google GenAI SDK Tutorial for Beginners (Part 5)" in res2["reply"]

def test_generate_channel_research_plan_creates_multi_ecosystem_intents() -> None:
    intents = generate_channel_research_plan()
    assert len(intents) >= 5
    ecosystems = {i.ecosystem for i in intents}
    assert "HACKER_NEWS" in ecosystems
    assert "REDDIT" in ecosystems
    assert "GITHUB" in ecosystems
    assert "PRIMARY_VENDOR" in ecosystems
    assert "ENGINEERING_DOCS" in ecosystems

    for i in intents:
        assert i.query != ""
        assert i.channel_reason != ""
        assert len(i.query) > 5


def test_generate_channel_research_plan_consumes_configured_preferred_sources() -> None:
    sources = ["news.ycombinator.com", "ai.google.dev", "cloud.google.com", "docs.vllm.ai"]
    intents = generate_channel_research_plan(preferred_sources=sources)
    queries = [i.query for i in intents]
    assert any("site:news.ycombinator.com" in q for q in queries)
    assert any("site:ai.google.dev" in q for q in queries)
    assert any("site:cloud.google.com" in q for q in queries)
    assert any("site:docs.vllm.ai" in q for q in queries)
    hn_intent = next(i for i in intents if "news.ycombinator.com" in i.query)
    assert hn_intent.ecosystem == "HACKER_NEWS"
    assert "Configured public source" in hn_intent.channel_reason

def test_classify_ecosystem_categories() -> None:
    assert classify_ecosystem("site:news.ycombinator.com MCP agents") == "HACKER_NEWS"
    assert classify_ecosystem("https://news.ycombinator.com/item?id=123") == "HACKER_NEWS"
    assert classify_ecosystem("site:reddit.com/r/LocalLLaMA vLLM benchmarks") == "REDDIT"
    assert classify_ecosystem("https://www.reddit.com/r/MachineLearning/comments/xyz") == "REDDIT"
    assert classify_ecosystem("site:github.com/vllm-project/vllm release") == "GITHUB"
    assert classify_ecosystem("https://github.com/langchain-ai/langgraph") == "GITHUB"
    assert classify_ecosystem("site:ai.google.dev Gemini 3.7") == "PRIMARY_VENDOR"
    assert classify_ecosystem("https://cloud.google.com/vertex-ai/docs") == "PRIMARY_VENDOR"
    assert classify_ecosystem("site:opentelemetry.io specification") == "ENGINEERING_DOCS"
    assert classify_ecosystem("https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API") == "ENGINEERING_DOCS"
    assert classify_ecosystem("https://example.com/random") == "GENERAL_WEB"


@pytest.mark.asyncio
async def test_alex_research_run_captures_diverse_ecosystems_and_discovery_signals() -> None:
    alex = AlexDataScientist()
    run, findings = await alex.run_grounded_research(
        workspace_id="ws-multi-eco",
        channel_id="croviq_syn_ai_eng_01",
        force_mock=True,
    )
    assert run.status == ResearchRunStatus.COMPLETED
    assert len(run.search_queries) >= 5
    assert any("ycombinator" in q or "news" in q for q in run.search_queries)
    assert any("reddit" in q for q in run.search_queries)
    assert any("github" in q for q in run.search_queries)
    assert any("google" in q for q in run.search_queries)

    # Check that findings contain citations with community discovery signal and primary source
    domains = {cite.domain for f in findings for cite in f.source_citations}
    assert "github.com" in domains
    assert "news.ycombinator.com" in domains or "reddit.com" in domains

    # Check discovery signals vs primary source roles in metadata
    roles = [
        cite.grounding_metadata.get("role")
        for f in findings
        for cite in f.source_citations
        if cite.grounding_metadata
    ]
    assert "discovery_signal" in roles
    assert "primary_source" in roles


def test_apply_research_diversity_and_dedup_funnel_stats() -> None:
    now = datetime.now(UTC)
    candidates = [
        ResearchFinding(
            finding_id=f"fnd_{idx}",
            run_id="run_test",
            channel_id="croviq_syn_ai_eng_01",
            category="Agent Workflows",
            title=f"Opportunity {idx}",
            summary=f"Summary {idx}",
            why_it_matters=f"Why it matters {idx}",
            relevance_score=0.9,
            freshness_score=0.9,
            opportunity_score=0.9,
            source_citations=[
                SourceCitation(
                    url=f"https://example.com/topic_{idx}",
                    title=f"Source {idx}",
                    domain="example.com",
                )
            ],
            topic_fingerprint=f"fp_{idx}",
            topic_cluster="agent-workflows",
            primary_entity=f"Entity {idx}",
            discovered_at=now,
        )
        for idx in range(5)
    ]
    # Add one disallowed citation finding to test low_source_quality_rejected when strict policy applies
    candidates.append(
        ResearchFinding(
            finding_id="fnd_disallowed",
            run_id="run_test",
            channel_id="croviq_syn_ai_eng_01",
            category="Agent Workflows",
            title="Disallowed Domain Opportunity",
            summary="Summary disallowed",
            why_it_matters="Why it matters disallowed",
            relevance_score=0.9,
            freshness_score=0.9,
            opportunity_score=0.9,
            source_citations=[
                SourceCitation(
                    url="https://untrusted-domain.com/article",
                    title="Untrusted",
                    domain="untrusted-domain.com",
                )
            ],
            topic_fingerprint="fp_disallowed",
            topic_cluster="agent-workflows",
            primary_entity="Untrusted Entity",
            discovered_at=now,
        )
    )

    deduped, funnel = apply_research_diversity_and_dedup(
        candidates,
        max_per_cluster=2,
        allowed_sources=["example.com"],
        allow_broad_web=False,
        return_funnel=True,
    )
    assert len(deduped) == 2
    assert funnel["low_source_quality_rejected"] == 1
    assert funnel["low_novelty_rejected"] == 3
    assert funnel["final_persisted"] == 2


def test_provenance_regression_a_reddit_community_signal() -> None:
    role, source_type = classify_url_provenance_role(
        "https://www.reddit.com/r/LocalLLaMA/comments/1vllm_benchmarks",
        "Speculative Decoding Benchmarks — r/LocalLLaMA",
    )
    assert role == "COMMUNITY_SIGNAL"
    assert source_type == "Reddit"

    citations = [
        SourceCitation(
            url="https://github.com/vllm-project/vllm",
            title="vLLM: Easy, Fast, and Cheap LLM Serving",
            domain="github.com",
        ),
        SourceCitation(
            url="https://www.reddit.com/r/LocalLLaMA/comments/1vllm_benchmarks",
            title="Speculative Decoding Benchmarks",
            domain="reddit.com",
        ),
    ]
    prov = derive_truthful_provenance_from_citations(citations)
    assert prov.discovery_signal is not None
    assert prov.discovery_signal.source_type == "Reddit"
    assert prov.discovery_signal.domain == "reddit.com"
    assert len(prov.primary_sources) == 1
    assert prov.primary_sources[0].domain == "github.com"


def test_provenance_regression_b_hackernews_community_signal() -> None:
    role, source_type = classify_url_provenance_role(
        "https://news.ycombinator.com/item?id=42300010",
        "Discussion: Production Security for MCP Agent Servers",
    )
    assert role == "COMMUNITY_SIGNAL"
    assert source_type == "Hacker News"

    citations = [
        SourceCitation(
            url="https://modelcontextprotocol.io/specification/architecture",
            title="MCP Architecture Specification",
            domain="modelcontextprotocol.io",
        ),
        SourceCitation(
            url="https://news.ycombinator.com/item?id=42300010",
            title="MCP Server Security Discussion",
            domain="news.ycombinator.com",
        ),
    ]
    prov = derive_truthful_provenance_from_citations(citations)
    assert prov.discovery_signal is not None
    assert prov.discovery_signal.source_type == "Hacker News"
    assert prov.discovery_signal.domain == "news.ycombinator.com"
    assert len(prov.primary_sources) == 1
    assert prov.primary_sources[0].domain == "modelcontextprotocol.io"


def test_provenance_regression_c_github_primary() -> None:
    role, source_type = classify_url_provenance_role(
        "https://github.com/google-github-actions/deploy-cloudrun",
        "Deploy to Cloud Run GitHub Action",
    )
    assert role == "PRIMARY"
    assert source_type == "GitHub Repository"

    citations = [
        SourceCitation(
            url="https://github.com/google-github-actions/deploy-cloudrun",
            title="Deploy to Cloud Run GitHub Action",
            domain="github.com",
        )
    ]
    prov = derive_truthful_provenance_from_citations(citations)
    assert len(prov.primary_sources) == 1
    assert prov.primary_sources[0].domain == "github.com"
    assert prov.discovery_signal is None


def test_provenance_regression_d_official_docs_primary() -> None:
    role_spec, type_spec = classify_url_provenance_role(
        "https://modelcontextprotocol.io/specification/architecture",
        "Model Context Protocol Specification",
    )
    assert role_spec == "PRIMARY"
    assert type_spec == "Official Specification"

    role_doc, type_doc = classify_url_provenance_role(
        "https://ai.google.dev/gemini-api/docs/models/gemini",
        "Gemini Models — Google AI",
    )
    assert role_doc == "PRIMARY"
    assert type_doc == "Official Documentation"

    role_otel, type_otel = classify_url_provenance_role(
        "https://opentelemetry.io/docs/specs/semconv/gen-ai/",
        "GenAI Semantic Conventions — OpenTelemetry",
    )
    assert role_otel == "PRIMARY"
    assert type_otel == "Official Specification"


def test_provenance_regression_e_random_engineering_blog_not_primary_by_default() -> None:
    role_particula, type_particula = classify_url_provenance_role(
        "https://particula.tech/blog/sglang-vs-vllm",
        "SGLang vs vLLM in 2026: Benchmarks and When to Use Each",
    )
    assert role_particula == "SUPPORTING"
    assert type_particula == "Independent Benchmark"

    role_spheron, type_spheron = classify_url_provenance_role(
        "https://spheron.network/blog/vllm-vs-sglang-benchmarks",
        "vLLM vs SGLang Benchmarks: Architecture and Latency",
    )
    assert role_spheron == "SUPPORTING"
    assert type_spheron == "Independent Benchmark"

    role_tds, type_tds = classify_url_provenance_role(
        "https://towardsdatascience.com/scaling-agentic-tools-with-mcp",
        "Scaling Complex Agentic Tool Plumbing",
    )
    assert role_tds == "SUPPORTING"
    assert type_tds == "Independent Analysis"

    citations = [
        SourceCitation(
            url="https://particula.tech/blog/sglang-vs-vllm",
            title="SGLang vs vLLM Benchmarks",
            domain="particula.tech",
        ),
        SourceCitation(
            url="https://spheron.network/blog/vllm-vs-sglang-benchmarks",
            title="vLLM vs SGLang Benchmarks",
            domain="spheron.network",
        ),
    ]
    prov = derive_truthful_provenance_from_citations(citations)
    assert len(prov.primary_sources) == 0
    assert len(prov.supporting_sources) == 2
    assert prov.discovery_signal is None


def test_provenance_regression_f_search_reddit_without_reddit_url_no_fake_spotted_on_reddit() -> None:
    # Even if grounding metadata claimed REDDIT ecosystem or discovery signal on a non-reddit domain:
    citations = [
        SourceCitation(
            url="https://particula.tech/blog/sglang-vs-vllm",
            title="SGLang vs vLLM: RadixAttention Benchmarks",
            domain="particula.tech",
            grounding_metadata={"role": "primary_source", "ecosystem": "REDDIT"},
        ),
        SourceCitation(
            url="https://spheron.network/blog/vllm-vs-sglang-benchmarks",
            title="vLLM vs SGLang Benchmarks",
            domain="spheron.network",
            grounding_metadata={"role": "discovery_signal", "ecosystem": "GENERAL_WEB"},
        ),
    ]
    prov = derive_truthful_provenance_from_citations(citations)
    # Because neither particula.tech nor spheron.network is reddit.com, discovery_signal MUST be None!
    assert prov.discovery_signal is None
    assert len(prov.primary_sources) == 0
    assert len(prov.supporting_sources) == 2


def test_provenance_regression_g_legacy_findings_degrade_truthfully() -> None:
    now = datetime.now(UTC)
    # Legacy finding created without explicit `provenance`
    legacy_finding = ResearchFinding(
        finding_id="fnd_legacy_01",
        run_id="run_legacy",
        channel_id="croviq_syn_ai_eng_01",
        category="Foundation Models",
        title="SGLang vs vLLM: RadixAttention Benchmarks",
        summary="Benchmarking inference frameworks",
        why_it_matters="Channel audience comparison deep-dive",
        relevance_score=0.92,
        freshness_score=0.90,
        opportunity_score=0.91,
        source_citations=[
            SourceCitation(
                url="https://particula.tech/blog/sglang-vs-vllm",
                title="SGLang vs vLLM",
                domain="particula.tech",
                grounding_metadata={"role": "primary_source", "ecosystem": "REDDIT"},
            ),
            SourceCitation(
                url="https://github.com/sgl-project/sglang",
                title="SGLang GitHub Repository",
                domain="github.com",
                grounding_metadata={"role": "primary_source", "ecosystem": "GITHUB"},
            ),
        ],
        topic_fingerprint="fp_legacy_01",
        discovered_at=now,
    )
    assert legacy_finding.provenance is not None
    # The GitHub repo is correctly classified as primary
    assert len(legacy_finding.provenance.primary_sources) == 1
    assert legacy_finding.provenance.primary_sources[0].domain == "github.com"
    # The particula.tech blog is correctly demoted to supporting
    assert len(legacy_finding.provenance.supporting_sources) == 1
    assert legacy_finding.provenance.supporting_sources[0].domain == "particula.tech"
    # No fake Reddit discovery signal is fabricated
    assert legacy_finding.provenance.discovery_signal is None
