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
    MATCH (owner)-[:OWNS]->(target)
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
           lead.id AS lead_id
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
               p.id AS lead_id
        """
        rows = query_graph(alt_cypher, {"name": clean_query})

    return {
        "query": project_or_topic,
        "results": rows,
        "found": len(rows) > 0,
        "note": "Ownership verified from Northwind Labs graph registry." if rows else "No owner record found."
    }


def who_knows_about(topic: str) -> Dict[str, Any]:
    """Ranks people with demonstrated evidence of knowing about a topic based on
    authored documents, tickets, and chat contributions.

    Args:
        topic: The topic keyword (e.g. 'OAuth', 'Kubernetes', 'Billing').

    Returns:
        Ranked list of people with evidence counts and sample evidence item IDs.
    """
    cypher = """
    MATCH (p:Person)-[:AUTHORED]->(item)-[:MENTIONS|ABOUT]->(top:Topic)
    WHERE toLower(top.name) = toLower($topic)
    WITH p, count(item) AS evidence_count, collect(item.id) AS evidence_items
    RETURN p.id AS person_id,
           p.name AS person_name,
           p.role AS role,
           evidence_count,
           evidence_items[0..5] AS sample_evidence
    ORDER BY evidence_count DESC
    LIMIT 5
    """
    rows = query_graph(cypher, {"topic": topic})
    return {
        "topic": topic,
        "ranked_experts": rows,
        "evidence_summary": f"Found {len(rows)} contributors with direct authorship evidence on '{topic}'."
    }


def trace_decision(topic: str) -> Dict[str, Any]:
    """Traces the active decision for a topic, previous decisions it replaced,
    and returns full text snippets from the Source nodes for citations.

    Args:
        topic: Topic of the decision (e.g. 'OAuth', 'Billing').

    Returns:
        Structured trace of current decision, superseded decisions, and source IDs.
    """
    cypher = """
    MATCH (d:Decision)-[:ABOUT]->(top:Topic)
    WHERE toLower(top.name) = toLower($topic)
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
    rows = query_graph(cypher, {"topic": topic})
    return {
        "topic": topic,
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


# ============================================================================
# WRITE / ACTION TOOLS (Simulated Actions Written Back to Graph)
# ============================================================================

def create_ticket(title: str, description: str, project_id: str, author_id: str = "P_ALICE") -> Dict[str, Any]:
    """Simulates creating a ticket and writes it back into the graph."""
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


def draft_message(channel: str, text: str, author_id: str = "P_ALICE") -> Dict[str, Any]:
    """Simulates drafting a message to a team channel and writes it to the graph."""
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


def assign_task(task_title: str, assignee_person_id: str, project_id: str) -> Dict[str, Any]:
    """Simulates assigning a task to a person for a project and updates graph relationships."""
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
    "what_changed_since": what_changed_since,
    "get_source": get_source,
    "find_related": find_related,
    "impact_analysis": impact_analysis,
    "create_ticket": create_ticket,
    "draft_message": draft_message,
    "assign_task": assign_task,
}
