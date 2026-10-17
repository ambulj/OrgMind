"""Source document retrieval and permission-checked grounding endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from orgmind.auth import WorkspaceContext
from orgmind.tools import get_source

from apps.api.dependencies import get_workspace_context
from apps.api.schemas import SourceDetailResponse

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source_by_id(
    source_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> SourceDetailResponse:
    """Retrieves verbatim source snippet, origin file, and cryptographic hash with in-query RBAC enforcement."""
    role_str = ctx.role.value if hasattr(ctx.role, "value") else str(ctx.role)
    result = get_source(source_id=source_id, caller_role=role_str, workspace_id=ctx.workspace_id)

    if not result.get("found"):
        err = result.get("error", "Source not found")
        if "access denied" in err.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: caller with role '{role_str}' is not authorized to view source '{source_id}'.",
            )
        if "redacted" in err.lower():
            return SourceDetailResponse(
                id=source_id,
                file_path=None,
                text_snippet="[REDACTED: Tombstone placeholder]",
                content_hash=None,
                origin_type="tombstone",
                visibility="restricted",
                redacted=True,
                redaction_reason="Redacted per data protection or privacy request",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found in graph.",
        )

    src = result["source"]
    return SourceDetailResponse(
        id=src.get("source_id") or source_id,
        file_path=src.get("file_path"),
        text_snippet=src.get("text_snippet") or "",
        content_hash=src.get("content_hash"),
        origin_type=src.get("origin_type"),
        visibility=src.get("visibility"),
        redacted=False,
    )
