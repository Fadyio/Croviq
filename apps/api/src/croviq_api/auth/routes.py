"""Authentication routes."""

from typing import Annotated
from fastapi import APIRouter, Depends

from croviq_api.auth.dependencies import get_current_user
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
