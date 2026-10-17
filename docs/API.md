# OrgMind REST & Streaming API Specification

**Version**: `v1`  
**Base Path**: `/api/v1`  
**Security**: Bearer JWT (`Authorization: Bearer <token>`) & Tenant Workspace Header (`X-Workspace-Id: <slug>`)

---

## 1. Global Standards & Conventions

### 1.1 Consistent Error Format
All 4xx and 5xx responses return a consistent error object:
```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "User lacks required role 'Admin' to perform this action.",
    "details": {
      "required_role": "Admin",
      "user_role": "Viewer"
    },
    "request_id": "req_8f192b0c",
    "timestamp": "2026-10-17T18:00:00Z"
  }
}
```

### 1.2 Pagination Parameters
Collection endpoints accept standard query parameters:
- `page`: Integer $\ge 1$ (default: `1`)
- `page_size`: Integer between $1$ and $100$ (default: `20`)

Paginated responses return:
```json
{
  "items": [...],
  "total": 142,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

### 1.3 Rate Limiting
- Default rate limit: 120 requests/minute per authenticated user.
- `/api/v1/ask`: 20 requests/minute per user.
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

---

## 2. Server-Sent Events (SSE) Protocol: `POST /api/v1/ask`

`POST /api/v1/ask` accepts an `AskRequest` and streams typed events (`text/event-stream`).

### Request Payload:
```json
{
  "question": "What is our OAuth standard and when did it change?",
  "as_of": "2026-02-01",
  "history": []
}
```

### SSE Event Stream Wire Format:
Each SSE frame has an `event` name and a JSON-encoded `data` payload:
```text
event: <event_type>
data: {"event": "<event_type>", ...}
```

### Typed SSE Event Catalog:
1. `step`: Plain-language human-readable progress description.
   - `{"event": "step", "description": "Consulting architectural decisions regarding OAuth..."}`
2. `tool_call`: Dispatched tool invocation.
   - `{"event": "tool_call", "tool": "trace_decision", "arguments": {"topic": "OAuth", "as_of": "2026-02-01"}}`
3. `tool_result_summary`: High-level summary of tool response.
   - `{"event": "tool_result_summary", "tool": "trace_decision", "found": true, "record_count": 2}`
4. `token`: Incremental stream chunk of the generated answer markdown.
   - `{"event": "token", "delta": "Northwind Labs adopted "}`
5. `citation`: Grounded source metadata cited in answer.
   - `{"event": "citation", "source_id": "SRC_DOC_AUTH_01", "uri": "data/docs/auth_architecture.md", "quote": "We have decided to adopt OAuth 2.1 with PKCE...", "content_hash": "f2077cb5..."}`
6. `validation`: Citation and grounding enforcement result.
   - `{"event": "validation", "status": "ok", "cited_sources": ["SRC_DOC_AUTH_01"], "repaired": false}`
7. `confidence`: Calibrated confidence score with explainable reasoning.
   - `{"event": "confidence", "level": "High", "score": 0.95, "reasons": ["Multiple primary architecture documents match", "Zero conflicting unratified drafts", "Recent decision date"]}`
8. `freshness`: Temporal validity and recency metadata.
   - `{"event": "freshness", "last_updated": "2026-01-28", "staleness_status": "fresh", "days_since_update": 80}`
9. `proposed_action`: Action proposed by agent requiring user confirmation.
   - `{"event": "proposed_action", "action_id": "act_8a92b", "action_type": "create_ticket", "title": "Upgrade Keycloak to 24.0", "target_system": "Jira"}`
10. `done`: Final answer payload and telemetry trace ID.
    - `{"event": "done", "answer_id": "ans_9a12b", "latency_ms": 1420}`
11. `error`: Stream error envelope.
    - `{"event": "error", "code": "AGENT_TIMEOUT", "message": "Query exceeded 30s timeout."}`

---

## 3. Endpoints Matrix

### 3.1 Authentication & Workspace (`/api/v1/auth`, `/api/v1/workspaces`)
- `POST /api/v1/auth/login`: Authenticate with email/password, returns JWT access token.
- `POST /api/v1/auth/register`: Create user account and seed default membership.
- `GET /api/v1/auth/me`: Retrieve active user profile, memberships, and current workspace role.
- `GET /api/v1/workspaces`: List all workspaces the user has membership in.
- `POST /api/v1/workspaces`: Create a new isolated workspace partition.
- `GET /api/v1/workspaces/{id}/members`: List workspace members and their roles.
- `POST /api/v1/workspaces/{id}/members`: Add or update a user's role in the workspace (`Admin` only).

### 3.2 Question Answering & Traces (`/api/v1/ask`, `/api/v1/answers`)
- `POST /api/v1/ask`: Streams typed SSE events for questions.
- `GET /api/v1/answers/{id}/trace`: Detailed execution telemetry trace (tool inputs/outputs, timings, validator result, prompt tokens).
- `POST /api/v1/answers/{id}/feedback`: Submit user satisfaction rating (`+1` / `-1`) and qualitative feedback.

### 3.3 Entities & Graph Intelligence (`/api/v1/entities`, `/api/v1/decisions`, `/api/v1/graph`)
- `GET /api/v1/entities/{type}`: List entities of type (`people`, `projects`, `teams`, `topics`, `decisions`, `tickets`, `documents`). Supports `?search=&as_of=&page=&page_size=`.
- `GET /api/v1/entities/{type}/{id}`: Full detail view for a specific entity with connected neighborhood.
- `GET /api/v1/decisions/{id}/lineage`: Supersession lineage graph for a decision showing previous/superseded decisions and source anchors.
- `GET /api/v1/graph/neighborhood?entity=&hops=2&as_of=`: Subgraph traversal centered around an entity.
- `GET /api/v1/graph/path?from=&to=`: Shortest semantic path connecting two entities in the company brain.

### 3.4 Sources & Redaction (`/api/v1/sources`)
- `GET /api/v1/sources/{id}`: Fetch verbatim source snippet, origin file, and cryptographic content hash. Permission-checked against caller's role; returns tombstone notice if redacted.

### 3.5 Ingestion & Review Workflows (`/api/v1/ingestion`, `/api/v1/reviews`)
- `POST /api/v1/ingestion/jobs`: Trigger file/document ingestion job.
- `GET /api/v1/ingestion/jobs`: List past ingestion jobs and status.
- `GET /api/v1/ingestion/jobs/{id}`: Detailed ingestion job progress and errors.
- `GET /api/v1/reviews`: List items pending human-in-the-loop review (e.g. decision reversals, unknown person handles).
- `POST /api/v1/reviews/{id}/action`: Act on review item (`approve`, `edit`, `reject`).

### 3.6 Two-Phase Actions (`/api/v1/actions`)
- `POST /api/v1/actions/propose`: Propose a ticket creation, chat draft, or task assignment without mutating external systems.
- `POST /api/v1/actions/confirm`: Confirm and execute proposed action (`Editor` or `Admin` role required). Writes to relational audit log.
- `POST /api/v1/actions/cancel`: Abort a proposed action.

### 3.7 Governance, Audit & Health (`/api/v1/audit`, `/api/v1/health`)
- `GET /api/v1/audit`: Query immutable audit trail (`?actor=&action=&entity_type=&since=`).
- `GET /api/v1/health`: Deep system health report verifying FalkorDB, Postgres/SQLite, Redis queues, and LLM readiness.
