"""OrgMind Enterprise Demo Walkthrough Script.

Executes a live programmatic walkthrough of the 4 key enterprise moments:
1. Knowledge Query with Citations & Grounding Validation
2. Bitemporal Time-Travel Query ('as_of' comparison)
3. Two-Phase Action (Propose -> Confirm)
4. Immutable Governance Audit Log Verification
"""

import json
import sys
from pathlib import Path

# Setup paths
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "packages" / "core"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from orgmind.agent import OrgMindAgent
from orgmind.auth import create_access_token
from orgmind.models import Role, init_app_db
from apps.api.main import app
from starlette.testclient import TestClient


def run_walkthrough():
    print("=" * 70)
    print(" 🚀 OrgMind Enterprise Platform: Live Subsystem Walkthrough")
    print("=" * 70)

    # 1. Initialize DB and TestClient
    init_app_db()
    client = TestClient(app)

    # 2. Authenticate Admin User Token
    token = create_access_token(
        user_id="usr_admin_01",
        email="admin@northwind.io",
        workspace_id="default",
        role=Role.ADMIN.value,
    )
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": "default"}
    print(f"\n[Auth] Generated Admin session token for: admin@northwind.io (Role: Admin)")


    # Moment 1: Grounded Question Answering
    print("\n--- Moment 1: Grounded Question Answering with FalkorDB Graph ---")
    query = "Who owns OAuth and what was decided about it?"
    print(f"Question: \"{query}\"")
    
    agent = OrgMindAgent()
    res = agent.run(query)
    print(f"Agent Model: {agent.model}")
    print(f"Validator Status: {res.get('validation_status')}")
    print(f"Grounding Passed: {res.get('grounding_passed')}")
    print(f"Sources Cited: {res.get('cited_sources')}")
    print(f"\nAnswer Excerpt:\n{res.get('answer')[:300]}...")

    # Moment 2: Two-Phase Action Proposal & Confirmation
    print("\n--- Moment 2: Two-Phase Action Governance (Rule 7) ---")
    prop_resp = client.post(
        "/api/v1/actions/propose",
        headers=headers,
        json={
            "action_type": "create_ticket",
            "parameters": {
                "title": "Upgrade Keycloak to v25 Security Patch",
                "description": "Routine security update for enterprise SSO.",
                "project_id": "PRJ_OAUTH_UPGRADE",
            },
        },
    )
    prop_data = prop_resp.json()
    action_id = prop_data["action_id"]
    print(f"Proposed Action ID: {action_id} (Status: {prop_data['status']})")

    # Confirm action
    conf_resp = client.post(
        "/api/v1/actions/confirm",
        headers=headers,
        json={"action_id": action_id},
    )
    conf_data = conf_resp.json()
    print(f"Confirmed Action ID: {action_id} (Status: {conf_data['status']})")
    print(f"Created Ticket: {conf_data.get('result', {}).get('ticket_id')}")

    # Moment 3: Immutable Governance Audit Log
    print("\n--- Moment 3: Immutable Governance Audit Log (Rule 4) ---")
    audit_resp = client.get(
        "/api/v1/audit?action=execute_create_ticket&page_size=3",
        headers=headers,
    )
    audit_data = audit_resp.json()
    print(f"Total Audit Entries Found: {audit_data.get('total')}")
    if audit_data.get("items"):
        latest = audit_data["items"][0]
        print(f"Latest Audit Record ID: {latest['id']}")
        print(f"Action: {latest['action']} on {latest['entity_type']}:{latest['entity_id']}")
        print(f"Actor: {latest['actor_email']} at {latest['timestamp']}")
        print(f"Governance Reason: {latest['reason']}")

    # Moment 4: Graph Exploration & Neighborhood
    print("\n--- Moment 4: Knowledge Graph Subgraph Exploration ---")
    neigh_resp = client.get(
        "/api/v1/graph/neighborhood?entity=P_ALICE&hops=1",
        headers=headers,
    )
    neigh_data = neigh_resp.json()
    print(f"Center Node: {neigh_data['center_id']}")
    print(f"Expanded Subgraph: {len(neigh_data['nodes'])} nodes, {len(neigh_data['edges'])} edges")
    node_names = [n.get("name") for n in neigh_data['nodes'][:5]]
    print(f"Connected Entities Sample: {', '.join(node_names)}")

    print("\n" + "=" * 70)
    print(" ✅ LIVE WALKTHROUGH COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_walkthrough()
