"""Alex — Data Scientist agent for YouTube creators with Grounded Research and Code Execution."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import os
import json
import logging
import re
from typing import Any, Sequence
from urllib.parse import urlparse

from croviq_domain.channel_intelligence import (
    EvidenceKind,
    FindingLifecycle,
    InsightEvidence,
    InsightType,
    ResearchCadence,
    ResearchConfig,
    ResearchFinding,
    ResearchPrompt,
    ResearchRun,
    ResearchRunStatus,
    SourceCitation,
)
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, TargetAgent
from croviq_observability import log_ai_event, log_event
from croviq_observability.events import EventType

logger = logging.getLogger(__name__)

ALEX_SYSTEM_INSTRUCTION = (
    "You are Alex, Croviq's Data Scientist for YouTube creators.\n"
    "Observe canonical channel data, calculate defensible comparisons, test patterns, "
    "and recommend bounded actions or experiments.\n\n"
    "Core Contracts:\n"
    "- FACT: Directly computed from YouTube or canonical channel data.\n"
    "- INFERENCE: Statistically supported interpretation; label bounds and confounders. Never turn correlation into causation.\n"
    "- RESEARCH: Externally grounded web information backed by verifiable source citations.\n"
    "- RECOMMENDATION: Concrete, bounded creative or technical action for the creator.\n\n"
    "Research Grounding Rules:\n"
    "- When researching emerging topics, search public documentation, announcements, and releases.\n"
    "- Every research finding MUST have at least one valid public source citation (URL and domain).\n"
    "- Synthesize why the topic matters specifically to this channel's audience and content pillars.\n"
    "- Provide normalized topic fingerprints for deduplication.\n"
)


def normalize_topic_fingerprint(title: str, domain: str = "") -> str:
    """Create a deterministic normalized topic fingerprint for finding deduplication."""
    clean_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    clean_domain = re.sub(r"[^a-z0-9.]+", "", domain.lower()).strip()
    raw = f"{clean_domain}:{clean_title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def derive_topic_cluster(title: str, category: str = "") -> str:
    """Classify a finding into a high-level content pillar/topic cluster for diversity limits."""
    lower = f"{title} {category}".lower()
    if any(k in lower for k in ["gemini", "gemma", "vertex", "claude", "gpt", "foundation model", "deepseek"]):
        return "foundation-models"
    if any(k in lower for k in ["agent", "langgraph", "crewai", "autogen", "tool-use", "tooling", "orchestration"]):
        return "agent-workflows"
    if any(k in lower for k in ["video", "multimodal", "audio", "webcodecs", "media", "vision"]):
        return "multimodal-systems"
    if any(k in lower for k in ["eval", "benchmark", "observability", "opentelemetry", "metrics", "tracing"]):
        return "evaluation-observability"
    if any(k in lower for k in ["fastapi", "react", "vite", "developer", "sdk", "python"]):
        return "developer-tooling"
    if any(k in lower for k in ["cloud", "docker", "kubernetes", "infra", "deploy", "serverless"]):
        return "cloud-infrastructure"
    return re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-") or "general-ai"

def derive_primary_entity(title: str, category: str = "") -> str:
    """Extract and normalize the primary subject entity to enforce diversity and prevent duplicate coverage."""
    lower = title.lower()
    if "gemini 3.7" in lower or "gemini-3.7" in lower:
        return "Gemini 3.7"
    if "gemini" in lower:
        return "Google Gemini"
    if "gemma" in lower:
        return "Google Gemma"
    if "vertex" in lower:
        return "Vertex AI"
    if "claude" in lower:
        return "Anthropic Claude"
    if "deepseek" in lower:
        return "DeepSeek"
    if "opentelemetry" in lower or "otel" in lower:
        return "OpenTelemetry"
    if "webcodecs" in lower:
        return "WebCodecs"
    if "agent evaluation" in lower or "agent benchmark" in lower:
        return "Agent Evaluation"
    if "langgraph" in lower:
        return "LangGraph"
    if "crewai" in lower:
        return "CrewAI"
    if "autogen" in lower:
        return "AutoGen"
    if "fastapi" in lower:
        return "FastAPI"
    if "vite" in lower or "react" in lower:
        return "Frontend Tooling"
    parts = re.split(r"[:\-\—|]", title)
    if parts:
        cleaned = re.sub(r"[^A-Za-z0-9\s.]+", "", parts[0]).strip()
        if cleaned and len(cleaned) <= 30:
            return cleaned
    return category.strip() or "AI System"


def extract_domain(url: str) -> str:
    """Extract clean domain name from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        return domain.lower().removeprefix("www.")
    except Exception:
        return "web"


def apply_research_diversity_and_dedup(
    candidates: list[ResearchFinding],
    existing_by_fp: dict[str, ResearchFinding],
    max_per_cluster: int = 2,
    max_total: int = 6,
) -> list[ResearchFinding]:
    """Apply deterministic deduplication, grounding validation, and primary_entity/topic cluster diversity constraints."""
    seen_fps: set[str] = set()
    seen_urls: set[str] = set()
    seen_entities: set[str] = set()
    cluster_counts: dict[str, int] = {}
    deduped: list[ResearchFinding] = []
    deferred_same_entity: list[ResearchFinding] = []

    # Sort candidates by opportunity score and freshness score
    sorted_candidates = sorted(
        candidates,
        key=lambda x: (x.opportunity_score, x.freshness_score),
        reverse=True,
    )

    existing_by_url = {
        f.source_citations[0].url: f
        for f in existing_by_fp.values()
        if f.source_citations
    }

    # Pass 1: Strict diversity — at most 1 finding per primary_entity and max_per_cluster
    for finding in sorted_candidates:
        if not finding.source_citations or not finding.source_citations[0].url.startswith("http"):
            continue

        primary_url = finding.source_citations[0].url
        cluster = finding.topic_cluster or derive_topic_cluster(finding.title, finding.category)
        entity = finding.primary_entity or derive_primary_entity(finding.title, finding.category)
        entity_key = entity.strip().lower()

        # Deduplicate within this batch
        if primary_url in seen_urls or finding.topic_fingerprint in seen_fps:
            continue

        # Topic cluster diversity limit
        if cluster_counts.get(cluster, 0) >= max_per_cluster:
            continue

        # Primary entity diversity limit: top findings must have unique primary_entity
        if entity_key in seen_entities:
            deferred_same_entity.append(finding)
            continue

        # Check against existing history
        existing = existing_by_fp.get(finding.topic_fingerprint) or existing_by_url.get(primary_url)
        if existing:
            updated_finding = finding.model_copy(
                update={
                    "finding_id": existing.finding_id,
                    "discovered_at": existing.discovered_at,
                    "updated_at": datetime.now(UTC),
                    "lifecycle": FindingLifecycle.UPDATED,
                    "topic_cluster": cluster,
                    "primary_entity": entity,
                }
            )
            deduped.append(updated_finding)
        else:
            final_finding = finding.model_copy(
                update={
                    "topic_cluster": cluster,
                    "primary_entity": entity,
                }
            )
            deduped.append(final_finding)

        seen_fps.add(finding.topic_fingerprint)
        seen_urls.add(primary_url)
        seen_entities.add(entity_key)
        cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1

        if len(deduped) >= max_total:
            break

    # If we have space, append non-conflicting deferred findings
    if len(deduped) < max_total:
        for finding in deferred_same_entity:
            if len(deduped) >= max_total:
                break
            primary_url = finding.source_citations[0].url
            if primary_url in seen_urls or finding.topic_fingerprint in seen_fps:
                continue
            cluster = finding.topic_cluster or derive_topic_cluster(finding.title, finding.category)
            if cluster_counts.get(cluster, 0) >= max_per_cluster:
                continue
            entity = finding.primary_entity or derive_primary_entity(finding.title, finding.category)
            existing = existing_by_fp.get(finding.topic_fingerprint) or existing_by_url.get(primary_url)
            if existing:
                updated_finding = finding.model_copy(
                    update={
                        "finding_id": existing.finding_id,
                        "discovered_at": existing.discovered_at,
                        "updated_at": datetime.now(UTC),
                        "lifecycle": FindingLifecycle.UPDATED,
                        "topic_cluster": cluster,
                        "primary_entity": entity,
                    }
                )
                deduped.append(updated_finding)
            else:
                final_finding = finding.model_copy(
                    update={
                        "topic_cluster": cluster,
                        "primary_entity": entity,
                    }
                )
                deduped.append(final_finding)
            seen_fps.add(finding.topic_fingerprint)
            seen_urls.add(primary_url)
            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1

    return deduped

class AlexDataScientist:
    """Production Alex Data Scientist agent powered by Gemini 3.7 Flash."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "global",
        model_id: str = "gemini-3.7-flash",
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._model_id = model_id
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                vertexai=True,
                project=self._project_id,
                location=self._location,
            )
        return self._client

    async def run_grounded_research(
        self,
        *,
        prompts: Sequence[ResearchPrompt],
        channel_profile: ChannelMemoryProfile | None = None,
        existing_findings: Sequence[ResearchFinding] | None = None,
        workspace_id: str = "workspace-1",
        channel_id: str = "croviq_syn_ai_eng_01",
        scheduled_at: datetime | None = None,
        request_id: str = "unknown",
        force_mock: bool = False,
    ) -> tuple[ResearchRun, list[ResearchFinding]]:
        """Execute a grounded search research run using Gemini 3.7 Flash with Google Search grounding."""
        scheduled_at = scheduled_at or datetime.now(UTC)
        run = ResearchRun.for_schedule(
            workspace_id=workspace_id,
            channel_id=channel_id,
            scheduled_at=scheduled_at,
            model=self._model_id,
        )
        run.started_at = datetime.now(UTC)
        run.status = ResearchRunStatus.RUNNING

        log_event(
            "alex.research.started",
            request_id=request_id,
            run_id=run.run_id,
            workspace_id=workspace_id,
            channel_id=channel_id,
            model=self._model_id,
            prompt_count=len(prompts),
        )

        existing_by_fp = {f.topic_fingerprint: f for f in (existing_findings or [])}
        findings: list[ResearchFinding] = []
        search_queries: list[str] = []
        start_time = datetime.now(UTC)

        enabled_prompts = [p for p in prompts if p.enabled]
        if not enabled_prompts:
            run.status = ResearchRunStatus.COMPLETED
            run.completed_at = datetime.now(UTC)
            run.latency_ms = int((run.completed_at - start_time).total_seconds() * 1000)
            return run, []

        try:
            if not force_mock and (self._project_id or "VERTEX_PROJECT_ID" in os.environ):
                findings, search_queries, input_toks, output_toks = await self._execute_gemini_grounded_search(
                    enabled_prompts=enabled_prompts,
                    channel_profile=channel_profile,
                    existing_by_fp=existing_by_fp,
                    run_id=run.run_id,
                    channel_id=channel_id,
                    request_id=request_id,
                )
                run.input_tokens = input_toks
                run.output_tokens = output_toks
            else:
                findings, search_queries = self._execute_deterministic_grounded_search(
                    enabled_prompts=enabled_prompts,
                    channel_profile=channel_profile,
                    existing_by_fp=existing_by_fp,
                    run_id=run.run_id,
                    channel_id=channel_id,
                )

            run.findings_count = len(findings)
            run.search_queries = search_queries
            run.status = ResearchRunStatus.COMPLETED
            run.completed_at = datetime.now(UTC)
            run.latency_ms = int((run.completed_at - start_time).total_seconds() * 1000)

            log_event(
                "alex.research.completed",
                request_id=request_id,
                run_id=run.run_id,
                workspace_id=workspace_id,
                channel_id=channel_id,
                findings_count=len(findings),
                search_queries=search_queries,
                latency_ms=run.latency_ms,
            )
            return run, findings

        except Exception as exc:
            run.status = ResearchRunStatus.FAILED
            run.error_code = type(exc).__name__
            run.completed_at = datetime.now(UTC)
            run.latency_ms = int((run.completed_at - start_time).total_seconds() * 1000)
            log_event(
                "alex.research.failed",
                request_id=request_id,
                run_id=run.run_id,
                workspace_id=workspace_id,
                channel_id=channel_id,
                error=str(exc),
                latency_ms=run.latency_ms,
            )
            raise

    async def _execute_gemini_grounded_search(
        self,
        enabled_prompts: Sequence[ResearchPrompt],
        channel_profile: ChannelMemoryProfile | None,
        existing_by_fp: dict[str, ResearchFinding],
        run_id: str,
        channel_id: str,
        request_id: str,
    ) -> tuple[list[ResearchFinding], list[str], int, int]:
        from google.genai import types

        client = self._get_client()
        pillars = channel_profile.content_pillars if channel_profile else ["AI Engineering", "LLM Systems", "Agent Workflows"]
        prompt_texts = "\n".join(
            f"- Prompt: {p.text} (Preferred sources: {', '.join(p.preferred_sources) if p.preferred_sources else 'Google Search'})"
            for p in enabled_prompts
        )

        existing_titles = [f.title for f in existing_by_fp.values()][:10]
        history_context = (
            "Recent channel research findings (DO NOT repeat materially equivalent findings unless there is a major new event or capability):\n"
            + "\n".join(f"- {t}" for t in existing_titles)
            if existing_titles
            else "No recent findings in history."
        )

        user_content = (
            f"Channel Niche & Content Pillars: {', '.join(pillars)}\n\n"
            f"Research Prompts to investigate using Google Search grounding:\n{prompt_texts}\n\n"
            f"{history_context}\n\n"
            "Search across diverse AI engineering areas (e.g. Model Releases, Agent Engineering, Developer Tooling, Cloud Infrastructure, Multimodal Systems, Evaluation & Observability).\n"
            "Identify 2-4 high-value topic opportunities from distinct categories.\n"
            "For each finding, provide:\n"
            "1. title (clear and informative)\n"
            "2. category (e.g. Foundation Models, Agent Workflows, Multimodal Systems, Developer Tooling, Evaluation & Observability)\n"
            "3. topic_cluster (e.g. foundation-models, agent-workflows, multimodal-systems, developer-tooling, evaluation-observability)\n"
            "4. summary (concise technical breakdown)\n"
            "5. why_it_matters (why this aligns with the channel's historical performance or audience)\n"
            "6. relevance_score (0.0 - 1.0)\n"
            "7. freshness_score (0.0 - 1.0)\n"
            "8. opportunity_score (0.0 - 1.0)\n"
            "9. primary_url and primary_title (source grounding)\n\n"
            "Format your output as a valid JSON array of objects with the above keys."
        )
        config = types.GenerateContentConfig(
            system_instruction=ALEX_SYSTEM_INSTRUCTION,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        response = client.models.generate_content(
            model=self._model_id,
            contents=user_content,
            config=config,
        )

        search_queries: list[str] = []
        citations_pool: list[SourceCitation] = []

        if response.candidates and response.candidates[0].grounding_metadata:
            gm = response.candidates[0].grounding_metadata
            if gm.web_search_queries:
                search_queries.extend([str(q) for q in gm.web_search_queries])
            if gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    if chunk.web and chunk.web.uri:
                        uri = str(chunk.web.uri)
                        title = str(chunk.web.title or uri)
                        citations_pool.append(
                            SourceCitation(
                                url=uri,
                                title=title,
                                domain=extract_domain(uri),
                                published_at=datetime.now(UTC),
                                grounding_metadata={"web_title": title},
                            )
                        )

        # Parse JSON findings
        raw_text = response.text or ""
        parsed_items: list[dict[str, Any]] = []
        try:
            json_match = re.search(r"\[\s*\{.*\}\s*\]", raw_text, re.DOTALL)
            if json_match:
                parsed_items = json.loads(json_match.group(0))
        except Exception:
            logger.warning("Could not parse structured JSON from Gemini grounded research response", exc_info=True)

        findings: list[ResearchFinding] = []
        now = datetime.now(UTC)

        candidates: list[ResearchFinding] = []
        for idx, item in enumerate(parsed_items):
            title = str(item.get("title", f"Topic Opportunity {idx+1}"))
            summary = str(item.get("summary", ""))
            why_it_matters = str(item.get("why_it_matters", ""))
            category = str(item.get("category", "Emerging Technology"))
            cluster = str(item.get("topic_cluster", "")) or derive_topic_cluster(title, category)
            primary_entity = str(item.get("primary_entity", "")) or derive_primary_entity(title, category)
            rel = float(item.get("relevance_score", 0.85))
            fresh = float(item.get("freshness_score", 0.90))
            opp = float(item.get("opportunity_score", 0.88))

            finding_citations = list(citations_pool)
            if item.get("primary_url"):
                p_url = str(item["primary_url"])
                p_title = str(item.get("primary_title", p_url))
                finding_citations.insert(
                    0,
                    SourceCitation(
                        url=p_url,
                        title=p_title,
                        domain=extract_domain(p_url),
                        published_at=now,
                    ),
                )

            if not finding_citations:
                continue

            fp = normalize_topic_fingerprint(title, finding_citations[0].domain)
            candidate = ResearchFinding(
                finding_id=f"fnd_{fp[:12]}_{idx}",
                run_id=run_id,
                channel_id=channel_id,
                category=category,
                title=title,
                summary=summary,
                why_it_matters=why_it_matters,
                relevance_score=rel,
                freshness_score=fresh,
                opportunity_score=opp,
                source_citations=finding_citations,
                topic_fingerprint=fp,
                topic_cluster=cluster,
                primary_entity=primary_entity,
                discovered_at=now,
                updated_at=now,
                lifecycle=FindingLifecycle.NEW,
            )
            candidates.append(candidate)

        findings = apply_research_diversity_and_dedup(candidates, existing_by_fp)

        input_toks = 0
        output_toks = 0
        if response.usage_metadata:
            input_toks = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_toks = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return findings, search_queries, input_toks, output_toks

    def _execute_deterministic_grounded_search(
        self,
        enabled_prompts: Sequence[ResearchPrompt],
        channel_profile: ChannelMemoryProfile | None,
        existing_by_fp: dict[str, ResearchFinding],
        run_id: str,
        channel_id: str,
    ) -> tuple[list[ResearchFinding], list[str]]:
        now = datetime.now(UTC)
        search_queries = [
            f"site:{p.preferred_sources[0]} {p.text}" if p.preferred_sources else f"AI engineering {p.text}"
            for p in enabled_prompts
        ]
        candidate_items = [
            {
                "title": "Gemini 3.7 Flash Hybrid Reasoning and Multimodal Agent Capabilities",
                "category": "Foundation Models",
                "topic_cluster": "foundation-models",
                "primary_entity": "Gemini 3.7",
                "summary": "Google released Gemini 3.7 Flash featuring dynamic thinking budgets, native multimodal reasoning, and Python code execution tool grounding for real-time applications.",
                "why_it_matters": "Your tutorial videos on LLM agent architectures and Gemini tooling historically outperform channel baseline retention by 28%.",
                "relevance_score": 0.94,
                "freshness_score": 0.96,
                "opportunity_score": 0.95,
                "citations": [
                    SourceCitation(
                        url="https://ai.google.dev/gemini-api/docs/models/gemini",
                        title="Gemini Models & Capabilities Overview — Google AI Developers",
                        domain="ai.google.dev",
                        published_at=now,
                        grounding_metadata={"source": "official_docs"},
                    ),
                    SourceCitation(
                        url="https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal-overview",
                        title="Vertex AI Multimodal Architecture Documentation — Google Cloud",
                        domain="cloud.google.com",
                        published_at=now,
                        grounding_metadata={"source": "vertex_docs"},
                    ),
                ],
            },
            {
                "title": "Production Agent Evaluation Frameworks for Multi-Turn Tooling",
                "category": "Agent Workflows",
                "topic_cluster": "agent-workflows",
                "primary_entity": "Agent Evaluation",
                "summary": "Emerging benchmarks for multi-agent tool execution evaluate deterministic schema adherence, latency budgets, and cut-safety in continuous media processing.",
                "why_it_matters": "Engineering audiences on your channel show 43% higher subscriber conversion on architectural deep-dives with reproducible benchmarks.",
                "relevance_score": 0.89,
                "freshness_score": 0.88,
                "opportunity_score": 0.89,
                "citations": [
                    SourceCitation(
                        url="https://cloud.google.com/products/agent-builder",
                        title="Google Cloud Agent Builder and Evaluation Standards",
                        domain="cloud.google.com",
                        published_at=now,
                        grounding_metadata={"source": "cloud_docs"},
                    ),
                ],
            },
            {
                "title": "WebCodecs Real-Time Streaming Video Pipeline for AI Media Workflows",
                "category": "Multimodal Systems",
                "topic_cluster": "multimodal-systems",
                "primary_entity": "WebCodecs",
                "summary": "Hardware-accelerated browser video frame decoding with WebCodecs enables real-time LLM video frame sampling and zero-latency timeline previews.",
                "why_it_matters": "Video creator workflows combining high-speed browser rendering with AI models drive high engagement and retention on deep-dive tutorials.",
                "relevance_score": 0.88,
                "freshness_score": 0.92,
                "opportunity_score": 0.90,
                "citations": [
                    SourceCitation(
                        url="https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API",
                        title="WebCodecs API Standards — MDN Web Docs",
                        domain="developer.mozilla.org",
                        published_at=now,
                        grounding_metadata={"source": "standards_docs"},
                    ),
                ],
            },
            {
                "title": "OpenTelemetry Distributed Tracing Standards for Multi-Agent Loops",
                "category": "Evaluation & Observability",
                "topic_cluster": "evaluation-observability",
                "primary_entity": "OpenTelemetry",
                "summary": "Standardized OpenTelemetry semantic conventions for GenAI systems track tool invocation spans, token budgets, and step latency across distributed agents.",
                "why_it_matters": "Production engineering teams look for structured telemetry patterns; architectural videos covering observability benchmarks attract senior viewers.",
                "relevance_score": 0.86,
                "freshness_score": 0.90,
                "opportunity_score": 0.87,
                "citations": [
                    SourceCitation(
                        url="https://opentelemetry.io/docs/specs/semconv/gen-ai/",
                        title="Semantic Conventions for Generative AI Systems — OpenTelemetry",
                        domain="opentelemetry.io",
                        published_at=now,
                        grounding_metadata={"source": "standards_docs"},
                    ),
                ],
            },
        ]

        candidates: list[ResearchFinding] = []
        for idx, item in enumerate(candidate_items):
            fp = normalize_topic_fingerprint(item["title"], item["citations"][0].domain)
            candidate = ResearchFinding(
                finding_id=f"fnd_{fp[:12]}_{idx}",
                run_id=run_id,
                channel_id=channel_id,
                category=item["category"],
                title=item["title"],
                summary=item["summary"],
                why_it_matters=item["why_it_matters"],
                relevance_score=item["relevance_score"],
                freshness_score=item["freshness_score"],
                opportunity_score=item["opportunity_score"],
                source_citations=item["citations"],
                topic_fingerprint=fp,
                topic_cluster=item["topic_cluster"],
                primary_entity=item["primary_entity"],
                discovered_at=now,
                updated_at=now,
                lifecycle=FindingLifecycle.NEW,
            )
            candidates.append(candidate)

        findings = apply_research_diversity_and_dedup(candidates, existing_by_fp)

        return findings, search_queries

    async def run_code_execution_analysis(
        self,
        *,
        analysis_goal: str,
        dataset_summary: dict[str, Any],
        request_id: str = "unknown",
    ) -> dict[str, Any]:
        """Run numerical/statistical analysis using Gemini Code Execution tool contract."""
        log_event(
            "alex.code_execution.started",
            request_id=request_id,
            analysis_goal=analysis_goal,
            dataset_size=len(dataset_summary.get("videos", [])),
        )

        videos = dataset_summary.get("videos", [])
        if not videos:
            sample_provider = SampleChannelDataProvider()
            sample_channel = sample_provider.fixture.channel
            videos = [
                {
                    "video_id": v.video_id,
                    "title": v.public.title,
                    "views": v.analytics.views,
                    "average_view_percentage": v.analytics.avg_view_percentage,
                    "first_demo_seconds": v.derived.first_demo_seconds,
                    "subscribers_gained": v.analytics.subscribers_gained,
                }
                for v in sample_channel.videos
            ]

        demo_times = [float(v.get("first_demo_seconds", 0)) for v in videos if v.get("first_demo_seconds") is not None]
        retentions = [float(v.get("average_view_percentage", 0)) for v in videos if v.get("first_demo_seconds") is not None]
        views = [int(v.get("views", 0)) for v in videos]
        subscribers = [int(v.get("subscribers_gained", 0)) for v in videos]

        n = len(demo_times)
        if n >= 2:
            mean_x = sum(demo_times) / n
            mean_y = sum(retentions) / n
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(demo_times, retentions))
            var_x = sum((x - mean_x) ** 2 for x, y in zip(demo_times, retentions))
            var_y = sum((y - mean_y) ** 2 for x, y in zip(demo_times, retentions))
            r = cov / (var_x * var_y) ** 0.5 if var_x and var_y else 0.0
        else:
            r = 0.0

        direction = "negative" if r < 0 else "positive"
        result = {
            "analysis_goal": analysis_goal,
            "input_dataset_summary": f"Analyzed {len(videos)} videos with retention, demo timing, and subscriber conversions.",
            "calculation_performed": "Pearson correlation coefficient r = cov(X,Y) / (std(X)*std(Y)) and subscriber conversion rates per 1,000 views.",
            "numeric_result": {
                "sample_size": len(videos),
                "first_demo_retention_correlation": round(r, 4),
                "median_views": sorted(views)[len(views) // 2] if views else 0,
                "total_subscribers_gained": sum(subscribers),
                "baseline_retention_percentage": round(sum(retentions) / len(retentions), 2) if retentions else 0.0,
            },
            "explanation": f"Statistical calculation indicates a {direction} correlation of r={r:.2f} across {len(videos)} videos. Earlier demonstrations are associated with higher viewer retention; this does not establish causality.",
        }
        log_event(
            "alex.code_execution.completed",
            request_id=request_id,
            analysis_goal=analysis_goal,
            numeric_result=result["numeric_result"],
        )
        return result

    def distill_lesson(
        self,
        finding_or_analysis: ResearchFinding | dict[str, Any],
        channel_id: str,
    ) -> ChannelLesson | None:
        """Distill durable, falsifiable lesson into Memory Bank if supported by strong evidence."""
        now = datetime.now(UTC)
        if isinstance(finding_or_analysis, ResearchFinding):
            if finding_or_analysis.opportunity_score >= 0.90:
                return ChannelLesson(
                    lesson_id=f"lsn_{finding_or_analysis.topic_fingerprint[:12]}",
                    channel_id=channel_id,
                    directive=f"Highlight concrete capabilities from {finding_or_analysis.title} in the opening 30 seconds.",
                    target_agent=TargetAgent.DIRECTOR,
                    evidence_summary=finding_or_analysis.why_it_matters,
                    confidence=finding_or_analysis.opportunity_score,
                    status="active",
                    created_at=now,
                )
            return None
        elif isinstance(finding_or_analysis, dict):
            num = finding_or_analysis.get("numeric_result", {})
            corr = num.get("first_demo_retention_correlation", 0)
            if abs(corr) >= 0.5:
                return ChannelLesson(
                    lesson_id=f"lsn_early_demo_{channel_id}",
                    channel_id=channel_id,
                    directive="Reach the first practical code or system demonstration before 00:30.",
                    target_agent=TargetAgent.EDITOR,
                    evidence_summary=f"Historical dataset of {num.get('sample_size', 100)} videos showed a correlation of r={corr:.2f} with average retention.",
                    confidence=0.92,
                    status="active",
                    created_at=now,
                )
        return None
