"""Background Job Worker for Ingestion Pipeline using arq / Redis."""

import asyncio
from typing import Any

from orgmind.config import settings
from orgmind.ingest.pipeline import PipelineResult, run_ingestion_job


async def execute_ingestion_job_task(
    ctx: dict[str, Any],
    job_id: str,
    connector_type: str,
    source_uri: str,
    workspace_id: str = "default",
) -> dict[str, Any]:
    """Background task function executed by arq worker."""
    result: PipelineResult = run_ingestion_job(
        job_id=job_id,
        connector_type=connector_type,
        source_uri=source_uri,
        workspace_id=workspace_id,
    )
    return {
        "job_id": result.job_id,
        "status": result.status,
        "content_hash": result.content_hash,
        "sources_written": result.sources_written,
        "decisions_written": result.decisions_written,
        "review_items_created": result.review_items_created,
        "error_message": result.error_message,
    }


class WorkerSettings:
    """arq Worker configuration."""

    functions = [execute_ingestion_job_task]
    redis_settings: Any = None  # Populated dynamically from settings.REDIS_JOBS_URL
    max_jobs = 10
    poll_delay = 0.5


async def enqueue_ingestion_task(
    job_id: str,
    connector_type: str,
    source_uri: str,
    workspace_id: str = "default",
) -> None:
    """Enqueues an ingestion task to the arq Redis queue, or falls back to an asyncio task."""
    try:
        # Parse Redis settings from REDIS_JOBS_URL
        from urllib.parse import urlparse

        from arq import create_pool
        from arq.connections import RedisSettings

        parsed = urlparse(settings.REDIS_JOBS_URL)
        r_settings = RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6380,
            password=parsed.password,
        )
        redis_pool = await create_pool(r_settings)
        await redis_pool.enqueue_job(
            "execute_ingestion_job_task",
            job_id=job_id,
            connector_type=connector_type,
            source_uri=source_uri,
            workspace_id=workspace_id,
        )
        await redis_pool.close()
    except Exception as e:
        # Fallback to local asyncio task for zero-dependency local runs or tests
        print(f"[Worker] Warning: Redis queue unavailable ({e}). Running in-process background task.")
        asyncio.create_task(
            asyncio.to_thread(
                run_ingestion_job,
                job_id=job_id,
                connector_type=connector_type,
                source_uri=source_uri,
                workspace_id=workspace_id,
            )
        )
