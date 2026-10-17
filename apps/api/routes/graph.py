"""Graph visualization, neighborhood exploration, and semantic path endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from orgmind.auth import WorkspaceContext
from orgmind.db import query_graph

from apps.api.dependencies import get_workspace_context
from apps.api.schemas import NeighborhoodResponse, PathResponse

router = APIRouter(prefix="/graph", tags=["Graph Operations"])


@router.get("/neighborhood", response_model=NeighborhoodResponse)
def get_graph_neighborhood(
    entity: str = Query(..., description="Center entity ID or name (e.g. 'P_ALICE', 'OAuth')"),
    hops: int = Query(2, ge=1, le=3, description="Expansion radius in hops"),
    as_of: str | None = Query(None, description="Bitemporal as-of filter"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> NeighborhoodResponse:
    """Traverses and extracts an N-hop subgraph centered around a starting node."""
    clean_entity = entity.strip()

    # Find center node
    center_cypher = """
    MATCH (c)
    WHERE c.id = $entity OR toLower(c.name) = toLower($entity)
    RETURN c.id AS id, coalesce(c.name, c.title, c.topic, c.id) AS name, labels(c)[0] AS type, properties(c) AS props
    """
    center_res = query_graph(center_cypher, {"entity": clean_entity}, workspace_id=ctx.workspace_id)
    if not center_res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Center entity '{entity}' not found in graph.",
        )

    center_node = center_res[0]
    center_id = center_node["id"]

    # Traverse 1-hop connected neighborhood
    cypher = """
    MATCH (start {id: $center_id})-[r]-(neighbor)
    RETURN DISTINCT labels(neighbor)[0] AS neighbor_type,
                    neighbor.id AS neighbor_id,
                    coalesce(neighbor.name, neighbor.title, neighbor.topic, neighbor.text, neighbor.id) AS neighbor_name,
                    properties(neighbor) AS neighbor_props,
                    type(r) AS rel_type,
                    startNode(r).id AS src_id,
                    endNode(r).id AS dst_id,
                    properties(r) AS rel_props
    LIMIT 100
    """
    rows = query_graph(cypher, {"center_id": center_id}, workspace_id=ctx.workspace_id)

    nodes_map: dict[str, dict[str, Any]] = {
        center_id: {
            "id": center_id,
            "name": center_node.get("name"),
            "type": center_node.get("type"),
            "properties": center_node.get("props") or {},
        }
    }
    edges: list[dict[str, Any]] = []
    seen_edges = set()

    for r in rows:
        nid = r.get("neighbor_id")
        if nid and nid not in nodes_map:
            nodes_map[nid] = {
                "id": nid,
                "name": r.get("neighbor_name"),
                "type": r.get("neighbor_type"),
                "properties": r.get("neighbor_props") or {},
            }

        src = r.get("src_id")
        dst = r.get("dst_id")
        rel_type = r.get("rel_type")
        edge_key = (src, dst, rel_type)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append({
                "source": src,
                "target": dst,
                "type": rel_type,
                "properties": r.get("rel_props") or {},
            })

    return NeighborhoodResponse(
        center_id=center_id,
        hops=hops,
        as_of=as_of,
        nodes=list(nodes_map.values()),
        edges=edges,
    )


@router.get("/path", response_model=PathResponse)
def get_graph_path(
    from_entity: str = Query(..., alias="from", description="Starting entity ID or name"),
    to_entity: str = Query(..., alias="to", description="Target entity ID or name"),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> PathResponse:
    """Discovers the shortest semantic path connecting two entities in the company brain."""
    f_clean = from_entity.strip()
    t_clean = to_entity.strip()

    # Try directed shortestPath from -> to
    cypher_forward = """
    MATCH (a), (b)
    WHERE (a.id = $from OR toLower(a.name) = toLower($from))
      AND (b.id = $to OR toLower(b.name) = toLower($to))
    RETURN shortestPath((a)-[*..5]->(b)) AS p
    """
    rows = query_graph(cypher_forward, {"from": f_clean, "to": t_clean}, workspace_id=ctx.workspace_id)
    path_obj = rows[0].get("p") if rows else None

    # Try reverse directed shortestPath to -> from if forward not found
    if not path_obj:
        cypher_reverse = """
        MATCH (a), (b)
        WHERE (a.id = $from OR toLower(a.name) = toLower($from))
          AND (b.id = $to OR toLower(b.name) = toLower($to))
        RETURN shortestPath((b)-[*..5]->(a)) AS p
        """
        rows = query_graph(cypher_reverse, {"from": f_clean, "to": t_clean}, workspace_id=ctx.workspace_id)
        path_obj = rows[0].get("p") if rows else None

    if not path_obj:
        return PathResponse(
            from_entity=f_clean,
            to_entity=t_clean,
            found=False,
            path_length=0,
            nodes=[],
            edges=[],
        )

    # Format nodes and edges from FalkorDB Path object
    path_nodes = []
    for n in path_obj.nodes():
        props = getattr(n, "properties", {})
        lbl = getattr(n, "labels", ["Entity"])
        path_nodes.append({
            "id": props.get("id", str(getattr(n, "id", ""))),
            "name": props.get("name") or props.get("title") or props.get("topic") or props.get("id"),
            "type": lbl[0] if lbl else "Entity",
            "properties": props,
        })

    path_edges = []
    for e in path_obj.edges():
        path_edges.append({
            "type": getattr(e, "relation", "RELATED"),
            "properties": getattr(e, "properties", {}),
        })

    return PathResponse(
        from_entity=f_clean,
        to_entity=t_clean,
        found=True,
        path_length=len(path_edges),
        nodes=path_nodes,
        edges=path_edges,
    )
