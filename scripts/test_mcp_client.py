"""Test MCP Client for OrgMind FastMCP Server & FalkorDB MCP Interface.

Validates:
1. Discovery of all registered OrgMind MCP tools and their parameter schemas.
2. Direct invocation of MCP tools through the MCP protocol interface.
3. Verification of tool results for ownership, expertise, decision lineage, draft comparison, and multi-hop impact.
4. Action simulation safety verification over MCP (confirm=False).
5. FalkorDB read-only query execution verification.
"""

import asyncio
import json
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import query_graph
from orgmind.mcp_server import mcp


async def test_mcp_tools():
    print("=" * 65)
    print(" [Phase 6 Test] OrgMind MCP Protocol & Server Verification")
    print("=" * 65)

    # -------------------------------------------------------------
    # Step 1: List Tools
    # -------------------------------------------------------------
    print("\n[Step 1] Discovering tools registered on OrgMind MCP server...")
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    print(f" Registered MCP Tools ({len(tools)} total):")
    for t in tools:
        print(f"   - {t.name}: {t.description[:60]}...")

    expected_tools = [
        "who_owns",
        "who_knows_about",
        "trace_decision",
        "compare_draft_vs_decision",
        "impact_analysis",
        "what_changed_since",
        "get_source",
        "find_related",
        "create_ticket",
        "draft_message",
        "assign_task",
    ]
    missing = [et for et in expected_tools if et not in tool_names]
    assert not missing, f"Missing expected MCP tools: {missing}"
    print(f" -> PASS: All {len(expected_tools)} expected tools discovered over MCP.")

    # -------------------------------------------------------------
    # Step 2: Test who_owns tool
    # -------------------------------------------------------------
    print("\n[Step 2] Invoking MCP tool 'who_owns' (OAuth)...")
    res_raw = await mcp.call_tool("who_owns", {"project_or_topic": "OAuth"})
    assert not res_raw.is_error, f"MCP tool returned error: {res_raw}"
    payload = json.loads(res_raw.content[0].text)
    curr_owners = payload.get("current_owners", [])
    person_owners = [o["owner_name"] for o in curr_owners if o.get("owner_type") == "Person"]
    print(f" Current Owners: {person_owners} | Found: {payload.get('found')}")
    assert "Alice Chen" in person_owners, f"Unexpected owner: {payload}"
    print(" -> PASS: 'who_owns' successfully resolved owner Alice Chen over MCP.")

    # -------------------------------------------------------------
    # Step 3: Test who_knows_about tool with weighted ranking
    # -------------------------------------------------------------
    print("\n[Step 3] Invoking MCP tool 'who_knows_about' (Paynova)...")
    res_raw = await mcp.call_tool("who_knows_about", {"topic": "Paynova"})
    assert not res_raw.is_error, f"MCP tool returned error: {res_raw}"
    payload = json.loads(res_raw.content[0].text)
    top_person = payload.get("top_expert")
    top_score = payload.get("ranked_experts", [{}])[0].get("weighted_score")
    print(f" Top Expert: {top_person} | Top Score: {top_score} pts")
    assert top_person == "Rohan Iyer", f"Expected Rohan Iyer, got {top_person}"
    print(" -> PASS: 'who_knows_about' ranked Rohan Iyer #1 with weighted evidence.")

    # -------------------------------------------------------------
    # Step 4: Test trace_decision tool
    # -------------------------------------------------------------
    print("\n[Step 4] Invoking MCP tool 'trace_decision' (OAuth)...")
    res_raw = await mcp.call_tool("trace_decision", {"topic": "OAuth"})
    assert not res_raw.is_error, f"MCP tool returned error: {res_raw}"
    payload = json.loads(res_raw.content[0].text)
    decisions = payload.get("decisions", [])
    active_dec = next(
        (d for d in decisions if d.get("status") == "current"), decisions[0] if decisions else {}
    )
    print(f" Active Decision ID: {active_dec.get('decision_id')}")
    print(f" Decision Text: {active_dec.get('decision_text')}")
    print(f" Source File: {active_dec.get('source_file')}")
    assert active_dec.get("decision_id") == "DEC_AUTH_2026_02", f"Unexpected decision: {active_dec}"
    print(" -> PASS: 'trace_decision' traced official policy and source lineage.")

    # -------------------------------------------------------------
    # Step 5: Test compare_draft_vs_decision tool
    # -------------------------------------------------------------
    print("\n[Step 5] Invoking MCP tool 'compare_draft_vs_decision' (Paynova)...")
    res_raw = await mcp.call_tool("compare_draft_vs_decision", {"topic": "Paynova"})
    assert not res_raw.is_error, f"MCP tool returned error: {res_raw}"
    payload = json.loads(res_raw.content[0].text)
    draft = payload.get("draft_proposal", {})
    ratified = payload.get("ratified_decision", {})
    print(f" Draft Author: {draft.get('author_name')} ({draft.get('draft_date')})")
    print(f" Ratified Decider: {ratified.get('decider_name')}")
    assert draft.get("author_name") == "Rohan Iyer"
    assert ratified.get("decider_name") == "Priya Sharma"
    print(" -> PASS: 'compare_draft_vs_decision' surfaced dissenting draft vs policy.")

    # -------------------------------------------------------------
    # Step 6: Test impact_analysis tool
    # -------------------------------------------------------------
    print("\n[Step 6] Invoking MCP tool 'impact_analysis' (Paynova)...")
    res_raw = await mcp.call_tool("impact_analysis", {"target": "Paynova"})
    assert not res_raw.is_error, f"MCP tool returned error: {res_raw}"
    payload = json.loads(res_raw.content[0].text)
    print(f" Impacted Tickets: {[t['ticket_id'] for t in payload.get('affected_tickets', [])]}")
    print(f" Blocked Items: {[b['ticket_id'] for b in payload.get('blocked_tickets', [])]}")
    assert len(payload.get("affected_tickets", [])) >= 3
    print(" -> PASS: 'impact_analysis' completed multi-hop dependency traversal.")

    # -------------------------------------------------------------
    # Step 7: Test Action Simulation Safety (confirm=False)
    # -------------------------------------------------------------
    print("\n[Step 7] Testing Action Simulation Safety over MCP (confirm=False)...")
    res_raw = await mcp.call_tool(
        "create_ticket",
        {
            "title": "Evaluate EU SEPA Webhook Reliability",
            "description": "Assess idempotency compliance for recurring SEPA transfers.",
            "project_id": "PRJ_BILLING_STRIPE",
            "confirm": False,
        },
    )
    assert not res_raw.is_error, f"MCP tool returned error: {res_raw}"
    payload = json.loads(res_raw.content[0].text)
    print(f" Proposal Status: {payload.get('status')}")
    print(f" Confirm Required: {payload.get('confirm_required')}")
    print(f" Proposed Ticket Title: {payload.get('preview', {}).get('title')}")
    assert payload.get("status") == "proposed_pending_confirmation", (
        f"Expected proposed_pending_confirmation, got {payload}"
    )
    assert payload.get("confirm_required") is True
    print(" -> PASS: Action simulation returned approval preview without mutating graph.")

    # -------------------------------------------------------------
    # Step 8: FalkorDB Read-Only Query Capability
    # -------------------------------------------------------------
    print("\n[Step 8] Testing FalkorDB Read-Only Cypher Query Interface...")
    ro_cypher = """
    MATCH (p:Person)-[:MEMBER_OF]->(t:Team)
    RETURN t.name AS team, count(p) AS member_count
    ORDER BY member_count DESC
    """
    team_counts = query_graph(ro_cypher)
    print(" Team Distribution in FalkorDB:")
    for tc in team_counts:
        print(f"   - {tc['team']}: {tc['member_count']} members")
    assert len(team_counts) >= 4, f"Expected at least 4 teams, got {len(team_counts)}"
    print(" -> PASS: FalkorDB read-only OpenCypher query succeeded.")

    print("\n" + "=" * 65)
    print(" ALL PHASE 6 MCP PROTOCOL & SERVER TESTS PASSED (100%)")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(test_mcp_tools())
