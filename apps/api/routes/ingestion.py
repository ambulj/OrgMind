"""Ingestion jobs and connector dispatch endpoints."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from orgmind.auth import WorkspaceContext
from orgmind.ingest.pipeline import run_ingestion_job
from orgmind.ingest.worker import enqueue_ingestion_task
from orgmind.models import IngestionJob, Role
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session, get_workspace_context, require_role
from apps.api.schemas import IngestionJobCreate, IngestionJobResponse, PaginatedResponse

router = APIRouter(prefix="/ingestion", tags=["Ingestion Service"])


def _job_to_response(job: IngestionJob) -> IngestionJobResponse:
    """Helper to convert SQLAlchemy IngestionJob to pydantic IngestionJobResponse with explicit typing."""
    return IngestionJobResponse(
        id=str(job.id),
        workspace_id=str(job.workspace_id),
        connector_type=str(job.connector_type),
        source_uri=str(job.source_uri),
        status=str(job.status),
        items_processed=int(job.items_processed or 0),
        items_failed=int(job.items_failed or 0),
        error_message=str(job.error_message) if job.error_message else None,
        created_at=job.created_at.isoformat() if job.created_at else "",
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.post("/jobs", response_model=IngestionJobResponse)
def trigger_ingestion_job(
    payload: IngestionJobCreate,
    sync: bool = Query(False, description="Run synchronously before returning"),
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

    if sync:
        run_ingestion_job(
            job_id=str(job.id),
            connector_type=str(job.connector_type),
            source_uri=str(job.source_uri),
            workspace_id=str(job.workspace_id),
            db_session=session,
        )
        session.refresh(job)
    else:
        import asyncio

        asyncio.create_task(
            enqueue_ingestion_task(
                job_id=str(job.id),
                connector_type=str(job.connector_type),
                source_uri=str(job.source_uri),
                workspace_id=str(job.workspace_id),
            )
        )

    return _job_to_response(job)


@router.post("/upload", response_model=IngestionJobResponse)
async def upload_and_ingest_file(
    file: UploadFile = File(...),
    sync: bool = Query(True, description="Run pipeline synchronously for immediate feedback"),
    ctx: WorkspaceContext = Depends(require_role(Role.EDITOR)),
    session: Session = Depends(get_db_session),
) -> IngestionJobResponse:
    """Uploads a document (.md, .txt, .pdf) and triggers the multi-stage ingestion pipeline."""
    filename = file.filename or "uploaded_file.txt"
    ext = Path(filename).suffix.lower()
    if ext not in (".md", ".txt", ".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: .md, .txt, .pdf",
        )

    upload_dir = Path("data/uploads") / ctx.workspace_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / filename

    content_bytes = await file.read()
    saved_path.write_bytes(content_bytes)

    job = IngestionJob(
        id=f"job_up_{uuid.uuid4().hex[:8]}",
        workspace_id=ctx.workspace_id,
        connector_type="file_upload",
        source_uri=str(saved_path),
        status="pending",
        items_processed=0,
        items_failed=0,
    )
    session.add(job)
    session.commit()

    if sync:
        run_ingestion_job(
            job_id=str(job.id),
            connector_type="file_upload",
            source_uri=str(saved_path),
            workspace_id=str(job.workspace_id),
            db_session=session,
        )
        session.refresh(job)
    else:
        await enqueue_ingestion_task(
            job_id=str(job.id),
            connector_type="file_upload",
            source_uri=str(saved_path),
            workspace_id=str(job.workspace_id),
        )

    return _job_to_response(job)


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

    items = [_job_to_response(j) for j in jobs]
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
    job = session.query(IngestionJob).filter_by(id=job_id, workspace_id=ctx.workspace_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job '{job_id}' not found.",
        )

    return _job_to_response(job)
