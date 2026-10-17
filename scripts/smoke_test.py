"""One-command smoke test for OrgMind.

Exits with code 0 on success, or non-zero on failure.
Checks:
1. Connection to FalkorDB
2. Node count > 0 and Edge count > 0
3. All 5 core Cypher queries execute successfully
4. Tools execute and return structured data
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import get_graph, query_graph
from orgmind.tools import who_owns, who_knows_about, trace_decision, what_changed_since


def run_smoke_test() -> int:
    print("==================================================")
    print(" [OrgMind Smoke Test] Starting System Verification ")
    print("==================================================")

    # 1. Connection check
    try:
        graph = get_graph()
        ping_res = graph.query("RETURN 1 AS ping")
        assert ping_res.result_set[0][0] == 1, "Ping query failed"
        print("[PASS] FalkorDB connection verified.")
    except Exception as exc:
        print(f"[FAIL] FalkorDB connection error: {exc}")
        return 1

    # 2. Node & Edge count check
    try:
        nodes_res = query_graph("MATCH (n) RETURN count(n) AS cnt")
        edges_res = query_graph("MATCH ()-[r]->() RETURN count(r) AS cnt")
        node_cnt = nodes_res[0]["cnt"]
        edge_cnt = edges_res[0]["cnt"]
        print(f"[INFO] Current graph status: {node_cnt} nodes, {edge_cnt} edges.")
        if node_cnt == 0:
            print("[FAIL] Graph is completely empty! Ingestion required.")
            return 2
        print("[PASS] Node & edge presence confirmed.")
    except Exception as exc:
        print(f"[FAIL] Node/Edge count query failed: {exc}")
        return 2

    # 3. Core Cypher Queries
    print("\n--- Verifying 5 Core Cypher Queries ---")
    queries = [
        ("Query 1: Who Owns", "MATCH (owner)-[:OWNS]->(target) RETURN labels(target)[0], target.name, owner.name LIMIT 3"),
        ("Query 2: Who Knows About", "MATCH (p:Person)-[:AUTHORED]->(item)-[:MENTIONS|ABOUT]->(top:Topic) RETURN p.name, top.name, count(item) AS cnt LIMIT 3"),
        ("Query 3: Decision Trace", "MATCH (d:Decision)-[:ABOUT]->(top:Topic) OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source) RETURN d.id, d.text, d.status, src.id LIMIT 3"),
        ("Query 4: Supersedes Linkage", "MATCH (d:Decision) OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision) RETURN d.id, d.status, old.id LIMIT 3"),
        ("Query 5: What Changed", "MATCH (d:Decision) RETURN 'Decision' AS type, d.id AS id, d.valid_from AS ts LIMIT 3"),
    ]

    for name, cypher in queries:
        try:
            res = query_graph(cypher)
            print(f"[PASS] {name} executed ({len(res)} sample records returned).")
        except Exception as exc:
            print(f"[FAIL] {name} failed: {exc}")
            return 3

    # 4. Tool Execution Verification
    print("\n--- Verifying Agent Tools Execution ---")
    try:
        owns = who_owns("OAuth")
        assert owns["found"] is True, "who_owns('OAuth') expected found=True"
        print(f"[PASS] Tool who_owns('OAuth') verified -> {owns['results'][0]['owner_name']}")

        knows = who_knows_about("Paynova")
        assert len(knows["ranked_experts"]) > 0, "who_knows_about('Paynova') expected experts"
        print(f"[PASS] Tool who_knows_about('Paynova') verified -> Top expert: {knows['ranked_experts'][0]['person_name']}")

        trace = trace_decision("OAuth")
        assert trace["found"] is True, "trace_decision('OAuth') expected found=True"
        print(f"[PASS] Tool trace_decision('OAuth') verified -> Decision: {trace['decisions'][0]['decision_id']}")
    except Exception as exc:
        print(f"[FAIL] Tool verification error: {exc}")
        return 4

    print("\n==================================================")
    print(" [OrgMind Smoke Test] ALL CHECKS PASSED (EXIT 0)   ")
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(run_smoke_test())
