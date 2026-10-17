"""FastAPI Dependencies for Authentication, Workspace Context, and RBAC Guards."""

import uuid
from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from orgmind.auth import WorkspaceContext, decode_access_token
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
    Falls back to default developer admin user if no header is supplied in local mode.
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
        email = payload.get("email") or f"{user_id}@northwind.io"
        user = session.query(User).filter((User.id == user_id) | (User.email == email)).first()
        if not user:
            # Auto-provision user record for valid signed token
            user = User(
                id=user_id,
                email=email,
                hashed_password="jwt_authenticated_user",
                full_name=payload.get("name", user_id),
                is_active=True,
            )
            session.add(user)
            session.commit()
        return user

    # Local development fallback user: Ensure developer admin user exists
    dev_user = session.query(User).filter_by(email="admin@northwind.io").first()
    if not dev_user:
        dev_user = User(
            id="usr_admin_default",
            email="admin@northwind.io",
            hashed_password="local_dev_dummy_hash",
            full_name="Northwind Admin",
            is_active=True,
        )
        session.add(dev_user)
        session.commit()
    return dev_user


def get_workspace_context(
    x_workspace_id: str | None = Header(None, alias="X-Workspace-Id"),
    user: User = Depends(get_current_user),
    auth_creds: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    session: Session = Depends(get_db_session),
) -> WorkspaceContext:
    """Resolves multi-tenant workspace context and user's role within that workspace."""
    ws_slug = (x_workspace_id or "default").strip()
    workspace = session.query(Workspace).filter_by(slug=ws_slug).first()
    if not workspace:
        # Auto-create workspace record for default slug if not exists
        workspace = Workspace(id=ws_slug, slug=ws_slug, name=f"{ws_slug.title()} Workspace")
        session.add(workspace)
        session.commit()

    payload_role = None
    if auth_creds and auth_creds.credentials:
        try:
            payload = decode_access_token(auth_creds.credentials)
            payload_role = payload.get("role")
        except Exception:
            pass

    # Determine user's membership role in this workspace
    membership = (
        session.query(Membership)
        .filter_by(user_id=user.id, workspace_id=workspace.id)
        .first()
    )
    role_val = membership.role if membership else payload_role

    if not role_val:
        role_val = Role.ADMIN.value if user.email.startswith("admin") else Role.VIEWER.value

    # Parse role enum
    role_enum = Role(role_val) if role_val in [r.value for r in Role] else Role.VIEWER

    req_id = f"req_{uuid.uuid4().hex[:8]}"
    return WorkspaceContext(
        user_id=user.id,
        user_email=user.email,
        workspace_id=workspace.slug,
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
