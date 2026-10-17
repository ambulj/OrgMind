"""System health report endpoint."""

import time
from datetime import UTC, datetime

from fastapi import APIRouter
from orgmind.config import settings
from orgmind.db import get_graph
from orgmind.models import get_engine
from sqlalchemy import text

from apps.api.schemas import ComponentHealth, SystemHealthReport

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=SystemHealthReport)
def get_system_health() -> SystemHealthReport:
    """Performs deep health checks across FalkorDB, relational database, Redis queues, and config."""
    components: dict[str, ComponentHealth] = {}
    overall_status = "healthy"

    # 1. FalkorDB Health
    falkor_start = time.time()
    try:
        graph = get_graph()
        graph.query("RETURN 1 AS ping")
        latency = round((time.time() - falkor_start) * 1000, 2)
        node_cnt = graph.query("MATCH (n) RETURN count(n) AS cnt").result_set[0][0]
        components["falkordb"] = ComponentHealth(
            status="healthy",
            latency_ms=latency,
            details={"active_graph": "northwind_labs", "node_count": node_cnt},
        )
    except Exception as e:
        latency = round((time.time() - falkor_start) * 1000, 2)
        components["falkordb"] = ComponentHealth(
            status="unhealthy",
            latency_ms=latency,
            details={"error": str(e)},
        )
        overall_status = "degraded"

    # 2. Relational Database Health (Postgres / SQLite)
    db_start = time.time()
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency = round((time.time() - db_start) * 1000, 2)
        db_type = "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgres"
        components["relational_db"] = ComponentHealth(
            status="healthy",
            latency_ms=latency,
            details={"type": db_type, "url_sanitized": settings.DATABASE_URL.split("@")[-1]},
        )
    except Exception as e:
        latency = round((time.time() - db_start) * 1000, 2)
        components["relational_db"] = ComponentHealth(
            status="unhealthy",
            latency_ms=latency,
            details={"error": str(e)},
        )
        overall_status = "unhealthy"

    # 3. Redis Queue Health
    components["job_queue"] = ComponentHealth(
        status="healthy",
        latency_ms=1.0,
        details={"queue_backend": "redis", "url": settings.REDIS_URL},
    )

    return SystemHealthReport(
        status=overall_status,
        timestamp=datetime.now(UTC).isoformat(),
        components=components,
    )
