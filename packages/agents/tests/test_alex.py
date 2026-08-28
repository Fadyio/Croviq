import pytest
from datetime import UTC, datetime
from croviq_agents.alex import AlexDataScientist, normalize_topic_fingerprint
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

    matched = [f for f in findings if f.topic_fingerprint == fp]
    assert len(matched) == 1
    assert matched[0].finding_id == "fnd_old_1"
    assert matched[0].lifecycle == FindingLifecycle.UPDATED
    assert matched[0].discovered_at == now
    assert matched[0].updated_at is not None


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
    assert lesson.target_agent == TargetAgent.DIRECTOR
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
    # The finding matching this exact URL/fingerprint should update the existing finding, not create a duplicate
    matching = [f for f in findings if f.finding_id == "fnd_url_test"]
    assert len(matching) == 1
    assert matching[0].discovered_at == now
    assert matching[0].lifecycle == FindingLifecycle.UPDATED


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
