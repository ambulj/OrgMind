"""FastAPI Dependencies for Authentication, Workspace Context, and RBAC Guards."""

import uuid
from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from orgmind.auth import WorkspaceContext, decode_access_token
from orgmind.config import settings
from orgmind.models import Membership, Role, User, Workspace, get_session_factory
from sqlalchemy.orm import Session

security_scheme = HTTPBearer(auto_error=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yields an active database session for a request lifecycle."""
    session_factory = get_session_factory()
    with session_factory() as session:
        yield session


def get_current_user(
    auth_creds: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    session: Session = Depends(get_db_session),
) -> User:
    """Authenticates the request via Bearer JWT token.
    Returns 401 without a valid token. Development fallback user is ONLY permitted
    when settings.ENV == 'development'.
    """
    if auth_creds and auth_creds.credentials:
        try:
            payload = decode_access_token(auth_creds.credentials)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        user_id = payload.get("sub")
        email = payload.get("email")
        user = session.query(User).filter((User.id == user_id) | (User.email == email)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or deactivated.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )
        return user

    # Dev fallback ONLY behind explicit ENV == 'development'
    if settings.ENV.lower() in ("development", "dev"):
        dev_user = session.query(User).filter_by(email="admin@northwind.io").first()
        if not dev_user:
            from orgmind.auth import hash_password
            dev_user = User(
                id="usr_admin_default",
                email="admin@northwind.io",
                hashed_password=hash_password("admin123"),
                full_name="Northwind Admin",
                is_active=True,
            )
            session.add(dev_user)
            default_ws = session.query(Workspace).filter_by(slug="default").first()
            if default_ws:
                session.add(Membership(user_id=dev_user.id, workspace_id=default_ws.id, role=Role.ADMIN.value))
            session.commit()
        return dev_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a valid Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_workspace_context(
    x_workspace_id: str | None = Header(None, alias="X-Workspace-Id"),
    user: User = Depends(get_current_user),
    auth_creds: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    session: Session = Depends(get_db_session),
) -> WorkspaceContext:
    """Resolves multi-tenant workspace context and user's role within that workspace.
    Enforces that:
    1. Workspace must exist (never auto-create on GET/lookup).
    2. User MUST have a membership record in the workspace.
    3. Role is taken strictly from the membership row in database, NEVER from token or headers.
    """
    ws_target = (x_workspace_id or "default").strip().lower()

    # Locate workspace by id or slug
    workspace = (
        session.query(Workspace)
        .filter((Workspace.slug == ws_target) | (Workspace.id == ws_target))
        .first()
    )
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{ws_target}' not found.",
        )

    # Require membership row in the database
    membership = (
        session.query(Membership)
        .filter_by(user_id=user.id, workspace_id=workspace.id)
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: user '{user.email}' is not a member of workspace '{workspace.slug}'.",
        )

    # Take role strictly from the membership row
    role_val = membership.role
    role_enum = Role(role_val) if role_val in [r.value for r in Role] else Role.VIEWER

    req_id = f"req_{uuid.uuid4().hex[:8]}"
    return WorkspaceContext(
        user_id=str(user.id),
        user_email=str(user.email),
        workspace_id=str(workspace.id),
        role=role_enum,
        request_id=req_id,
    )


def require_role(min_role: Role):
    """Enforces role hierarchy (Admin > Editor > Viewer / Auditor)."""
    role_hierarchy = {
        Role.VIEWER: 1,
        Role.AUDITOR: 1,
        Role.EDITOR: 2,
        Role.ADMIN: 3,
    }

    def role_checker(ctx: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
        user_level = role_hierarchy.get(ctx.role, 0)
        required_level = role_hierarchy.get(min_role, 3)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires minimum role '{min_role.value}'. Current role: '{ctx.role.value}'.",
            )
        return ctx

    return role_checker
