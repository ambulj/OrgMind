"""Human-in-the-loop review queue endpoints."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from orgmind.auth import WorkspaceContext
from orgmind.models import ReviewItem, Role
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session, get_workspace_context, require_role
from apps.api.schemas import PaginatedResponse, ReviewActionRequest, ReviewItemResponse

router = APIRouter(prefix="/reviews", tags=["Review Queue"])


@router.get("", response_model=PaginatedResponse[ReviewItemResponse])
def list_review_items(
    status_filter: str | None = Query(
        "pending", description="Filter by status (pending | approved | rejected | all)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> PaginatedResponse[ReviewItemResponse]:
    """Lists items queued for human review (unknown entity aliases, decision reversals, conflicts)."""
    query = session.query(ReviewItem).filter_by(workspace_id=ctx.workspace_id)
    if status_filter and status_filter.lower() != "all":
        query = query.filter_by(status=status_filter.lower())

    total = query.count()
    items_db = (
        query.order_by(ReviewItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for it in items_db:
        payload_dict = {}
        try:
            payload_dict = json.loads(it.payload)
        except Exception:
            payload_dict = {}
        items.append(
            ReviewItemResponse(
                id=it.id,
                workspace_id=it.workspace_id,
                item_type=it.item_type,
                status=it.status,
                summary=it.summary,
                payload=payload_dict,
                before_diff=it.before_diff,
                after_diff=it.after_diff,
                reviewed_by=it.reviewed_by,
                created_at=it.created_at.isoformat(),
                reviewed_at=it.reviewed_at.isoformat() if it.reviewed_at else None,
            )
        )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/{item_id}/action", response_model=ReviewItemResponse)
def act_on_review_item(
    item_id: str,
    payload: ReviewActionRequest,
    ctx: WorkspaceContext = Depends(require_role(Role.EDITOR)),
    session: Session = Depends(get_db_session),
) -> ReviewItemResponse:
    """Applies human approval, edit, or rejection to a queued review item. Requires Editor or Admin role."""
    item = session.query(ReviewItem).filter_by(id=item_id, workspace_id=ctx.workspace_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review item '{item_id}' not found.",
        )

    action = payload.action.strip().lower()
    if action not in ("approve", "reject", "edit"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be one of: 'approve', 'reject', 'edit'.",
        )

    item.status = (
        "approved" if action == "approve" else ("rejected" if action == "reject" else "edited")
    )
    item.reviewed_by = ctx.user_email
    item.reviewed_at = datetime.now(UTC)

    if action == "edit" and payload.edited_payload:
        item.payload = json.dumps(payload.edited_payload)

    session.commit()

    payload_dict = {}
    try:
        payload_dict = json.loads(item.payload)
    except Exception:
        payload_dict = {}

    return ReviewItemResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        item_type=item.item_type,
        status=item.status,
        summary=item.summary,
        payload=payload_dict,
        before_diff=item.before_diff,
        after_diff=item.after_diff,
        reviewed_by=item.reviewed_by,
        created_at=item.created_at.isoformat(),
        reviewed_at=item.reviewed_at.isoformat() if item.reviewed_at else None,
    )
