"""Decision supersession lineage endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from orgmind.auth import WorkspaceContext
from orgmind.db import query_graph

from apps.api.dependencies import get_workspace_context
from apps.api.schemas import DecisionLineageResponse

router = APIRouter(prefix="/decisions", tags=["Decisions & Lineage"])


@router.get("/{decision_id}/lineage", response_model=DecisionLineageResponse)
def get_decision_lineage(
    decision_id: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> DecisionLineageResponse:
    """Traverses and returns the supersession lineage chain for a given decision, including source anchors."""
    cypher = """
    MATCH (d:Decision {id: $id})
    OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
    OPTIONAL MATCH (newer:Decision)-[:SUPERSEDES]->(d)
    OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
    RETURN d.id AS id,
           d.topic AS topic,
           d.text AS text,
           d.status AS status,
           d.valid_from AS valid_from,
           d.valid_to AS valid_to,
           old.id AS supersedes_id,
           old.text AS supersedes_text,
           newer.id AS superseded_by_id,
           newer.text AS superseded_by_text,
           src.id AS source_id,
           src.file_path AS source_file,
           src.content_hash AS source_hash
    """
    rows = query_graph(cypher, {"id": decision_id}, workspace_id=ctx.workspace_id)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found.",
        )

    row = rows[0]
    source_anchors = []
    if row.get("source_id"):
        source_anchors.append(
            {
                "source_id": row["source_id"],
                "file_path": row.get("source_file"),
                "content_hash": row.get("source_hash"),
            }
        )

    # Build lineage chain
    lineage_chain = []
    if row.get("supersedes_id"):
        lineage_chain.append(
            {
                "relation": "supersedes",
                "decision_id": row["supersedes_id"],
                "text": row.get("supersedes_text"),
            }
        )
    if row.get("superseded_by_id"):
        lineage_chain.append(
            {
                "relation": "superseded_by",
                "decision_id": row["superseded_by_id"],
                "text": row.get("superseded_by_text"),
            }
        )

    return DecisionLineageResponse(
        decision_id=row["id"],
        topic=row.get("topic") or "General",
        status=row.get("status") or "current",
        valid_from=row.get("valid_from"),
        valid_to=row.get("valid_to"),
        superseded_by=row.get("superseded_by_id"),
        supersedes=row.get("supersedes_id"),
        source_anchors=source_anchors,
        lineage_chain=lineage_chain,
    )
