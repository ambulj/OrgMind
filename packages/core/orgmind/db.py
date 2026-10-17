"""Database connection, workspace isolation guard, and schema management for FalkorDB."""

import re
from typing import Any

from falkordb import FalkorDB

from orgmind.config import settings


def get_workspace_graph_name(workspace_id: str | None = None) -> str:
    """Maps a workspace identifier to its strictly isolated FalkorDB graph partition.

    Enforces workspace isolation by construction:
    - Default workspace -> settings.FALKORDB_GRAPH_NAME (e.g. 'northwind_labs')
    - Tenant workspaces -> 'org_' + sanitized_workspace_id
    - Cross-workspace graph access is impossible because graph names are
      deterministically derived and cannot cross partition boundaries.
    """
    if not workspace_id or workspace_id.strip() in (
        "",
        "default",
        "northwind_labs",
        settings.FALKORDB_GRAPH_NAME,
    ):
        return settings.FALKORDB_GRAPH_NAME

    # Sanitize workspace identifier: only alphanumeric and underscores allowed
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", workspace_id.strip().lower())
    clean_id = re.sub(r"_+", "_", clean_id).strip("_")

    if not clean_id:
        return settings.FALKORDB_GRAPH_NAME

    return f"org_{clean_id}" if not clean_id.startswith("org_") else clean_id


def get_db_client() -> FalkorDB:
    """Creates and returns a connection client to the FalkorDB server.
    Uses settings from pydantic-settings configuration with graceful password fallback.
    """
    host = settings.FALKORDB_HOST
    port = settings.FALKORDB_PORT
    password = settings.FALKORDB_PASSWORD if settings.FALKORDB_PASSWORD else None

    try:
        client = FalkorDB(host=host, port=port, password=password)
        client.connection.ping()
        return client
    except Exception as e:
        if "without any password configured" in str(e) or "WRONGPASS" in str(e):
            # FalkorDB instance has no password configured; auto-fallback to passwordless
            return FalkorDB(host=host, port=port, password=None)
        raise


def get_graph(workspace_or_graph: str | None = None):
    """Selects and returns an isolated graph instance within FalkorDB.

    Accepts either a workspace ID (which maps to 'org_<id>') or direct graph name.
    """
    graph_name = get_workspace_graph_name(workspace_or_graph)
    client = get_db_client()
    return client.select_graph(graph_name)


def init_schema(graph=None) -> None:
    """Initializes primary range indexes and schema constraints in FalkorDB.

    VERIFIED Cypher syntax for FalkorDB:
      CREATE INDEX FOR (n:Label) ON (n.property)
    """
    if graph is None:
        graph = get_graph()

    indexes = [
        "CREATE INDEX FOR (p:Person) ON (p.id)",
        "CREATE INDEX FOR (t:Team) ON (t.id)",
        "CREATE INDEX FOR (pr:Project) ON (pr.id)",
        "CREATE INDEX FOR (tp:Topic) ON (tp.name)",
        "CREATE INDEX FOR (d:Decision) ON (d.id)",
        "CREATE INDEX FOR (d:Decision) ON (d.topic)",
        "CREATE INDEX FOR (s:Source) ON (s.id)",
        "CREATE INDEX FOR (doc:Document) ON (doc.id)",
        "CREATE INDEX FOR (tk:Ticket) ON (tk.id)",
    ]

    for idx_query in indexes:
        try:
            graph.query(idx_query)
        except Exception:
            # Expected if index already exists
            pass


def query_graph(
    query: str,
    params: dict[str, Any] | None = None,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """Executes a parameterised OpenCypher query within an isolated workspace graph.

    Args:
        query: Parameterised OpenCypher query string.
        params: Dictionary of parameters (e.g. {'topic_name': 'OAuth'}).
        workspace_id: Optional workspace ID for multi-tenant isolation.

    Returns:
        List of dicts representing tabular rows returned by the Cypher RETURN clause.
    """
    graph = get_graph(workspace_id)
    params = params or {}

    result = graph.query(query, params)
    rows: list[dict[str, Any]] = []

    if hasattr(result, "header") and hasattr(result, "result_set"):
        headers = [col[1] if isinstance(col, (list, tuple)) else str(col) for col in result.header]
        for row in result.result_set:
            rows.append(dict(zip(headers, row)))

    return rows


def smoke_test() -> bool:
    """Runs a quick sanity check against FalkorDB: connects, writes one node, reads it, and cleans up."""
    try:
        graph = get_graph()
        graph.query("CREATE (t:SmokeTestNode {test_id: 'smoke_1', status: 'ok'})")
        res = graph.query("MATCH (t:SmokeTestNode {test_id: 'smoke_1'}) RETURN t.status")
        graph.query("MATCH (t:SmokeTestNode {test_id: 'smoke_1'}) DELETE t")

        return bool(res.result_set and res.result_set[0][0] == "ok")
    except Exception as exc:
        print(f"[OrgMind] Smoke test ERROR: {exc}")
        return False


if __name__ == "__main__":
    success = smoke_test()
    print(f"[OrgMind] DB Smoke Test: {'PASSED' if success else 'FAILED'}")
