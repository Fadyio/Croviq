from datetime import UTC, date, datetime, timedelta
import logging
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
import httpx
from pydantic import BaseModel, ConfigDict, Field

from croviq_agents.alex import AlexDataScientist
from croviq_api.auth.dependencies import get_current_user
from croviq_api.channels.research_repository import (
    ResearchRepository,
    get_research_repository,
)
from croviq_api.channels.youtube_provider import (
    YouTubeChannelDataProvider,
    YouTubeProviderError,
)
from croviq_api.channels.youtube_repository import (
    YouTubeConnection,
    YouTubeConnectionPublicSummary,
    YouTubeConnectionRepository,
    get_youtube_connection_repository,
)
from croviq_api.channels.token_refresh import (
    YouTubeReauthRequiredError,
    refresh_youtube_access_token_if_needed,
)
from croviq_api.config import get_settings
from croviq_api.memory.dependencies import get_memory_store
from croviq_api.memory.store import ChannelMemoryStore
from croviq_api.workspaces.repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from croviq_api.workspaces.agent_config_repository import (
    AgentConfigRepository,
    get_agent_config_repository,
)
from croviq_domain.agent_config import AgentId
from croviq_domain.channel_dashboard import ChannelDashboard, build_channel_dashboard
from croviq_domain.channel_intelligence import (
    FindingLifecycle,
    ResearchCadence,
    ResearchConfig,
    ResearchFinding,
    ResearchPrompt,
    ResearchRun,
    ResearchRunStatus,
)
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_api.channels.scheduler_auth import verify_scheduler_identity
from croviq_domain.memory import ChannelLesson, ChannelMemoryProfile, ChannelProfileBuilder
from croviq_domain.user import User
from croviq_observability import log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["Channel Intelligence"])

YOUTUBE_OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
YOUTUBE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPE_YOUTUBE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"
SCOPE_ANALYTICS_READONLY = "https://www.googleapis.com/auth/yt-analytics.readonly"
SCOPE_MONETARY_READONLY = "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"
SCOPE_YOUTUBE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"

class UpdateResearchConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    cadence: ResearchCadence
    prompts: list[ResearchPrompt] = Field(default_factory=list)

class YouTubeAuthUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    redirect_uri: str = Field(..., min_length=1)
    include_monetary: bool = False
    include_upload: bool = False

class YouTubeAuthUrlResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_url: str
    state_token: str
    scopes: list[str]


class YouTubeCallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    redirect_uri: str = Field(..., min_length=1)


class CodeExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_goal: str = "Evaluate first demonstration timing effect on retention and subscriber conversion"


class DistillFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_id: str | None
    directive: str | None
    confidence: float | None
    status: str


class SchedulerTickResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs_evaluated: int
    runs_executed: int
    findings_created: int
    status: str


# -----------------------------------------------------------------------------
# 1. Sample Channel Intelligence Dashboard
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# 2. YouTube OAuth & Connected Channel Dashboard
# -----------------------------------------------------------------------------


@router.post(
    "/youtube/auth-url",
    response_model=YouTubeAuthUrlResponse,
    summary="Generate YouTube OAuth Authorization URL",
    description="Generate secure Google OAuth 2.0 authorization URL with CSRF state token.",
)
async def generate_youtube_auth_url(
    payload: YouTubeAuthUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
) -> YouTubeAuthUrlResponse:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    state_token = await youtube_repo.create_oauth_state(
        workspace_id=workspace.workspace_id,
        user_id=current_user.user_id,
        redirect_uri=payload.redirect_uri,
        include_monetary=payload.include_monetary,
        include_upload=payload.include_upload,
    )

    scopes = [SCOPE_YOUTUBE_READONLY, SCOPE_ANALYTICS_READONLY]
    if payload.include_monetary:
        scopes.append(SCOPE_MONETARY_READONLY)
    if payload.include_upload:
        scopes.append(SCOPE_YOUTUBE_UPLOAD)
    client_id = get_settings().google_oauth_client_id or "dummy-client-id"
    params = {
        "client_id": client_id,
        "redirect_uri": payload.redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": state_token,
    }
    auth_url = f"{YOUTUBE_OAUTH_AUTH_URL}?{urlencode(params)}"
    return YouTubeAuthUrlResponse(auth_url=auth_url, state_token=state_token, scopes=scopes)


@router.post(
    "/youtube/callback",
    response_model=YouTubeConnectionPublicSummary,
    summary="Handle YouTube OAuth Callback",
    description="Exchange authorization code for tokens, verify CSRF state, and store connection server-side.",
)
async def handle_youtube_callback(
    payload: YouTubeCallbackRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
) -> YouTubeConnectionPublicSummary:
    request_id = getattr(request.state, "request_id", "unknown")
    state = await youtube_repo.verify_and_consume_oauth_state(payload.state)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state token (CSRF protection).",
        )

    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    if state.workspace_id != workspace.workspace_id or state.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-workspace or cross-user OAuth state is forbidden.",
        )

    client_id = get_settings().google_oauth_client_id
    client_secret = get_settings().google_oauth_client_secret
    existing_conn = await youtube_repo.get_connection(workspace.workspace_id)
    access_token = f"yt_access_{payload.code}"
    refresh_token = (
        existing_conn.refresh_token
        if existing_conn and existing_conn.refresh_token
        else f"yt_refresh_{payload.code}"
    )
    scopes = [SCOPE_YOUTUBE_READONLY, SCOPE_ANALYTICS_READONLY]
    if state.include_monetary:
        scopes.append(SCOPE_MONETARY_READONLY)
    if state.include_upload:
        scopes.append(SCOPE_YOUTUBE_UPLOAD)
    if existing_conn and existing_conn.scopes:
        scopes = list(dict.fromkeys(existing_conn.scopes + scopes))
    if client_id and client_secret and not payload.code.startswith("mock-"):
        async with httpx.AsyncClient(timeout=20) as http_client:
            token_resp = await http_client.post(
                YOUTUBE_OAUTH_TOKEN_URL,
                data={
                    "code": payload.code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": payload.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                error_detail = token_resp.text
                try:
                    error_json = token_resp.json()
                    error_detail = (
                        error_json.get("error_description")
                        or error_json.get("error")
                        or token_resp.text
                    )
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Google OAuth token exchange failed: {error_detail}",
                )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google OAuth token response missing access_token",
                )
            if "refresh_token" in token_data and token_data["refresh_token"]:
                refresh_token = token_data["refresh_token"]
            if "scope" in token_data:
                granted_scopes = token_data["scope"].split()
                scopes = list(dict.fromkeys(scopes + granted_scopes))

    if payload.code.startswith("mock-"):
        channel_id = "UC_mock_connected_channel"
        title = "Connected YouTube Channel (Mock)"
        avatar_url = ""
        sub_count = 50000
    else:
        provider = YouTubeChannelDataProvider(access_token=access_token)
        try:
            channel = await provider.get_channel()
            channel_id = channel.channel_id
            title = channel.public.title
            avatar_url = channel.public.avatar_url or ""
            sub_count = channel.public.subscriber_count
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch authentic YouTube channel metadata: {exc}",
            )
    now = datetime.now(UTC)
    connection = YouTubeConnection(
        workspace_id=workspace.workspace_id,
        user_id=current_user.user_id,
        channel_id=channel_id,
        channel_title=title,
        avatar_url=avatar_url,
        subscriber_count=sub_count,
        access_token=access_token,
        refresh_token=refresh_token,
        status="connected",
        error_message=None,
        token_expiry=now + timedelta(hours=1),
        scopes=scopes,
        connected_at=now,
        last_sync_at=now,
    )
    await youtube_repo.save_connection(connection)

    log_event(
        "youtube.oauth.connected",
        request_id=request_id,
        user_id=current_user.user_id,
        workspace_id=workspace.workspace_id,
        channel_id=channel_id,
        channel_title=title,
        subscriber_count=sub_count,
    )

    return YouTubeConnectionPublicSummary(
        connected=True,
        status="connected",
        error_message=None,
        channel_id=channel_id,
        channel_title=title,
        avatar_url=avatar_url,
        subscriber_count=sub_count,
        last_sync_at=now,
        has_monetary_access=SCOPE_MONETARY_READONLY in scopes,
        has_upload_access=SCOPE_YOUTUBE_UPLOAD in scopes,
        scopes=scopes,
    )

@router.get(
    "/youtube/connection",
    response_model=YouTubeConnectionPublicSummary,
    summary="Get Connected YouTube Channel Status",
)
async def get_youtube_connection_status(
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
) -> YouTubeConnectionPublicSummary:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    connection = await youtube_repo.get_connection(workspace.workspace_id)
    if connection is None:
        return YouTubeConnectionPublicSummary(connected=False, status="disconnected")
    return YouTubeConnectionPublicSummary(
        connected=True,
        status=connection.status,
        error_message=connection.error_message,
        channel_id=connection.channel_id,
        channel_title=connection.channel_title,
        avatar_url=connection.avatar_url,
        subscriber_count=connection.subscriber_count,
        last_sync_at=connection.last_sync_at,
        has_monetary_access=SCOPE_MONETARY_READONLY in connection.scopes,
        has_upload_access=SCOPE_YOUTUBE_UPLOAD in connection.scopes,
        scopes=connection.scopes,
    )

@router.post(
    "/youtube/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect YouTube Channel",
)
async def disconnect_youtube_channel(
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
) -> None:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    connection = await youtube_repo.get_connection(workspace.workspace_id)
    if connection and (connection.access_token or connection.refresh_token):
        try:
            token_to_revoke = connection.refresh_token or connection.access_token
            async with httpx.AsyncClient(timeout=10) as http_client:
                await http_client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": token_to_revoke},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except Exception as exc:
            logger.warning("Google OAuth token revocation attempt ignored: %s", exc)

    await youtube_repo.delete_connection(workspace.workspace_id)

@router.get(
    "/youtube/dashboard",
    response_model=ChannelDashboard,
    summary="Get Connected Real YouTube Channel Dashboard",
)
async def get_youtube_channel_dashboard(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    youtube_repo: Annotated[YouTubeConnectionRepository, Depends(get_youtube_connection_repository)],
    days: int = 28,
    end_date: Annotated[date | None, Query(alias="endDate")] = None,
) -> ChannelDashboard:
    if days not in {28, 90, 365}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="days must be one of 28, 90, or 365",
        )
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    connection = await youtube_repo.get_connection(workspace.workspace_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected YouTube channel found for this workspace. Connect your channel first.",
        )

    request_id = getattr(request.state, "request_id", "unknown")
    log_event(
        "youtube.sync.started",
        request_id=request_id,
        user_id=current_user.user_id,
        workspace_id=workspace.workspace_id,
        channel_id=connection.channel_id,
        period_days=days,
    )

    try:
        access_token, connection = await refresh_youtube_access_token_if_needed(
            connection, youtube_repo
        )
    except YouTubeReauthRequiredError as exc:
        log_event(
            "youtube.sync.reauth_required",
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=workspace.workspace_id,
            channel_id=connection.channel_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"YouTube authorization expired or invalid: {exc}",
        ) from exc
    provider = YouTubeChannelDataProvider(
        access_token=access_token,
        analytics_start_date=date(2025, 1, 1),
        analytics_end_date=end_date or datetime.now(UTC).date(),
    )
    try:
        dashboard = await build_channel_dashboard(provider, days=days, end_date=end_date)
        log_event(
            "youtube.sync.completed",
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=workspace.workspace_id,
            channel_id=connection.channel_id,
            period_days=days,
        )
        return dashboard
    except Exception as exc:
        err_msg = str(exc).lower()
        log_event(
            "youtube.sync.failed",
            request_id=request_id,
            user_id=current_user.user_id,
            workspace_id=workspace.workspace_id,
            channel_id=connection.channel_id,
            error=str(exc),
        )
        if "401" in err_msg or "unauthorized" in err_msg:
            error_message = f"YouTube authorization expired or invalid: {exc}"
            await youtube_repo.save_connection(
                connection.model_copy(
                    update={
                        "status": "reauth_required",
                        "error_message": error_message,
                    }
                )
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_message,
            ) from exc
        if "403" in err_msg or "forbidden" in err_msg or "permission" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"YouTube API permissions required (e.g. Analytics scope): {exc}",
            ) from exc
        if "429" in err_msg or "quota" in err_msg or "rate limit" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"YouTube API quota limit exceeded: {exc}",
            ) from exc
        if "validation error" in err_msg or "pydantic" in err_msg or "input_value=none" in err_msg:
            logger.error("Data validation error during YouTube dashboard calculation: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to process YouTube analytics data. Please try again later.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch YouTube analytics: {exc}",
        ) from exc


# -----------------------------------------------------------------------------
# 3. Alex Research Settings, Topic Radar & Background Scheduler
# -----------------------------------------------------------------------------


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
    next_run_at = payload.cadence.next_run_after(current.last_run_at or now)
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


async def _load_channel_context_for_research(
    channel_id: str,
    memory_store: ChannelMemoryStore,
) -> tuple[ChannelMemoryProfile | None, list[ChannelLesson], list[Any]]:
    """Load or build canonical channel memory profile, lessons, and video catalog for research context."""
    sample_provider = SampleChannelDataProvider()
    channel = await sample_provider.get_channel()
    videos = await sample_provider.get_videos(limit=10)

    profile = await memory_store.get_profile(channel_id)
    if profile is None:
        profile = ChannelProfileBuilder.build_profile(channel)
        try:
            await memory_store.upsert_profile(profile)
        except Exception:
            pass

    lessons = await memory_store.get_lessons(channel_id)
    if not lessons:
        derived_lessons = ChannelProfileBuilder.build_lessons(channel)
        lessons = derived_lessons
        for l in derived_lessons:
            try:
                await memory_store.add_lesson(l)
            except Exception:
                pass

    return profile, lessons, videos


@router.get(
    "/research/findings",
    response_model=list[ResearchFinding],
    summary="Get Active Topic Radar Research Findings",
    description="Retrieve ranked, grounded research findings with source citations for the Alex Briefing rail.",
)
async def get_research_findings(
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    limit: int = 10,
) -> list[ResearchFinding]:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    config = await research_repo.get_config(workspace.workspace_id)
    findings = await research_repo.list_findings(
        workspace_id=workspace.workspace_id,
        channel_id=config.channel_id,
        limit=limit,
    )
    if not findings:
        # If no findings yet in repository (cold start), execute initial channel-grounded research run
        alex_prompt = await agent_config_repo.get_agent_prompt(workspace.workspace_id, AgentId.ALEX)
        channel_profile, lessons, recent_videos = await _load_channel_context_for_research(
            config.channel_id, memory_store
        )
        alex = AlexDataScientist(
            project_id=get_settings().gcp_project_id,
            location=get_settings().vertexai_location,
        )
        run, seeded = await alex.run_grounded_research(
            prompts=config.prompts,
            channel_profile=channel_profile,
            recent_videos=recent_videos,
            lessons=lessons,
            custom_prompt=alex_prompt.prompt_text if alex_prompt.is_custom else None,
            workspace_id=workspace.workspace_id,
            channel_id=config.channel_id,
            force_mock=not get_settings().gcp_project_id,
        )
        await research_repo.save_run(run)
        if seeded:
            await research_repo.save_findings(seeded)
        findings = await research_repo.list_findings(
            workspace_id=workspace.workspace_id,
            channel_id=config.channel_id,
            limit=limit,
        )
    return findings


@router.post(
    "/research/run",
    response_model=list[ResearchFinding],
    summary="Trigger Manual Alex Research Run",
)
async def trigger_manual_research_run(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
) -> list[ResearchFinding]:
    request_id = getattr(request.state, "request_id", "unknown")
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    config = await research_repo.get_config(workspace.workspace_id)
    existing = await research_repo.list_findings(
        workspace_id=workspace.workspace_id, channel_id=config.channel_id, limit=50
    )
    alex_prompt = await agent_config_repo.get_agent_prompt(workspace.workspace_id, AgentId.ALEX)
    channel_profile, lessons, recent_videos = await _load_channel_context_for_research(
        config.channel_id, memory_store
    )

    alex = AlexDataScientist(
        project_id=get_settings().gcp_project_id,
        location=get_settings().vertexai_location,
    )
    run, new_findings = await alex.run_grounded_research(
        prompts=config.prompts,
        channel_profile=channel_profile,
        recent_videos=recent_videos,
        lessons=lessons,
        existing_findings=existing,
        custom_prompt=alex_prompt.prompt_text if alex_prompt.is_custom else None,
        workspace_id=workspace.workspace_id,
        channel_id=config.channel_id,
        request_id=request_id,
    )
    await research_repo.save_run(run)
    if new_findings:
        await research_repo.save_findings(new_findings)
    now = datetime.now(UTC)
    updated_config = config.model_copy(
        update={
            "last_run_at": now,
            "next_run_at": config.cadence.next_run_after(now),
            "updated_at": now,
        }
    )
    await research_repo.save_config(updated_config)
    return await research_repo.list_findings(
        workspace_id=workspace.workspace_id, channel_id=config.channel_id, limit=10
    )


@router.post(
    "/research/tick",
    response_model=SchedulerTickResponse,
    summary="Cloud Scheduler Background Research Tick",
    description="Internal idempotent endpoint invoked by Cloud Scheduler to process due Alex research runs.",
)
async def process_scheduler_tick(
    request: Request,
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)],
    agent_config_repo: Annotated[AgentConfigRepository, Depends(get_agent_config_repository)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
    scheduler_principal: Annotated[str, Depends(verify_scheduler_identity)],
) -> SchedulerTickResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    log_event("research.scheduler.tick", request_id=request_id)
    now = datetime.now(UTC)
    due_configs = await research_repo.list_due_configs(now)

    if not due_configs:
        log_event("research.scheduler.skipped", request_id=request_id, reason="no_due_configs")
        return SchedulerTickResponse(
            runs_evaluated=0,
            runs_executed=0,
            findings_created=0,
            status="skipped",
        )

    alex = AlexDataScientist(
        project_id=get_settings().gcp_project_id,
        location=get_settings().vertexai_location,
    )
    total_findings = 0
    executed = 0

    for cfg in due_configs:
        run_key = f"{cfg.workspace_id}:{cfg.channel_id}:{cfg.next_run_at.isoformat()}"
        existing_run = await research_repo.get_run(run_key)
        if existing_run and existing_run.status == ResearchRunStatus.COMPLETED:
            continue

        try:
            existing_findings = await research_repo.list_findings(
                workspace_id=cfg.workspace_id, channel_id=cfg.channel_id, limit=50
            )
            alex_prompt = await agent_config_repo.get_agent_prompt(
                cfg.workspace_id, AgentId.ALEX
            )
            channel_profile, lessons, recent_videos = await _load_channel_context_for_research(
                cfg.channel_id, memory_store
            )
            run, new_findings = await alex.run_grounded_research(
                prompts=cfg.prompts,
                channel_profile=channel_profile,
                recent_videos=recent_videos,
                lessons=lessons,
                existing_findings=existing_findings,
                custom_prompt=alex_prompt.prompt_text
                if alex_prompt.is_custom
                else None,
                workspace_id=cfg.workspace_id,
                channel_id=cfg.channel_id,
                scheduled_at=cfg.next_run_at,
                request_id=request_id,
            )
            await research_repo.save_run(run)
            if new_findings:
                await research_repo.save_findings(new_findings)
            total_findings += len(new_findings)
            executed += 1
        except Exception as exc:
            logger.exception(
                "Scheduled research execution failed for workspace=%s channel=%s: %s",
                cfg.workspace_id,
                cfg.channel_id,
                exc,
            )
            log_event(
                "research.scheduler.config_failed",
                request_id=request_id,
                workspace_id=cfg.workspace_id,
                channel_id=cfg.channel_id,
                error_code=type(exc).__name__,
                error_detail=str(exc),
            )
        finally:
            # Always advance next_run_at to prevent repeated retry storms
            updated_cfg = cfg.model_copy(
                update={
                    "last_run_at": now,
                    "next_run_at": cfg.cadence.next_run_after(now),
                    "updated_at": now,
                }
            )
            await research_repo.save_config(updated_cfg)
    status_label = "completed" if executed == len(due_configs) else "partial_failure" if executed > 0 else "failed"
    log_event(
        "research.scheduler.completed",
        request_id=request_id,
        runs_evaluated=len(due_configs),
        runs_executed=executed,
        findings_created=total_findings,
        status=status_label,
    )
    return SchedulerTickResponse(
        runs_evaluated=len(due_configs),
        runs_executed=executed,
        findings_created=total_findings,
        status=status_label,
    )


@router.post(
    "/analysis/code-execution",
    summary="Run Alex Python Code Execution Statistical Analysis",
)
async def run_alex_code_execution(
    payload: CodeExecutionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    alex = AlexDataScientist()
    provider = SampleChannelDataProvider()
    channel = await provider.get_channel()
    dataset = {
        "videos": [
            {
                "video_id": v.video_id,
                "views": v.analytics.views,
                "first_demo_seconds": v.derived.first_demo_seconds,
                "average_view_percentage": v.analytics.avg_view_percentage,
                "subscribers_gained": v.analytics.subscribers_gained,
            }
            for v in channel.videos
        ]
    }
    return await alex.run_code_execution_analysis(
        analysis_goal=payload.analysis_goal,
        dataset_summary=dataset,
    )


@router.post(
    "/research/findings/{finding_id}/distill",
    response_model=DistillFindingResponse,
    summary="Distill Research Finding into Durable Memory Bank Lesson",
)
async def distill_research_finding(
    finding_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    research_repo: Annotated[ResearchRepository, Depends(get_research_repository)],
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    memory_store: Annotated[ChannelMemoryStore, Depends(get_memory_store)],
) -> DistillFindingResponse:
    workspace, _ = await workspace_repo.get_or_create_default_workspace(current_user)
    finding = await research_repo.get_finding(finding_id)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research finding '{finding_id}' not found.",
        )
    run = await research_repo.get_run(finding.run_id)
    if run is not None and run.workspace_id != workspace.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research finding '{finding_id}' not found.",
        )
    alex = AlexDataScientist()
    lesson = alex.distill_lesson(finding, channel_id=finding.channel_id)
    if lesson is None:
        return DistillFindingResponse(
            lesson_id=None,
            directive=None,
            confidence=None,
            status="insufficient_evidence_for_long_term_memory",
        )
    await memory_store.add_lesson(lesson)
    return DistillFindingResponse(
        lesson_id=lesson.lesson_id,
        directive=lesson.directive,
        confidence=lesson.confidence,
        status="distilled_to_memory_bank",
    )
