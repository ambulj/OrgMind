"""OrgMind FastAPI Application Entry Point.
Versioned under /api/v1 with consistent error handling, CORS, and OpenAPI export.
"""

import json
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

# Ensure monorepo packages are on sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
core_pkg = root_dir / "packages" / "core"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(core_pkg) not in sys.path:
    sys.path.insert(0, str(core_pkg))

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from orgmind.config import settings
from orgmind.models import init_app_db

from apps.api.routes import (
    actions,
    answers,
    ask,
    audit,
    auth,
    decisions,
    entities,
    graph,
    health,
    ingestion,
    reviews,
    sources,
    workspaces,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database schema and warm connections upon API startup."""
    init_app_db()
    yield


app = FastAPI(
    title="OrgMind API",
    version="1.0.0",
    description="Enterprise Company Brain Knowledge Graph and Agent API for Northwind Labs.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware for Next.js web application
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler enforcing consistent error envelope
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:8]}")
    code = "HTTP_ERROR"
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "PERMISSION_DENIED"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"
    elif exc.status_code == status.HTTP_400_BAD_REQUEST:
        code = "BAD_REQUEST"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                "details": exc.detail if isinstance(exc.detail, dict) else {},
                "request_id": req_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:8]}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "details": {"error_type": type(exc).__name__, "description": str(exc)},
                "request_id": req_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        },
    )


# Mount all routers under /api/v1
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(workspaces.router)
api_v1.include_router(ask.router)
api_v1.include_router(answers.router)
api_v1.include_router(entities.router)
api_v1.include_router(decisions.router)
api_v1.include_router(graph.router)
api_v1.include_router(sources.router)
api_v1.include_router(ingestion.router)
api_v1.include_router(reviews.router)
api_v1.include_router(actions.router)
api_v1.include_router(audit.router)
api_v1.include_router(health.router)

app.include_router(api_v1)
# Direct health endpoint at root
app.include_router(health.router)


def export_openapi_json(output_path: str = "docs/openapi.json") -> str:
    """Exports the complete OpenAPI JSON specification to the documentation directory."""
    full_path = Path(output_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    openapi_schema = app.openapi()
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    return str(full_path)


if __name__ == "__main__":
    import uvicorn

    # If run directly with --export-openapi
    if "--export-openapi" in sys.argv:
        p = export_openapi_json()
        print(f"[OpenAPI] Exported OpenAPI schema to {p}")
    else:
        uvicorn.run(
            "apps.api.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True
        )
