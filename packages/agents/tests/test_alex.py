import pytest
from datetime import UTC, datetime
from croviq_agents.alex import (
    ALEX_SYSTEM_INSTRUCTION,
    AlexDataScientist,
    is_url_allowed_by_sources,
    normalize_topic_fingerprint,
)
from croviq_domain.channel_intelligence import (
    FindingLifecycle,
    ResearchCadence,
    ResearchConfig,
    ResearchFinding,
    ResearchPrompt,
    ResearchRunStatus,
    SourceCitation,
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
