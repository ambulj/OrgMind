"""Workspace and membership management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from orgmind.auth import WorkspaceContext
from orgmind.models import Membership, Role, User, Workspace
from sqlalchemy.orm import Session

from apps.api.dependencies import (
    get_current_user,
    get_db_session,
    get_workspace_context,
    require_role,
)
from apps.api.schemas import (
    AddMemberRequest,
    CreateWorkspaceRequest,
    MembershipResponse,
    WorkspaceResponse,
)

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[WorkspaceResponse]:
    """Lists all workspaces in which the current user holds membership."""
    memberships = session.query(Membership).filter_by(user_id=user.id).all()
    workspaces = [m.workspace for m in memberships if m.workspace]
    return [
        WorkspaceResponse(
            id=ws.id,
            slug=ws.slug,
            name=ws.name,
            created_at=ws.created_at.isoformat(),
        )
        for ws in workspaces
    ]


@router.post("", response_model=WorkspaceResponse)
def create_workspace(
    payload: CreateWorkspaceRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> WorkspaceResponse:
    """Creates a new isolated tenant workspace and grants Admin role to the creator."""
    clean_slug = payload.slug.strip().lower()
    existing = session.query(Workspace).filter_by(slug=clean_slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workspace with slug '{clean_slug}' already exists.",
        )

    ws = Workspace(
        id=clean_slug,
        slug=clean_slug,
        name=payload.name.strip(),
    )
    session.add(ws)
    session.flush()

    # Creator gets Admin role
    membership = Membership(
        user_id=user.id,
        workspace_id=ws.id,
        role=Role.ADMIN.value,
    )
    session.add(membership)
    session.commit()

    return WorkspaceResponse(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        created_at=ws.created_at.isoformat(),
    )


@router.get("/{workspace_id}/members", response_model=list[MembershipResponse])
def list_workspace_members(
    workspace_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> list[MembershipResponse]:
    """Lists all members and their assigned RBAC roles for a given workspace."""
    ws = session.query(Workspace).filter((Workspace.id == workspace_id) | (Workspace.slug == workspace_id)).first()
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

    memberships = session.query(Membership).filter_by(workspace_id=ws.id).all()
    return [
        MembershipResponse(
            id=m.id,
            user_id=m.user.id,
            user_email=m.user.email,
            user_name=m.user.full_name,
            workspace_id=ws.slug,
            role=m.role,
            created_at=m.created_at.isoformat(),
        )
        for m in memberships
        if m.user
    ]


@router.post("/{workspace_id}/members", response_model=MembershipResponse)
def add_or_update_member(
    workspace_id: str,
    payload: AddMemberRequest,
    admin_ctx: WorkspaceContext = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_db_session),
) -> MembershipResponse:
    """Adds a member to the workspace or updates their existing role. Admin role required."""
    ws = session.query(Workspace).filter((Workspace.id == workspace_id) | (Workspace.slug == workspace_id)).first()
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

    target_user = session.query(User).filter_by(email=payload.user_email.strip()).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{payload.user_email}' not found.")

    valid_roles = [r.value for r in Role]
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: {valid_roles}",
        )

    membership = (
        session.query(Membership)
        .filter_by(user_id=target_user.id, workspace_id=ws.id)
        .first()
    )
    if membership:
        membership.role = payload.role
    else:
        membership = Membership(
            user_id=target_user.id,
            workspace_id=ws.id,
            role=payload.role,
        )
        session.add(membership)

    session.commit()

    return MembershipResponse(
        id=membership.id,
        user_id=target_user.id,
        user_email=target_user.email,
        user_name=target_user.full_name,
        workspace_id=ws.slug,
        role=membership.role,
        created_at=membership.created_at.isoformat(),
    )
