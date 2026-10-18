"""Unit tests for Phase 3 Domain Model Upgrade.
Acceptance criteria:
- As-of temporal queries (known fact changes across dates)
- Permission filtering inside queries (Viewer cannot see restricted Source)
- Redaction tombstones (blank text, preserve hash and topology, audit log)
- Merge candidates (never merge silently)
- Idempotent migration
"""

import hashlib
import sys
from pathlib import Path

# Ensure monorepo package is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "core"))

from orgmind.auth import Role
from orgmind.db import get_db_client, get_graph, query_graph
from orgmind.models import AuditLog, get_session_factory, init_app_db
from orgmind.resolve import EntityResolver
from orgmind.tools import get_source, redact_source, trace_decision, who_owns


def setup_module() -> None:
    """Initialize test relational DB and seed default workspace."""
    init_app_db()


def test_as_of_ownership_temporal_query() -> None:
    """Tests that who_owns correctly respects as_of timestamps across an ownership transition."""
    # In Northwind Labs: Customer Self-Serve Portal (PRJ_PORTAL_REDESIGN)
    # Carol Danvers: valid_from: '2026-01-01', valid_to: '2026-03-15'
    # Frank Wright: valid_from: '2026-03-15', valid_to: ''

    # 1. As of 2026-02-01 (before transition) -> Carol Danvers active
    past_res = who_owns("Customer Self-Serve Portal", as_of="2026-02-01")
    assert past_res["found"] is True
    past_owners = [o["owner_name"] for o in past_res["current_owners"]]
    assert "Carol Danvers" in past_owners
    assert "Frank Wright" not in past_owners

    # 2. As of 2026-04-01 (after transition) -> Frank Wright active
    future_res = who_owns("Customer Self-Serve Portal", as_of="2026-04-01")
    assert future_res["found"] is True
    future_owners = [o["owner_name"] for o in future_res["current_owners"]]
    assert "Frank Wright" in future_owners
    assert "Carol Danvers" not in future_owners


def test_as_of_decision_temporal_query() -> None:
    """Tests that trace_decision accurately retrieves the active decision at a historical date."""
    # Northwind Labs OAuth decisions:
    # DEC_AUTH_2026_01 valid_from: 2026-01-15, valid_to: 2026-01-28
    # DEC_AUTH_2026_02 valid_from: 2026-01-28, valid_to: ''

    # 1. As of 2026-01-20 -> DEC_AUTH_2026_01 was active
    past_res = trace_decision("OAuth", as_of="2026-01-20")
    assert past_res["found"] is True
    assert len(past_res["decisions"]) >= 1
    assert past_res["decisions"][0]["decision_id"] == "DEC_AUTH_2026_01"

    # 2. As of 2026-02-15 -> DEC_AUTH_2026_02 was active
    future_res = trace_decision("OAuth", as_of="2026-02-15")
    assert future_res["found"] is True
    assert len(future_res["decisions"]) >= 1
    assert past_res["decisions"][0]["decision_id"] == "DEC_AUTH_2026_01"
    assert future_res["decisions"][0]["decision_id"] == "DEC_AUTH_2026_02"


def test_in_query_permission_filtering() -> None:
    """Tests that permission filtering occurs in the query itself and prevents Viewers from seeing restricted sources."""
    graph = get_graph()
    test_src_id = "SRC_RESTRICTED_CONFIDENTIAL_01"
    raw_content = "Confidential Q4 M&A strategy details."
    content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

    # Create restricted source accessible only to Admin and Auditor
    graph.query(
        """
        MERGE (s:Source {id: $id})
        SET s.content_hash = $hash,
            s.text_snippet = $snippet,
            s.visibility = $visibility,
            s.redacted = false,
            s.origin_type = 'strategy_doc'
        """,
        {
            "id": test_src_id,
            "hash": content_hash,
            "snippet": raw_content,
            "visibility": '["Admin", "Auditor"]',
        },
    )

    # 1. Viewer attempt -> Must be denied / not returned by Cypher query
    viewer_res = get_source(test_src_id, caller_role=Role.VIEWER.value)
    assert viewer_res["found"] is False
    err_msg = viewer_res.get("error", "").lower()
    assert "access denied" in err_msg or "permission denied" in err_msg or "not found" in err_msg

    # 2. Editor attempt -> Must also be denied
    editor_res = get_source(test_src_id, caller_role=Role.EDITOR.value)
    assert editor_res["found"] is False

    # 3. Admin attempt -> Permitted
    admin_res = get_source(test_src_id, caller_role=Role.ADMIN.value)
    assert admin_res["found"] is True
    assert admin_res["source"]["content_hash"] == content_hash
    assert admin_res["source"]["text_snippet"] == raw_content


def test_redaction_tombstone_and_audit() -> None:
    """Tests that redact_source blanks text, preserves hash/topology, and logs to relational AuditLog."""
    graph = get_graph()
    test_src_id = "SRC_PII_TEST_01"
    raw_content = "Customer credit card number 4111-2222-3333-4444."
    content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

    # Seed source node
    graph.query(
        """
        MERGE (s:Source {id: $id})
        SET s.content_hash = $hash,
            s.text_snippet = $snippet,
            s.visibility = '["all"]',
            s.redacted = false
        """,
        {
            "id": test_src_id,
            "hash": content_hash,
            "snippet": raw_content,
        },
    )

    # Execute redaction tombstone
    actor = "usr_dpo_officer_01"
    reason = "GDPR Article 17 Right to Erasure request"
    redact_res = redact_source(
        source_id=test_src_id,
        reason=reason,
        actor=actor,
    )
    assert redact_res["status"] == "success"
    assert redact_res["content_hash"] == content_hash

    # Verify node in FalkorDB
    node_rows = query_graph(
        "MATCH (s:Source {id: $id}) RETURN s.text_snippet AS snippet, s.redacted AS redacted, s.content_hash AS hash",
        {"id": test_src_id},
    )
    assert len(node_rows) == 1
    assert node_rows[0]["redacted"] is True
    assert f"[REDACTED: {reason}]" in node_rows[0]["snippet"]
    assert "4111" not in node_rows[0]["snippet"]
    assert node_rows[0]["hash"] == content_hash

    # Verify relational AuditLog entry
    session_factory = get_session_factory()
    with session_factory() as session:
        log_entry = (
            session.query(AuditLog)
            .filter_by(action="redact_source")
            .order_by(AuditLog.timestamp.desc())
            .first()
        )
        assert log_entry is not None
        assert log_entry.actor_id == actor
        assert log_entry.entity_id == test_src_id
        assert reason in (log_entry.reason or "")


def test_merge_candidates_never_merge_silently() -> None:
    """Tests that entity resolution does not merge ambiguous mentions silently, but returns structured candidates."""
    resolver = EntityResolver()
    # Misspelled mention 'alce'
    candidates = resolver.suggest_merge_candidates("alce", top_k=3)
    assert len(candidates) > 0
    top = candidates[0]
    assert top["suggested_id"] == "P_ALICE"
    assert top["review_action"] == "requires_human_approval"


def test_idempotent_migration() -> None:
    """Tests that running the domain migration script multiple times produces identical, idempotent graph states."""
    from scripts.migrate_v02_domain import migrate_domain_v02

    # Measure graph node/edge counts before
    client = get_db_client()
    g = client.select_graph("northwind_labs")
    nodes_before = g.query("MATCH (n) RETURN count(n) AS cnt").result_set[0][0]
    edges_before = g.query("MATCH ()-[r]->() RETURN count(r) AS cnt").result_set[0][0]

    # Re-run migration
    migrate_domain_v02(graph_name="northwind_labs")

    nodes_after = g.query("MATCH (n) RETURN count(n) AS cnt").result_set[0][0]
    edges_after = g.query("MATCH ()-[r]->() RETURN count(r) AS cnt").result_set[0][0]

    assert nodes_after == nodes_before, (
        f"Node count changed: before={nodes_before}, after={nodes_after}"
    )
    assert edges_after == edges_before, (
        f"Edge count changed: before={edges_before}, after={edges_after}"
    )
