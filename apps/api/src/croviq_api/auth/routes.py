"""Authentication routes."""

from typing import Annotated
from fastapi import APIRouter, Depends, Request, status

from croviq_api.auth.dependencies import get_current_user
from croviq_api.auth.logging import log_auth_event
from croviq_domain.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/me",
    response_model=User,
    summary="Get Current Authenticated User",
    description="Retrieve the canonical User profile derived from verified identity.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the canonical User entity for the current authenticated principal."""
    return current_user


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Record User Logout",
    description="Record client-side logout activity and emit operational audit log.",
)
async def logout(
    request: Request,
) -> dict[str, str]:
    """Record client logout activity."""
    request_id = getattr(request.state, "request_id", "unknown")
    log_auth_event(
        event_type="auth.logout_observed",
        status=status.HTTP_200_OK,
        request_id=request_id,
        message="Client-side logout observed",
    )
    return {"status": "ok"}
