"""Ingestion jobs and connector dispatch endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from orgmind.auth import WorkspaceContext
from orgmind.models import IngestionJob, Role
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session, get_workspace_context, require_role
from apps.api.schemas import IngestionJobCreate, IngestionJobResponse, PaginatedResponse

router = APIRouter(prefix="/ingestion", tags=["Ingestion Service"])


@router.post("/jobs", response_model=IngestionJobResponse)
def trigger_ingestion_job(
    payload: IngestionJobCreate,
    ctx: WorkspaceContext = Depends(require_role(Role.EDITOR)),
    session: Session = Depends(get_db_session),
) -> IngestionJobResponse:
    """Enqueues an asynchronous document or connector ingestion job. Requires Editor or Admin role."""
    job = IngestionJob(
        id=f"job_{uuid.uuid4().hex[:10]}",
        workspace_id=ctx.workspace_id,
        connector_type=payload.connector_type,
        source_uri=payload.source_uri,
        status="pending",
        items_processed=0,
        items_failed=0,
    )
    session.add(job)
    session.commit()

    return IngestionJobResponse(
        id=job.id,
        workspace_id=job.workspace_id,
        connector_type=job.connector_type,
        source_uri=job.source_uri,
        status=job.status,
        items_processed=job.items_processed,
        items_failed=job.items_failed,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.get("/jobs", response_model=PaginatedResponse[IngestionJobResponse])
def list_ingestion_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> PaginatedResponse[IngestionJobResponse]:
    """Lists recent ingestion jobs for the active workspace."""
    query = session.query(IngestionJob).filter_by(workspace_id=ctx.workspace_id)
    total = query.count()
    jobs = (
        query.order_by(IngestionJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        IngestionJobResponse(
            id=j.id,
            workspace_id=j.workspace_id,
            connector_type=j.connector_type,
            source_uri=j.source_uri,
            status=j.status,
            items_processed=j.items_processed,
            items_failed=j.items_failed,
            error_message=j.error_message,
            created_at=j.created_at.isoformat(),
            completed_at=j.completed_at.isoformat() if j.completed_at else None,
        )
        for j in jobs
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(
    job_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db_session),
) -> IngestionJobResponse:
    """Retrieves status and error logs for an ingestion job."""
    job = (
        session.query(IngestionJob)
        .filter_by(id=job_id, workspace_id=ctx.workspace_id)
        .first()
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job '{job_id}' not found.",
        )

    return IngestionJobResponse(
        id=job.id,
        workspace_id=job.workspace_id,
        connector_type=job.connector_type,
        source_uri=job.source_uri,
        status=job.status,
        items_processed=job.items_processed,
        items_failed=job.items_failed,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )
