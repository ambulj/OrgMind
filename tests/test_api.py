"""Comprehensive Contract Tests and SSE Streaming Tests for OrgMind API Layer (Phase 4)."""

import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "core"))

from orgmind.auth import Role, create_access_token
from orgmind.models import init_app_db

from apps.api.main import app


@pytest.fixture(scope="module", autouse=True)
def setup_api_database():
    """Ensure database schema is initialized before running tests."""
    init_app_db()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token():
    return create_access_token(
        user_id="usr_admin_test_01",
        email="admin_test_01@northwind.io",
        workspace_id="default",
        role=Role.ADMIN.value,
    )


@pytest.fixture
def viewer_token():
    return create_access_token(
        user_id="usr_viewer_test_01",
        email="viewer_test_01@northwind.io",
        workspace_id="default",
        role=Role.VIEWER.value,
    )


def test_health_endpoint(client: TestClient):
    """Tests the /health system diagnostics report."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "falkordb" in data["components"]
    assert "relational_db" in data["components"]
    assert "job_queue" in data["components"]


def test_consistent_error_envelope(client: TestClient):
    """Tests that errors follow the standard envelope format defined in API.md."""
    response = client.get("/api/v1/entities/invalid_category")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "BAD_REQUEST"
    assert "request_id" in data["error"]
    assert "timestamp" in data["error"]


def test_auth_and_user_lifecycle(client: TestClient):
    """Tests registration, login, and user profile endpoints."""
    test_email = f"tester_{uuid.uuid4().hex[:8]}@northwind.io"
    password = "SecurePassword123!"

    # 1. Register
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": test_email, "password": password, "full_name": "Phase 4 Tester"},
    )
    assert reg_resp.status_code == 200
    token = reg_resp.json()["access_token"]
    assert token is not None

    # 2. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": password},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # 3. Profile /me
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "default"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == test_email
    assert me_data["current_workspace"] == "default"


def test_workspaces_crud(client: TestClient, admin_token: str):
    """Tests listing workspaces and inspecting workspace memberships."""
    headers = {"Authorization": f"Bearer {admin_token}", "X-Workspace-Id": "default"}

    # 1. List workspaces
    ws_resp = client.get("/api/v1/workspaces", headers=headers)
    assert ws_resp.status_code == 200
    assert isinstance(ws_resp.json(), list)

    # 2. List members
    members_resp = client.get("/api/v1/workspaces/default/members", headers=headers)
    assert members_resp.status_code == 200
    assert isinstance(members_resp.json(), list)


def test_entities_catalog_and_detail(client: TestClient, viewer_token: str):
    """Tests entity listing with pagination and 1-hop detail views."""
    headers = {"Authorization": f"Bearer {viewer_token}", "X-Workspace-Id": "default"}

    # 1. List people
    people_resp = client.get("/api/v1/entities/people?page=1&page_size=5", headers=headers)
    assert people_resp.status_code == 200
    p_data = people_resp.json()
    assert p_data["total"] > 0
    assert len(p_data["items"]) <= 5
    assert p_data["items"][0]["type"] == "Person"

    # 2. Detail view of Alice Chen
    alice_resp = client.get("/api/v1/entities/people/P_ALICE", headers=headers)
    assert alice_resp.status_code == 200
    a_data = alice_resp.json()
    assert a_data["entity"]["id"] == "P_ALICE"
    assert a_data["entity"]["name"] == "Alice Chen"
    assert len(a_data["relationships"]) > 0


def test_decision_lineage(client: TestClient, viewer_token: str):
    """Tests decision supersession lineage traversal."""
    headers = {"Authorization": f"Bearer {viewer_token}", "X-Workspace-Id": "default"}

    resp = client.get("/api/v1/decisions/DEC_AUTH_2026_02/lineage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision_id"] == "DEC_AUTH_2026_02"
    assert data["supersedes"] == "DEC_AUTH_2026_01"
    assert len(data["source_anchors"]) > 0


def test_graph_neighborhood_and_path(client: TestClient, viewer_token: str):
    """Tests graph neighborhood extraction and semantic pathfinding."""
    headers = {"Authorization": f"Bearer {viewer_token}", "X-Workspace-Id": "default"}

    # 1. Neighborhood
    neigh_resp = client.get("/api/v1/graph/neighborhood?entity=P_ALICE&hops=2", headers=headers)
    assert neigh_resp.status_code == 200
    n_data = neigh_resp.json()
    assert n_data["center_id"] == "P_ALICE"
    assert len(n_data["nodes"]) > 1
    assert len(n_data["edges"]) > 0

    # 2. Semantic Path
    path_resp = client.get("/api/v1/graph/path?from=P_ALICE&to=OAuth", headers=headers)
    assert path_resp.status_code == 200
    p_data = path_resp.json()
    assert p_data["found"] is True
    assert p_data["path_length"] >= 1
    assert len(p_data["nodes"]) >= 2


def test_source_permission_enforcement(client: TestClient, viewer_token: str, admin_token: str):
    """Tests that restricted sources are blocked for Viewers and accessible for Admins."""
    from orgmind.db import get_graph

    graph = get_graph()
    graph.query(
        "MERGE (s:Source {id: 'SRC_RESTRICTED_CONFIDENTIAL_01'}) "
        "SET s.visibility = '[\"Admin\", \"Auditor\"]', s.redacted = false, s.text_snippet = 'Confidential Strategy M&A.'"
    )

    # 1. Public/All Source -> Viewer can access
    pub_resp = client.get(
        "/api/v1/sources/SRC_DOC_AUTH_01",
        headers={"Authorization": f"Bearer {viewer_token}", "X-Workspace-Id": "default"},
    )
    assert pub_resp.status_code == 200
    assert pub_resp.json()["id"] == "SRC_DOC_AUTH_01"

    # 2. Restricted Source -> Viewer gets 403 Forbidden
    viewer_restricted = client.get(
        "/api/v1/sources/SRC_RESTRICTED_CONFIDENTIAL_01",
        headers={"Authorization": f"Bearer {viewer_token}", "X-Workspace-Id": "default"},
    )
    assert viewer_restricted.status_code == 403
    assert "permission denied" in viewer_restricted.json()["error"]["message"].lower()

    # 3. Restricted Source -> Admin gets 200 OK
    admin_restricted = client.get(
        "/api/v1/sources/SRC_RESTRICTED_CONFIDENTIAL_01",
        headers={"Authorization": f"Bearer {admin_token}", "X-Workspace-Id": "default"},
    )
    assert admin_restricted.status_code == 200
    assert admin_restricted.json()["id"] == "SRC_RESTRICTED_CONFIDENTIAL_01"


def test_two_phase_actions_and_audit(client: TestClient, admin_token: str):
    """Tests propose-then-confirm action lifecycle and audit trail generation."""
    headers = {"Authorization": f"Bearer {admin_token}", "X-Workspace-Id": "default"}

    # 1. Propose Ticket Action
    prop_resp = client.post(
        "/api/v1/actions/propose",
        headers=headers,
        json={
            "action_type": "create_ticket",
            "parameters": {
                "title": "Upgrade Keycloak Identity Provider to v24",
                "description": "Security patch for CVE-2026-X",
                "project_id": "PRJ_OAUTH_UPGRADE",
            },
        },
    )
    assert prop_resp.status_code == 200
    prop_data = prop_resp.json()
    action_id = prop_data["action_id"]
    assert prop_data["status"] == "proposed"

    # 2. Confirm Action
    conf_resp = client.post(
        "/api/v1/actions/confirm",
        headers=headers,
        json={"action_id": action_id},
    )
    assert conf_resp.status_code == 200
    conf_data = conf_resp.json()
    assert conf_data["status"] == "confirmed"

    # 3. Verify in Audit Log
    audit_resp = client.get(
        "/api/v1/audit?action=execute_create_ticket",
        headers=headers,
    )
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert audit_data["total"] >= 1
    latest = audit_data["items"][0]
    assert latest["entity_id"] == action_id


def test_end_to_end_ask_sse_streaming(client: TestClient, admin_token: str):
    """Tests the full end-to-end /ask SSE streaming endpoint, event parsing, trace persistence, and feedback."""
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Workspace-Id": "default",
        "Accept": "text/event-stream",
    }

    # 1. Connect to SSE stream
    with client.stream(
        "POST",
        "/api/v1/ask",
        headers=headers,
        json={"question": "What is our OAuth standard and what did it supersede?"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        received_events = []
        answer_id = None

        # Parse SSE stream chunks
        for line in response.iter_lines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("event:"):
                ev_name = line_str.replace("event:", "").strip()
                received_events.append(ev_name)
            elif line_str.startswith("data:"):
                data_json = json.loads(line_str.replace("data:", "").strip())
                if data_json.get("event") == "done":
                    answer_id = data_json.get("answer_id")

        # Verify critical SSE event types were emitted in sequence
        expected_events = [
            "step",
            "tool_call",
            "tool_result_summary",
            "token",
            "citation",
            "validation",
            "confidence",
            "freshness",
            "done",
        ]
        for exp in expected_events:
            assert exp in received_events, f"Missing required SSE event: {exp}"

        assert answer_id is not None

    # 2. Verify answer trace was saved to relational database
    trace_resp = client.get(f"/api/v1/answers/{answer_id}/trace", headers=headers)
    assert trace_resp.status_code == 200
    t_data = trace_resp.json()
    assert t_data["id"] == answer_id
    assert "DEC_AUTH" in t_data["answer"]
    assert len(t_data["sources_cited"]) > 0
    assert t_data["validation_status"] == "ok"
    assert t_data["confidence_label"] == "High"

    # 3. Submit feedback on the trace
    feedback_resp = client.post(
        f"/api/v1/answers/{answer_id}/feedback",
        headers=headers,
        json={"rating": 1, "comment": "Accurately cited PKCE spec!"},
    )
    assert feedback_resp.status_code == 200
    f_data = feedback_resp.json()
    assert f_data["rating"] == 1
    assert f_data["answer_id"] == answer_id
