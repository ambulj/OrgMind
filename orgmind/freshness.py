"""Freshness & Decision Superseding Module.

Technical Terms:
- Provenance: Keeping track of the exact origin (Source node) of a fact or decision.
- Superseding: Instead of deleting an outdated decision, we link the new decision
  to the old decision via a (:SUPERSEDES) edge, setting the old decision status to 'superseded'.
- Non-destructive Update: Ensuring our corporate graph preserves full historical context.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import query_graph, get_graph


def apply_decision(
    decision_id: str,
    topic: str,
    text: str,
    source_id: str,
    source_file: str,
    source_snippet: str,
    chunk_offset: int = 0,
    decided_by_person_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Inserts a new decision, attaches its mandatory Source node, and supersedes any existing current decision on the topic.

    Integrity rules enforced:
    1. Decision must be linked to at least one Source node via [:DERIVED_FROM].
    2. Any existing Decision with status='current' for this topic will have its status
       changed to 'superseded', valid_to set to timestamp, and a [:SUPERSEDES] edge created.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    graph = get_graph()

    # Cypher query combining creation, source attachment, and superseding link
    cypher_mutation = """
    // 1. Locate any currently active decision for this topic
    OPTIONAL MATCH (old:Decision {topic: $topic, status: "current"})
    SET old.status = "superseded",
        old.valid_to = $timestamp

    // 2. Create the new Source node (provenance)
    MERGE (src:Source {id: $source_id})
    ON CREATE SET src.file_path = $source_file,
                  src.chunk_offset = $chunk_offset,
                  src.text_snippet = $source_snippet,
                  src.created_at = $timestamp

    // 3. Create the new Decision node
    CREATE (new:Decision {
        id: $decision_id,
        topic: $topic,
        text: $text,
        status: "current",
        valid_from: $timestamp,
        valid_to: ""
    })

    // 4. Connect Decision to Source (provenance edge)
    CREATE (new)-[:DERIVED_FROM]->(src)

    // 5. Connect to Topic node
    MERGE (top:Topic {name: $topic})
    CREATE (new)-[:ABOUT]->(top)

    // 6. If an older active decision existed, create SUPERSEDES relationship
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
    }

    result = graph.query(cypher_mutation, params)

    # TODO (Person A): If decided_by_person_id is provided, link (new)-[:DECIDED_BY]->(Person)
    if decided_by_person_id:
        link_actor_query = """
        MATCH (new:Decision {id: $decision_id})
        MATCH (p:Person {id: $person_id})
        CREATE (new)-[:DECIDED_BY]->(p)
        """
        graph.query(link_actor_query, {"decision_id": decision_id, "person_id": decided_by_person_id})

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


def ingest_live_decision(file_path: str = "data/live/new_billing_decision.json") -> Dict[str, Any]:
    """Reads a live decision file from /data/live and executes the superseding pipeline.
    Used for Demo Moment C.
    """
    import json
    import os

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Live decision file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    src = data["source"]
    return apply_decision(
        decision_id=data["new_decision_id"],
        topic=data["topic"],
        text=data["text"],
        source_id=src["source_id"],
        source_file=src["file_path"],
        source_snippet=src["snippet"],
        chunk_offset=src.get("chunk_offset", 0),
        decided_by_person_id=data.get("decided_by"),
        timestamp=data.get("timestamp"),
    )
