"""Answer trace telemetry and user feedback endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from orgmind.auth import WorkspaceContext
from orgmind.models import AnswerTrace, Feedback
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session, get_workspace_context
from apps.api.schemas import AnswerFeedbackRequest, AnswerTraceResponse, FeedbackResponse

router = APIRouter(prefix="/answers", tags=["Answers & Traces"])


@router.get("/{answer_id}/trace", response_model=AnswerTraceResponse)
def get_answer_trace(
    answer_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> AnswerTraceResponse:
    """Retrieves full execution trace, tool invocations, and grounding verification for an answer."""
    trace = (
        session.query(AnswerTrace)
        .filter_by(id=answer_id, workspace_id=ctx.workspace_id)
        .first()
    )
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer trace '{answer_id}' not found.",
        )

    sources = []
    try:
        sources = json.loads(trace.sources_cited)
    except Exception:
        sources = []

    trace_dict = {}
    try:
        trace_dict = json.loads(trace.trace_data)
    except Exception:
        trace_dict = {}

    return AnswerTraceResponse(
        id=trace.id,
        workspace_id=trace.workspace_id,
        user_id=trace.user_id,
        question=trace.question,
        answer=trace.answer,
        sources_cited=sources,
        validation_status=trace.validation_status,
        confidence_label=trace.confidence_label,
        confidence_score=trace.confidence_score,
        trace_data=trace_dict,
        created_at=trace.created_at.isoformat(),
    )


@router.post("/{answer_id}/feedback", response_model=FeedbackResponse)
def submit_answer_feedback(
    answer_id: str,
    payload: AnswerFeedbackRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> FeedbackResponse:
    """Submits a user rating (+1 or -1) and optional qualitative feedback on an answer."""
    trace = (
        session.query(AnswerTrace)
        .filter_by(id=answer_id, workspace_id=ctx.workspace_id)
        .first()
    )
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer trace '{answer_id}' not found.",
        )

    if payload.rating not in (1, -1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be +1 (positive) or -1 (negative).",
        )

    feedback = Feedback(
        answer_id=trace.id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    session.add(feedback)
    session.commit()

    return FeedbackResponse(
        id=feedback.id,
        answer_id=feedback.answer_id,
        user_id=feedback.user_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at.isoformat(),
    )
