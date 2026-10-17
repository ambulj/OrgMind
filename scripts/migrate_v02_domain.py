"""Migration script: Upgrades FalkorDB graph schema to v0.2 Domain Model.

Adds bitemporal fields, cryptographic content hashes, visibility ACLs,
redaction tombstone attributes, and relationship tenure tracking.
"""

import hashlib
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

from orgmind.db import get_graph, query_graph


def migrate_domain_v02(graph_name: str = "northwind_labs") -> dict[str, Any]:
    """Executes schema upgrade on the target FalkorDB graph."""
    print("==================================================")
    print(f" [OrgMind Migration] Upgrading Graph to v0.2: '{graph_name}'")
    print("==================================================")

    graph = get_graph(graph_name)
    now_iso = datetime.now(UTC).isoformat()

    # 1. Migrate Decision Nodes
    decisions = query_graph(
        "MATCH (d:Decision) RETURN d.id AS id, d.valid_from AS valid_from, d.valid_to AS valid_to, d.status AS status",
        workspace_id=graph_name,
    )
    for dec in decisions:
        did = dec["id"]
        v_from = dec.get("valid_from") or "2026-01-01"
        v_to = dec.get("valid_to") or ""
        update_cypher = """
        MATCH (d:Decision {id: $id})
        SET d.valid_from = $valid_from,
            d.valid_to = $valid_to,
            d.recorded_at = $now,
            d.confidence = 1.0,
            d.confidence_tier = 'High',
            d.review_status = 'approved',
            d.extracted_by = 'manual',
            d.extraction_run_id = 'run_v02_migration'
        """
        graph.query(update_cypher, {
            "id": did,
            "valid_from": v_from,
            "valid_to": v_to,
            "now": now_iso,
        })
    print(f"[Migrate] Updated {len(decisions)} Decision nodes with bitemporal & confidence metadata.")

    # 2. Migrate Source Nodes
    sources = query_graph(
        "MATCH (s:Source) RETURN s.id AS id, s.file_path AS file_path, s.text_snippet AS snippet, s.created_at AS created_at",
        workspace_id=graph_name,
    )
    for src in sources:
        sid = src["id"]
        snippet = src.get("snippet") or ""
        fp = src.get("file_path") or ""
        created_at = src.get("created_at") or "2026-01-01T00:00:00Z"
        content_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()

        # Origin classification
        if "docs" in fp.lower():
            origin_type = "document"
        elif "chat" in fp.lower():
            origin_type = "chat"
        elif "live" in fp.lower() or "incident" in fp.lower():
            origin_type = "incident"
        else:
            origin_type = "meeting_notes"

        update_src_cypher = """
        MATCH (s:Source {id: $id})
        SET s.content_hash = $content_hash,
            s.uri = $uri,
            s.origin_type = $origin_type,
            s.visibility = '["all"]',
            s.redacted = false,
            s.redacted_at = '',
            s.redacted_by = '',
            s.redaction_reason = '',
            s.valid_from = $created_at,
            s.valid_to = '',
            s.recorded_at = $now
        """
        graph.query(update_src_cypher, {
            "id": sid,
            "content_hash": content_hash,
            "uri": f"file://{fp}" if fp and not fp.startswith("http") else fp,
            "origin_type": origin_type,
            "created_at": created_at,
            "now": now_iso,
        })
    print(f"[Migrate] Updated {len(sources)} Source nodes with SHA-256 hashes, visibility ACLs, and redaction flags.")

    # 3. Migrate OWNS Relationships
    owners_res = graph.query("""
    MATCH (a)-[r:OWNS]->(b)
    RETURN a.id AS a_id, b.id AS b_id, properties(r) AS props
    """)
    owns_count = 0
    if hasattr(owners_res, "result_set"):
        for row in owners_res.result_set:
            a_id = row[0]
            b_id = row[1]
            props = row[2] or {}
            v_from = props.get("valid_from") or "2026-01-01"
            v_to = props.get("valid_to") or ""
            status = "previous" if (v_to and v_to.strip()) else "current"

            update_owns_cypher = """
            MATCH (a {id: $a_id})-[r:OWNS]->(b {id: $b_id})
            SET r.valid_from = $valid_from,
                r.valid_to = $valid_to,
                r.recorded_at = $now,
                r.status = $status
            """
            graph.query(update_owns_cypher, {
                "a_id": a_id,
                "b_id": b_id,
                "valid_from": v_from,
                "valid_to": v_to,
                "now": now_iso,
                "status": status,
            })
            owns_count += 1
    print(f"[Migrate] Updated {owns_count} OWNS relationships with bitemporal validity and tenure status.")

    # 4. Initialize New Range Indexes
    new_indexes = [
        "CREATE INDEX FOR (d:Decision) ON (d.valid_from)",
        "CREATE INDEX FOR (d:Decision) ON (d.review_status)",
        "CREATE INDEX FOR (s:Source) ON (s.content_hash)",
        "CREATE INDEX FOR (s:Source) ON (s.redacted)",
    ]
    for idx in new_indexes:
        try:
            graph.query(idx)
        except Exception:
            pass

    print("[Migrate] Successfully applied v0.2 Domain Model migration.\n")
    return {
        "status": "success",
        "graph": graph_name,
        "decisions_migrated": len(decisions),
        "sources_migrated": len(sources),
        "ownership_edges_migrated": owns_count,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OrgMind Domain Model v0.2 Migration")
    parser.add_argument("--graph", default="northwind_labs", help="Target graph partition")
    args = parser.parse_args()
    migrate_domain_v02(args.graph)
