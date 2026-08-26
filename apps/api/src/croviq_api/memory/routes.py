"""Channel Memory API endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from croviq_api.auth.dependencies import get_current_user
from croviq_api.memory.dependencies import get_memory_store, initialize_sample_channel_memory
from croviq_api.memory.logging import log_memory_event
from croviq_api.memory.store import ChannelMemoryStore
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, TargetAgent
from croviq_domain.user import User

memory_router = APIRouter(prefix="/channel/memory", tags=["Memory"])


@memory_router.get(
    "/profile",
    response_model=ChannelMemoryProfile,
    summary="Retrieve Channel Memory Profile",
    description="Retrieve the canonical structured ChannelMemoryProfile from Memory Bank.",
)
async def get_channel_memory_profile(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    channel_id: str = Query(
        default="croviq_syn_ai_eng_01",
        description="Canonical channel identifier.",
    ),
) -> ChannelMemoryProfile:
    """Retrieve structured channel memory profile."""
    request_id = getattr(request.state, "request_id", "unknown")

    # If querying sample channel, ensure it has been seeded
    if channel_id == "croviq_syn_ai_eng_01":
        await initialize_sample_channel_memory(store)

    profile = await store.get_profile(channel_id)
    if profile is None:
        log_memory_event(
            event_type="memory.profile.retrieve",
            channel_id=channel_id,
            status=status.HTTP_404_NOT_FOUND,
            request_id=request_id,
            message=f"Memory profile for channel '{channel_id}' not found.",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory profile for channel '{channel_id}' not found.",
        )

    log_memory_event(
        event_type="memory.profile.retrieve",
        channel_id=channel_id,
        status=status.HTTP_200_OK,
        request_id=request_id,
        message=f"Successfully retrieved memory profile for channel '{channel_id}'.",
    )
    return profile


@memory_router.get(
    "/lessons",
    response_model=list[ChannelLesson],
    summary="Retrieve Channel Lessons",
    description="Retrieve active ChannelLessons scoped to a channel, optionally filtered by target agent.",
)
async def get_channel_lessons(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    channel_id: str = Query(
        default="croviq_syn_ai_eng_01",
        description="Canonical channel identifier.",
    ),
    target_agent: TargetAgent | None = Query(
        default=None,
        description="Optional filter by target agent (director, editor, packaging, qa).",
    ),
) -> list[ChannelLesson]:
    """Retrieve structured channel lessons for collaborative agent workflows."""
    if channel_id == "croviq_syn_ai_eng_01":
        await initialize_sample_channel_memory(store)

    return await store.get_lessons(channel_id, target_agent=target_agent)
