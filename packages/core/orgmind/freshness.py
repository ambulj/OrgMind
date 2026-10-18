"""Freshness & Decision Superseding Module.

Technical Terms:
- Provenance: Keeping track of the exact origin (Source node) of a fact or decision.
- Superseding: Instead of deleting an outdated decision, we link the new decision
  to the old decision via a (:SUPERSEDES) edge, setting the old decision status to 'superseded'.
- Non-destructive Update: Ensuring our corporate graph preserves full historical context.
- Extraction Preview: Showing the proposed graph mutation before writing to database.
- Idempotency: Running the same ingestion twice produces identical graph state with no duplicates.
- Multi-hop Impact Analysis: Tracing how a decision change cascades across topics, projects,
  tickets (and blocked tickets), and responsible team members.
"""

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import get_graph, query_graph
from orgmind.resolve import resolver


def preview_decision(
    raw_payload_or_path: str | Path | dict[str, Any],
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Inspects a proposed decision payload against current graph state WITHOUT mutating.

    Args:
        raw_payload_or_path: Path to JSON decision file or raw dictionary payload.
        workspace_id: Optional workspace partition identifier.

    Returns:
        Structured preview dictionary detailing:
        - action: 'SUPERSEDE' or 'CREATE'
        - status: 'ready' or 'already_committed'
        - proposed_decision: metadata of decision to be written
        - source: source provenance node details
        - superseded_decision_candidate: existing active decision on topic (if any)
        - affected_tickets_preview: tickets currently tied to the topic
        - confidence: float score (1.0 for validated schema)
    """
    if isinstance(raw_payload_or_path, (str, Path)):
        file_path = str(raw_payload_or_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Decision file not found: {file_path}")
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = dict(raw_payload_or_path)

    new_decision_id = data.get("new_decision_id") or data.get("id")
    topic = data.get("topic", "")
    text = data.get("text", "")
    decided_by = data.get("decided_by")
    timestamp = data.get("timestamp") or datetime.now(UTC).isoformat()
    src = data.get("source", {})
    supersedes_id = data.get("supersedes_id")

    # Check if already exists in graph (idempotency preview)
    existing_check = query_graph(
        "MATCH (d:Decision {id: $id}) RETURN d.id AS id, d.text AS text, d.status AS status",
        {"id": new_decision_id},
        workspace_id=workspace_id,
    )
    already_committed = len(existing_check) > 0 and existing_check[0]["text"] == text

    # Query currently active candidate decision to supersede
    candidate_rows = query_graph(
        """
        MATCH (old:Decision)
        WHERE (
            ($supersedes_id IS NOT NULL AND old.id = $supersedes_id)
            OR (
                $supersedes_id IS NULL
                AND (toLower(old.topic) = toLower($topic) OR (old)-[:ABOUT]->(:Topic {name: $topic}))
                AND old.id <> $new_id
                AND (old.valid_from IS NULL OR old.valid_from < $timestamp)
            )
        )
          AND old.status = 'current'
        OPTIONAL MATCH (old)-[:DERIVED_FROM]->(src:Source)
        OPTIONAL MATCH (old)-[:DECIDED_BY]->(p:Person)
        RETURN old.id AS id,
               old.text AS text,
               old.valid_from AS valid_from,
               p.name AS decided_by_name,
               p.id AS decided_by_id,
               src.id AS source_id,
               src.file_path AS source_file,
               src.text_snippet AS source_snippet
        LIMIT 1
        """,
        {
            "topic": topic,
            "new_id": new_decision_id or "",
            "timestamp": timestamp,
            "supersedes_id": supersedes_id,
        },
        workspace_id=workspace_id,
    )
    superseded_candidate = candidate_rows[0] if candidate_rows else None

    # Query affected tickets preview
    ticket_rows = query_graph(
        """
        MATCH (tk:Ticket)-[:ABOUT]->(top:Topic)
        WHERE toLower(top.name) = toLower($topic)
        RETURN tk.id AS id, tk.title AS title, tk.status AS status
        LIMIT 5
        """,
        {"topic": topic},
        workspace_id=workspace_id,
    )

    action = "SUPERSEDE" if superseded_candidate else "CREATE"
    status = "already_committed" if already_committed else "ready"

    return {
        "status": status,
        "action": action,
        "already_committed": already_committed,
        "proposed_decision": {
            "id": new_decision_id,
            "topic": topic,
            "text": text,
            "decided_by": decided_by,
            "timestamp": timestamp,
        },
        "source": {
            "source_id": src.get("source_id"),
            "file_path": src.get("file_path"),
            "snippet": src.get("snippet") or src.get("text_snippet"),
            "chunk_offset": src.get("chunk_offset", 0),
        },
        "superseded_decision_candidate": superseded_candidate,
        "affected_tickets_preview": ticket_rows,
        "confidence": 1.0,
    }


def apply_decision(
    decision_id: str,
    topic: str,
    text: str,
    source_id: str,
    source_file: str,
    source_snippet: str,
    chunk_offset: int = 0,
    decided_by_person_id: str | None = None,
    timestamp: str | None = None,
    supersedes_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Inserts a new decision, attaches its mandatory Source node, and supersedes any existing active decision on the topic.

    Integrity rules enforced:
    1. Decision must be linked to at least one Source node via [:DERIVED_FROM].
    2. Any existing Decision with status='current' candidate will have its status
       changed to 'superseded', valid_to set to timestamp, and a [:SUPERSEDES] edge created.
    3. Supersession NEVER applies to older or equal-timestamp decisions (old.valid_from < timestamp).
    4. Sets full v0.2 Domain Model fields natively on Source and Decision.
    """
    if timestamp is None:
        timestamp = datetime.now(UTC).isoformat()

    graph = get_graph(workspace_id)
    content_hash = hashlib.sha256(source_snippet.encode("utf-8")).hexdigest()
    origin_type = (
        "document"
        if "doc" in source_file.lower()
        else ("chat" if "chat" in source_file.lower() else "decision_record")
    )

    # Cypher query combining creation, source attachment, and superseding link
    cypher_mutation = """
    // 1. Locate candidate decision to supersede:
    // If explicit supersedes_id is provided, match that candidate.
    // Otherwise, match active decision on the same topic ONLY IF old.valid_from < $timestamp.
    OPTIONAL MATCH (old:Decision)
    WHERE (
        ($supersedes_id IS NOT NULL AND old.id = $supersedes_id)
        OR (
            $supersedes_id IS NULL
            AND (toLower(old.topic) = toLower($topic) OR (old)-[:ABOUT]->(:Topic {name: $topic}))
            AND old.id <> $decision_id
            AND (old.valid_from IS NULL OR old.valid_from < $timestamp)
        )
    )
    AND old.status = 'current'
    SET old.status = "superseded",
        old.valid_to = $timestamp

    // 2. Create or update the new Source node with full v0.2 enterprise properties
    MERGE (src:Source {id: $source_id})
    SET src.file_path = $source_file,
        src.chunk_offset = $chunk_offset,
        src.text_snippet = $source_snippet,
        src.created_at = $timestamp,
        src.content_hash = $content_hash,
        src.visibility = '["all"]',
        src.redacted = false,
        src.origin_type = $origin_type,
        src.valid_from = $timestamp,
        src.valid_to = ""

    // 3. Create or update the new Decision node
    MERGE (new:Decision {id: $decision_id})
    SET new.topic = $topic,
        new.text = $text,
        new.status = "current",
        new.valid_from = $timestamp,
        new.valid_to = "",
        new.confidence = 1.0,
        new.confidence_tier = "High",
        new.review_status = "approved",
        new.extracted_by = "doc_ingest",
        new.recorded_at = $timestamp

    // 4. Connect Decision to Source (provenance edge)
    MERGE (new)-[:DERIVED_FROM]->(src)

    // 5. Connect to Topic node
    MERGE (top:Topic {name: $topic})
    MERGE (new)-[:ABOUT]->(top)

    // 6. If an older active decision was superseded, create SUPERSEDES relationship
    FOREACH (_ IN CASE WHEN old IS NOT NULL THEN [1] ELSE [] END |
        CREATE (new)-[:SUPERSEDES {superseded_at: $timestamp}]->(old)
    )

    RETURN new.id AS new_id,
           old.id AS superseded_id,
           src.id AS source_id
    """

    params = {
        "topic": topic,
        "text": text,
        "timestamp": timestamp,
        "source_id": source_id,
        "source_file": source_file,
        "chunk_offset": chunk_offset,
        "source_snippet": source_snippet,
        "decision_id": decision_id,
        "content_hash": content_hash,
        "origin_type": origin_type,
        "supersedes_id": supersedes_id,
    }

    result = graph.query(cypher_mutation, params)

    # Link deciding actor if provided
    if decided_by_person_id:
        resolved_pid = resolver.resolve_person(decided_by_person_id) or decided_by_person_id
        link_actor_query = """
        MATCH (new:Decision {id: $decision_id})
        MATCH (p:Person {id: $person_id})
        MERGE (new)-[:DECIDED_BY]->(p)
        """
        graph.query(link_actor_query, {"decision_id": decision_id, "person_id": resolved_pid})

    superseded_id = None
    if result.result_set and len(result.result_set) > 0:
        superseded_id = result.result_set[0][1]

    return {
        "status": "success",
        "new_decision_id": decision_id,
        "superseded_decision_id": superseded_id,
        "source_id": source_id,
        "topic": topic,
        "timestamp": timestamp,
    }


def commit_decision(
    payload_or_preview_or_path: str | Path | dict[str, Any],
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Commits a decision payload to the graph with idempotency checks.

    If the decision ID already exists in the graph with the exact same text:
    Returns {"status": "noop_idempotent", ...} and leaves the graph untouched.
    """
    if isinstance(payload_or_preview_or_path, (str, Path)):
        with open(payload_or_preview_or_path, encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(payload_or_preview_or_path, dict):
        if "proposed_decision" in payload_or_preview_or_path:
            p = payload_or_preview_or_path["proposed_decision"]
            s = payload_or_preview_or_path.get("source", {})
            data = {
                "new_decision_id": p.get("id"),
                "topic": p.get("topic"),
                "text": p.get("text"),
                "decided_by": p.get("decided_by"),
                "timestamp": p.get("timestamp"),
                "supersedes_id": payload_or_preview_or_path.get("superseded_decision_candidate", {}).get("id") if payload_or_preview_or_path.get("superseded_decision_candidate") else None,
                "source": {
                    "source_id": s.get("source_id"),
                    "file_path": s.get("file_path"),
                    "snippet": s.get("snippet"),
                    "chunk_offset": s.get("chunk_offset", 0),
                },
            }
        else:
            data = payload_or_preview_or_path
    else:
        raise ValueError("Invalid payload type for commit_decision.")

    decision_id = data.get("new_decision_id") or data.get("id")
    topic = data.get("topic", "")
    text = data.get("text", "")
    src = data.get("source", {})
    supersedes_id = data.get("supersedes_id")

    # IDEMPOTENCY CHECK:
    existing = query_graph(
        "MATCH (d:Decision {id: $id}) RETURN d.id AS id, d.text AS text, d.status AS status",
        {"id": decision_id},
        workspace_id=workspace_id,
    )
    if existing and existing[0]["text"] == text:
        return {
            "status": "noop_idempotent",
            "decision_id": decision_id,
            "topic": topic,
            "message": f"Decision '{decision_id}' already committed with identical content. Graph untouched.",
        }

    return apply_decision(
        decision_id=decision_id,
        topic=topic,
        text=text,
        source_id=src.get("source_id", f"SRC_{decision_id}"),
        source_file=src.get("file_path", "unknown"),
        source_snippet=src.get("snippet") or src.get("text_snippet", ""),
        chunk_offset=src.get("chunk_offset", 0),
        decided_by_person_id=data.get("decided_by"),
        timestamp=data.get("timestamp"),
        supersedes_id=supersedes_id,
        workspace_id=workspace_id,
    )


def impact_analysis(
    topic_or_decision_id: str,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Performs multi-hop Cypher traversal to analyze how a decision impacts the company.

    Traverses:
    Decision -> Topic -> Projects -> Tickets (including BLOCKED_BY chains) -> People

    Args:
        topic_or_decision_id: Either a topic name ('Paynova') or Decision ID ('DEC_PAYMENTS_...').
        workspace_id: Tenant workspace identifier for isolated graph access.

    Returns:
        Structured impact report containing:
        - topic: Canonical topic
        - decision_context: Current active decision and superseded history
        - affected_tickets: Tickets working on or discussing this topic
        - blocked_tickets: Tickets whose progress is blocked by related tickets
        - affected_projects: Projects containing the affected tickets
        - responsible_people: Project owners, ticket assignees, and key topic experts
        - evidence_paths: Human-readable narrative provenance chains
        - summary: High-level impact summary
    """
    clean_target = topic_or_decision_id.strip()

    # If passed a Decision ID, resolve its associated topic
    if clean_target.startswith("DEC_"):
        dec_topic_rows = query_graph(
            "MATCH (d:Decision {id: $id})-[:ABOUT]->(top:Topic) RETURN top.name AS topic",
            {"id": clean_target},
            workspace_id=workspace_id,
        )
        if dec_topic_rows:
            topic = dec_topic_rows[0]["topic"]
        else:
            topic = clean_target
    else:
        topic = clean_target

    # 1. Decision Context: active decision and superseded decisions
    decision_rows = query_graph(
        """
        MATCH (d:Decision)
        WHERE (toLower(d.topic) = toLower($topic)
               OR (d)-[:ABOUT]->(:Topic {name: $topic}))
        OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)
        OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
        RETURN d.id AS id,
               d.text AS text,
               d.status AS status,
               d.valid_from AS valid_from,
               d.valid_to AS valid_to,
               p.name AS decided_by,
               src.id AS source_id,
               src.file_path AS source_file
        ORDER BY d.valid_from DESC
        """,
        {"topic": topic},
        workspace_id=workspace_id,
    )

    current_decision = next((d for d in decision_rows if d["status"] == "current"), None)
    superseded_decisions = [d for d in decision_rows if d["status"] == "superseded"]

    # 2. Affected Tickets: directly linked to topic or mentioning topic
    tickets_query = """
    MATCH (tk:Ticket)
    WHERE (tk)-[:ABOUT]->(:Topic {name: $topic})
       OR toLower(tk.title) CONTAINS toLower($topic)
       OR toLower(tk.description) CONTAINS toLower($topic)
    OPTIONAL MATCH (p_auth:Person)-[:AUTHORED]->(tk)
    OPTIONAL MATCH (p_ass:Person)-[:ASSIGNED_TO]->(tk)
    OPTIONAL MATCH (tk)-[:PART_OF]->(pr:Project)
    OPTIONAL MATCH (tk)-[:BLOCKED_BY]->(blocker:Ticket)
    RETURN tk.id AS ticket_id,
           tk.title AS title,
           tk.status AS status,
           p_auth.name AS author_name,
           p_auth.id AS author_id,
           p_ass.name AS assignee_name,
           p_ass.id AS assignee_id,
           pr.id AS project_id,
           pr.name AS project_name,
           blocker.id AS blocked_by_id,
           blocker.title AS blocked_by_title
    """
    ticket_rows = query_graph(tickets_query, {"topic": topic}, workspace_id=workspace_id)

    # 3. Blocked Tickets: find tickets blocked by any tickets associated with this topic
    blocked_query = """
    MATCH (other:Ticket)-[:BLOCKED_BY]->(tk:Ticket)
    WHERE (tk)-[:ABOUT]->(:Topic {name: $topic})
       OR toLower(tk.title) CONTAINS toLower($topic)
    OPTIONAL MATCH (p:Person)-[:ASSIGNED_TO]->(other)
    OPTIONAL MATCH (p_auth:Person)-[:AUTHORED]->(other)
    RETURN other.id AS ticket_id,
           other.title AS title,
           other.status AS status,
           tk.id AS blocked_by_ticket_id,
           tk.title AS blocker_title,
           coalesce(p.name, p_auth.name, 'Unassigned') AS assignee_or_author
    """
    blocked_rows = query_graph(blocked_query, {"topic": topic}, workspace_id=workspace_id)

    # 4. Affected Projects
    project_map: dict[str, dict[str, Any]] = {}
    for t in ticket_rows:
        pid = t.get("project_id")
        if pid and pid not in project_map:
            project_map[pid] = {
                "project_id": pid,
                "project_name": t.get("project_name", pid),
            }

    # Query leads/owners of affected projects
    for pid in list(project_map.keys()):
        proj_meta = query_graph(
            """
            MATCH (pr:Project {id: $pid})
            OPTIONAL MATCH (owner)-[:OWNS]->(pr)
            OPTIONAL MATCH (lead:Person)-[:WORKS_ON {role: 'Lead'}]->(pr)
            RETURN owner.name AS owner_name, lead.name AS lead_name
            """,
            {"pid": pid},
            workspace_id=workspace_id,
        )
        if proj_meta:
            project_map[pid]["owner"] = proj_meta[0].get("owner_name")
            project_map[pid]["lead"] = proj_meta[0].get("lead_name")

    # 5. Responsible People
    people_map: dict[str, dict[str, Any]] = {}
    # From ticket assignees/authors
    for t in ticket_rows:
        if t.get("assignee_id") and t.get("assignee_name"):
            people_map[t["assignee_id"]] = {
                "id": t["assignee_id"],
                "name": t["assignee_name"],
                "reason": f"Assignee of {t['ticket_id']} ({t['title']})",
            }
        elif t.get("author_id") and t.get("author_name"):
            people_map[t["author_id"]] = {
                "id": t["author_id"],
                "name": t["author_name"],
                "reason": f"Author of {t['ticket_id']} ({t['title']})",
            }

    # From blocked tickets
    for b in blocked_rows:
        assignee = b.get("assignee_or_author")
        if assignee and assignee != "Unassigned":
            pid = resolver.resolve_person(assignee) or assignee
            if pid not in people_map:
                people_map[pid] = {
                    "id": pid,
                    "name": assignee,
                    "reason": f"Responsible for blocked ticket {b['ticket_id']} ({b['title']})",
                }

    # From Decider
    if current_decision and current_decision.get("decided_by"):
        d_name = current_decision["decided_by"]
        d_pid = resolver.resolve_person(d_name) or d_name
        people_map[d_pid] = {
            "id": d_pid,
            "name": d_name,
            "reason": f"Decided active policy ({current_decision['id']})",
        }

    # 6. Build Human-Readable Evidence Paths
    evidence_paths: list[str] = []
    if current_decision:
        evidence_paths.append(
            f"Decision[{current_decision['id']}: '{current_decision['text'][:70]}...'] -> ABOUT -> Topic[{topic}]"
        )
    if superseded_decisions:
        for s in superseded_decisions:
            evidence_paths.append(
                f"SUPERSEDES -> Historical Decision[{s['id']}] (Valid: {s['valid_from']} to {s['valid_to']})"
            )
    for t in ticket_rows:
        assignee = t.get("assignee_name") or "Unassigned"
        evidence_paths.append(
            f"Topic[{topic}] -> Affects Ticket[{t['ticket_id']}: '{t['title']}'] (Status: {t['status']}, Assignee: {assignee})"
        )
    for b in blocked_rows:
        evidence_paths.append(
            f"CRITICAL DEPENDENCY: Ticket[{b['ticket_id']}: '{b['title']}'] is BLOCKED BY Ticket[{b['blocked_by_ticket_id']}] due to topic '{topic}'"
        )

    # 7. Summary
    blocked_count = len(blocked_rows)
    affected_count = len(ticket_rows)
    summary = (
        f"Impact Analysis for '{topic}': Found {affected_count} directly impacted tickets across "
        f"{len(project_map)} projects, with {blocked_count} blocked work items. "
        f"Key responsible personnel: {', '.join(p['name'] for p in people_map.values())}."
    )

    return {
        "topic": topic,
        "decision_context": {
            "current_decision": current_decision,
            "superseded_decisions": superseded_decisions,
        },
        "affected_tickets": ticket_rows,
        "blocked_tickets": blocked_rows,
        "affected_projects": list(project_map.values()),
        "responsible_people": list(people_map.values()),
        "evidence_paths": evidence_paths,
        "summary": summary,
    }


def ingest_live_decision(
    file_path: str = "data/live/new_billing_decision.json",
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Reads a live decision file from /data/live and executes the superseding pipeline.
    Used for Demo Moment C.
    """
    return commit_decision(file_path, workspace_id=workspace_id)


def calculate_staleness(
    entity_id: str,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Computes staleness metric for an entity based on its most recent grounded evidence date.

    Returns:
        Structured staleness metric including days since last evidence,
        staleness tier ('Fresh', 'Aging', 'Stale'), and recent activity count.
    """
    clean_id = entity_id.strip()

    # Query last evidence timestamps across connected sources, messages, and tickets
    cypher = """
    MATCH (n {id: $id})
    OPTIONAL MATCH (n)-[:DERIVED_FROM|AUTHORED|OWNS|ASSIGNED_TO|MENTIONS*1..2]-(item)
    WHERE item.created_at IS NOT NULL OR item.valid_from IS NOT NULL OR item.timestamp IS NOT NULL
    RETURN coalesce(item.created_at, item.valid_from, item.timestamp) AS event_date
    ORDER BY event_date DESC
    LIMIT 10
    """
    rows = query_graph(cypher, {"id": clean_id}, workspace_id=workspace_id)

    last_evidence_date: str | None = None
    if rows and rows[0].get("event_date"):
        last_evidence_date = str(rows[0]["event_date"])

    now = datetime.now(UTC)
    days_stale = 0
    tier = "Fresh"

    if last_evidence_date:
        try:
            parsed_date = datetime.fromisoformat(last_evidence_date[:10]).replace(tzinfo=UTC)
            days_stale = max(0, (now - parsed_date).days)
            if days_stale > 180:
                tier = "Stale"
            elif days_stale > 60:
                tier = "Aging"
            else:
                tier = "Fresh"
        except Exception:
            days_stale = 0
            tier = "Fresh"
    else:
        tier = "Unknown"

    return {
        "entity_id": clean_id,
        "last_evidence_date": last_evidence_date,
        "days_since_last_evidence": days_stale,
        "staleness_tier": tier,
        "evidence_count": len(rows),
    }
