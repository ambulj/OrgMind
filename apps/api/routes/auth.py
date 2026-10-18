"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from orgmind.auth import WorkspaceContext, create_access_token, hash_password, verify_password
from orgmind.models import Membership, Role, User, Workspace
from sqlalchemy.orm import Session

from apps.api.dependencies import get_current_user, get_db_session, get_workspace_context
from apps.api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserProfileResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db_session)) -> TokenResponse:
    """Authenticates user credentials and issues a signed JWT session token."""
    user = session.query(User).filter_by(email=payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch primary workspace and role
    membership = session.query(Membership).filter_by(user_id=user.id).first()
    ws_id = membership.workspace.slug if (membership and membership.workspace) else "default"
    role_val = membership.role if membership else Role.VIEWER.value

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        workspace_id=ws_id,
        role=role_val,
    )
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_db_session)) -> TokenResponse:
    """Creates a new user account and seeds initial default workspace membership."""
    existing = session.query(User).filter_by(email=payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
    )
    session.add(user)
    session.flush()

    # Ensure default workspace exists
    default_ws = session.query(Workspace).filter_by(slug="default").first()
    if not default_ws:
        default_ws = Workspace(id="default", slug="default", name="Default Workspace")
        session.add(default_ws)
        session.flush()

    # First registered user is Admin (for initial bootstrapping); all subsequent users are Viewers by default
    user_count = session.query(User).count()
    assigned_role = Role.ADMIN.value if user_count <= 1 else Role.VIEWER.value

    membership = Membership(
        user_id=user.id,
        workspace_id=default_ws.id,
        role=assigned_role,
    )
    session.add(membership)
    session.commit()

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        workspace_id=default_ws.slug,
        role=assigned_role,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(
    user: User = Depends(get_current_user),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """Returns the authenticated user's profile and active workspace role."""
    memberships = session.query(Membership).filter_by(user_id=user.id).all()
    available = [
        {"id": m.workspace.id, "slug": m.workspace.slug, "name": m.workspace.name, "role": m.role}
        for m in memberships
        if m.workspace
    ]

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        current_workspace=ctx.workspace_id,
        current_role=ctx.role.value if hasattr(ctx.role, "value") else str(ctx.role),
        available_workspaces=available,
    )
