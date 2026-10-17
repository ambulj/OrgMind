# OrgMind API Service (`apps/api`)

FastAPI REST & Server-Sent Events (SSE) service providing:
- `/api/v1/auth`: JWT authentication & role-based access control.
- `/api/v1/workspaces`: Workspace isolation (`org_<workspace_id>`).
- `/api/v1/ask`: Streaming agent reasoning loop via SSE.
- `/api/v1/entities`: People, Teams, Projects, Decisions, Tickets, and Docs graph views.
- `/api/v1/graph`: Multi-hop neighborhood and path exploration.
- `/api/v1/audit`: Immutable mutation and action event log.
- `/api/v1/review`: Staging review queue for incoming extractions.

Scaffolded in Phase 1; fully implemented in Phase 4.
