"""Entity catalog and detail view endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from orgmind.auth import WorkspaceContext
from orgmind.db import query_graph

from apps.api.dependencies import get_workspace_context
from apps.api.schemas import EntityDetailResponse, EntitySummary, PaginatedResponse

router = APIRouter(prefix="/entities", tags=["Entities"])

TYPE_LABEL_MAP = {
    "people": "Person",
    "projects": "Project",
    "teams": "Team",
    "topics": "Topic",
    "decisions": "Decision",
    "tickets": "Ticket",
    "documents": "Document",
}


@router.get("/{entity_type}", response_model=PaginatedResponse[EntitySummary])
def list_entities(
    entity_type: str,
    search: str | None = Query(None, description="Filter entities by name or id substring"),
    as_of: str | None = Query(None, description="Historical as-of filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> PaginatedResponse[EntitySummary]:
    """Lists entities of a given type with pagination and optional substring search."""
    clean_type = entity_type.strip().lower()
    label = TYPE_LABEL_MAP.get(clean_type)
    if not label:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity type '{entity_type}'. Supported types: {list(TYPE_LABEL_MAP.keys())}",
        )

    search_clause = ""
    params: dict[str, Any] = {}
    if search:
        search_clause = "WHERE toLower(n.name) CONTAINS toLower($search) OR toLower(n.id) CONTAINS toLower($search)"
        params["search"] = search.strip()

    count_cypher = f"MATCH (n:{label}) {search_clause} RETURN count(n) AS total"
    count_rows = query_graph(count_cypher, params, workspace_id=ctx.workspace_id)
    total = count_rows[0].get("total", 0) if count_rows else 0

    skip = (page - 1) * page_size
    query_cypher = f"""
    MATCH (n:{label}) {search_clause}
    RETURN n.id AS id, coalesce(n.name, n.title, n.topic, n.id) AS name, properties(n) AS props
    SKIP {skip} LIMIT {page_size}
    """
    rows = query_graph(query_cypher, params, workspace_id=ctx.workspace_id)

    items = [
        EntitySummary(
            id=r.get("id") or "",
            name=r.get("name") or "",
            type=label,
            properties=r.get("props") or {},
        )
        for r in rows
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{entity_type}/{entity_id}", response_model=EntityDetailResponse)
def get_entity_detail(
    entity_type: str,
    entity_id: str,
    as_of: str | None = Query(None, description="Historical as-of filter"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> EntityDetailResponse:
    """Retrieves full entity details, its direct 1-hop relationships, and recent changes."""
    clean_type = entity_type.strip().lower()
    label = TYPE_LABEL_MAP.get(clean_type)
    if not label:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity type '{entity_type}'.",
        )

    cypher = f"""
    MATCH (n:{label} {{id: $id}})
    RETURN n.id AS id, coalesce(n.name, n.title, n.topic, n.id) AS name, properties(n) AS props
    """
    rows = query_graph(cypher, {"id": entity_id}, workspace_id=ctx.workspace_id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Entity '{entity_id}' not found.")

    row = rows[0]
    entity_summary = EntitySummary(
        id=row.get("id") or entity_id,
        name=row.get("name") or entity_id,
        type=label,
        properties=row.get("props") or {},
    )

    # 1-hop relationships
    rel_cypher = """
    MATCH (n {id: $id})-[r]-(target)
    RETURN type(r) AS rel_type,
           labels(target)[0] AS target_type,
           target.id AS target_id,
           coalesce(target.name, target.title, target.topic, target.id) AS target_name,
           properties(r) AS rel_props
    LIMIT 50
    """
    rel_rows = query_graph(rel_cypher, {"id": entity_id}, workspace_id=ctx.workspace_id)

    relationships = [
        {
            "relationship": r.get("rel_type"),
            "target_type": r.get("target_type"),
            "target_id": r.get("target_id"),
            "target_name": r.get("target_name"),
            "properties": r.get("rel_props") or {},
        }
        for r in rel_rows
    ]

    return EntityDetailResponse(
        entity=entity_summary,
        relationships=relationships,
        recent_changes=[],
    )
