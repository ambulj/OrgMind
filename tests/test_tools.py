from orgmind.tools import (
    compare_draft_vs_decision,
    create_ticket,
    trace_decision,
    who_knows_about,
    who_owns,
)


def test_who_owns_existing_project():
    res = who_owns("OAuth")
    assert res["found"] is True
    assert (
        "Alice Chen" in res["results"][0]["owner_name"]
        or "Platform" in res["results"][0]["owner_name"]
    )


def test_who_owns_nonexistent_project():
    res = who_owns("NonExistentProject_XYZ")
    assert res["found"] is False


def test_who_knows_about_weighted_scoring():
    res = who_knows_about("Paynova")
    assert res["found"] is True
    assert len(res["ranked_experts"]) >= 2
    top = res["ranked_experts"][0]
    assert "Rohan" in top["person_name"]
    assert top["weighted_score"] >= 8.0
    assert len(top["sample_evidence"]) > 0


def test_trace_decision_with_source():
    res = trace_decision("OAuth")
    assert res["found"] is True
    assert len(res["decisions"]) > 0
    dec = res["decisions"][0]
    assert "DEC_AUTH" in dec["decision_id"]
    assert dec.get("source_id") is not None


def test_compare_draft_vs_decision():
    res = compare_draft_vs_decision("Paynova")
    assert res["found"] is True
    assert res["draft_proposal"] is not None
    assert res["ratified_decision"] is not None
    assert "Rohan" in res["draft_proposal"]["author_name"]
    assert "Priya" in res["ratified_decision"]["decider_name"]


def test_simulated_action_propose_mode():
    res = create_ticket(
        title="Test Security Vulnerability Audit",
        description="Run security scan on API",
        project_id="PRJ_OAUTH_UPGRADE",
        confirm=False,
    )
    assert res["status"] == "proposed_pending_confirmation"
    assert res["confirm_required"] is True
