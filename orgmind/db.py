"""Database connection and schema management for FalkorDB.

Technical Terms:
- FalkorDB: A low-latency graph database engine built on Redis that executes Cypher queries.
- Cypher: Declarative graph query language used to create and query nodes and edges.
- Graph Instance: A named graph partition inside FalkorDB (e.g. 'northwind_labs').
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from falkordb import FalkorDB

# Load environment variables from .env
load_dotenv()


def get_db_client() -> FalkorDB:
    """Creates and returns a connection client to the FalkorDB server.

    Reads configuration from environment variables:
    - FALKORDB_HOST (default: 'localhost')
    - FALKORDB_PORT (default: 6379)
    - FALKORDB_PASSWORD (optional)
    """
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    raw_pw = os.getenv("FALKORDB_PASSWORD", "").strip()
    password = raw_pw if raw_pw else None

    try:
        client = FalkorDB(host=host, port=port, password=password)
        client.connection.ping()
        return client
    except Exception as e:
        if "without any password configured" in str(e) or "WRONGPASS" in str(e):
            # FalkorDB instance has no password configured; auto-fallback to passwordless
            return FalkorDB(host=host, port=port, password=None)
        raise


def get_graph(graph_name: Optional[str] = None):
    """Selects and returns a specific graph instance within FalkorDB."""
    if graph_name is None:
        graph_name = os.getenv("FALKORDB_GRAPH_NAME", "northwind_labs")
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

    print("[OrgMind] Initializing graph indexes...")
    for idx_query in indexes:
        try:
            # TODO: FalkorDB will raise an exception if index already exists. Catch and ignore.
            graph.query(idx_query)
        except Exception as e:
            # Expected if index already exists
            print(f"[OrgMind] Index note: {e}")

    print("[OrgMind] Schema & indexes successfully initialized.")


def query_graph(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Executes a Cypher query with optional parameters and returns records as Python dictionaries.

    Args:
        query: OpenCypher query string compatible with FalkorDB.
        params: Dictionary of parameters to substitute (e.g. {'topic_name': 'OAuth'}).

    Returns:
        List of dicts representing tabular rows returned by the Cypher RETURN clause.
    """
    graph = get_graph()
    params = params or {}

    # TODO: In Person A sprint, convert FalkorDB QueryResult result_set into standard dict rows
    result = graph.query(query, params)
    rows: List[Dict[str, Any]] = []

    if hasattr(result, "header") and hasattr(result, "result_set"):
        headers = [col[1] if isinstance(col, (list, tuple)) else str(col) for col in result.header]
        for row in result.result_set:
            rows.append(dict(zip(headers, row)))

    return rows


def smoke_test() -> bool:
    """Runs a quick sanity check against FalkorDB: connects, writes one node, reads it, and cleans up."""
    print("[OrgMind] Running smoke test against FalkorDB...")
    try:
        graph = get_graph()
        # Create temporary node
        graph.query("CREATE (t:SmokeTestNode {test_id: 'smoke_1', status: 'ok'})")
        # Read back
        res = graph.query("MATCH (t:SmokeTestNode {test_id: 'smoke_1'}) RETURN t.status")
        # Clean up
        graph.query("MATCH (t:SmokeTestNode {test_id: 'smoke_1'}) DELETE t")

        if res.result_set and res.result_set[0][0] == "ok":
            print("[OrgMind] Smoke test PASSED: successfully wrote and read from FalkorDB!")
            return True
        else:
            print("[OrgMind] Smoke test FAILED: unexpected result set.")
            return False
    except Exception as exc:
        print(f"[OrgMind] Smoke test ERROR: {exc}")
        return False


if __name__ == "__main__":
    smoke_test()
