"""Demo Reset Script.

Wipes ONLY the specified northwind graph ('northwind_labs'),
re-initializes indexes, and re-ingests the base dataset.
Leaves /data/live files UNLOADED so live update demo moments start from clean baseline.
"""

import os
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
core_pkg = os.path.join(project_root, "packages", "core")
if core_pkg not in sys.path:
    sys.path.insert(0, core_pkg)

from orgmind.db import get_db_client, query_graph
from orgmind.ingest_structured import run_all_structured_ingestion
from orgmind.ingest_unstructured import run_all_unstructured_ingestion


def reset_northwind_graph(graph_name: str = "northwind_labs") -> bool:
    print("==================================================")
    print(f" [OrgMind Demo Reset] Resetting graph: '{graph_name}'")
    print("==================================================")

    client = get_db_client()
    try:
        # Check existing graphs
        existing_graphs = client.list_graphs()
        print(f"[INFO] Existing graphs in FalkorDB: {existing_graphs}")

        if graph_name in existing_graphs:
            print(f"[INFO] Deleting graph '{graph_name}' (safe wipe: other graphs untouched)...")
            g = client.select_graph(graph_name)
            g.delete()
            print(f"[PASS] Successfully wiped '{graph_name}'.")
        else:
            print(
                f"[INFO] Graph '{graph_name}' does not exist yet. Proceeding with clean initialization."
            )

    except Exception as exc:
        print(f"[WARN] Error during graph deletion: {exc}")

    # Re-run structured ingestion (creates indexes, people, teams, projects, tickets)
    print("\n--- Running Structured Ingestion ---")
    run_all_structured_ingestion()

    # Re-run unstructured ingestion (docs and chats)
    print("\n--- Running Unstructured Ingestion ---")
    run_all_unstructured_ingestion()

    # Run v0.2 Domain Upgrade Pass to guarantee visibility, hashes, and bitemporal dates
    print("\n--- Running v0.2 Domain Upgrade Pass ---")
    try:
        from migrate_v02_domain import migrate_domain_v02
    except ImportError:
        from scripts.migrate_v02_domain import migrate_domain_v02
    migrate_domain_v02(graph_name)

    # Verify counts
    node_cnt = query_graph("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
    edge_cnt = query_graph("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]
    print(f"\n[DONE] Demo Reset complete! Clean base state: {node_cnt} nodes, {edge_cnt} edges.")
    print("[NOTE] /data/live/ update files remain unloaded. Ready for Demo Moments A-D.\n")
    return True


if __name__ == "__main__":
    reset_northwind_graph()
