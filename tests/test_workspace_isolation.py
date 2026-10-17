from orgmind.db import get_db_client, get_graph, get_workspace_graph_name, query_graph


def test_workspace_graph_name_mapping():
    # Default workspaces
    assert get_workspace_graph_name(None) == "northwind_labs"
    assert get_workspace_graph_name("") == "northwind_labs"
    assert get_workspace_graph_name("default") == "northwind_labs"

    # Multi-tenant custom workspaces
    assert get_workspace_graph_name("acme") == "org_acme"
    assert get_workspace_graph_name("team-alpha") == "org_team_alpha"
    assert get_workspace_graph_name("org_finance") == "org_finance"
    # Malicious injection characters are stripped
    assert get_workspace_graph_name("evil; DROP GRAPH *") == "org_evil_drop_graph"


def test_cross_workspace_isolation_guaranteed():
    client = get_db_client()
    ws_a = "tenant_alpha"
    ws_b = "tenant_beta"

    graph_name_a = get_workspace_graph_name(ws_a)
    graph_name_b = get_workspace_graph_name(ws_b)

    # Clean up any leftover test graphs
    for g_name in (graph_name_a, graph_name_b):
        try:
            client.select_graph(g_name).delete()
        except Exception:
            pass

    graph_a = get_graph(ws_a)
    graph_b = get_graph(ws_b)

    try:
        # 1. Create a secret proprietary entity strictly in Workspace A
        graph_a.query(
            "CREATE (p:Person {id: 'P_SECRET_ALPHA', name: 'Alpha Agent', salary: 250000})"
        )

        # Verify it exists in Workspace A
        res_a = query_graph(
            "MATCH (p:Person {id: 'P_SECRET_ALPHA'}) RETURN p.name AS name", workspace_id=ws_a
        )
        assert len(res_a) == 1
        assert res_a[0]["name"] == "Alpha Agent"

        # 2. Query Workspace B: it MUST NOT find the entity from Workspace A
        res_b = query_graph(
            "MATCH (p:Person {id: 'P_SECRET_ALPHA'}) RETURN p.name AS name", workspace_id=ws_b
        )
        assert len(res_b) == 0, "Isolation failure! Workspace B accessed data from Workspace A."

        # 3. Create an entity with the same ID in Workspace B, but different attributes
        graph_b.query(
            "CREATE (p:Person {id: 'P_SECRET_ALPHA', name: 'Beta Impostor', salary: 10000})"
        )

        res_a_again = query_graph(
            "MATCH (p:Person {id: 'P_SECRET_ALPHA'}) RETURN p.salary AS salary", workspace_id=ws_a
        )
        res_b_again = query_graph(
            "MATCH (p:Person {id: 'P_SECRET_ALPHA'}) RETURN p.salary AS salary", workspace_id=ws_b
        )

        assert res_a_again[0]["salary"] == 250000
        assert res_b_again[0]["salary"] == 10000

    finally:
        # Clean up test graphs
        for g_name in (graph_name_a, graph_name_b):
            try:
                client.select_graph(g_name).delete()
            except Exception:
                pass
