"""Automated End-to-End Execution of Hackathon Demo Moments A through E.

Simulates a presenter stepping through the full live demonstration:
- Moment A: Ownership & Weighted Expertise
- Moment B: Decision Lineage & Source Provenance
- Moment C: Live Superseding (Paynova Reversal)
- Moment D: Dissenting Draft vs Ratified Decision
- Moment E: Multi-Hop Impact & Critical Blocker Discovery
- Reset: Restores clean 163-node baseline
"""

import os
import sys
import time
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from orgmind.agent import OrgMindAgent
from orgmind.freshness import commit_decision

from scripts.reset_demo import reset_northwind_graph


def main():
    print("=" * 65)
    print(" 🎬 [OrgMind Phase 8 Execution] 5 Demo Moments Walkthrough")
    print("=" * 65)

    agent = OrgMindAgent()

    # Step 0: Ensure baseline
    print("\n[Step 0] Verifying clean starting graph...")
    reset_northwind_graph()

    # Moment A
    print("\n[Moment A] Executing Ownership & Weighted Expertise...")
    t0 = time.perf_counter()
    res_a = agent.run(
        "Who owns the OAuth Upgrade project, and who has the highest demonstrated knowledge on OAuth?"
    )
    dt_a = round(time.perf_counter() - t0, 2)
    print(f" -> Completed in {dt_a}s | Grounded: {res_a.get('grounded')}")
    print(f"    Answer Preview: {res_a.get('answer')[:180]}...")
    assert "Alice Chen" in res_a.get("answer"), "Moment A failed to cite Alice Chen"
    print(" -> PASS: Moment A verified.")

    # Moment B
    print("\n[Moment B] Executing Decision Lineage & Source Provenance...")
    t0 = time.perf_counter()
    res_b = agent.run(
        "What is our official decision on authentication standards, where was it documented, and what source ID supports it?"
    )
    dt_b = round(time.perf_counter() - t0, 2)
    print(f" -> Completed in {dt_b}s | Grounded: {res_b.get('grounded')}")
    print(f"    Answer Preview: {res_b.get('answer')[:180]}...")
    assert "OAuth" in res_b.get("answer"), "Moment B failed to cite OAuth"
    print(" -> PASS: Moment B verified.")

    # Moment C
    print("\n[Moment C] Executing Live Superseding Ingestion...")
    t0 = time.perf_counter()
    commit_res = commit_decision("data/live/live_decision_reversal.json")
    print(
        f"    Commit Result: {commit_res.get('status')} | New ID: {commit_res.get('new_decision_id')}"
    )
    res_c = agent.run(
        "What is our current official policy on Paynova and recurring payments, and what older decision did it supersede?"
    )
    dt_c = round(time.perf_counter() - t0, 2)
    print(f" -> Completed in {dt_c}s | Grounded: {res_c.get('grounded')}")
    print(f"    Answer Preview: {res_c.get('answer')[:180]}...")
    assert (
        "superseded" in res_c.get("answer").lower() or "supersedes" in res_c.get("answer").lower()
    ), "Moment C failed to describe superseding"
    print(" -> PASS: Moment C verified.")

    # Moment D
    print("\n[Moment D] Executing Dissenting Draft vs Ratified Decision...")
    t0 = time.perf_counter()
    res_d = agent.run(
        "Compare the draft technical evaluation for European billing against the official decision. Was there any dissenting advice?"
    )
    dt_d = round(time.perf_counter() - t0, 2)
    print(f" -> Completed in {dt_d}s | Grounded: {res_d.get('grounded')}")
    print(f"    Answer Preview: {res_d.get('answer')[:180]}...")
    assert "Rohan" in res_d.get("answer") or "idempotency" in res_d.get("answer").lower(), (
        "Moment D failed to cite draft"
    )
    print(" -> PASS: Moment D verified.")

    # Moment E
    print("\n[Moment E] Executing Multi-Hop Impact & Critical Blocker Analysis...")
    t0 = time.perf_counter()
    res_e = agent.run(
        "What tickets and projects are impacted by Paynova, and which specific work item is currently blocked?"
    )
    dt_e = round(time.perf_counter() - t0, 2)
    print(f" -> Completed in {dt_e}s | Grounded: {res_e.get('grounded')}")
    print(f"    Answer Preview: {res_e.get('answer')[:180]}...")
    assert "TICK-202" in res_e.get("answer") or "blocked" in res_e.get("answer").lower(), (
        "Moment E failed to surface blocker"
    )
    print(" -> PASS: Moment E verified.")

    # Reset
    print("\n[Reset] Restoring pristine 163-node baseline for live presentation...")
    reset_northwind_graph()
    print(" -> PASS: Clean baseline restored.")

    print("\n" + "=" * 65)
    print(" ALL 5 DEMO MOMENTS EXECUTED AND VERIFIED SUCCESSFULLY (100%)")
    print("=" * 65)


if __name__ == "__main__":
    main()
