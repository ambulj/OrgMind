import pytest
from orgmind.resolve import EntityResolver


@pytest.fixture
def resolver():
    return EntityResolver()


def test_resolve_exact_match(resolver):
    # Test canonical exact match
    res = resolver.resolve_with_status("Alice Chen")
    assert res["status"] == "exact"
    assert res["resolved_id"] == "P_ALICE"
    assert res["confidence"] == 1.0


def test_resolve_alias_handle(resolver):
    # Test nickname / handle resolution
    res = resolver.resolve_with_status("Pri")
    assert res["status"] == "exact"
    assert res["resolved_id"] == "P_PRIYA"

    res_ro = resolver.resolve_with_status("Ro")
    assert res_ro["status"] == "exact"
    assert res_ro["resolved_id"] == "P_ROHAN"


def test_resolve_fuzzy_typo(resolver):
    # Test fuzzy typo match (e.g. Ailce Chen)
    res = resolver.resolve_with_status("Ailce Chen")
    assert res["status"] == "fuzzy"
    assert res["resolved_id"] == "P_ALICE"
    assert res["confidence"] >= 0.85


def test_unknown_handle_flagged(resolver):
    # Test unknown handle is quarantined and not silently mapped
    res = resolver.resolve_with_status("phantom_user_999")
    assert res["status"] == "unknown"
    assert res["resolved_id"] is None
    assert len(resolver.get_flagged_unknowns()) > 0
