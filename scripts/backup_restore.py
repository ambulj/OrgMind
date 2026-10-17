"""FalkorDB Graph Backup & Restore Utility.

Provides per-graph serialization and restoration for backup routines, disaster recovery,
and workspace replication.
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add project root and packages/core to sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
core_pkg = os.path.join(project_root, "packages", "core")
if core_pkg not in sys.path:
    sys.path.insert(0, core_pkg)

from orgmind.db import get_db_client, init_schema


def dump_graph(
    source_graph_name: str = "northwind_labs", output_path: str | None = None
) -> dict[str, Any]:
    """Exports all nodes, relationships, and properties from a FalkorDB graph into a JSON backup payload."""
    client = get_db_client()
    graph = client.select_graph(source_graph_name)

    # 1. Fetch all nodes
    node_query = """
    MATCH (n)
    RETURN labels(n) AS labels, properties(n) AS props
    """
    node_res = graph.query(node_query)
    nodes = []
    if hasattr(node_res, "result_set"):
        for row in node_res.result_set:
            labels = row[0]
            props = row[1]
            nodes.append({"labels": labels, "props": props})

    # 2. Fetch all directed relationships
    edge_query = """
    MATCH (a)-[r]->(b)
    RETURN labels(a)[0] AS a_label,
           coalesce(a.id, a.name) AS a_id,
           type(r) AS rel_type,
           properties(r) AS props,
           labels(b)[0] AS b_label,
           coalesce(b.id, b.name) AS b_id
    """
    edge_res = graph.query(edge_query)
    edges = []
    if hasattr(edge_res, "result_set"):
        for row in edge_res.result_set:
            edges.append(
                {
                    "from_label": row[0],
                    "from_id": row[1],
                    "rel_type": row[2],
                    "props": row[3],
                    "to_label": row[4],
                    "to_id": row[5],
                }
            )

    backup_payload = {
        "graph_name": source_graph_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(backup_payload, f, indent=2)
        print(
            f"[Backup] Successfully dumped graph '{source_graph_name}' ({len(nodes)} nodes, {len(edges)} edges) to: {output_path}"
        )

    return backup_payload


def restore_graph(backup_source: Any, target_graph_name: str) -> dict[str, Any]:
    """Restores a graph from a JSON backup file or payload dictionary into a target graph partition."""
    if isinstance(backup_source, (str, Path)):
        with open(backup_source, encoding="utf-8") as f:
            payload = json.load(f)
    elif isinstance(backup_source, dict):
        payload = backup_source
    else:
        raise ValueError("backup_source must be a file path or dict payload")

    client = get_db_client()

    # Safely wipe target graph first if it already exists
    try:
        client.select_graph(target_graph_name).delete()
    except Exception:
        pass

    target_graph = client.select_graph(target_graph_name)
    init_schema(target_graph)

    # 1. Restore nodes
    nodes = payload.get("nodes", [])
    for node in nodes:
        labels_str = ":".join(node["labels"])
        props = node.get("props") or {}
        if props:
            param_defs = [f"`{k}`: ${k}" for k in props]
            cypher = f"CREATE (n:{labels_str} {{{', '.join(param_defs)}}})"
            target_graph.query(cypher, props)
        else:
            target_graph.query(f"CREATE (n:{labels_str})")

    # 2. Restore relationships
    edges = payload.get("edges", [])
    for edge in edges:
        from_label = edge["from_label"]
        from_id = edge["from_id"]
        to_label = edge["to_label"]
        to_id = edge["to_id"]
        rel = edge["rel_type"]
        props = edge.get("props") or {}

        if props:
            param_defs = [f"`{k}`: $p_{k}" for k in props]
            rel_props_str = f" {{{', '.join(param_defs)}}}"
            edge_params = {f"p_{k}": v for k, v in props.items()}
        else:
            rel_props_str = ""
            edge_params = {}

        edge_params["from_id"] = from_id
        edge_params["to_id"] = to_id

        cypher = f"""
        MATCH (a:{from_label}), (b:{to_label})
        WHERE coalesce(a.id, a.name) = $from_id AND coalesce(b.id, b.name) = $to_id
        CREATE (a)-[r:{rel}{rel_props_str}]->(b)
        """
        target_graph.query(cypher, edge_params)

    # Verify restored counts
    res_nodes = target_graph.query("MATCH (n) RETURN count(n) AS cnt").result_set[0][0]
    res_edges = target_graph.query("MATCH ()-[r]->() RETURN count(r) AS cnt").result_set[0][0]

    print(f"[Restore] Restored into '{target_graph_name}': {res_nodes} nodes, {res_edges} edges.")
    return {
        "status": "success",
        "target_graph": target_graph_name,
        "restored_nodes": res_nodes,
        "restored_edges": res_edges,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OrgMind FalkorDB Graph Backup & Restore")
    parser.add_argument("action", choices=["backup", "restore"], help="Action to perform")
    parser.add_argument("--graph", default="northwind_labs", help="Graph name")
    parser.add_argument("--file", default="data/backups/graph_backup.json", help="Backup file path")

    args = parser.parse_args()
    if args.action == "backup":
        dump_graph(args.graph, args.file)
    elif args.action == "restore":
        restore_graph(args.file, args.graph)
