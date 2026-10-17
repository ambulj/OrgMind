# OrgMind Authentication & OIDC / SSO Integration Guide

OrgMind supports a hybrid authentication architecture:
1. **Local Authentication**: Salted PBKDF2-HMAC-SHA256 password hashing with JWT bearer tokens for development and standalone deployments.
2. **Federated Enterprise SSO**: OpenID Connect (OIDC) / SAML 2.0 readiness via the extensible `OIDCProviderInterface`.

---

## 1. Role-Based Access Control (RBAC) Matrix

Every request carries a validated `WorkspaceContext` containing:
- `user_id`: UUID
- `workspace_id`: Tenant partition identifier
- `role`: One of the 4 defined RBAC roles

| Capability | Admin | Editor | Viewer | Auditor |
| :--- | :---: | :---: | :---: | :---: |
| **Ask Agent & Query Knowledge Graph** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Inspect Source Citations & Provenance** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Interactive Graph Visualizer** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Propose Actions (Tickets / Messages)** | ✅ Yes | ✅ Yes | ❌ Read-Only | ❌ Read-Only |
| **Confirm / Execute Actions** | ✅ Yes | ✅ Yes | ❌ Denied | ❌ Denied |
| **Commit Decisions & Supersede Graph Edges** | ✅ Yes | ✅ Yes | ❌ Denied | ❌ Denied |
| **Inspect Full Audit Trail** | ✅ Yes | ❌ Denied | ❌ Denied | ✅ Yes |
| **Manage Workspace Members & Roles** | ✅ Yes | ❌ Denied | ❌ Denied | ❌ Denied |
| **Redact Sources & Create Tombstones** | ✅ Yes | ❌ Denied | ❌ Denied | ❌ Denied |

---

## 2. Multi-Tenant Workspace Isolation Guard

Tenant data separation is strictly enforced at the database level by construction:
```python
def get_workspace_graph_name(workspace_id: str | None) -> str:
    # Returns 'org_<workspace_id>'
    # Prevents any cross-workspace leakage by querying strictly within the tenant partition
```
Even if an agent or query is compromised, it is physically impossible to traverse nodes outside the designated `org_<workspace_id>` graph.

---

## 3. How to Add an OIDC / SAML SSO Provider

To integrate an enterprise identity provider (e.g., Okta, Google Workspace, Microsoft Entra ID / Azure AD), implement the `OIDCProviderInterface` defined in `packages/core/orgmind/auth.py`:

```python
from orgmind.auth import OIDCProviderInterface

class OktaOIDCProvider(OIDCProviderInterface):
    def __init__(self, client_id: str, client_secret: str, domain: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.domain = domain

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        return f"https://{self.domain}/oauth2/v1/authorize?client_id={self.client_id}&response_type=code&scope=openid%20email%20profile&redirect_uri={redirect_uri}&state={state}"

    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> dict:
        # POST to https://{self.domain}/oauth2/v1/token
        ...

    def extract_user_claims(self, id_token: str) -> dict:
        # Decode and verify RS256 signature using JWKS
        # Map Okta groups (e.g. 'Engineering-Leads') to OrgMind Role.EDITOR
        ...
```

Register your implementation in `apps/api/routers/auth.py` via FastAPI dependency injection.
