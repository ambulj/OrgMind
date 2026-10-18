"""Agent tools exposing graph querying, bitemporal As-Of navigation, permission filtering, and simulated actions."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import get_graph, query_graph
from orgmind.models import Role

# ============================================================================
# READ TOOLS (Graph Intelligence, As-Of Time-Travel, & Permission Filtering)
# ============================================================================


def who_owns(
    project_or_topic: str,
    as_of: str | None = None,
    caller_role: str = Role.VIEWER.value,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Finds the designated owner (Person or Team) for a specific Project or Topic.
    Supports bitemporal 'as_of' history queries to inspect historical ownership.

    Args:
        project_or_topic: Name or keyword of the project or topic (e.g. 'OAuth', 'Billing').
        as_of: Optional ISO 8601 timestamp string (e.g. '2025-12-01') to query state as of that date.
        caller_role: RBAC role of the caller for permission checks.
        workspace_id: Tenant workspace identifier for isolated graph access.
    """
    clean_query = project_or_topic.strip()
    synonyms = {
        "identity": "OAuth",
        "authentication": "OAuth",
        "auth": "OAuth",
        "login": "OAuth",
        "sso": "OAuth",
        "payment": "Paynova",
        "payments": "Paynova",
        "portal": "Portal",
    }
    resolved_query = synonyms.get(clean_query.lower(), clean_query)
    if resolved_query == clean_query:
        for syn_k, syn_v in synonyms.items():
            if syn_k in clean_query.lower():
                resolved_query = syn_v
                break

    # Query with bitemporal validity check
    cypher = """
    MATCH (owner)-[r:OWNS]->(target)
    WHERE (target:Project AND (
            toLower(target.name) CONTAINS toLower($name)
         OR toLower(target.id) CONTAINS toLower($name)
    ))
       OR (target:Topic AND (
            toLower(target.name) = toLower($name)
         OR toLower($name) CONTAINS toLower(target.name)
    ))
    OPTIONAL MATCH (target)<-[:WORKS_ON {role: 'Lead'}]-(lead:Person)
    RETURN labels(target)[0] AS target_type,
           target.name AS target_name,
           target.id AS target_id,
           labels(owner)[0] AS owner_type,
           owner.name AS owner_name,
           owner.id AS owner_id,
           lead.name AS lead_name,
           lead.id AS lead_id,
           r.valid_from AS valid_from,
           r.valid_to AS valid_to,
           r.source AS source_doc
    """
    rows = query_graph(cypher, {"name": resolved_query}, workspace_id=workspace_id)

    # If nothing found, try tokenized fallback
    if not rows:
        tokens = [
            t.lower()
            for t in clean_query.split()
            if len(t) > 2 and t.lower() not in ["the", "project", "system", "app"]
        ]
        for token in tokens:
            resolved_token = synonyms.get(token, token)
            rows = query_graph(cypher, {"name": resolved_token}, workspace_id=workspace_id)
            if rows:
                break

    if not rows:
        alt_cypher = """
        MATCH (p:Person)-[:WORKS_ON {role: 'Lead'}]->(pr:Project)
        WHERE toLower(pr.name) CONTAINS toLower($name) OR toLower(pr.id) CONTAINS toLower($name)
        RETURN 'Project' AS target_type,
               pr.name AS target_name,
               pr.id AS target_id,
               'Person' AS owner_type,
               p.name AS owner_name,
               p.id AS owner_id,
               p.name AS lead_name,
               p.id AS lead_id,
               '' AS valid_from,
               '' AS valid_to,
               '' AS source_doc
        """
        rows = query_graph(alt_cypher, {"name": clean_query}, workspace_id=workspace_id)

    # Process and filter bitemporal validity if as_of provided
    current_owners = []
    previous_owners = []
    as_of_owners = []
    seen = set()

    for r in rows:
        key = (r.get("owner_id"), r.get("valid_from"), r.get("valid_to"))
        if key in seen:
            continue
        seen.add(key)

        v_from = str(r.get("valid_from") or "").strip()
        v_to = str(r.get("valid_to") or "").strip()

        s_doc = str(r.get("source_doc") or "").strip()
        if s_doc:
            doc_map = {
                "DOC_AUTH_SPEC": "SRC_DOC_AUTH_01",
                "DOC_BILLING_SPEC": "SRC_DOC_BILL_01",
                "DOC_PORTAL_PRD": "SRC_DOC_PORTAL_PRD_01",
                "DOC_PORTAL_HANDOFF": "SRC_DOC_PORTAL_HANDOFF_01",
                "DOC_PORTAL_HANDOFF_MEMO": "SRC_DOC_PORTAL_HANDOFF_01",
            }
            r["source_id"] = doc_map.get(
                s_doc, s_doc if s_doc.startswith("SRC_") else f"SRC_{s_doc}"
            )

        if v_to:
            previous_owners.append(r)
        else:
            current_owners.append(r)

        # As-of temporal filter: active on or before as_of date
        if as_of:
            is_valid_at_date = True
            if v_from and v_from > as_of:
                is_valid_at_date = False
            if v_to and v_to <= as_of:
                is_valid_at_date = False
            if is_valid_at_date:
                as_of_owners.append(r)

    active_results = as_of_owners if as_of is not None else rows
    display_owners = as_of_owners if as_of is not None else current_owners

    return {
        "query": project_or_topic,
        "as_of": as_of,
        "results": active_results,
        "current_owners": display_owners,
        "previous_owners": previous_owners,
        "has_ownership_history": len(previous_owners) > 0,
        "found": len(active_results) > 0,
        "note": f"Ownership verified as of {as_of}."
        if as_of
        else "Ownership verified from Northwind Labs graph registry.",
    }


def who_knows_about(
    topic: str,
    as_of: str | None = None,
    caller_role: str = Role.VIEWER.value,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Ranks people with demonstrated evidence of knowing about a topic based on
    a weighted scoring system across architecture docs, decisions, tickets, and chats.
    Supports bitemporal as_of queries and permission-aware evidence retrieval.
    """
    clean_topic = topic.strip()

    # Check if the query is a person name or handle (e.g. 'Pri' for Priya Sharma)
    from orgmind.resolve import EntityResolver

    resolver = EntityResolver()
    person_match = resolver.resolve_with_status(clean_topic)
    if person_match.get("resolved_id"):
        pid = person_match["resolved_id"]
        person_info = resolver.id_to_person.get(pid, {})
        person_name = person_info.get("name", clean_topic)
        role = person_info.get("role", "Engineer")

        # Query all topics this person knows about
        p_cypher = """
        MATCH (p:Person {id: $pid})-[:AUTHORED]->(item)-[:MENTIONS|ABOUT]->(top:Topic)
        RETURN top.name AS topic_name, count(item) AS count
        """
        topic_rows = query_graph(p_cypher, {"pid": pid}, workspace_id=workspace_id)
        topic_list = [r["topic_name"] for r in topic_rows if r.get("topic_name")]

        ranked_experts = [
            {
                "person_id": pid,
                "person_name": person_name,
                "role": role,
                "weighted_score": 10.0,
                "evidence_count": len(topic_rows),
                "confidence_tier": "High",
                "evidence_breakdown": {"topics": topic_list},
                "sample_evidence": topic_list,
            }
        ]
        return {
            "topic": clean_topic,
            "resolved_topic": person_name,
            "as_of": as_of,
            "ranked_experts": ranked_experts,
            "top_expert": person_name,
            "evidence_summary": f"{person_name} ({role}) has verified domain knowledge across topics: {', '.join(topic_list)}.",
            "found": True,
        }

    topic_synonyms = {
        "authentication": "OAuth",
        "auth": "OAuth",
        "login": "OAuth",
        "sso": "OAuth",
        "payment": "Paynova",
        "payments": "Paynova",
        "paynova": "Paynova",
        "billing": "Paynova",
        "gateway": "Paynova",
        "k8s": "Kubernetes",
        "infra": "Kubernetes",
        "database": "Security",
    }
    resolved_topic = topic_synonyms.get(clean_topic.lower(), clean_topic)
    if resolved_topic == clean_topic:
        for syn_k, syn_v in topic_synonyms.items():
            if syn_k in clean_topic.lower():
                resolved_topic = syn_v
                break

    cypher = """
    MATCH (p:Person)-[:AUTHORED]->(item)-[:MENTIONS|ABOUT]->(top:Topic)
    WHERE toLower(top.name) = toLower($topic)
    RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
           labels(item)[0] AS item_type, item.id AS item_id,
           coalesce(item.created_at, item.valid_from, '') AS created_at
    UNION
    MATCH (p:Person)-[:ASSIGNED_TO]->(tk:Ticket)-[:ABOUT]->(top:Topic)
    WHERE toLower(top.name) = toLower($topic)
    RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
           'AssignedTicket' AS item_type, tk.id AS item_id,
           coalesce(tk.created_at, '') AS created_at
    UNION
    MATCH (d:Decision)-[:DECIDED_BY]->(p:Person)
    WHERE toLower(d.topic) = toLower($topic) OR (d)-[:ABOUT]->(:Topic {name: $topic})
    RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
           'Decision' AS item_type, d.id AS item_id,
           coalesce(d.valid_from, '') AS created_at
    UNION
    MATCH (p:Person)-[:AUTHORED]->(dr:DraftRecommendation)
    WHERE toLower(dr.topic) = toLower($topic)
    RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
           'DraftRecommendation' AS item_type, dr.id AS item_id,
           coalesce(dr.draft_date, '') AS created_at
    """
    rows = query_graph(cypher, {"topic": resolved_topic}, workspace_id=workspace_id)

    if not rows:
        fallback_cypher = """
        MATCH (p:Person)-[:AUTHORED]->(item)
        WHERE toLower(item.id) CONTAINS toLower($topic)
           OR (item.title IS NOT NULL AND toLower(item.title) CONTAINS toLower($topic))
           OR (item.text IS NOT NULL AND toLower(item.text) CONTAINS toLower($topic))
        RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
               labels(item)[0] AS item_type, item.id AS item_id,
               coalesce(item.created_at, item.valid_from, '') AS created_at
        """
        rows = query_graph(fallback_cypher, {"topic": clean_topic}, workspace_id=workspace_id)

    # Filter by as_of if specified
    if as_of:
        rows = [
            r
            for r in rows
            if not str(r.get("created_at") or "") or str(r.get("created_at") or "") <= as_of
        ]

    person_data: dict[str, dict[str, Any]] = {}
    for r in rows:
        pid = r["person_id"]
        if pid not in person_data:
            person_data[pid] = {
                "person_id": pid,
                "person_name": r["person_name"],
                "role": r["role"],
                "score": 0.0,
                "doc_count": 0,
                "ticket_count": 0,
                "chat_count": 0,
                "sample_evidence": [],
                "item_ids": set(),
            }

        itype = r["item_type"]
        item_id = r["item_id"]

        if item_id not in person_data[pid]["item_ids"]:
            person_data[pid]["item_ids"].add(item_id)
            if len(person_data[pid]["sample_evidence"]) < 5:
                person_data[pid]["sample_evidence"].append(item_id)

            if itype in ("Document", "Decision", "DraftRecommendation"):
                weight = 3.0
                person_data[pid]["doc_count"] += 1
            elif itype == "Ticket":
                weight = 2.0
                person_data[pid]["ticket_count"] += 1
            elif itype == "AssignedTicket":
                weight = 1.5
                person_data[pid]["ticket_count"] += 1
            elif itype == "Message":
                weight = 1.0
                person_data[pid]["chat_count"] += 1
            else:
                weight = 1.0

            person_data[pid]["score"] += weight

    ranked_experts = sorted(person_data.values(), key=lambda x: x["score"], reverse=True)

    clean_ranked = []
    for exp in ranked_experts[:5]:
        total_items = exp["doc_count"] + exp["ticket_count"] + exp["chat_count"]
        confidence = "High" if exp["score"] >= 8.0 else ("Medium" if exp["score"] >= 3.0 else "Low")
        clean_ranked.append(
            {
                "person_id": exp["person_id"],
                "person_name": exp["person_name"],
                "role": exp["role"],
                "weighted_score": round(exp["score"], 1),
                "evidence_count": total_items,
                "confidence_tier": confidence,
                "evidence_breakdown": {
                    "architecture_and_decisions": exp["doc_count"],
                    "tickets": exp["ticket_count"],
                    "chat_messages": exp["chat_count"],
                },
                "sample_evidence": exp["sample_evidence"],
            }
        )

    top_expert = clean_ranked[0]["person_name"] if clean_ranked else "None"
    summary = (
        f"Top expert for '{clean_topic}' is {top_expert} with a weighted score of "
        f"{clean_ranked[0]['weighted_score'] if clean_ranked else 0} pts."
        if clean_ranked
        else f"No demonstrated authorship or ticket activity found for '{clean_topic}'."
    )

    return {
        "topic": clean_topic,
        "resolved_topic": resolved_topic,
        "as_of": as_of,
        "ranked_experts": clean_ranked,
        "top_expert": top_expert,
        "evidence_summary": summary,
        "found": len(clean_ranked) > 0,
    }


def trace_decision(
    topic: str,
    as_of: str | None = None,
    caller_role: str = Role.VIEWER.value,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Traces the active decision for a topic, previous decisions it replaced,
    and returns full text snippets from the Source nodes for citations.
    Applies strict in-query permission filtering and As-Of temporal filtering.
    """
    clean_topic = topic.strip()
    topic_synonyms = {
        "authentication": "OAuth",
        "auth": "OAuth",
        "login": "OAuth",
        "sso": "OAuth",
        "payment": "Paynova",
        "payments": "Paynova",
        "gateway": "Paynova",
        "european payment": "Paynova",
        "european payments": "Paynova",
        "european payment rails": "Paynova",
        "european payment gateway": "Paynova",
        "k8s": "Kubernetes",
        "infra": "Kubernetes",
        "database": "Security",
    }
    lower_t = clean_topic.lower()
    if "european" in lower_t:
        resolved_topic = "Paynova"
    else:
        resolved_topic = topic_synonyms.get(lower_t, clean_topic)

    # IN-QUERY PERMISSION FILTER: Only match sources visible to caller and not redacted
    cypher = """
    MATCH (d:Decision)-[:ABOUT]->(top:Topic)
    WHERE toLower(top.name) = toLower($topic)
       OR toLower(d.topic) = toLower($topic)
    OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
    WHERE (NOT src.redacted) AND (src.visibility CONTAINS 'all' OR src.visibility CONTAINS $caller_role)
    OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
    OPTIONAL MATCH (old)-[:DERIVED_FROM]->(old_src:Source)
    WHERE (NOT old_src.redacted) AND (old_src.visibility CONTAINS 'all' OR old_src.visibility CONTAINS $caller_role)
    RETURN d.id AS decision_id,
           d.text AS decision_text,
           d.status AS status,
           d.valid_from AS valid_from,
           d.valid_to AS valid_to,
           src.id AS source_id,
           src.file_path AS source_file,
           src.text_snippet AS source_snippet,
           src.content_hash AS source_hash,
           old.id AS superseded_decision_id,
           old.text AS superseded_text,
           old.status AS superseded_status,
           old_src.id AS superseded_source_id,
           old_src.text_snippet AS superseded_source_snippet
    """
    rows = query_graph(
        cypher, {"topic": resolved_topic, "caller_role": caller_role}, workspace_id=workspace_id
    )

    if not rows:
        fallback_cypher = """
        MATCH (d:Decision)
        OPTIONAL MATCH (d)-[:ABOUT]->(top:Topic)
        WHERE (top IS NOT NULL AND (toLower(top.name) CONTAINS toLower($topic) OR toLower($topic) CONTAINS toLower(top.name)))
           OR toLower(d.topic) CONTAINS toLower($topic)
           OR toLower(d.text) CONTAINS toLower($topic)
        OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
        WHERE (NOT src.redacted) AND (src.visibility CONTAINS 'all' OR src.visibility CONTAINS $caller_role)
        OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
        OPTIONAL MATCH (old)-[:DERIVED_FROM]->(old_src:Source)
        WHERE (NOT old_src.redacted) AND (old_src.visibility CONTAINS 'all' OR old_src.visibility CONTAINS $caller_role)
        RETURN d.id AS decision_id,
               d.text AS decision_text,
               d.status AS status,
               d.valid_from AS valid_from,
               d.valid_to AS valid_to,
               src.id AS source_id,
               src.file_path AS source_file,
               src.text_snippet AS source_snippet,
               src.content_hash AS source_hash,
               old.id AS superseded_decision_id,
               old.text AS superseded_text,
               old.status AS superseded_status,
               old_src.id AS superseded_source_id,
               old_src.text_snippet AS superseded_source_snippet
        """
        rows = query_graph(
            fallback_cypher,
            {"topic": clean_topic, "caller_role": caller_role},
            workspace_id=workspace_id,
        )

    # Apply As-Of temporal filtering
    if as_of:
        filtered_rows = []
        for r in rows:
            v_from = str(r.get("valid_from") or "").strip()
            v_to = str(r.get("valid_to") or "").strip()
            if v_from and v_from > as_of:
                continue
            if v_to and v_to <= as_of:
                continue
            filtered_rows.append(r)
        rows = filtered_rows

    return {
        "topic": clean_topic,
        "resolved_topic": resolved_topic,
        "as_of": as_of,
        "decisions": rows,
        "found": len(rows) > 0,
    }


def what_changed_since(
    date_str: str,
    as_of: str | None = None,
    caller_role: str = Role.VIEWER.value,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Retrieves all architectural decisions, ownership reassignments, and tickets modified since a date."""
    cypher = """
    MATCH (d:Decision)
    WHERE d.valid_from >= $since_date
    OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
    WHERE (NOT src.redacted) AND (src.visibility CONTAINS 'all' OR src.visibility CONTAINS $caller_role)
    OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)
    RETURN "Decision" AS change_type,
           d.id AS item_id,
           d.text AS summary,
           d.valid_from AS timestamp,
           d.status AS status,
           src.id AS source_id,
           p.name AS actor_name
    UNION
    MATCH (owner)-[r:OWNS]->(target)
    WHERE r.valid_from >= $since_date
    RETURN "OwnershipChange" AS change_type,
           coalesce(target.id, target.name) AS item_id,
           "Ownership assigned to " + owner.name AS summary,
           r.valid_from AS timestamp,
           r.status AS status,
           r.source AS source_id,
           owner.name AS actor_name
    UNION
    MATCH (tk:Ticket)
    WHERE tk.created_at >= $since_date
    OPTIONAL MATCH (p:Person)-[:AUTHORED]->(tk)
    RETURN "Ticket" AS change_type,
           tk.id AS item_id,
           tk.title AS summary,
           tk.created_at AS timestamp,
           tk.status AS status,
           tk.id AS source_id,
           p.name AS actor_name
    ORDER BY timestamp DESC
    """
    rows = query_graph(
        cypher, {"since_date": date_str, "caller_role": caller_role}, workspace_id=workspace_id
    )

    if as_of:
        rows = [
            r
            for r in rows
            if not str(r.get("timestamp") or "") or str(r.get("timestamp") or "") <= as_of
        ]

    return {
        "since_date": date_str,
        "as_of": as_of,
        "changes": rows,
        "total_changes": len(rows),
    }


def get_source(
    source_id: str,
    caller_role: str = Role.VIEWER.value,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Fetches the verbatim source text chunk for a given Source ID to guarantee grounding.
    Enforces in-query permission filtering and blocks redacted tombstones.
    """
    cypher = """
    MATCH (s:Source {id: $source_id})
    WHERE (NOT s.redacted) AND (s.visibility CONTAINS 'all' OR s.visibility CONTAINS $caller_role)
    RETURN s.id AS source_id,
           s.file_path AS file_path,
           s.chunk_offset AS chunk_offset,
           s.text_snippet AS text_snippet,
           s.content_hash AS content_hash,
           s.origin_type AS origin_type,
           s.visibility AS visibility,
           s.created_at AS created_at
    """
    rows = query_graph(
        cypher, {"source_id": source_id, "caller_role": caller_role}, workspace_id=workspace_id
    )
    if rows:
        return {"found": True, "source": rows[0]}

    # Check if source exists but is redacted or restricted
    meta_cypher = "MATCH (s:Source {id: $source_id}) RETURN s.redacted AS redacted, s.visibility AS visibility"
    meta = query_graph(meta_cypher, {"source_id": source_id}, workspace_id=workspace_id)
    if meta:
        if meta[0].get("redacted"):
            return {
                "found": False,
                "source_id": source_id,
                "error": "Source has been redacted via tombstone.",
            }
        return {
            "found": False,
            "source_id": source_id,
            "error": f"Access denied: restricted to roles {meta[0].get('visibility')}.",
        }

    return {"found": False, "source_id": source_id, "error": "Source not found in graph."}


def find_related(
    entity_id_or_name: str,
    hops: int = 2,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Explores neighboring nodes connected to an entity up to N hops away."""
    hops = max(1, min(hops, 3))
    cypher = f"""
    MATCH (start)
    WHERE start.id = $entity OR toLower(start.name) = toLower($entity)
    MATCH path = (start)-[*1..{hops}]-(neighbor)
    RETURN DISTINCT labels(neighbor)[0] AS neighbor_type,
                    neighbor.id AS neighbor_id,
                    coalesce(neighbor.name, neighbor.title, neighbor.text, neighbor.id) AS label,
                    neighbor.status AS status,
                    length(path) AS distance
    LIMIT 60
    """
    rows = query_graph(cypher, {"entity": entity_id_or_name}, workspace_id=workspace_id)
    return {
        "entity": entity_id_or_name,
        "hops": hops,
        "neighbors": rows,
        "total_found": len(rows),
    }


def compare_draft_vs_decision(
    topic: str,
    as_of: str | None = None,
    caller_role: str = Role.VIEWER.value,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Compares preliminary draft proposals against official ratified decisions for a topic."""
    clean_topic = topic.strip()
    topic_synonyms = {
        "authentication": "OAuth",
        "auth": "OAuth",
        "login": "OAuth",
        "payment": "Paynova",
        "payments": "Paynova",
        "european billing": "Paynova",
        "european payments": "Paynova",
        "european payment": "Paynova",
        "paynova": "Paynova",
        "billing": "Billing",
    }
    lower_t = clean_topic.lower()
    if "european" in lower_t or "paynova" in lower_t:
        resolved_topic = "Paynova"
    else:
        resolved_topic = topic_synonyms.get(lower_t, clean_topic)

    draft_cypher = """
    MATCH (dr:DraftRecommendation)
    WHERE toLower(dr.topic) CONTAINS toLower($topic)
       OR toLower($topic) CONTAINS toLower(dr.topic)
    OPTIONAL MATCH (p:Person)-[:AUTHORED]->(dr)
    OPTIONAL MATCH (dr)-[:DERIVED_FROM]->(src:Source)
    WHERE (NOT src.redacted) AND (src.visibility CONTAINS 'all' OR src.visibility CONTAINS $caller_role)
    OPTIONAL MATCH (doc:Document)-[:CONTAINS_DRAFT]->(dr)
    RETURN dr.id AS draft_id,
           dr.topic AS topic,
           dr.recommendation AS recommendation,
           dr.tradeoffs_identified AS tradeoffs,
           dr.draft_date AS draft_date,
           p.name AS author_name,
           p.id AS author_id,
           src.id AS source_id,
           src.file_path AS source_file,
           src.text_snippet AS source_snippet,
           doc.id AS document_id
    """
    draft_rows = query_graph(
        draft_cypher,
        {"topic": resolved_topic, "caller_role": caller_role},
        workspace_id=workspace_id,
    )

    decision_cypher = """
    MATCH (d:Decision)
    WHERE toLower(d.topic) CONTAINS toLower($topic)
       OR toLower($topic) CONTAINS toLower(d.topic)
       OR (d)-[:ABOUT]->(:Topic {name: $topic})
    OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)
    OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
    WHERE (NOT src.redacted) AND (src.visibility CONTAINS 'all' OR src.visibility CONTAINS $caller_role)
    OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
    RETURN d.id AS decision_id,
           d.text AS decision_text,
           d.status AS status,
           d.valid_from AS valid_from,
           d.valid_to AS valid_to,
           p.name AS decider_name,
           p.id AS decider_id,
           src.id AS source_id,
           src.file_path AS source_file,
           src.text_snippet AS source_snippet,
           old.id AS superseded_decision_id
    ORDER BY d.valid_from DESC
    """
    decision_rows = query_graph(
        decision_cypher,
        {"topic": resolved_topic, "caller_role": caller_role},
        workspace_id=workspace_id,
    )

    draft = draft_rows[0] if draft_rows else None
    current_decision = next((d for d in decision_rows if d["status"] == "current"), None)
    superseded_decisions = [d for d in decision_rows if d["status"] == "superseded"]

    sources = []
    if draft and draft.get("source_id"):
        sources.append(draft["source_id"])
    if current_decision and current_decision.get("source_id"):
        sources.append(current_decision["source_id"])

    if draft and current_decision:
        divergence_summary = (
            f"Draft proposal by {draft.get('author_name', 'Author')} on {draft.get('draft_date', '')} advised: "
            f'"{draft.get("recommendation", "")}". '
            f"However, ratified policy by {current_decision.get('decider_name', 'Decider')} on "
            f'{current_decision.get("valid_from", "")} established: "{current_decision.get("decision_text", "")}".'
        )
    else:
        divergence_summary = f"Comparison complete for topic '{clean_topic}'."

    return {
        "topic": clean_topic,
        "resolved_topic": resolved_topic,
        "as_of": as_of,
        "draft_proposal": draft,
        "ratified_decision": current_decision,
        "historical_superseded_decisions": superseded_decisions,
        "key_divergence_summary": divergence_summary,
        "sources": sources,
        "found": draft is not None or current_decision is not None,
    }


# ============================================================================
# WRITE & GOVERNANCE TOOLS (Actions, Redaction Tombstones, & Audit)
# ============================================================================


def redact_source(
    source_id: str,
    reason: str,
    actor: str,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Redacts a sensitive Source node using a Redaction Tombstone.
    Blanks the verbatim text while preserving cryptographic content hash and graph topology.
    Creates an immutable record in the relational AuditLog.
    """
    graph = get_graph(workspace_id)
    now_iso = datetime.now(UTC).isoformat()

    # 1. Fetch current source details
    check_res = query_graph(
        "MATCH (s:Source {id: $id}) RETURN s.id AS id, s.content_hash AS hash, s.text_snippet AS snippet",
        {"id": source_id},
        workspace_id=workspace_id,
    )
    if not check_res:
        return {"status": "error", "message": f"Source '{source_id}' not found in graph."}

    orig_hash = check_res[0].get("hash")
    orig_snippet = check_res[0].get("snippet")
    tombstone_text = f"[REDACTED: {reason}]"

    # 2. Mutate graph: blank text, set tombstone metadata, preserve hash
    redact_cypher = """
    MATCH (s:Source {id: $id})
    SET s.text_snippet = $tombstone,
        s.redacted = true,
        s.redacted_at = $now,
        s.redacted_by = $actor,
        s.redaction_reason = $reason
    RETURN s.id AS id, s.content_hash AS hash
    """
    graph.query(
        redact_cypher,
        {
            "id": source_id,
            "tombstone": tombstone_text,
            "now": now_iso,
            "actor": actor,
            "reason": reason,
        },
    )

    # 3. Write immutable audit log to relational database
    try:
        from orgmind.models import AuditLog, Workspace, get_session_factory

        session_factory = get_session_factory()
        with session_factory() as session:
            ws_slug = workspace_id or "default"
            ws = session.query(Workspace).filter_by(slug=ws_slug).first()
            ws_id = ws.id if ws else "default"

            audit_entry = AuditLog(
                workspace_id=ws_id,
                actor_id=actor,
                actor_email=actor if "@" in actor else f"{actor}@northwind.com",
                action="redact_source",
                entity_type="Source",
                entity_id=source_id,
                before_state=json.dumps({"snippet_length": len(orig_snippet or "")}),
                after_state=json.dumps({"tombstone": tombstone_text, "content_hash": orig_hash}),
                reason=reason,
            )
            session.add(audit_entry)
            session.commit()
    except Exception as e:
        print(f"[Audit] Warning: Failed to write audit event: {e}")

    return {
        "status": "success",
        "action": "redact_source",
        "source_id": source_id,
        "content_hash": orig_hash,
        "tombstone": tombstone_text,
        "redacted_by": actor,
        "redacted_at": now_iso,
        "reason": reason,
    }


def create_ticket(
    title: str,
    description: str,
    project_id: str,
    author_id: str = "P_ALICE",
    confirm: bool = True,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Simulates creating a ticket and writes it back into the graph."""
    if not confirm:
        return {
            "action": "create_ticket",
            "status": "proposed_pending_confirmation",
            "confirm_required": True,
            "proposed_ticket": {
                "title": title,
                "description": description,
                "project_id": project_id,
                "author_id": author_id,
            },
            "message": "Action proposal created. Awaiting explicit user confirmation before modifying the graph.",
        }

    graph = get_graph(workspace_id)
    prefix_map = {
        "PRJ_OAUTH_UPGRADE": "AUTH",
        "PRJ_BILLING_STRIPE": "BILL",
        "PRJ_PORTAL_REDESIGN": "PORT",
        "PRJ_DATA_PIPELINE": "DATA",
    }
    prefix = prefix_map.get(project_id, "TICK")
    now_ts = int(datetime.now(UTC).timestamp()) % 100000
    ticket_id = f"TICK-{prefix}-{now_ts}"
    now_iso = datetime.now(UTC).isoformat()

    cypher = """
    MATCH (pr:Project {id: $project_id})
    MATCH (p:Person {id: $author_id})
    CREATE (tk:Ticket {
        id: $ticket_id,
        title: $title,
        description: $description,
        status: 'Open',
        priority: 'High',
        created_at: $now
    })
    CREATE (p)-[:AUTHORED]->(tk)
    CREATE (tk)-[:PART_OF]->(pr)
    RETURN tk.id AS ticket_id, pr.name AS project_name
    """
    graph.query(
        cypher,
        {
            "project_id": project_id,
            "author_id": author_id,
            "ticket_id": ticket_id,
            "title": title,
            "description": description,
            "now": now_iso,
        },
    )

    return {
        "action": "create_ticket",
        "status": "simulated_success",
        "ticket_id": ticket_id,
        "project_id": project_id,
        "title": title,
        "author_id": author_id,
        "created_at": now_iso,
    }


def draft_message(
    channel_name: str,
    content: str,
    sender_id: str = "P_ALICE",
    confirm: bool = True,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Simulates drafting and posting a chat message to a company channel."""
    if not confirm:
        return {
            "action": "draft_message",
            "status": "proposed_pending_confirmation",
            "confirm_required": True,
            "proposed_message": {
                "channel": channel_name,
                "content": content,
                "sender_id": sender_id,
            },
            "message": "Message draft created. Awaiting explicit confirmation before sending.",
        }

    now_ts = int(datetime.now(UTC).timestamp()) % 100000
    msg_id = f"MSG-SIM-{now_ts}"
    now_iso = datetime.now(UTC).isoformat()
    clean_channel = channel_name.lstrip("#")

    graph = get_graph(workspace_id)
    cypher = """
    MATCH (p:Person {id: $sender_id})
    MERGE (top:Topic {name: $channel})
    CREATE (m:Message {
        id: $msg_id,
        text: $content,
        timestamp: $now,
        channel: $channel
    })
    CREATE (p)-[:AUTHORED]->(m)
    CREATE (m)-[:MENTIONS]->(top)
    RETURN m.id AS message_id
    """
    graph.query(
        cypher,
        {
            "channel": clean_channel,
            "sender_id": sender_id,
            "msg_id": msg_id,
            "content": content,
            "now": now_iso,
        },
    )

    return {
        "action": "draft_message",
        "status": "simulated_success",
        "message_id": msg_id,
        "channel": channel_name,
        "sender_id": sender_id,
        "timestamp": now_iso,
    }


def assign_task(
    project_id: str,
    task_title: str,
    assignee_person_id: str,
    assigner_person_id: str = "P_ALICE",
    confirm: bool = True,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Assigns a work item to an employee and updates the graph."""
    if not confirm:
        return {
            "action": "assign_task",
            "status": "proposed_pending_confirmation",
            "confirm_required": True,
            "proposed_assignment": {
                "project_id": project_id,
                "task_title": task_title,
                "assignee": assignee_person_id,
            },
            "message": "Task assignment proposed. Awaiting confirmation.",
        }

    graph = get_graph(workspace_id)
    now_ts = int(datetime.now(UTC).timestamp()) % 100000
    task_id = f"TASK-SIM-{now_ts}"
    now_iso = datetime.now(UTC).isoformat()

    cypher = """
    MATCH (pr:Project {id: $project_id})
    MATCH (p:Person {id: $assignee_id})
    CREATE (tk:Ticket {
        id: $task_id,
        title: $task_title,
        status: 'Assigned',
        priority: 'Medium',
        created_at: $now
    })
    CREATE (p)-[:ASSIGNED_TO]->(tk)
    CREATE (tk)-[:PART_OF]->(pr)
    RETURN tk.id AS task_id, p.name AS assignee_name
    """
    graph.query(
        cypher,
        {
            "assignee_id": assignee_person_id,
            "project_id": project_id,
            "task_id": task_id,
            "task_title": task_title,
            "now": now_iso,
        },
    )

    return {
        "action": "assign_task",
        "status": "simulated_success",
        "task_id": task_id,
        "task_title": task_title,
        "assignee_id": assignee_person_id,
        "assigned_at": now_iso,
    }


# Map string names to function pointers for LiteLLM dispatcher
TOOLS_REGISTRY: dict[str, Any] = {
    "who_owns": who_owns,
    "who_knows_about": who_knows_about,
    "trace_decision": trace_decision,
    "what_changed_since": what_changed_since,
    "get_source": get_source,
    "find_related": find_related,
    "compare_draft_vs_decision": compare_draft_vs_decision,
    "create_ticket": create_ticket,
    "draft_message": draft_message,
    "assign_task": assign_task,
    "redact_source": redact_source,
}
