from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from croviq_api.auth.dependencies import get_current_user
from croviq_api.channels.research_repository import (
    ResearchRepository,
    get_research_repository,
)
from croviq_api.workspaces.repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from croviq_domain.channel_dashboard import ChannelDashboard, build_channel_dashboard
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.user import User
from croviq_observability import log_event
from croviq_domain.channel_intelligence import (
    ResearchCadence,
    ResearchConfig,
    ResearchPrompt,
)


router = APIRouter(prefix="/channels", tags=["Channel Intelligence"])


class UpdateResearchConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    cadence: ResearchCadence
    prompts: list[ResearchPrompt]


@router.get(
    "/sample/dashboard",
    response_model=ChannelDashboard,
    summary="Get Sample Channel Intelligence Dashboard",
    description=(
        "Compute channel intelligence from the canonical deterministic sample channel. "
        "Daily sample trends are modeled from the fixture and disclosed in the response."
    ),
)
async def get_sample_channel_dashboard(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    days: int = 28,
    end_date: Annotated[date | None, Query(alias="endDate")] = None,
) -> ChannelDashboard:
    if days not in {28, 90, 365}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="days must be one of 28, 90, or 365",
        )
    request_id = getattr(request.state, "request_id", "unknown")
    log_event(
        "alex.analysis.started",
        request_id=request_id,
        user_id=current_user.user_id,
        channel_id="croviq_syn_ai_eng_01",
        period_days=days,
        status="started",
    )
    try:
        dashboard = await build_channel_dashboard(
            SampleChannelDataProvider(), days=days, end_date=end_date
        )
    except Exception as exc:
        log_event(
            "alex.analysis.failed",
            request_id=request_id,
            user_id=current_user.user_id,
            channel_id="croviq_syn_ai_eng_01",
            period_days=days,
            status="failed",
            error_code=type(exc).__name__,
        )
        raise
    log_event(
        "alex.analysis.completed",
        request_id=request_id,
        user_id=current_user.user_id,
        channel_id=dashboard.channel.channel_id,
        period_days=days,
        insight_count=len(dashboard.insights),
        status="completed",
    )
    return dashboard


@router.get(
    "/research/config",
    response_model=ResearchConfig,
    summary="Get Alex Research Settings",
)
async def get_research_config(
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)],
) -> ResearchConfig:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    return await research_repo.get_config(workspace.workspace_id)


@router.put(
    "/research/config",
    response_model=ResearchConfig,
    summary="Update Alex Research Settings",
)
async def update_research_config(
    payload: UpdateResearchConfigRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)],
) -> ResearchConfig:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    current = await research_repo.get_config(workspace.workspace_id)
    now = datetime.now(UTC)
    next_run_at = (
        current.next_run_at
        if current.cadence is payload.cadence
        else now + payload.cadence.interval
    )
    updated = ResearchConfig(
        workspace_id=workspace.workspace_id,
        channel_id=current.channel_id,
        enabled=payload.enabled,
        cadence=payload.cadence,
        prompts=payload.prompts,
        last_run_at=current.last_run_at,
        next_run_at=next_run_at,
        updated_at=now,
    )
    return await research_repo.save_config(updated)
