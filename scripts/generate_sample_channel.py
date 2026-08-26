#!/usr/bin/env python3
"""Deterministic Generator for Croviq Sample AI Engineering Channel Dataset.

Generates exactly 100 historical videos across ~18 months (~540 days) for a fictional
AI engineering YouTube creator (~50,000 subscribers) with mathematically coherent
retention curves, view metrics, traffic breakdowns, and discoverable statistical signals.

Seed: random.Random(42)
Output: packages/domain/src/croviq_domain/fixtures/sample_channel_ai_engineering_v1.json
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys

# Ensure croviq_domain is importable
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "packages" / "domain" / "src"))

from croviq_domain.channel import (
    Channel,
    ChannelPrivateAnalytics,
    ChannelPublicMetadata,
    ChannelVideo,
    ContentPillar,
    DerivedChannelFeatures,
    DerivedVideoFeatures,
    DeviceMetric,
    GeographyMetric,
    RetentionPoint,
    SampleChannelFixture,
    TitleStyle,
    TrafficSourceMetric,
    VideoFormat,
    VideoPrivateAnalytics,
    VideoPublicMetadata,
)

SEED = 42

# Topic blueprints designed for realistic variety and discoverable statistical patterns
TOPIC_BLUEPRINTS = [
    # 1. AI Agents & Multi-Agent
    {
        "title": "Building an Autonomous Multi-Agent DevOps Team with Python & Claude",
        "pillar": ContentPillar.AI_AGENTS,
        "format": VideoFormat.AGENT_BUILD,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "multi_agent_systems",
        "time_sensitive": False,
        "first_demo": 18,
        "setup_time": 14,
        "base_duration": 820,
        "base_views": 46000,
        "base_ctr": 8.4,
    },
    {
        "title": "Why Most AI Agent Frameworks Fail in Production (And How to Fix It)",
        "pillar": ContentPillar.AI_AGENTS,
        "format": VideoFormat.ARCHITECTURE_DEEP_DIVE,
        "style": TitleStyle.PROBLEM_SOLUTION,
        "cluster": "agent_architecture",
        "time_sensitive": False,
        "first_demo": 52,
        "setup_time": 48,
        "base_duration": 980,
        "base_views": 38000,
        "base_ctr": 7.6,
    },
    {
        "title": "How to Build a Coding Agent from Scratch in 45 Minutes",
        "pillar": ContentPillar.AI_AGENTS,
        "format": VideoFormat.TUTORIAL,
        "style": TitleStyle.GENERIC_TUTORIAL,
        "cluster": "coding_agents",
        "time_sensitive": False,
        "first_demo": 65,
        "setup_time": 60,
        "base_duration": 1140,
        "base_views": 22000,
        "base_ctr": 4.5,
    },
    {
        "title": "Hierarchical vs Peer-to-Peer AI Agents: Production Latency Benchmarks",
        "pillar": ContentPillar.AI_AGENTS,
        "format": VideoFormat.PRODUCTION_EXPERIMENT,
        "style": TitleStyle.BENCHMARK_COMPARISON,
        "cluster": "multi_agent_systems",
        "time_sensitive": False,
        "first_demo": 22,
        "setup_time": 18,
        "base_duration": 760,
        "base_views": 41000,
        "base_ctr": 8.1,
    },
    # 2. Gemini & Vertex AI
    {
        "title": "Gemini 3.7 Flash vs Claude 3.7 Sonnet: Real Engineering Code Evaluation",
        "pillar": ContentPillar.GEMINI_VERTEX,
        "format": VideoFormat.TOOL_COMPARISON,
        "style": TitleStyle.BENCHMARK_COMPARISON,
        "cluster": "model_evaluation",
        "time_sensitive": True,
        "first_demo": 15,
        "setup_time": 12,
        "base_duration": 710,
        "base_views": 84000,
        "base_ctr": 9.8,
    },
    {
        "title": "Deploying Gemini on Vertex AI with Structured Outputs & Python Pydantic",
        "pillar": ContentPillar.GEMINI_VERTEX,
        "format": VideoFormat.TUTORIAL,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "vertex_deployment",
        "time_sensitive": False,
        "first_demo": 20,
        "setup_time": 16,
        "base_duration": 640,
        "base_views": 32000,
        "base_ctr": 7.2,
    },
    {
        "title": "Vertex AI Search vs Custom Vector DB: Which is Cheaper at Scale?",
        "pillar": ContentPillar.GEMINI_VERTEX,
        "format": VideoFormat.TOOL_COMPARISON,
        "style": TitleStyle.PROBLEM_SOLUTION,
        "cluster": "vertex_search",
        "time_sensitive": False,
        "first_demo": 35,
        "setup_time": 30,
        "base_duration": 890,
        "base_views": 29000,
        "base_ctr": 6.9,
    },
    {
        "title": "Google GenAI SDK Tutorial for Beginners",
        "pillar": ContentPillar.GEMINI_VERTEX,
        "format": VideoFormat.TUTORIAL,
        "style": TitleStyle.GENERIC_TUTORIAL,
        "cluster": "genai_sdk",
        "time_sensitive": False,
        "first_demo": 72,
        "setup_time": 68,
        "base_duration": 600,
        "base_views": 16000,
        "base_ctr": 4.1,
    },
    # 3. GitHub Actions & DevOps
    {
        "title": "Automate Your Entire CI/CD Pipeline with GitHub Actions & Cloud Run",
        "pillar": ContentPillar.GITHUB_ACTIONS_DEVOPS,
        "format": VideoFormat.DEVOPS_PIPELINE,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "cicd_automation",
        "time_sensitive": False,
        "first_demo": 24,
        "setup_time": 18,
        "base_duration": 780,
        "base_views": 52000,
        "base_ctr": 8.7,
    },
    {
        "title": "Keyless GCP Authentication in GitHub Actions via Workload Identity Federation",
        "pillar": ContentPillar.GITHUB_ACTIONS_DEVOPS,
        "format": VideoFormat.DEVOPS_PIPELINE,
        "style": TitleStyle.PROBLEM_SOLUTION,
        "cluster": "security_wif",
        "time_sensitive": False,
        "first_demo": 16,
        "setup_time": 12,
        "base_duration": 540,
        "base_views": 44000,
        "base_ctr": 8.0,
    },
    {
        "title": "GitHub Actions Tutorial: Complete Walkthrough",
        "pillar": ContentPillar.GITHUB_ACTIONS_DEVOPS,
        "format": VideoFormat.TUTORIAL,
        "style": TitleStyle.GENERIC_TUTORIAL,
        "cluster": "cicd_basics",
        "time_sensitive": False,
        "first_demo": 58,
        "setup_time": 54,
        "base_duration": 920,
        "base_views": 25000,
        "base_ctr": 4.4,
    },
    {
        "title": "Fast Docker Builds in GitHub Actions Using Remote Cache & Buildx",
        "pillar": ContentPillar.GITHUB_ACTIONS_DEVOPS,
        "format": VideoFormat.DEVOPS_PIPELINE,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "docker_optimization",
        "time_sensitive": False,
        "first_demo": 21,
        "setup_time": 15,
        "base_duration": 610,
        "base_views": 39000,
        "base_ctr": 7.8,
    },
    # 4. Cloud Run & GCP
    {
        "title": "Google Cloud Run for Production AI Services: 0 to 1 Million Requests",
        "pillar": ContentPillar.CLOUD_RUN_GCP,
        "format": VideoFormat.ARCHITECTURE_DEEP_DIVE,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "cloud_run_scaling",
        "time_sensitive": False,
        "first_demo": 28,
        "setup_time": 22,
        "base_duration": 940,
        "base_views": 48000,
        "base_ctr": 8.3,
    },
    {
        "title": "Single-Origin Routing with Google Cloud Load Balancer & Serverless NEGs",
        "pillar": ContentPillar.CLOUD_RUN_GCP,
        "format": VideoFormat.ARCHITECTURE_DEEP_DIVE,
        "style": TitleStyle.PROBLEM_SOLUTION,
        "cluster": "networking_load_balancer",
        "time_sensitive": False,
        "first_demo": 26,
        "setup_time": 20,
        "base_duration": 850,
        "base_views": 36000,
        "base_ctr": 7.5,
    },
    {
        "title": "Cloud Run Tutorial for Web Developers",
        "pillar": ContentPillar.CLOUD_RUN_GCP,
        "format": VideoFormat.TUTORIAL,
        "style": TitleStyle.GENERIC_TUTORIAL,
        "cluster": "cloud_run_basics",
        "time_sensitive": False,
        "first_demo": 64,
        "setup_time": 58,
        "base_duration": 720,
        "base_views": 18000,
        "base_ctr": 4.2,
    },
    # 5. RAG & Memory Systems
    {
        "title": "Agent Platform Memory Bank: Long-Term Semantic Memory Without Vector DBs",
        "pillar": ContentPillar.RAG_MEMORY,
        "format": VideoFormat.ARCHITECTURE_DEEP_DIVE,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "agent_memory",
        "time_sensitive": False,
        "first_demo": 19,
        "setup_time": 15,
        "base_duration": 880,
        "base_views": 45000,
        "base_ctr": 8.6,
    },
    {
        "title": "Graph RAG vs Hybrid Search: Production Retrieval Accuracy Benchmarks",
        "pillar": ContentPillar.RAG_MEMORY,
        "format": VideoFormat.PRODUCTION_EXPERIMENT,
        "style": TitleStyle.BENCHMARK_COMPARISON,
        "cluster": "rag_evaluation",
        "time_sensitive": False,
        "first_demo": 25,
        "setup_time": 20,
        "base_duration": 910,
        "base_views": 39000,
        "base_ctr": 7.9,
    },
    {
        "title": "RAG Tutorial: How to Build RAG with LangChain",
        "pillar": ContentPillar.RAG_MEMORY,
        "format": VideoFormat.TUTORIAL,
        "style": TitleStyle.GENERIC_TUTORIAL,
        "cluster": "rag_basics",
        "time_sensitive": False,
        "first_demo": 70,
        "setup_time": 65,
        "base_duration": 840,
        "base_views": 19000,
        "base_ctr": 4.3,
    },
    # 6. Multimodal AI
    {
        "title": "Native Video Understanding with Gemini: Frame-Accurate Speech & Scene Analysis",
        "pillar": ContentPillar.MULTIMODAL_AI,
        "format": VideoFormat.ARCHITECTURE_DEEP_DIVE,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "video_multimodal",
        "time_sensitive": False,
        "first_demo": 17,
        "setup_time": 12,
        "base_duration": 790,
        "base_views": 53000,
        "base_ctr": 8.9,
    },
    {
        "title": "Building a Real-Time Audio AI Agent with Google Speech-to-Text v2 & FastAPI",
        "pillar": ContentPillar.MULTIMODAL_AI,
        "format": VideoFormat.AGENT_BUILD,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "audio_agents",
        "time_sensitive": False,
        "first_demo": 23,
        "setup_time": 18,
        "base_duration": 860,
        "base_views": 42000,
        "base_ctr": 8.2,
    },
    # 7. AI Coding Tools & Production LLM
    {
        "title": "Cursor vs Windsurf vs Claude Code: 5 Hard Refactoring Tasks Tested",
        "pillar": ContentPillar.AI_CODING_TOOLS,
        "format": VideoFormat.TOOL_COMPARISON,
        "style": TitleStyle.BENCHMARK_COMPARISON,
        "cluster": "coding_tools",
        "time_sensitive": True,
        "first_demo": 14,
        "setup_time": 10,
        "base_duration": 680,
        "base_views": 92000,
        "base_ctr": 10.4,
    },
    {
        "title": "Stop Using Naive LLM Retries: Bounded Deterministic State Machines in Python",
        "pillar": ContentPillar.PRODUCTION_LLM,
        "format": VideoFormat.ARCHITECTURE_DEEP_DIVE,
        "style": TitleStyle.PROBLEM_SOLUTION,
        "cluster": "llm_reliability",
        "time_sensitive": False,
        "first_demo": 29,
        "setup_time": 24,
        "base_duration": 960,
        "base_views": 37000,
        "base_ctr": 7.7,
    },
    {
        "title": "Structured Pydantic v2 Outputs with LLMs: Zero-Hallucination Schemas",
        "pillar": ContentPillar.PRODUCTION_LLM,
        "format": VideoFormat.TUTORIAL,
        "style": TitleStyle.OUTCOME_FOCUSED,
        "cluster": "schema_enforcement",
        "time_sensitive": False,
        "first_demo": 20,
        "setup_time": 15,
        "base_duration": 580,
        "base_views": 35000,
        "base_ctr": 7.4,
    },
]


def generate_retention_curve(
    rng: random.Random,
    first_demo_seconds: int,
    setup_time_seconds: int,
    duration_seconds: int,
) -> list[RetentionPoint]:
    """Generates a realistic 101-point retention curve (0% to 100%).

    Earlier demos (<=30s) produce higher initial retention (~80-86% at 30s).
    Longer setup (>45s) produces steeper dropoff (~58-68% at 30s).
    """
    points: list[RetentionPoint] = []

    # Calculate 30-second mark percentage offset
    thirty_sec_pct = max(1, min(15, int((30 / duration_seconds) * 100)))

    # Opening retention target at 30s
    if first_demo_seconds <= 25:
        target_30s = rng.uniform(82.0, 88.0)
    elif first_demo_seconds <= 40:
        target_30s = rng.uniform(74.0, 81.0)
    else:
        # Long setup penalty
        penalty = min(15.0, (setup_time_seconds - 30) * 0.4)
        target_30s = rng.uniform(58.0, 68.0) - penalty

    # Midpoint target (50% through video)
    if first_demo_seconds <= 30:
        target_50pct = target_30s * rng.uniform(0.68, 0.76)
    else:
        target_50pct = target_30s * rng.uniform(0.55, 0.65)

    # End target (90% through video)
    target_90pct = target_50pct * rng.uniform(0.62, 0.74)

    # Outro target (100%)
    target_100pct = target_90pct * rng.uniform(0.70, 0.82)

    current_val = 100.0

    for i in range(101):
        if i == 0:
            val = 100.0
        elif i <= thirty_sec_pct:
            # Steepest drop from 100 to target_30s
            progress = i / thirty_sec_pct
            val = 100.0 - (progress**0.7) * (100.0 - target_30s)
        elif i <= 50:
            # Drop from target_30s to target_50pct with occasional mini-spikes (rewatches)
            progress = (i - thirty_sec_pct) / (50 - thirty_sec_pct)
            base = target_30s - (progress**0.9) * (target_30s - target_50pct)
            # Add small rewatch bump around 35-40% if demo is interesting
            if 34 <= i <= 38 and first_demo_seconds <= 30:
                base += rng.uniform(1.2, 2.5)
            val = base
        elif i <= 90:
            # Drop from target_50pct to target_90pct
            progress = (i - 50) / 40
            val = target_50pct - (progress**0.95) * (target_50pct - target_90pct)
        else:
            # Outro drop
            progress = (i - 90) / 10
            val = target_90pct - (progress**1.1) * (target_90pct - target_100pct)

        # Ensure curve is monotonic with tiny non-disruptive noise
        val = max(10.0, min(100.0, val))
        rel_ret = round(val / 50.0, 2)  # Relative to platform 50% baseline
        points.append(
            RetentionPoint(
                percent_offset=i,
                retention_percentage=round(val, 2),
                relative_retention=rel_ret,
            )
        )

    return points


def generate_sample_dataset() -> SampleChannelFixture:
    rng = random.Random(SEED)

    # Start date: ~18 months before 2026-08-26 (~540 days ago)
    start_date = datetime(2025, 2, 20, 14, 0, 0, tzinfo=timezone.utc)
    channel_id = "croviq_syn_ai_eng_01"

    videos: list[ChannelVideo] = []
    current_date = start_date

    total_views_accum = 0
    total_watch_time_mins_accum = 0.0
    total_subs_gained_accum = 0
    total_subs_lost_accum = 0
    total_impressions_accum = 0
    total_likes_accum = 0
    total_comments_accum = 0
    total_shares_accum = 0

    # We generate exactly 100 videos
    for idx in range(1, 101):
        # Pick blueprint with cyclic variety and small variations
        bp = TOPIC_BLUEPRINTS[(idx - 1) % len(TOPIC_BLUEPRINTS)]

        # Video publish date cadence: ~4 to 7 days, with occasional clustering
        days_offset = rng.randint(4, 7)
        if bp["time_sensitive"]:
            days_offset = rng.randint(2, 4)
        current_date += timedelta(
            days=days_offset,
            hours=rng.randint(-2, 3),
            minutes=rng.randint(0, 59),
        )

        video_id = f"vid_syn_{idx:03d}"
        duration = bp["base_duration"] + rng.randint(-45, 60)
        duration = max(300, duration)

        first_demo = max(5, bp["first_demo"] + rng.randint(-4, 6))
        setup_time = max(4, bp["setup_time"] + rng.randint(-3, 5))

        # Title variations to avoid repetitive patterns
        prefix_variations = ["", "Deep Dive: ", "Tutorial: ", "Tested: ", "Guide: "]
        title_text = bp["title"]
        if idx > len(TOPIC_BLUEPRINTS):
            var_num = (idx // len(TOPIC_BLUEPRINTS)) + 1
            title_text = f"{bp['title']} (Part {var_num})"

        # Views: growth curve across channel history + blueprint baseline + noise
        history_growth_factor = 0.35 + (idx / 100.0) * 0.95  # 0.35x up to 1.30x
        view_noise = rng.uniform(0.85, 1.25)
        views = int(bp["base_views"] * history_growth_factor * view_noise)

        # Retention curve
        retention_curve = generate_retention_curve(
            rng, first_demo, setup_time, duration
        )

        # Average view percentage: mean of retention points
        avg_view_pct = round(
            sum(p.retention_percentage for p in retention_curve)
            / len(retention_curve),
            2,
        )
        avg_view_dur = round(duration * (avg_view_pct / 100.0), 2)
        watch_time_mins = round((views * avg_view_dur) / 60.0, 2)

        # CTR percentage
        ctr_noise = rng.uniform(-0.6, 0.6)
        ctr_pct = max(2.5, min(14.0, round(bp["base_ctr"] + ctr_noise, 2)))

        # Impressions = views / (CTR / 100) + organic non-click impressions
        impressions = int(views / (ctr_pct / 100.0)) + rng.randint(200, 1500)

        # Engagement
        sub_conv_rate = rng.uniform(0.011, 0.017)  # ~1.1% to 1.7% conversion
        if bp["pillar"] == ContentPillar.GITHUB_ACTIONS_DEVOPS:
            sub_conv_rate += 0.003  # DevOps content has high returning utility
        subs_gained = max(10, int(views * sub_conv_rate))
        subs_lost = max(1, int(subs_gained * rng.uniform(0.06, 0.12)))

        likes = max(15, int(views * rng.uniform(0.042, 0.062)))
        comments = max(3, int(views * rng.uniform(0.004, 0.009)))
        shares = max(2, int(views * rng.uniform(0.002, 0.006)))

        # Revenue: ~$4.50 to $7.80 RPM for engineering niche
        rpm = rng.uniform(4.50, 7.80)
        est_revenue = round((views / 1000.0) * rpm, 2)

        # Traffic Sources
        if bp["pillar"] == ContentPillar.GITHUB_ACTIONS_DEVOPS:
            search_pct = rng.uniform(38.0, 44.0)
            suggested_pct = rng.uniform(22.0, 26.0)
            browse_pct = rng.uniform(16.0, 20.0)
        elif bp["time_sensitive"]:
            search_pct = rng.uniform(14.0, 18.0)
            suggested_pct = rng.uniform(36.0, 42.0)
            browse_pct = rng.uniform(24.0, 28.0)
        else:
            search_pct = rng.uniform(22.0, 26.0)
            suggested_pct = rng.uniform(30.0, 36.0)
            browse_pct = rng.uniform(20.0, 26.0)

        ext_pct = rng.uniform(3.5, 5.5)
        search_pct = round(search_pct, 2)
        suggested_pct = round(suggested_pct, 2)
        browse_pct = round(browse_pct, 2)
        ext_pct = round(ext_pct, 2)
        direct_pct = round(
            100.0 - (search_pct + suggested_pct + browse_pct + ext_pct), 2
        )

        traffic_sources = [
            TrafficSourceMetric(
                source="youtube_search",
                views=int(views * (search_pct / 100.0)),
                percentage=search_pct,
            ),
            TrafficSourceMetric(
                source="suggested_videos",
                views=int(views * (suggested_pct / 100.0)),
                percentage=suggested_pct,
            ),
            TrafficSourceMetric(
                source="browse_features",
                views=int(views * (browse_pct / 100.0)),
                percentage=browse_pct,
            ),
            TrafficSourceMetric(
                source="external",
                views=int(views * (ext_pct / 100.0)),
                percentage=ext_pct,
            ),
            TrafficSourceMetric(
                source="direct_or_other",
                views=int(views * (direct_pct / 100.0)),
                percentage=direct_pct,
            ),
        ]

        # Geography
        us_pct = rng.uniform(36.0, 40.0)
        in_pct = rng.uniform(20.0, 24.0)
        gb_pct = rng.uniform(6.5, 8.5)
        de_pct = rng.uniform(4.5, 6.5)
        ca_pct = rng.uniform(3.5, 5.5)
        us_pct = round(us_pct, 2)
        in_pct = round(in_pct, 2)
        gb_pct = round(gb_pct, 2)
        de_pct = round(de_pct, 2)
        ca_pct = round(ca_pct, 2)
        other_pct = round(100.0 - (us_pct + in_pct + gb_pct + de_pct + ca_pct), 2)

        geography = [
            GeographyMetric(
                country_code="US",
                views=int(views * (us_pct / 100.0)),
                percentage=us_pct,
            ),
            GeographyMetric(
                country_code="IN",
                views=int(views * (in_pct / 100.0)),
                percentage=in_pct,
            ),
            GeographyMetric(
                country_code="GB",
                views=int(views * (gb_pct / 100.0)),
                percentage=gb_pct,
            ),
            GeographyMetric(
                country_code="DE",
                views=int(views * (de_pct / 100.0)),
                percentage=de_pct,
            ),
            GeographyMetric(
                country_code="CA",
                views=int(views * (ca_pct / 100.0)),
                percentage=ca_pct,
            ),
            GeographyMetric(
                country_code="ZZ",
                views=int(views * (other_pct / 100.0)),
                percentage=other_pct,
            ),
        ]

        # Device types
        desktop_pct = rng.uniform(52.0, 58.0)
        mobile_pct = rng.uniform(28.0, 34.0)
        tablet_pct = rng.uniform(4.0, 6.0)
        desktop_pct = round(desktop_pct, 2)
        mobile_pct = round(mobile_pct, 2)
        tablet_pct = round(tablet_pct, 2)
        tv_pct = round(100.0 - (desktop_pct + mobile_pct + tablet_pct), 2)

        device_types = [
            DeviceMetric(
                device_type="desktop",
                views=int(views * (desktop_pct / 100.0)),
                percentage=desktop_pct,
            ),
            DeviceMetric(
                device_type="mobile_phone",
                views=int(views * (mobile_pct / 100.0)),
                percentage=mobile_pct,
            ),
            DeviceMetric(
                device_type="tablet",
                views=int(views * (tablet_pct / 100.0)),
                percentage=tablet_pct,
            ),
            DeviceMetric(
                device_type="tv",
                views=int(views * (tv_pct / 100.0)),
                percentage=tv_pct,
            ),
        ]

        # Public metadata
        public_meta = VideoPublicMetadata(
            video_id=video_id,
            title=title_text,
            description=(
                f"In this video we explore {title_text}. "
                "Step-by-step practical implementation with complete code repository links and production architecture guidelines."
            ),
            tags=[
                "ai",
                "software engineering",
                "python",
                "google cloud",
                "gemini",
                bp["cluster"],
            ],
            duration_seconds=duration,
            published_at=current_date,
            view_count=views,
            like_count=likes,
            comment_count=comments,
            thumbnail_url=f"https://assets.croviq.app/thumbnails/{video_id}.jpg",
            category_id="28",
        )

        # Private analytics
        analytics = VideoPrivateAnalytics(
            views=views,
            watch_time_minutes=watch_time_mins,
            avg_view_duration_seconds=avg_view_dur,
            avg_view_percentage=avg_view_pct,
            subscribers_gained=subs_gained,
            subscribers_lost=subs_lost,
            likes=likes,
            comments=comments,
            shares=shares,
            impressions=impressions,
            ctr_percentage=ctr_pct,
            estimated_revenue_usd=est_revenue,
            retention_curve=retention_curve,
            traffic_sources=traffic_sources,
            geography=geography,
            device_types=device_types,
        )

        # Derived features
        derived = DerivedVideoFeatures(
            content_pillar=bp["pillar"],
            video_format=bp["format"],
            title_style=bp["style"],
            first_demo_seconds=first_demo,
            hook_length_seconds=max(6, first_demo - 4),
            setup_time_seconds=setup_time,
            topic_cluster=bp["cluster"],
            is_time_sensitive_topic=bp["time_sensitive"],
        )

        video = ChannelVideo(
            video_id=video_id,
            public=public_meta,
            analytics=analytics,
            derived=derived,
        )
        videos.append(video)

        # Accumulate channel aggregates
        total_views_accum += views
        total_watch_time_mins_accum += watch_time_mins
        total_subs_gained_accum += subs_gained
        total_subs_lost_accum += subs_lost
        total_impressions_accum += impressions
        total_likes_accum += likes
        total_comments_accum += comments
        total_shares_accum += shares

    # Final net subscriber count (~50,000 target)
    current_subs = (total_subs_gained_accum - total_subs_lost_accum) + 4850

    # Aggregate private channel analytics
    avg_channel_view_dur = round(
        (total_watch_time_mins_accum * 60.0) / total_views_accum, 2
    )
    avg_channel_ctr = round(
        (total_views_accum / total_impressions_accum) * 100.0, 2
    )

    channel_private_analytics = ChannelPrivateAnalytics(
        total_views=total_views_accum,
        total_watch_time_hours=round(total_watch_time_mins_accum / 60.0, 2),
        current_subscribers=current_subs,
        total_subscribers_gained=total_subs_gained_accum,
        total_subscribers_lost=total_subs_lost_accum,
        avg_view_duration_seconds=avg_channel_view_dur,
        avg_ctr_percentage=avg_channel_ctr,
        total_impressions=total_impressions_accum,
        top_traffic_sources=[
            TrafficSourceMetric(
                source="suggested_videos",
                views=int(total_views_accum * 0.35),
                percentage=35.0,
            ),
            TrafficSourceMetric(
                source="youtube_search",
                views=int(total_views_accum * 0.31),
                percentage=31.0,
            ),
            TrafficSourceMetric(
                source="browse_features",
                views=int(total_views_accum * 0.24),
                percentage=24.0,
            ),
            TrafficSourceMetric(
                source="external",
                views=int(total_views_accum * 0.06),
                percentage=6.0,
            ),
            TrafficSourceMetric(
                source="direct_or_other",
                views=int(total_views_accum * 0.04),
                percentage=4.0,
            ),
        ],
        top_geographies=[
            GeographyMetric(
                country_code="US",
                views=int(total_views_accum * 0.39),
                percentage=39.0,
            ),
            GeographyMetric(
                country_code="IN",
                views=int(total_views_accum * 0.23),
                percentage=23.0,
            ),
            GeographyMetric(
                country_code="GB",
                views=int(total_views_accum * 0.08),
                percentage=8.0,
            ),
            GeographyMetric(
                country_code="DE",
                views=int(total_views_accum * 0.06),
                percentage=6.0,
            ),
            GeographyMetric(
                country_code="CA",
                views=int(total_views_accum * 0.05),
                percentage=5.0,
            ),
            GeographyMetric(
                country_code="ZZ",
                views=int(total_views_accum * 0.19),
                percentage=19.0,
            ),
        ],
        device_distribution=[
            DeviceMetric(
                device_type="desktop",
                views=int(total_views_accum * 0.58),
                percentage=58.0,
            ),
            DeviceMetric(
                device_type="mobile_phone",
                views=int(total_views_accum * 0.33),
                percentage=33.0,
            ),
            DeviceMetric(
                device_type="tablet",
                views=int(total_views_accum * 0.05),
                percentage=5.0,
            ),
            DeviceMetric(
                device_type="tv",
                views=int(total_views_accum * 0.04),
                percentage=4.0,
            ),
        ],
    )

    channel_public = ChannelPublicMetadata(
        channel_id=channel_id,
        title="Modern AI Engineering",
        description=(
            "Deep-dive technical tutorials, architecture walkthroughs, and production benchmarks "
            "for AI engineers building with Gemini, Vertex AI, Cloud Run, Python, and GitHub Actions."
        ),
        custom_url="@ModernAIEngineering",
        subscriber_count=current_subs,
        video_count=len(videos),
        total_views=total_views_accum,
        joined_at=start_date,
        country="US",
        avatar_url="https://assets.croviq.app/channels/modern_ai_eng_avatar.jpg",
        banner_url="https://assets.croviq.app/channels/modern_ai_eng_banner.jpg",
    )

    derived_channel = DerivedChannelFeatures(
        primary_niche="AI Engineering & Cloud Architecture",
        content_pillars=[
            ContentPillar.AI_AGENTS,
            ContentPillar.GEMINI_VERTEX,
            ContentPillar.GITHUB_ACTIONS_DEVOPS,
            ContentPillar.CLOUD_RUN_GCP,
            ContentPillar.RAG_MEMORY,
        ],
        high_performing_formats=[
            VideoFormat.AGENT_BUILD,
            VideoFormat.DEVOPS_PIPELINE,
            VideoFormat.TOOL_COMPARISON,
        ],
        weak_formats=[VideoFormat.TUTORIAL],
        average_publish_interval_days=round(540.0 / len(videos), 1),
        inferred_audience_level="Senior Software Engineer / AI Practitioner",
    )

    channel = Channel(
        channel_id=channel_id,
        source_type="synthetic",
        public=channel_public,
        analytics=channel_private_analytics,
        derived=derived_channel,
        videos=videos,
    )

    return SampleChannelFixture(
        fixture_version="1.0.0",
        schema_version="1.0.0",
        source_type="synthetic",
        generated_by="scripts/generate_sample_channel.py",
        seed=SEED,
        generated_at=datetime(2026, 8, 26, 0, 0, 0, tzinfo=timezone.utc),
        video_count=len(videos),
        channel=channel,
    )


def main() -> None:
    fixture = generate_sample_dataset()

    output_dir = (
        repo_root
        / "packages"
        / "domain"
        / "src"
        / "croviq_domain"
        / "fixtures"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sample_channel_ai_engineering_v1.json"

    # Serialize with stable 2-space indentation and sorted keys for strict byte determinism
    json_str = fixture.model_dump_json(indent=2)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_str + "\n")

    print(f"Generated {fixture.video_count} videos for {fixture.channel.public.title}")
    print(f"Total Subscribers: {fixture.channel.public.subscriber_count:,}")
    print(f"Total Lifetime Views: {fixture.channel.analytics.total_views:,}")
    print(f"Wrote static fixture to: {output_path}")


if __name__ == "__main__":
    main()
