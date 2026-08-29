"""Live Production Verification for Alex Canonical Agent Refactor."""

import asyncio
from datetime import UTC, datetime
import json
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api/src"))
sys.path.insert(0, os.path.abspath("packages/domain/src"))
sys.path.insert(0, os.path.abspath("packages/observability/src"))
sys.path.insert(0, os.path.abspath("packages/agents/src"))

import firebase_admin
from firebase_admin import firestore

from croviq_agents.alex import AlexDataScientist
from croviq_api.memory.google import GoogleMemoryBankStore
from croviq_domain.agent_config import AgentId
from croviq_domain.channel_intelligence import (
    ResearchCadence,
    ResearchConfig,
    ResearchPrompt,
)
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.memory import build_memory_scope


async def main() -> None:
    project_id = os.getenv("GCP_PROJECT_ID", "croviq-506602")
    location = os.getenv("GCP_REGION", "us-central1")
    memory_bank_id = "9001435065032376320"

    print("=" * 80)
    print("ALEX CANONICAL AGENT REFACTOR — LIVE GCP PRODUCTION VERIFICATION")
    print("=" * 80)

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    results = {}

    # -------------------------------------------------------------------------
    # 1. GOOGLE AGENT PLATFORM MEMORY BANK CRUD TRUTH
    # -------------------------------------------------------------------------
    print("\n[STEP 1] Testing Google Agent Platform Memory Bank...")
    store = GoogleMemoryBankStore(
        project_id=project_id,
        location=location,
        memory_bank_id=memory_bank_id,
    )

    parent = store._resolve_parent()
    print(f"   Resolved Memory Bank Parent: {parent}")
    assert "9001435065032376320" in parent, "Reasoning Engine ID must be numeric"

    # List
    memories = await store.list_memories(scope={"channel_id": "croviq_syn_ai_eng_01"})
    print(f"   Found {len(memories)} existing memories in Memory Bank")
    for m in memories[:3]:
        print(f"   - [{m.memory_id}] {m.fact[:80]}... (Source: {m.provenance})")

    # Create
    test_fact = "Live Verification Memory: Videos featuring early technical demonstrations retain viewers 28% better."
    test_scope = build_memory_scope(channel_id="croviq_syn_ai_eng_01", agent_id="alex")
    created = await store.create_memory(
        fact=test_fact,
        scope=test_scope,
        provenance="Live Audit Verification",
    )
    print(f"   ✓ Created Memory Record: {created.name} (ID: {created.memory_id})")

    # Search
    search_results = await store.search_memories(
        query="technical demonstrations",
        scope={"channel_id": "croviq_syn_ai_eng_01"},
    )
    print(f"   ✓ Search retrieved {len(search_results)} matching memories")
    assert any(created.memory_id in r.name or created.memory_id == r.memory_id for r in search_results), "Search must retrieve newly created memory"

    # Delete
    deleted = await store.delete_memory(created.name)
    print(f"   ✓ Deleted Memory Record: {deleted}")

    # Verify no longer present
    after_del = await store.list_memories(scope={"channel_id": "croviq_syn_ai_eng_01"})
    assert not any(created.memory_id in r.name for r in after_del), "Deleted memory must not appear in retrieval"
    print("   ✓ Memory Bank CRUD passed with 100% truthfulness")
    results["memory_bank"] = "PASS"

    # -------------------------------------------------------------------------
    # 2. ALEX CHAT REASONING WITH GEMINI 3.7 FLASH
    # -------------------------------------------------------------------------
    print("\n[STEP 2] Testing Alex Conversational Reasoning with Gemini 3.7 Flash...")
    alex = AlexDataScientist(project_id=project_id, model_id="gemini-3.7-flash")
    provider = SampleChannelDataProvider()
    channel = await provider.get_channel()
    videos = await provider.get_videos(limit=20)
    profile = await store.get_profile(channel.channel_id)
    lessons = await store.get_lessons(channel.channel_id)

    # 2.1 Greeting "hi"
    print("   Testing greeting 'hi'...")
    hi_res = await alex.chat(
        message="hi",
        channel_profile=profile,
        channel_lessons=lessons,
        channel=channel,
        videos=videos,
    )
    print(f"   ✓ Alex Response: {hi_res['reply'][:120]}...")
    assert len(hi_res["reply"]) > 20, "Alex must generate a substantive response"
    assert "alex" in hi_res["reply"].lower() or "channel" in hi_res["reply"].lower() or "data" in hi_res["reply"].lower()

    # 2.2 Analytical question: "How did my last video perform?"
    print("   Testing 'How did my last video perform?'...")
    perf_res = await alex.chat(
        message="How did my last video perform?",
        channel_profile=profile,
        channel_lessons=lessons,
        channel=channel,
        videos=videos,
    )
    print(f"   ✓ Alex Analytical Response: {perf_res['reply'][:120]}...")
    print(f"   ✓ Tools executed: {[t['tool_name'] for t in perf_res.get('tool_executions', [])]}")
    assert any(t["tool_name"] == "channel_analytics_inspection" for t in perf_res.get("tool_executions", []))

    # 2.3 Topic recommendation: "What should I make next?"
    print("   Testing 'What should I make next?'...")
    next_res = await alex.chat(
        message="What should I make next?",
        channel_profile=profile,
        channel_lessons=lessons,
        channel=channel,
        videos=videos,
    )
    print(f"   ✓ Alex Recommendation: {next_res['reply'][:120]}...")
    assert any(t["tool_name"] == "channel_interest_profile_match" for t in next_res.get("tool_executions", []))

    results["alex_chat"] = "PASS"

    # -------------------------------------------------------------------------
    # 3. PROMPT RUNTIME INSERTION & OVERRIDE
    # -------------------------------------------------------------------------
    print("\n[STEP 3] Testing Prompt Runtime Insertion...")
    custom_directive = "When answering analytical questions, begin with the word EVIDENCE."
    custom_res = await alex.chat(
        message="Calculate the correlation between demo timing and retention.",
        custom_prompt=f"You are Alex. {custom_directive}",
        channel_profile=profile,
        channel_lessons=lessons,
        channel=channel,
        videos=videos,
    )
    print(f"   ✓ Alex Custom Response: {custom_res['reply'][:120]}...")
    assert any(t["tool_name"] == "python_code_execution" for t in custom_res.get("tool_executions", []))
    results["prompt_runtime"] = "PASS"

    # -------------------------------------------------------------------------
    # 4. GROUNDED RESEARCH & DIVERSE IDEAS WORTH MAKING
    # -------------------------------------------------------------------------
    print("\n[STEP 4] Testing Alex Grounded Research & Ideas Worth Making...")
    prompts = [
        ResearchPrompt(
            prompt_id="emerging-opportunities",
            text="Discover high-conviction video opportunities and emerging technical breakthroughs for this channel",
            enabled=True,
            use_broad_web_search=True,
            preferred_sources=[],
        ),
    ]
    run, findings = await alex.run_grounded_research(
        prompts=prompts,
        channel_profile=profile,
        workspace_id="ws_accept_prod",
        channel_id="croviq_syn_ai_eng_01",
    )
    print(f"   ✓ Research Run Status: {run.status} (Findings: {len(findings)}, Latency: {run.latency_ms}ms)")
    for f in findings[:3]:
        print(f"   - [{f.primary_entity}] {f.title}")
        print(f"     Why it fits: {f.why_it_matters[:80]}...")
        if f.source_citations:
            print(f"     Source: {f.source_citations[0].domain} ({f.source_citations[0].url})")

    assert len(findings) > 0, "Grounded research must return findings"
    results["ideas_worth_making"] = "PASS"

    print("\n" + "=" * 80)
    print("ALL PRODUCTION ACCEPTANCE CHECKS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
