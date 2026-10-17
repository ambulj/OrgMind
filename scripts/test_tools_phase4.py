"""Comprehensive Verification Test for Phase 4: Advanced Graph Tools & Weighted Evidence.

Verifies:
1. who_knows_about weighted scoring (Docs=3.0, Decisions=3.0, Tickets=2.0, Chats=1.0)
   eliminating near-ties and establishing Rohan Iyer as top Paynova expert and Alice Chen as OAuth expert.
2. compare_draft_vs_decision comparing Rohan's dissenting draft evaluation with Priya's ratified decision.
3. Action simulation safety: propose-then-confirm workflow (confirm=False previews, confirm=True commits).
"""

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import query_graph
from orgmind.tools import (
    assign_task,
    compare_draft_vs_decision,
    create_ticket,
    draft_message,
    who_knows_about,
)


def run_phase4_tests() -> bool:
    print("=" * 65)
    print(" [Phase 4 Test] Advanced Graph Tools & Weighted Evidence")
    print("=" * 65)

    # ---------------------------------------------------------
    # 1. Weighted Evidence Scoring: Paynova
    # ---------------------------------------------------------
    print("\n[Step 1] Testing who_knows_about('Paynova') with weighted scoring...")
    paynova_exp = who_knows_about("Paynova")
    print(f" Summary: {paynova_exp['evidence_summary']}")
    for exp in paynova_exp["ranked_experts"]:
        print(
            f"   - {exp['person_name']} ({exp['role']}): {exp['weighted_score']} pts [{exp['confidence_tier']}] {exp['evidence_breakdown']}"
        )

    assert paynova_exp["found"] is True, "Paynova experts should be found"
    assert paynova_exp["top_expert"] == "Rohan Iyer", (
        f"Expected Rohan Iyer as top expert, got {paynova_exp['top_expert']}"
    )

    top = paynova_exp["ranked_experts"][0]
    assert top["weighted_score"] >= 8.0, (
        f"Expected high score for Rohan, got {top['weighted_score']}"
    )
    assert top["evidence_breakdown"]["architecture_and_decisions"] >= 1, (
        "Rohan should have draft/doc evidence"
    )
    assert top["evidence_breakdown"]["tickets"] >= 1, "Rohan should have ticket evidence"
    assert top["evidence_breakdown"]["chat_messages"] >= 1, "Rohan should have chat evidence"

    # Verify tie-breaking: Rohan must score higher than Aarav Mehta
    aarav = next(
        (e for e in paynova_exp["ranked_experts"] if e["person_name"] == "Aarav Mehta"), None
    )
    if aarav:
        assert top["weighted_score"] > aarav["weighted_score"], (
            f"Weighted scoring failed to break tie! Rohan: {top['weighted_score']}, Aarav: {aarav['weighted_score']}"
        )
        print(
            f" -> PASS: Tie-breaking verified (Rohan {top['weighted_score']} pts vs Aarav {aarav['weighted_score']} pts)."
        )

    # ---------------------------------------------------------
    # 2. Weighted Evidence Scoring: OAuth
    # ---------------------------------------------------------
    print("\n[Step 2] Testing who_knows_about('OAuth')...")
    oauth_exp = who_knows_about("OAuth")
    print(f" Summary: {oauth_exp['evidence_summary']}")
    assert oauth_exp["found"] is True
    assert oauth_exp["top_expert"] == "Alice Chen"
    assert oauth_exp["ranked_experts"][0]["weighted_score"] >= 12.0
    print(" -> PASS: Alice Chen confirmed as authoritative architect on OAuth.")

    # ---------------------------------------------------------
    # 3. Draft vs Decision Comparison
    # ---------------------------------------------------------
    print("\n[Step 3] Testing compare_draft_vs_decision('Paynova')...")
    comp = compare_draft_vs_decision("Paynova")
    print(" Comparison Results:")
    print(
        f"   Draft Author: {comp['draft_proposal']['author_name']} ({comp['draft_proposal']['draft_date']})"
    )
    print(f"   Draft Advice: {comp['draft_proposal']['recommendation']}")
    print(
        f"   Ratified Decider: {comp['ratified_decision']['decider_name']} ({comp['ratified_decision']['valid_from']})"
    )
    print(f"   Ratified Text: {comp['ratified_decision']['decision_text']}")
    print(f"   Sources: {comp['sources']}")
    print(f"   Divergence Summary: {comp['key_divergence_summary']}")

    assert comp["found"] is True, "Draft and decision comparison must be found"
    assert comp["draft_proposal"]["author_name"] == "Rohan Iyer"
    assert comp["ratified_decision"]["decider_name"] == "Priya Sharma"
    assert "SRC_DOC_DRAFT_PAYNOVA_EVAL" in comp["sources"]
    assert "SRC_DOC_PAYNOVA_DECISION_01" in comp["sources"]
    print(" -> PASS: Dissenting draft evaluation accurately compared against ratified decision.")

    # ---------------------------------------------------------
    # 4. Action Simulation Safety (confirm=False vs confirm=True)
    # ---------------------------------------------------------
    print("\n[Step 4] Testing Action Simulation Safety (Propose-Then-Confirm)...")

    # A. Preview / Propose Ticket
    prop_tick = create_ticket(
        title="Automate Gateway Reconciliation",
        description="Daily audit job",
        project_id="PRJ_BILLING_STRIPE",
        confirm=False,
    )
    assert prop_tick["status"] == "proposed_pending_confirmation"
    assert prop_tick["confirm_required"] is True

    # Check graph: ticket must NOT exist yet
    check_not_written = query_graph(
        "MATCH (tk:Ticket {title: 'Automate Gateway Reconciliation'}) RETURN tk.id"
    )
    assert len(check_not_written) == 0, "Ticket was written when confirm=False!"
    print(
        " -> PASS: create_ticket(confirm=False) returned proposal preview without database modification."
    )

    # B. Confirmed Execution
    exec_tick = create_ticket(
        title="Automate Gateway Reconciliation",
        description="Daily audit job",
        project_id="PRJ_BILLING_STRIPE",
        confirm=True,
    )
    assert exec_tick["status"] == "simulated_success"
    ticket_id = exec_tick["ticket_id"]

    check_written = query_graph(
        "MATCH (tk:Ticket {id: $id}) RETURN tk.id AS id, tk.title AS title", {"id": ticket_id}
    )
    assert (
        len(check_written) == 1 and check_written[0]["title"] == "Automate Gateway Reconciliation"
    )
    print(f" -> PASS: create_ticket(confirm=True) recorded simulated node '{ticket_id}' in graph.")

    # C. Message Draft Safety
    prop_msg = draft_message(
        channel="#payments", text="Deploying reconciliation patch", confirm=False
    )
    assert prop_msg["status"] == "proposed_pending_confirmation"

    exec_msg = draft_message(
        channel="#payments", text="Deploying reconciliation patch", confirm=True
    )
    assert exec_msg["status"] == "simulated_success"
    print(f" -> PASS: draft_message confirmed execution ({exec_msg['message_id']}).")

    # D. Task Assignment Safety
    prop_task = assign_task(
        task_title="Verify HMAC Secrets",
        assignee_person_id="P_ROHAN",
        project_id="PRJ_BILLING_STRIPE",
        confirm=False,
    )
    assert prop_task["status"] == "proposed_pending_confirmation"

    exec_task = assign_task(
        task_title="Verify HMAC Secrets",
        assignee_person_id="P_ROHAN",
        project_id="PRJ_BILLING_STRIPE",
        confirm=True,
    )
    assert exec_task["status"] == "simulated_success"
    print(f" -> PASS: assign_task confirmed execution ({exec_task['task_id']}).")

    # Cleanup simulated test artifacts from graph
    print("\n[Step 5] Cleaning up simulated test nodes...")
    query_graph("MATCH (tk:Ticket {title: 'Automate Gateway Reconciliation'}) DETACH DELETE tk")
    query_graph(f"MATCH (m:Message {{id: '{exec_msg['message_id']}'}}) DETACH DELETE m")
    query_graph(f"MATCH (tk:Ticket {{id: '{exec_task['task_id']}'}}) DETACH DELETE tk")
    print(" -> PASS: Graph clean.")

    print("\n" + "=" * 65)
    print(" ALL PHASE 4 ADVANCED TOOL TESTS PASSED (100%)")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_phase4_tests()
    sys.exit(0 if success else 1)
