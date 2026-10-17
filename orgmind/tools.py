"""Agent tools exposing graph querying and simulated actions.

Technical Terms:
- Tool Calling: An LLM feature where the model produces structured arguments to invoke
  a Python function, inspects the result, and uses it to formulate its response.
- Grounding: Forcing the agent to base answers strictly on retrieved data rather than its internal memory.
- Provenance Retrieval: Fetching the exact text chunk (`Source`) that substantiates a fact.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import json

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import query_graph, get_graph


# ============================================================================
# READ TOOLS (Graph Intelligence & Provenance)
# ============================================================================

def who_owns(project_or_topic: str) -> Dict[str, Any]:
    """Finds the designated owner (Person or Team) for a specific Project or Topic.

    Args:
        project_or_topic: Name or keyword of the project or topic (e.g. 'OAuth', 'Billing').

    Returns:
        Dictionary containing owner information and target details.
    """
    clean_query = project_or_topic.strip()
    # Try exact / substring match first
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
    rows = query_graph(cypher, {"name": clean_query})

    # If nothing found, try individual words (e.g. "OAuth" from "OAuth Upgrade")
    if not rows:
        tokens = [t.lower() for t in clean_query.split() if len(t) > 2 and t.lower() not in ["the", "project", "system", "app"]]
        for token in tokens:
            rows = query_graph(cypher, {"name": token})
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
        rows = query_graph(alt_cypher, {"name": clean_query})

    # Deduplicate and organize current vs previous owners
    current_owners = []
    previous_owners = []
    seen = set()

    for r in rows:
        key = (r.get("owner_id"), r.get("valid_from"), r.get("valid_to"))
        if key in seen:
            continue
        seen.add(key)
        valid_to = r.get("valid_to")
        if valid_to and str(valid_to).strip():
            previous_owners.append(r)
        else:
            current_owners.append(r)

    return {
        "query": project_or_topic,
        "results": rows,
        "current_owners": current_owners,
        "previous_owners": previous_owners,
        "has_ownership_history": len(previous_owners) > 0,
        "found": len(rows) > 0,
        "note": "Ownership verified from Northwind Labs graph registry." if rows else "No owner record found."
    }


def who_knows_about(topic: str) -> Dict[str, Any]:
    """Ranks people with demonstrated evidence of knowing about a topic based on
    a weighted scoring system across architecture docs, decisions, tickets, and chats.

    Weights:
    - Architecture Docs / Decisions / Drafts: 3.0 points
    - Authored Tickets: 2.0 points
    - Assigned Tickets: 1.5 points
    - Chat Channel Messages: 1.0 point

    Args:
        topic: The topic keyword (e.g. 'OAuth', 'Kubernetes', 'Billing', 'Paynova').

    Returns:
        Ranked list of people with weighted scores, breakdown, and sample evidence item IDs.
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
        "k8s": "Kubernetes",
        "infra": "Kubernetes",
        "database": "Security",
    }
    resolved_topic = topic_synonyms.get(clean_topic.lower(), clean_topic)

    cypher = """
    MATCH (p:Person)-[:AUTHORED]->(item)-[:MENTIONS|ABOUT]->(top:Topic)
    WHERE toLower(top.name) = toLower($topic)
    RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
           labels(item)[0] AS item_type, item.id AS item_id
    UNION
    MATCH (p:Person)-[:ASSIGNED_TO]->(tk:Ticket)-[:ABOUT]->(top:Topic)
    WHERE toLower(top.name) = toLower($topic)
    RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
           'AssignedTicket' AS item_type, tk.id AS item_id
    UNION
    MATCH (d:Decision)-[:DECIDED_BY]->(p:Person)
    WHERE toLower(d.topic) = toLower($topic) OR (d)-[:ABOUT]->(:Topic {name: $topic})
    RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
           'Decision' AS item_type, d.id AS item_id
    UNION
    MATCH (p:Person)-[:AUTHORED]->(dr:DraftRecommendation)
    WHERE toLower(dr.topic) = toLower($topic)
    RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
           'DraftRecommendation' AS item_type, dr.id AS item_id
    """
    rows = query_graph(cypher, {"topic": resolved_topic})

    if not rows:
        # Fallback substring search
        fallback_cypher = """
        MATCH (p:Person)-[:AUTHORED]->(item)
        WHERE toLower(item.id) CONTAINS toLower($topic)
           OR (item.title IS NOT NULL AND toLower(item.title) CONTAINS toLower($topic))
           OR (item.text IS NOT NULL AND toLower(item.text) CONTAINS toLower($topic))
        RETURN p.id AS person_id, p.name AS person_name, p.role AS role,
               labels(item)[0] AS item_type, item.id AS item_id
        """
        rows = query_graph(fallback_cypher, {"topic": clean_topic})

    # Group and calculate weighted scores
    person_data: Dict[str, Dict[str, Any]] = {}
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

    # Format structured expert profiles
    clean_ranked = []
    for exp in ranked_experts[:5]:
        total_items = exp["doc_count"] + exp["ticket_count"] + exp["chat_count"]
        confidence = "High" if exp["score"] >= 8.0 else ("Medium" if exp["score"] >= 3.0 else "Low")
        clean_ranked.append({
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
        })

    top_expert = clean_ranked[0]["person_name"] if clean_ranked else "None"
    summary = (
        f"Top expert for '{clean_topic}' is {top_expert} with a weighted evidence score of "
        f"{clean_ranked[0]['weighted_score'] if clean_ranked else 0} pts."
        if clean_ranked else f"No demonstrated authorship or ticket activity found for '{clean_topic}'."
    )

    return {
        "topic": clean_topic,
        "resolved_topic": resolved_topic,
        "ranked_experts": clean_ranked,
        "top_expert": top_expert,
        "evidence_summary": summary,
        "found": len(clean_ranked) > 0,
    }


def trace_decision(topic: str) -> Dict[str, Any]:
    """Traces the active decision for a topic, previous decisions it replaced,
    and returns full text snippets from the Source nodes for citations.

    Args:
        topic: Topic of the decision (e.g. 'OAuth', 'Billing', 'Authentication').

    Returns:
        Structured trace of current decision, superseded decisions, and source IDs.
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
        "k8s": "Kubernetes",
        "infra": "Kubernetes",
        "database": "Security",
    }
    resolved_topic = topic_synonyms.get(clean_topic.lower(), clean_topic)

    cypher = """
    MATCH (d:Decision)-[:ABOUT]->(top:Topic)
    WHERE toLower(top.name) = toLower($topic)
       OR toLower(d.topic) = toLower($topic)
    OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
    OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
    OPTIONAL MATCH (old)-[:DERIVED_FROM]->(old_src:Source)
    RETURN d.id AS decision_id,
           d.text AS decision_text,
           d.status AS status,
           d.valid_from AS valid_from,
           d.valid_to AS valid_to,
           src.id AS source_id,
           src.file_path AS source_file,
           src.text_snippet AS source_snippet,
           old.id AS superseded_decision_id,
           old.text AS superseded_text,
           old.status AS superseded_status,
           old_src.id AS superseded_source_id,
           old_src.text_snippet AS superseded_source_snippet
    """
    rows = query_graph(cypher, {"topic": resolved_topic})

    # Fallback: substring matching across topics or decision text
    if not rows:
        fallback_cypher = """
        MATCH (d:Decision)
        OPTIONAL MATCH (d)-[:ABOUT]->(top:Topic)
        WHERE (top IS NOT NULL AND (toLower(top.name) CONTAINS toLower($topic) OR toLower($topic) CONTAINS toLower(top.name)))
           OR toLower(d.topic) CONTAINS toLower($topic)
           OR toLower(d.text) CONTAINS toLower($topic)
        OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
        OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
        OPTIONAL MATCH (old)-[:DERIVED_FROM]->(old_src:Source)
        RETURN d.id AS decision_id,
               d.text AS decision_text,
               d.status AS status,
               d.valid_from AS valid_from,
               d.valid_to AS valid_to,
               src.id AS source_id,
               src.file_path AS source_file,
               src.text_snippet AS source_snippet,
               old.id AS superseded_decision_id,
               old.text AS superseded_text,
               old.status AS superseded_status,
               old_src.id AS superseded_source_id,
               old_src.text_snippet AS superseded_source_snippet
        """
        rows = query_graph(fallback_cypher, {"topic": clean_topic})

    return {
        "topic": topic,
        "resolved_topic": resolved_topic,
        "decisions": rows,
        "found": len(rows) > 0
    }


def what_changed_since(date_str: str) -> Dict[str, Any]:
    """Finds all decisions and tickets created or modified after a given date.

    Args:
        date_str: ISO date string (format 'YYYY-MM-DD').

    Returns:
        List of changed decisions and tickets with timestamps and actor info.
    """
    cypher = """
    MATCH (d:Decision)
    WHERE d.valid_from >= $since_date
    OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
    OPTIONAL MATCH (d)-[:DECIDED_BY]->(actor)
    RETURN "Decision" AS change_type,
           d.id AS item_id,
           d.text AS summary,
           d.valid_from AS timestamp,
           d.status AS status,
           src.id AS source_id,
           actor.name AS actor_name
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
    rows = query_graph(cypher, {"since_date": date_str})
    return {
        "since_date": date_str,
        "changes": rows,
        "total_changes": len(rows)
    }


def get_source(source_id: str) -> Dict[str, Any]:
    """Fetches the verbatim source text chunk for a given Source ID to guarantee grounding.

    Args:
        source_id: Unique identifier of the source (e.g. 'SRC_DOC_AUTH_01').
    """
    cypher = """
    MATCH (s:Source {id: $source_id})
    RETURN s.id AS source_id,
           s.file_path AS file_path,
           s.chunk_offset AS chunk_offset,
           s.text_snippet AS text_snippet,
           s.created_at AS created_at
    """
    rows = query_graph(cypher, {"source_id": source_id})
    if rows:
        return {"found": True, "source": rows[0]}
    return {"found": False, "source_id": source_id, "error": "Source not found in graph."}


def find_related(entity_id_or_name: str, hops: int = 2) -> Dict[str, Any]:
    """Explores neighboring nodes connected to an entity up to N hops away."""
    hops = max(1, min(hops, 3))  # Clamp between 1 and 3 hops for performance
    cypher = f"""
    MATCH (start)
    WHERE start.id = $entity OR toLower(start.name) = toLower($entity)
    MATCH path = (start)-[*1..{hops}]-(neighbor)
    RETURN DISTINCT labels(neighbor)[0] AS neighbor_type,
                    neighbor.id AS neighbor_id,
                    coalesce(neighbor.name, neighbor.title, neighbor.text, neighbor.id) AS label,
                    length(path) AS distance
    LIMIT 25
    """
    rows = query_graph(cypher, {"entity": entity_id_or_name})
    return {
        "entity": entity_id_or_name,
        "hops": hops,
        "neighbors": rows
    }


def compare_draft_vs_decision(topic: str) -> Dict[str, Any]:
    """Compares preliminary draft proposals against official ratified decisions for a topic.
    Identifies who authored each, what warnings or trade-offs were raised, and how decisions evolved.

    Args:
        topic: Topic or technology area (e.g. 'Paynova', 'Billing', 'OAuth').

    Returns:
        Structured comparison between draft proposal and ratified policy with source citations.
    """
    clean_topic = topic.strip()
    topic_synonyms = {
        "authentication": "OAuth",
        "auth": "OAuth",
        "login": "OAuth",
        "payment": "Paynova",
        "payments": "Paynova",
        "billing": "Billing",
    }
    resolved_topic = topic_synonyms.get(clean_topic.lower(), clean_topic)

    # 1. Query Draft Recommendations
    draft_cypher = """
    MATCH (dr:DraftRecommendation)
    WHERE toLower(dr.topic) CONTAINS toLower($topic)
       OR toLower($topic) CONTAINS toLower(dr.topic)
    OPTIONAL MATCH (p:Person)-[:AUTHORED]->(dr)
    OPTIONAL MATCH (dr)-[:DERIVED_FROM]->(src:Source)
    OPTIONAL MATCH (doc:Document)-[:CONTAINS_DRAFT]->(dr)
    RETURN dr.id AS draft_id,
           dr.topic AS topic,
           dr.recommendation AS recommendation,
           dr.date AS draft_date,
           p.name AS author_name,
           p.id AS author_id,
           src.id AS source_id,
           src.file_path AS source_file,
           src.text_snippet AS source_snippet,
           doc.id AS document_id
    """
    draft_rows = query_graph(draft_cypher, {"topic": resolved_topic})

    # 2. Query Ratified Decisions
    decision_cypher = """
    MATCH (d:Decision)
    WHERE toLower(d.topic) CONTAINS toLower($topic)
       OR toLower($topic) CONTAINS toLower(d.topic)
       OR (d)-[:ABOUT]->(:Topic {name: $topic})
    OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)
    OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
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
    decision_rows = query_graph(decision_cypher, {"topic": resolved_topic})

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
            f"\"{draft.get('recommendation', '')}\". "
            f"However, ratified policy by {current_decision.get('decider_name', 'Decider')} on "
            f"{current_decision.get('valid_from', '')} established: \"{current_decision.get('decision_text', '')}\"."
        )
        if superseded_decisions:
            divergence_summary += (
                f" Note: Decision was subsequently superseded by {len(superseded_decisions)} historical update(s)."
            )
    elif draft and not current_decision:
        divergence_summary = f"Draft recommendation exists by {draft.get('author_name')} but no ratified decision was recorded."
    elif current_decision and not draft:
        divergence_summary = f"Official decision recorded by {current_decision.get('decider_name')}, but no conflicting draft proposal was found in the graph."
    else:
        divergence_summary = f"No draft recommendations or decisions found for topic '{clean_topic}'."

    return {
        "topic": clean_topic,
        "resolved_topic": resolved_topic,
        "draft_proposal": draft,
        "ratified_decision": current_decision,
        "historical_superseded_decisions": superseded_decisions,
        "key_divergence_summary": divergence_summary,
        "sources": sources,
        "found": draft is not None or current_decision is not None,
    }


# ============================================================================
# WRITE / ACTION TOOLS (Simulated Actions Written Back to Graph)
# ============================================================================

def create_ticket(
    title: str,
    description: str,
    project_id: str,
    author_id: str = "P_ALICE",
    confirm: bool = True
) -> Dict[str, Any]:
    """Simulates creating a ticket and writes it back into the graph.

    Args:
        title: Title of the ticket
        description: Detailed description
        project_id: Target project ID (e.g. 'PRJ_OAUTH_UPGRADE')
        author_id: Creator Person ID
        confirm: If False, returns proposed preview without modifying database.
    """
    if not confirm:
        return {
            "action": "create_ticket",
            "status": "proposed_pending_confirmation",
            "confirm_required": True,
            "preview": {
                "title": title,
                "description": description,
                "project_id": project_id,
                "author_id": author_id,
            },
            "prompt": f"Proposed Ticket: '{title}' for project '{project_id}'. Pass confirm=True to write to graph."
        }

    graph = get_graph()
    now_iso = datetime.now(timezone.utc).isoformat()
    ticket_id = f"TICK-SIM-{int(datetime.now().timestamp()) % 10000}"

    cypher = """
    MERGE (tk:Ticket {id: $id})
    SET tk.title = $title,
        tk.description = $description,
        tk.status = 'simulated_created',
        tk.created_at = $created_at
    WITH tk
    MATCH (pr:Project {id: $project_id})
    MERGE (tk)-[:PART_OF]->(pr)
    WITH tk
    MATCH (p:Person {id: $author_id})
    MERGE (p)-[:AUTHORED {timestamp: $created_at}]->(tk)
    RETURN tk.id AS ticket_id
    """
    graph.query(cypher, {
        "id": ticket_id,
        "title": title,
        "description": description,
        "created_at": now_iso,
        "project_id": project_id,
        "author_id": author_id,
    })

    return {
        "action": "create_ticket",
        "status": "simulated_success",
        "ticket_id": ticket_id,
        "title": title,
        "project_id": project_id,
        "timestamp": now_iso,
        "note": "Ticket node written to FalkorDB graph with status 'simulated_created'."
    }


def draft_message(
    channel: str,
    text: str,
    author_id: str = "P_ALICE",
    confirm: bool = True
) -> Dict[str, Any]:
    """Simulates drafting a message to a team channel and writes it to the graph.

    Args:
        channel: Channel name, e.g. '#backend-eng'
        text: Message body text
        author_id: Author Person ID
        confirm: If False, returns proposed preview without modifying database.
    """
    if not confirm:
        return {
            "action": "draft_message",
            "status": "proposed_pending_confirmation",
            "confirm_required": True,
            "preview": {
                "channel": channel,
                "text": text,
                "author_id": author_id,
            },
            "prompt": f"Proposed Message to {channel}: '{text[:60]}...'. Pass confirm=True to write to graph."
        }

    graph = get_graph()
    now_iso = datetime.now(timezone.utc).isoformat()
    msg_id = f"MSG-SIM-{int(datetime.now().timestamp()) % 10000}"

    cypher = """
    CREATE (m:Message {
        id: $id,
        channel: $channel,
        text: $text,
        timestamp: $timestamp,
        status: 'simulated_draft'
    })
    WITH m
    MATCH (p:Person {id: $author_id})
    MERGE (p)-[:AUTHORED {timestamp: $timestamp}]->(m)
    RETURN m.id AS msg_id
    """
    graph.query(cypher, {
        "id": msg_id,
        "channel": channel,
        "text": text,
        "timestamp": now_iso,
        "author_id": author_id,
    })

    return {
        "action": "draft_message",
        "status": "simulated_success",
        "message_id": msg_id,
        "channel": channel,
        "text": text,
        "timestamp": now_iso,
        "note": "Draft message recorded in graph with status 'simulated_draft'."
    }


def assign_task(
    task_title: str,
    assignee_person_id: str,
    project_id: str,
    confirm: bool = True
) -> Dict[str, Any]:
    """Simulates assigning a task to a person for a project and updates graph relationships.

    Args:
        task_title: Title of the task
        assignee_person_id: Assignee Person ID
        project_id: Target project ID
        confirm: If False, returns proposed preview without modifying database.
    """
    if not confirm:
        return {
            "action": "assign_task",
            "status": "proposed_pending_confirmation",
            "confirm_required": True,
            "preview": {
                "task_title": task_title,
                "assignee_id": assignee_person_id,
                "project_id": project_id,
            },
            "prompt": f"Proposed Assignment: '{task_title}' to {assignee_person_id}. Pass confirm=True to write to graph."
        }

    graph = get_graph()
    task_id = f"TASK-SIM-{int(datetime.now().timestamp()) % 10000}"

    cypher = """
    MATCH (p:Person {id: $assignee_id})
    MATCH (pr:Project {id: $project_id})
    CREATE (tk:Ticket {
        id: $task_id,
        title: $task_title,
        status: 'assigned_pending',
        created_at: $now
    })
    CREATE (p)-[:ASSIGNED_TO]->(tk)
    CREATE (tk)-[:PART_OF]->(pr)
    RETURN tk.id AS task_id, p.name AS assignee_name
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = graph.query(cypher, {
        "assignee_id": assignee_person_id,
        "project_id": project_id,
        "task_id": task_id,
        "task_title": task_title,
        "now": now_iso,
    })

    return {
        "action": "assign_task",
        "status": "simulated_success",
        "task_id": task_id,
        "task_title": task_title,
        "assignee_id": assignee_person_id,
        "project_id": project_id,
        "note": "Task assigned and connected in knowledge graph."
    }


def impact_analysis(topic_or_decision_id: str) -> Dict[str, Any]:
    """Performs multi-hop graph traversal to analyze how a decision impacts the company.
    Finds affected tickets, blocked work items, affected projects, and responsible personnel.

    Args:
        topic_or_decision_id: Topic name (e.g. 'Paynova') or Decision ID (e.g. 'DEC_PAYMENTS_...').
    """
    from orgmind.freshness import impact_analysis as freshness_impact
    return freshness_impact(topic_or_decision_id)


# Tool registry mapping tool names to callable Python functions
TOOLS_REGISTRY = {
    "who_owns": who_owns,
    "who_knows_about": who_knows_about,
    "trace_decision": trace_decision,
    "compare_draft_vs_decision": compare_draft_vs_decision,
    "what_changed_since": what_changed_since,
    "get_source": get_source,
    "find_related": find_related,
    "impact_analysis": impact_analysis,
    "create_ticket": create_ticket,
    "draft_message": draft_message,
    "assign_task": assign_task,
}
