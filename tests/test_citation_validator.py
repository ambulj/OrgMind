from orgmind.agent import OrgMindAgent


def test_citation_validator_blocks_hallucinated_source():
    agent = OrgMindAgent()
    # Inject a response text with a fake source tag starting with SRC_
    fake_answer = "Northwind Labs migrates to DynamoDB [Source: SRC_FAKE_ID_99999]."
    tool_results = [{"tool": "who_owns", "result": {"found": True}}]
    processed = agent._post_process_answer(fake_answer, [], tool_results)
    sanitized = processed["answer"]

    # The fabricated source must be stripped or flagged
    assert "SRC_FAKE_ID_99999" not in sanitized


def test_citation_validator_preserves_valid_graph_source():
    agent = OrgMindAgent()
    # Use a source that really exists in FalkorDB (SRC_DOC_PKCE_01)
    valid_answer = (
        "Authentication requires PKCE with S256 code challenge [Source: SRC_DOC_PKCE_01]."
    )
    sources_collected = [
        {"source_id": "SRC_DOC_PKCE_01", "file_path": "data/docs/oauth_pkce_spec.md"}
    ]
    tool_results = [
        {
            "tool": "trace_decision",
            "result": {"found": True, "decisions": [{"id": "DEC_AUTH_2026_02"}]},
        }
    ]
    processed = agent._post_process_answer(valid_answer, sources_collected, tool_results)
    sanitized = processed["answer"]

    # Valid graph source must be preserved
    assert "SRC_DOC_PKCE_01" in sanitized
