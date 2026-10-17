from orgmind.db import get_db_client, query_graph

from scripts.backup_restore import dump_graph, restore_graph


def test_backup_and_restore_cycle():
    client = get_db_client()
    source_name = "northwind_labs"
    scratch_name = "org_scratch_restore_test"

    # Clean up any leftover scratch graph
    try:
        client.select_graph(scratch_name).delete()
    except Exception:
        pass

    # 1. Capture snapshot of source graph
    source_nodes = query_graph("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
    source_edges = query_graph("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]

    assert source_nodes > 0, "Source graph should have nodes before backup"

    # 2. Dump graph to memory payload
    dump_data = dump_graph(source_name)
    assert dump_data["node_count"] == source_nodes
    assert dump_data["edge_count"] == source_edges

    # 3. Restore into isolated scratch graph
    restore_res = restore_graph(dump_data, scratch_name)
    assert restore_res["status"] == "success"
    assert restore_res["restored_nodes"] == source_nodes
    assert restore_res["restored_edges"] == source_edges

    # 4. Query scratch graph to verify entity queryability
    oauth_res = query_graph(
        "MATCH (d:Decision {id: 'DEC_AUTH_2026_02'}) RETURN d.status AS status",
        workspace_id=scratch_name,
    )
    assert len(oauth_res) == 1
    assert oauth_res[0]["status"] == "current"

    # 5. Clean up scratch graph
    client.select_graph(scratch_name).delete()
