from orgmind.auth import (
    WorkspaceContext,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from orgmind.models import Role, init_app_db


def test_password_hashing_and_verification():
    password = "SuperSecretSecurePassword!2026"
    hashed = hash_password(password)

    # Must verify correctly
    assert verify_password(password, hashed) is True

    # Must reject wrong password
    assert verify_password("WrongPassword123", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_lifecycle():
    user_id = "usr_alice_123"
    email = "alice@northwind.com"
    workspace_id = "ws_engineering"
    role = Role.ADMIN.value

    token = create_access_token(user_id=user_id, email=email, workspace_id=workspace_id, role=role)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["workspace_id"] == workspace_id
    assert payload["role"] == Role.ADMIN.value


def test_workspace_rbac_permissions():
    viewer_ctx = WorkspaceContext(
        user_id="u1", user_email="v@test.com", workspace_id="ws1", role=Role.VIEWER
    )
    assert viewer_ctx.can_read() is True
    assert viewer_ctx.can_write() is False
    assert viewer_ctx.can_admin() is False
    assert viewer_ctx.can_audit() is False

    editor_ctx = WorkspaceContext(
        user_id="u2", user_email="e@test.com", workspace_id="ws1", role=Role.EDITOR
    )
    assert editor_ctx.can_read() is True
    assert editor_ctx.can_write() is True
    assert editor_ctx.can_admin() is False

    admin_ctx = WorkspaceContext(
        user_id="u3", user_email="a@test.com", workspace_id="ws1", role=Role.ADMIN
    )
    assert admin_ctx.can_read() is True
    assert admin_ctx.can_write() is True
    assert admin_ctx.can_admin() is True
    assert admin_ctx.can_audit() is True

    auditor_ctx = WorkspaceContext(
        user_id="u4", user_email="aud@test.com", workspace_id="ws1", role=Role.AUDITOR
    )
    assert auditor_ctx.can_read() is True
    assert auditor_ctx.can_write() is False
    assert auditor_ctx.can_audit() is True


def test_app_database_initialization():
    # Verify relational SQLite tables initialize cleanly
    init_app_db()
