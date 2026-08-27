from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from croviq_api.auth.dependencies import get_current_user
from croviq_domain.channel_dashboard import ChannelDashboard, build_channel_dashboard
from croviq_domain.channel_provider import SampleChannelDataProvider
from croviq_domain.user import User
from croviq_observability import log_event


router = APIRouter(prefix="/channels", tags=["Channel Intelligence"])


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
