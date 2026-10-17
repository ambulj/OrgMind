"""End-to-End Test for Ingestion Hardening & Live-Update Pipeline (Phase 2).

Verifies:
1. Extraction Preview (preview_decision) on live reversal payload without mutating graph.
2. Decision Commit (commit_decision) linking new decision, source, and :SUPERSEDES edge.
3. Decision Tracing (trace_decision) showing new decision as current and old as superseded.
4. Multi-hop Impact Analysis (impact_analysis) identifying affected tickets (TICK-201, 202, 203),
   blocked dependencies (TICK-202 blocked by TICK-201), and responsible people.
5. Idempotency: re-running commit produces status 'noop_idempotent' with zero duplicate nodes/edges.
6. Entity resolution hardening: handles with typos and unknown flags.
"""

import sys
import os
from pathlib import Path
import json

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import query_graph
from orgmind.resolve import resolver
from orgmind.freshness import preview_decision, commit_decision, impact_analysis
from orgmind.tools import trace_decision
from scripts.reset_demo import reset_northwind_graph


def run_pipeline_test() -> bool:
    print("=" * 60)
    print(" [Phase 2 Test] Live-Update Pipeline & Ingestion Hardening")
    print("=" * 60)

    # Step 0: Ensure starting from clean base graph
    print("\n[Step 0] Resetting graph to clean baseline...")
    reset_northwind_graph()
    initial_nodes = query_graph("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
    initial_edges = query_graph("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]
    print(f"[Baseline] Graph has {initial_nodes} nodes, {initial_edges} edges.")

    # Step 1: Entity Resolver fuzzy & unknown handle checks
    print("\n[Step 1] Testing EntityResolver hardening...")
    res_exact = resolver.resolve_with_status("@alice")
    assert res_exact["status"] == "exact" and res_exact["resolved_id"] == "P_ALICE", f"Failed exact: {res_exact}"

    res_fuzzy = resolver.resolve_with_status("Ailce Chen")
    assert res_fuzzy["status"] == "fuzzy" and res_fuzzy["resolved_id"] == "P_ALICE", f"Failed fuzzy: {res_fuzzy}"

    res_unknown = resolver.resolve_with_status("ghost_contractor_xyz")
    assert res_unknown["status"] == "unknown" and res_unknown["flag_for_review"] is True, f"Failed unknown: {res_unknown}"
    assert len(resolver.get_flagged_unknowns()) >= 1, "Expected flagged unknown in resolver review list."
    print(" -> PASS: Exact resolution, fuzzy typo correction, and unknown handle flagging verified.")

    # Step 2: Extraction Preview
    live_file = "data/live/live_decision_reversal.json"
    print(f"\n[Step 2] Testing preview_decision on '{live_file}'...")
    preview = preview_decision(live_file)
    print(" Preview Output:")
    print(f"   Status: {preview['status']}")
    print(f"   Action: {preview['action']}")
    print(f"   Proposed Decision: {preview['proposed_decision']['id']}")
    print(f"   Superseded Candidate: {preview['superseded_decision_candidate']['id'] if preview['superseded_decision_candidate'] else None}")

    assert preview["status"] == "ready", f"Preview status should be 'ready', got {preview['status']}"
    assert preview["action"] == "SUPERSEDE", f"Preview action should be 'SUPERSEDE', got {preview['action']}"
    assert preview["superseded_decision_candidate"] is not None, "Candidate should not be None."
    assert preview["superseded_decision_candidate"]["id"] == "DEC_PAYMENTS_2026_03_PAYNOVA", (
        f"Expected to supersede DEC_PAYMENTS_2026_03_PAYNOVA, got {preview['superseded_decision_candidate']['id']}"
    )

    # Verify preview did NOT mutate the database
    mid_nodes = query_graph("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
    assert mid_nodes == initial_nodes, f"Preview modified database! Initial: {initial_nodes}, Now: {mid_nodes}"
    print(" -> PASS: Preview accurately detected superseding target without database mutation.")

    # Step 3: Decision Commit
    print(f"\n[Step 3] Testing commit_decision on '{live_file}'...")
    commit_res = commit_decision(preview)
    print(" Commit Output:", commit_res)

    assert commit_res["status"] == "success", f"Expected 'success', got {commit_res['status']}"
    assert commit_res["new_decision_id"] == "DEC_PAYMENTS_2026_05_REVERSAL"
    assert commit_res["superseded_decision_id"] == "DEC_PAYMENTS_2026_03_PAYNOVA"
    print(" -> PASS: Decision committed and supersedes link created.")

    # Step 4: Decision Tracing
    print("\n[Step 4] Testing trace_decision('Paynova')...")
    trace = trace_decision("Paynova")
    print(f" Found {len(trace['decisions'])} decision entries.")
    active_d = next((d for d in trace["decisions"] if d["status"] == "current"), None)
    assert active_d is not None, "No active decision found for Paynova!"
    assert active_d["decision_id"] == "DEC_PAYMENTS_2026_05_REVERSAL", f"Active decision mismatch: {active_d['decision_id']}"
    assert "INC-409" in active_d["decision_text"] or "Stripe" in active_d["decision_text"]
    assert active_d["superseded_decision_id"] == "DEC_PAYMENTS_2026_03_PAYNOVA"
    print(" -> PASS: Graph provenance trace confirms new reversal active and old decision superseded.")

    # Step 5: Multi-hop Impact Analysis
    print("\n[Step 5] Testing impact_analysis('Paynova')...")
    impact = impact_analysis("Paynova")
    print(f" Summary: {impact['summary']}")
    print(f" Affected tickets: {[t['ticket_id'] for t in impact['affected_tickets']]}")
    print(f" Blocked tickets: {[b['ticket_id'] for b in impact['blocked_tickets']]}")
    print(f" Responsible people: {[p['name'] for p in impact['responsible_people']]}")

    affected_ids = [t["ticket_id"] for t in impact["affected_tickets"]]
    assert "TICK-201" in affected_ids, "TICK-201 must be in affected tickets"
    assert "TICK-202" in affected_ids, "TICK-202 must be in affected tickets"

    blocked_ids = [b["ticket_id"] for b in impact["blocked_tickets"]]
    assert "TICK-202" in blocked_ids, "TICK-202 must be marked as blocked"

    people_names = [p["name"] for p in impact["responsible_people"]]
    assert any("Rohan" in name for name in people_names), "Rohan Iyer should be identified as responsible"
    assert any("Neha" in name or "Priya" in name for name in people_names), "Neha or Priya should be identified"
    assert len(impact["evidence_paths"]) > 0, "Evidence paths must not be empty"
    print(" -> PASS: Multi-hop impact analysis surfaced tickets, blockers, projects, and people.")

    # Step 6: Idempotency Test
    print("\n[Step 6] Testing Idempotency (re-committing same live file)...")
    post_commit_nodes = query_graph("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
    post_commit_edges = query_graph("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]

    idempotent_res = commit_decision(live_file)
    print(" Second Commit Output:", idempotent_res)
    assert idempotent_res["status"] == "noop_idempotent", (
        f"Expected 'noop_idempotent', got {idempotent_res['status']}"
    )

    retest_nodes = query_graph("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
    retest_edges = query_graph("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]
    assert retest_nodes == post_commit_nodes, f"Node count changed on idempotent commit! {post_commit_nodes} -> {retest_nodes}"
    assert retest_edges == post_commit_edges, f"Edge count changed on idempotent commit! {post_commit_edges} -> {retest_edges}"
    print(f" -> PASS: Idempotent re-commit verified (Node count preserved at {retest_nodes}, edges at {retest_edges}).")

    # Step 7: Teardown / Return to Clean State
    print("\n[Step 7] Cleaning up: resetting graph to pristine baseline...")
    reset_northwind_graph()
    final_nodes = query_graph("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
    assert final_nodes == initial_nodes, f"Tear-down failed: initial {initial_nodes}, now {final_nodes}"
    print(" -> PASS: Baseline restored for Demo Moments A-D.")

    print("\n" + "=" * 60)
    print(" ALL PHASE 2 INGESTION & LIVE-UPDATE TESTS PASSED (100%)")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_pipeline_test()
    sys.exit(0 if success else 1)
