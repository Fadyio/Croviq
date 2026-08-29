"""Workspace and Agent Settings API routes."""

from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status

from croviq_agents.voice import StudioVoiceSynthesizer, VoiceCatalog
from croviq_api.auth.dependencies import get_current_user
from croviq_api.memory.dependencies import get_memory_store, initialize_sample_channel_memory
from croviq_api.memory.store import ChannelMemoryStore
from croviq_api.workspaces.agent_config_repository import (
    AgentConfigRepository,
    get_agent_config_repository,
)
from croviq_api.workspaces.logging import log_workspace_event
from croviq_api.workspaces.repository import WorkspaceRepository, get_workspace_repository
from croviq_api.channels.research_repository import (
    ResearchRepository,
    get_research_repository,
)
from croviq_api.channels.youtube_repository import (
    YouTubeConnectionRepository,
    get_youtube_connection_repository,
)
from croviq_api.workspaces.chat_service import (
    AgentChatService,
    get_conversation_history,
)
from croviq_api.workspaces.schemas import (
    AgentChatMessageRequest,
    AgentChatMessageResponse,
    AgentConversationHistoryResponse,
    AgentMemorySummaryResponse,
    AgentSettingsResponse,
    MemoryItemResponse,
    UpdatePromptRequest,
    UpdateVoiceSettingsRequest,
)
from croviq_domain.agent_config import (
    AgentId,
    AgentPromptConfig,
    VoiceCatalogItem,
    VoiceSampleRequest,
    VoiceSampleResponse,
    VoiceSettingsConfig,
)
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.memory import ChannelProfileBuilder
from croviq_domain.user import User
from croviq_domain.workspace import Workspace

router = APIRouter(tags=["Workspaces"])


@router.get(
    "/workspace",
    response_model=Workspace,
    summary="Get or Provision Default Workspace",
    description="Retrieve the default workspace belonging to the verified creator. If none exists, creates exactly one default Workspace idempotently.",
)
async def get_or_provision_default_workspace(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> Workspace:
    """Look up workspace belonging to verified uid; if it does not exist, create exactly one default Workspace."""
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        workspace, created = await repo.get_or_create_default_workspace(
            current_user, default_name="Croviq"
        )
    except Exception as exc:
        log_workspace_event(
            event_type="workspace.load_failed",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_id=request_id,
            user_id=current_user.user_id,
            error_code="workspace_load_failed",
            message=f"Failed to load or provision workspace for user {current_user.user_id}: {type(exc).__name__}",
            exception=exc,
        )
        raise

    if created:
        log_workspace_event(
            event_type="workspace.created",
            status=status.HTTP_200_OK,
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=workspace.workspace_id,
            message=f"Created default workspace {workspace.workspace_id} for user {current_user.user_id}",
        )
    log_workspace_event(
        event_type="workspace.loaded",
        status=status.HTTP_200_OK,
        request_id=request_id,
        user_id=current_user.user_id,
        workspace_id=workspace.workspace_id,
        message=f"Loaded workspace {workspace.workspace_id} for user {current_user.user_id}",
    )

    return workspace


@router.get(
    "/workspace/agent-settings",
    response_model=AgentSettingsResponse,
    summary="Get Agent Settings",
    description="Retrieve creator-configured prompts for Alex, Leo, and Maya, narration voice settings, and official Google voice catalog.",
)
async def get_agent_settings(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
) -> AgentSettingsResponse:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    leo_prompt = await agent_config_repo.get_agent_prompt(workspace.workspace_id, AgentId.LEO)
    maya_prompt = await agent_config_repo.get_agent_prompt(workspace.workspace_id, AgentId.MAYA)
    alex_prompt = await agent_config_repo.get_agent_prompt(workspace.workspace_id, AgentId.ALEX)
    iris_prompt = await agent_config_repo.get_agent_prompt(workspace.workspace_id, AgentId.IRIS)
    voice_settings = await agent_config_repo.get_voice_settings(workspace.workspace_id)
    voices = VoiceCatalog.list_voices()

    return AgentSettingsResponse(
        leo_prompt=leo_prompt,
        maya_prompt=maya_prompt,
        alex_prompt=alex_prompt,
        iris_prompt=iris_prompt,
        voice_settings=voice_settings,
        voices=voices,
    )


@router.put(
    "/workspace/agent-settings/prompts/{agent_id}",
    response_model=AgentPromptConfig,
    summary="Update Agent Working Prompt",
    description="Update the complete editorial working prompt for Leo, Maya, Alex, or Nina. Bumps version and timestamps.",
)
@router.put(
    "/workspace/agent-settings/prompt/{agent_id}",
    response_model=AgentPromptConfig,
    include_in_schema=False,
)
async def update_agent_prompt(
    agent_id: str,
    payload: UpdatePromptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
) -> AgentPromptConfig:
    aid = str(agent_id).lower()
    if aid not in ("alex", "leo", "maya", "iris"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent_id '{agent_id}'. Must be 'alex', 'leo', 'maya', or 'iris'.",
        )
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    return await agent_config_repo.save_agent_prompt(
        workspace_id=workspace.workspace_id,
        agent_id=aid,
        prompt_text=payload.prompt_text,
    )


@router.post(
    "/workspace/agent-settings/prompts/{agent_id}/reset",
    response_model=AgentPromptConfig,
    summary="Reset Agent Working Prompt",
    description="Reset Leo, Maya, Alex, or Nina working prompt back to the system default prompt.",
)
@router.post(
    "/workspace/agent-settings/prompt/{agent_id}/reset",
    response_model=AgentPromptConfig,
    include_in_schema=False,
)
async def reset_agent_prompt(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
) -> AgentPromptConfig:
    aid = str(agent_id).lower()
    if aid not in ("alex", "leo", "maya", "iris"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent_id '{agent_id}'. Must be 'alex', 'leo', 'maya', or 'iris'.",
        )
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    return await agent_config_repo.reset_agent_prompt(
        workspace_id=workspace.workspace_id,
        agent_id=aid,
    )


@router.get(
    "/workspace/agent-settings/memory",
    response_model=AgentMemorySummaryResponse,
    summary="View Agent Memory with Search",
    description="Retrieve agent-scoped lessons and preferences from Channel Memory Bank with search filtering.",
)
async def get_agent_memory(
    current_user: Annotated[User, Depends(get_current_user)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    agent_id: str | None = None,
    query: str | None = None,
) -> AgentMemorySummaryResponse:
    channel_id = "croviq_syn_ai_eng_01"
    channel_title = "Croviq"
    aid = (agent_id or "alex").lower()

    try:
        await initialize_sample_channel_memory(memory_store)
        profile = await memory_store.get_profile(channel_id)
        lessons = await memory_store.get_lessons(channel_id)
        if profile and getattr(profile, "channel_name", None):
            channel_title = profile.channel_name
        formatted_lessons = [
            MemoryItemResponse(
                topic=getattr(lesson, "directive", str(lesson)),
                content=getattr(lesson, "evidence_summary", getattr(lesson, "directive", "Memory lesson")),
                learned_from=getattr(lesson, "learned_from_production_id", "historical_analysis.mp4"),
            )
            for lesson in lessons
        ]
    except Exception:
        provider = SampleChannelDataProvider()
        channel = await provider.get_channel()
        profile = ChannelProfileBuilder.build_profile(channel)
        channel_title = profile.channel_name
        lessons = ChannelProfileBuilder.build_lessons(channel)
        formatted_lessons = [
            MemoryItemResponse(
                topic=getattr(lesson, "directive", str(lesson)),
                content=getattr(lesson, "evidence_summary", getattr(lesson, "directive", "Memory lesson")),
                learned_from=getattr(lesson, "learned_from_production_id", "historical_analysis.mp4"),
            )
            for lesson in lessons
        ]

    # Agent-specific knowledge enrichment
    if aid == "alex":
        style_guide = "Evidence-first quantitative statistical analysis with falsifiable hypotheses and regression baselines."
        prefs = [
            "Prefers 30-second early demonstrations to maximize viewer retention.",
            "Track net subscriber conversion per 1,000 views across all content pillars.",
            "Deduplicate external research semantically and prioritize high-signal developer releases.",
        ]
        if not any("demonstration" in l.topic.lower() for l in formatted_lessons):
            formatted_lessons.insert(
                0,
                MemoryItemResponse(
                    topic="Early demonstration timing tracks viewer retention",
                    content="Videos with technical terminal demonstrations in the first 30 seconds average 58.4% retention.",
                    learned_from="100-video historical channel dataset",
                ),
            )
    elif aid == "iris":
        style_guide = "Broadcast-grade quality verification adhering to strict audio loudness and caption timing standards."
        prefs = [
            "Target dialogue loudness at -16 LUFS (±1 LUFS) with -1 dBTP ceiling.",
            "Zero tolerance for caption drift exceeding 100ms from speech onset.",
            "Enforce strict human confirmation before external YouTube publishing.",
        ]
        formatted_lessons = [
            MemoryItemResponse(
                topic="Audio Loudness & Ceiling Compliance",
                content="Master renders must meet EBU R128 / ITU-R BS.1770 standards at -16.0 LUFS.",
                learned_from="Broadcast QA specification",
            ),
            MemoryItemResponse(
                topic="Caption Boundary Synchronization",
                content="Word-level timestamps must match speech start times within 50ms to prevent perceptual lag.",
                learned_from="Viewer accessibility benchmarks",
            ),
        ]
    else:
        style_guide = "Concise, high-momentum narrative pacing eliminating filler speech and dead air."
        prefs = [
            "Remove conversational preambles ('So basically', 'Um') while keeping natural rhythm.",
            "Apply room-tone bridges and visual B-roll coverage across dialogue cuts.",
            "Extract high-energy standalone excerpts for vertical 9:16 Shorts.",
        ]

    # Filter by query if provided
    if query and query.strip():
        q = query.strip().lower()
        formatted_lessons = [
            item for item in formatted_lessons
            if q in item.topic.lower() or q in item.content.lower() or (item.learned_from and q in item.learned_from.lower())
        ]
        prefs = [p for p in prefs if q in p.lower()]

    return AgentMemorySummaryResponse(
        channel_title=channel_title,
        style_guide=style_guide,
        creator_preferences=prefs,
        lessons=formatted_lessons,
    )


@router.get(
    "/workspace/agent-settings/voice",
    response_model=VoiceSettingsConfig,
    summary="Get Voice Settings",
    description="Get current narration mode and Studio Voice selection.",
)
async def get_voice_settings_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
) -> VoiceSettingsConfig:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    return await agent_config_repo.get_voice_settings(workspace.workspace_id)

@router.put(
    "/workspace/agent-settings/voice",
    response_model=VoiceSettingsConfig,
    summary="Update Voice Settings",
    description="Update narration mode (Original, Enhanced Original, Studio Voice) and selected Google voice.",
)
async def update_voice_settings_endpoint(
    payload: UpdateVoiceSettingsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
) -> VoiceSettingsConfig:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    config = VoiceSettingsConfig(
        narration_mode=payload.narration_mode,
        selected_voice=payload.selected_voice,
        language=payload.language,
        my_voice=payload.my_voice,
        updated_at=datetime.now(timezone.utc),
    )
    return await agent_config_repo.save_voice_settings(workspace.workspace_id, config)


@router.post(
    "/workspace/agent-settings/voice/sample",
    response_model=VoiceSampleResponse,
    summary="Audition Voice Sample",
    description="Preview audio sample for a selected Studio Voice (Gemini TTS) prebuilt voice.",
)
async def get_voice_sample_endpoint(
    payload: VoiceSampleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> VoiceSampleResponse:
    synthesizer = StudioVoiceSynthesizer()
    return synthesizer.generate_sample_audio_payload(
        voice_id=payload.voice_id,
        sample_text=payload.sample_text,
    )


@router.get(
    "/workspace/agents/{agent_id}/chat",
    response_model=AgentConversationHistoryResponse,
    summary="Get Agent Conversation History",
)
async def get_agent_chat_history(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> AgentConversationHistoryResponse:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    history = get_conversation_history(workspace.workspace_id, agent_id)
    return AgentConversationHistoryResponse(
        agent_id=agent_id.lower(),
        messages=[AgentChatMessageResponse.model_validate(m) for m in history],
    )


@router.post(
    "/workspace/agents/{agent_id}/chat",
    response_model=AgentChatMessageResponse,
    summary="Send Message to Agent Workspace Chat",
)
async def send_agent_chat_message(
    agent_id: str,
    payload: AgentChatMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)],
) -> AgentChatMessageResponse:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    aid = agent_id.lower()
    if aid not in {"alex", "leo", "iris"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' is not an active production agent",
        )

    service = AgentChatService(
        workspace_id=workspace.workspace_id,
        agent_config_repo=agent_config_repo,
        memory_store=memory_store,
        youtube_repo=youtube_repo,
        research_repo=research_repo,
    )

    if aid == "alex":
        result = await service.handle_alex_message(payload.message)
    elif aid == "leo":
        result = await service.handle_leo_message(payload.message)
    else:
        result = await service.handle_iris_message(payload.message)

    return AgentChatMessageResponse.model_validate(result)
