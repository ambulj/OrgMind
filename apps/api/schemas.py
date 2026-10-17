"""Pydantic Request and Response Schemas for OrgMind REST and SSE Streaming API."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ============================================================================
# ERROR AND PAGINATION ENVELOPES
# ============================================================================


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str
    timestamp: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================================
# AUTHENTICATION & WORKSPACE SCHEMAS
# ============================================================================


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    current_workspace: str
    current_role: str
    available_workspaces: list[dict[str, str]]


class CreateWorkspaceRequest(BaseModel):
    slug: str
    name: str


class WorkspaceResponse(BaseModel):
    id: str
    slug: str
    name: str
    created_at: str


class AddMemberRequest(BaseModel):
    user_email: str
    role: str = "Viewer"


class MembershipResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_name: str
    workspace_id: str
    role: str
    created_at: str


# ============================================================================
# QUESTION ANSWERING & SSE SCHEMAS
# ============================================================================


class AskRequest(BaseModel):
    question: str
    as_of: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)


class SSEEventData(BaseModel):
    event: str
    data: dict[str, Any]


class AnswerTraceResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str | None = None
    question: str
    answer: str
    sources_cited: list[str]
    validation_status: str
    confidence_label: str
    confidence_score: float
    trace_data: dict[str, Any]
    created_at: str


class AnswerFeedbackRequest(BaseModel):
    rating: int  # 1 or -1
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    answer_id: str
    user_id: str
    rating: int
    comment: str | None
    created_at: str


# ============================================================================
# ENTITY & GRAPH INTELLIGENCE SCHEMAS
# ============================================================================


class EntitySummary(BaseModel):
    id: str
    name: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class EntityDetailResponse(BaseModel):
    entity: EntitySummary
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    recent_changes: list[dict[str, Any]] = Field(default_factory=list)


class DecisionLineageResponse(BaseModel):
    decision_id: str
    topic: str
    status: str
    valid_from: str | None
    valid_to: str | None
    superseded_by: str | None
    supersedes: str | None
    source_anchors: list[dict[str, Any]] = Field(default_factory=list)
    lineage_chain: list[dict[str, Any]] = Field(default_factory=list)


class NeighborhoodResponse(BaseModel):
    center_id: str
    hops: int
    as_of: str | None = None
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class PathResponse(BaseModel):
    from_entity: str
    to_entity: str
    found: bool
    path_length: int
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# SOURCES & REDACTION SCHEMAS
# ============================================================================


class SourceDetailResponse(BaseModel):
    id: str
    file_path: str | None = None
    text_snippet: str
    content_hash: str | None = None
    origin_type: str | None = None
    visibility: str | None = None
    redacted: bool = False
    redacted_at: str | None = None
    redaction_reason: str | None = None


# ============================================================================
# INGESTION & REVIEW WORKFLOW SCHEMAS
# ============================================================================


class IngestionJobCreate(BaseModel):
    connector_type: str
    source_uri: str


class IngestionJobResponse(BaseModel):
    id: str
    workspace_id: str
    connector_type: str
    source_uri: str
    status: str
    items_processed: int
    items_failed: int
    error_message: str | None = None
    created_at: str
    completed_at: str | None = None


class ReviewItemResponse(BaseModel):
    id: str
    workspace_id: str
    item_type: str
    status: str
    summary: str
    payload: dict[str, Any]
    before_diff: str | None = None
    after_diff: str | None = None
    reviewed_by: str | None = None
    created_at: str
    reviewed_at: str | None = None


class ReviewActionRequest(BaseModel):
    action: str  # approve | reject | edit
    edited_payload: dict[str, Any] | None = None
    comment: str | None = None


# ============================================================================
# TWO-PHASE ACTIONS SCHEMAS
# ============================================================================


class ActionProposeRequest(BaseModel):
    action_type: str  # create_ticket | draft_message | assign_task
    parameters: dict[str, Any]


class ActionConfirmRequest(BaseModel):
    action_id: str


class ActionCancelRequest(BaseModel):
    action_id: str
    reason: str | None = None


class ActionResponse(BaseModel):
    action_id: str
    action_type: str
    status: str
    payload: dict[str, Any]
    proposed_by: str
    confirmed_by: str | None = None
    created_at: str
    resolved_at: str | None = None


# ============================================================================
# AUDIT & HEALTH SCHEMAS
# ============================================================================


class AuditLogResponse(BaseModel):
    id: str
    workspace_id: str
    actor_id: str
    actor_email: str
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    before_state: str | None = None
    after_state: str | None = None
    reason: str | None = None
    timestamp: str


class ComponentHealth(BaseModel):
    status: str  # healthy | degraded | unhealthy
    latency_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SystemHealthReport(BaseModel):
    status: str
    timestamp: str
    components: dict[str, ComponentHealth]
