"""Workspace API routes."""

from typing import Annotated
from fastapi import APIRouter, Depends, Request, status

from croviq_api.auth.dependencies import get_current_user
from croviq_api.workspaces.logging import log_workspace_event
from croviq_api.workspaces.repository import WorkspaceRepository, get_workspace_repository
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
