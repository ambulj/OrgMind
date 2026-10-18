"""Immutable audit log querying endpoints."""

from fastapi import APIRouter, Depends, Query
from orgmind.auth import WorkspaceContext
from orgmind.models import AuditLog, Role
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session, require_role
from apps.api.schemas import AuditLogResponse, PaginatedResponse

router = APIRouter(prefix="/audit", tags=["Audit & Governance"])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
def query_audit_logs(
    actor: str | None = Query(None, description="Filter by actor email or id"),
    action: str | None = Query(None, description="Filter by action name"),
    entity_type: str | None = Query(
        None, description="Filter by entity type (Decision, Source, Action)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: WorkspaceContext = Depends(require_role(Role.AUDITOR)),
    session: Session = Depends(get_db_session),
) -> PaginatedResponse[AuditLogResponse]:
    """Queries the immutable audit log. Requires Auditor or Admin role."""
    query = session.query(AuditLog).filter_by(workspace_id=ctx.workspace_id)
    if actor:
        query = query.filter((AuditLog.actor_email == actor) | (AuditLog.actor_id == actor))
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    total = query.count()
    records = (
        query.order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        AuditLogResponse(
            id=r.id,
            workspace_id=r.workspace_id,
            actor_id=r.actor_id,
            actor_email=r.actor_email,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            before_state=r.before_state,
            after_state=r.after_state,
            reason=r.reason,
            timestamp=r.timestamp.isoformat(),
        )
        for r in records
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
