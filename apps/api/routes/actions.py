"""Two-phase safety propose-then-confirm action endpoints."""

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from orgmind.auth import WorkspaceContext
from orgmind.models import AuditLog, ProposedAction, Role
from orgmind.tools import TOOLS_REGISTRY
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session, get_workspace_context, require_role
from apps.api.schemas import (
    ActionCancelRequest,
    ActionConfirmRequest,
    ActionProposeRequest,
    ActionResponse,
)

router = APIRouter(prefix="/actions", tags=["Two-Phase Actions"])


@router.post("/propose", response_model=ActionResponse)
def propose_action(
    payload: ActionProposeRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> ActionResponse:
    """Proposes an action (e.g., ticket creation or chat draft) for human preview without mutating external systems."""
    valid_types = ("create_ticket", "draft_message", "assign_task")
    if payload.action_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type '{payload.action_type}'. Must be one of: {valid_types}",
        )

    # Validate against tool parameters with confirm=False
    tool_fn = TOOLS_REGISTRY.get(payload.action_type)
    if not tool_fn:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool not registered.")

    params = dict(payload.parameters)
    params["confirm"] = False
    params["workspace_id"] = ctx.workspace_id

    preview_res = tool_fn(**params)

    action_id = f"act_{uuid.uuid4().hex[:10]}"
    action_record = ProposedAction(
        id=action_id,
        workspace_id=ctx.workspace_id,
        action_type=payload.action_type,
        status="proposed",
        payload=json.dumps(preview_res),
        proposed_by=ctx.user_email,
    )
    session.add(action_record)
    session.commit()

    return ActionResponse(
        action_id=action_record.id,
        action_type=action_record.action_type,
        status=action_record.status,
        payload=preview_res,
        proposed_by=action_record.proposed_by,
        confirmed_by=None,
        created_at=action_record.created_at.isoformat(),
        resolved_at=None,
    )


@router.post("/confirm", response_model=ActionResponse)
def confirm_action(
    payload: ActionConfirmRequest,
    ctx: WorkspaceContext = Depends(require_role(Role.EDITOR)),
    session: Session = Depends(get_db_session),
) -> ActionResponse:
    """Confirms and executes a previously proposed action. Requires Editor or Admin role."""
    action_record = (
        session.query(ProposedAction)
        .filter_by(id=payload.action_id, workspace_id=ctx.workspace_id)
        .first()
    )
    if not action_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found.")

    if action_record.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action cannot be confirmed because current status is '{action_record.status}'.",
        )

    # Execute tool with confirm=True
    tool_fn = TOOLS_REGISTRY.get(action_record.action_type)
    saved_payload = json.loads(action_record.payload)
    exec_params = dict(saved_payload.get("proposed_ticket") or saved_payload.get("proposed_message") or saved_payload.get("proposed_assignment") or {})
    exec_params["confirm"] = True
    exec_params["workspace_id"] = ctx.workspace_id

    exec_result = tool_fn(**exec_params)

    action_record.status = "confirmed"
    action_record.confirmed_by = ctx.user_email
    action_record.resolved_at = datetime.now(UTC)
    action_record.payload = json.dumps(exec_result)

    # Write audit log record
    audit = AuditLog(
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        actor_email=ctx.user_email,
        action=f"execute_{action_record.action_type}",
        entity_type="Action",
        entity_id=action_record.id,
        after_state=json.dumps(exec_result),
        reason="User confirmed proposed action",
    )
    session.add(audit)
    session.commit()

    return ActionResponse(
        action_id=action_record.id,
        action_type=action_record.action_type,
        status=action_record.status,
        payload=exec_result,
        proposed_by=action_record.proposed_by,
        confirmed_by=action_record.confirmed_by,
        created_at=action_record.created_at.isoformat(),
        resolved_at=action_record.resolved_at.isoformat() if action_record.resolved_at else None,
    )


@router.post("/cancel", response_model=ActionResponse)
def cancel_action(
    payload: ActionCancelRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> ActionResponse:
    """Cancels a previously proposed action without executing it."""
    action_record = (
        session.query(ProposedAction)
        .filter_by(id=payload.action_id, workspace_id=ctx.workspace_id)
        .first()
    )
    if not action_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found.")

    if action_record.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action cannot be cancelled because status is '{action_record.status}'.",
        )

    action_record.status = "cancelled"
    action_record.resolved_at = datetime.now(UTC)
    session.commit()

    saved_payload = json.loads(action_record.payload)
    return ActionResponse(
        action_id=action_record.id,
        action_type=action_record.action_type,
        status=action_record.status,
        payload=saved_payload,
        proposed_by=action_record.proposed_by,
        confirmed_by=None,
        created_at=action_record.created_at.isoformat(),
        resolved_at=action_record.resolved_at.isoformat() if action_record.resolved_at else None,
    )
