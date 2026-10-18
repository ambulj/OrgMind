"""Authentication, JWT session management, RBAC verification, and OIDC interface."""

import hashlib
import hmac
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from orgmind.config import settings
from orgmind.models import Role


@dataclass
class WorkspaceContext:
    """Carries active authenticated context across request boundaries."""

    user_id: str
    user_email: str
    workspace_id: str
    role: Role
    request_id: str | None = None

    def can_read(self) -> bool:
        """Viewers, Editors, Admins, and Auditors can read."""
        return self.role in (Role.ADMIN, Role.EDITOR, Role.VIEWER, Role.AUDITOR)

    def can_write(self) -> bool:
        """Only Editors and Admins can mutate decisions or create action items."""
        return self.role in (Role.ADMIN, Role.EDITOR)

    def can_admin(self) -> bool:
        """Only Admins can manage members, settings, and redactions."""
        return self.role == Role.ADMIN

    def can_audit(self) -> bool:
        """Admins and Auditors can inspect full audit logs."""
        return self.role in (Role.ADMIN, Role.AUDITOR)


def hash_password(password: str, salt: str | None = None) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP guidance)."""
    if salt is None:
        salt = secrets.token_hex(16)
    iterations = getattr(settings, "PBKDF2_ITERATIONS", 600_000)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"{salt}${iterations}${key.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verifies a plain password against stored PBKDF2 hash, supporting both legacy and 600k iteration formats."""
    try:
        parts = stored_hash.split("$")
        if len(parts) == 3:
            salt, iterations_str, expected_hex = parts
            iterations = int(iterations_str)
        elif len(parts) == 2:
            salt, expected_hex = parts
            iterations = 100_000  # Legacy fallback
        else:
            return False

        actual_hex = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(actual_hex, expected_hex)
    except Exception:
        return False


def create_access_token(
    user_id: str,
    email: str,
    workspace_id: str,
    role: str = Role.VIEWER.value,
    expires_delta: timedelta | None = None,
) -> str:
    """Creates a signed JWT session token."""
    expire = datetime.now(UTC) + (
        expires_delta if expires_delta else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": user_id,
        "email": email,
        "workspace_id": workspace_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.get_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodes and cryptographically validates a JWT session token."""
    return jwt.decode(token, settings.get_jwt_secret(), algorithms=[settings.JWT_ALGORITHM])


# OIDC / SSO Integration Interface
class OIDCProviderInterface(ABC):
    """Abstract interface for enterprise OpenID Connect / SAML Single Sign-On providers.

    Implementations (e.g. Okta, Google Workspace, Azure AD) subclass this interface.
    """

    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Returns the provider's OAuth 2.0 / OIDC login redirection URL."""
        pass

    @abstractmethod
    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchanges authorization code for ID and Access tokens."""
        pass

    @abstractmethod
    def extract_user_claims(self, id_token: str) -> dict[str, Any]:
        """Extracts and validates user email, name, and group memberships from ID token."""
        pass
