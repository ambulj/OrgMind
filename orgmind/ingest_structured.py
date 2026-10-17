"""Ingestion of structured data (CSVs and JSON tickets) into FalkorDB.

Technical Terms:
- Batch Ingestion: Loading batches of pre-formatted records into graph nodes and relationships.
- MERGE clause: A Cypher clause that creates a node/edge only if it does not already exist.
"""

import csv
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path so direct script execution works
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import get_graph, init_schema


def ingest_people(csv_path: str = "data/people.csv") -> int:
    """Loads people.csv into Person nodes."""
    graph = get_graph()
    count = 0
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = """
            MERGE (p:Person {id: $id})
            SET p.name = $name,
                p.email = $email,
                p.role = $role,
                p.aliases = $aliases
            """
            graph.query(query, {
                "id": row["id"].strip(),
                "name": row["name"].strip(),
                "email": row["email"].strip(),
                "role": row["role"].strip(),
                "aliases": row.get("aliases", "").strip(),
            })
            count += 1
    print(f"[Ingest] Loaded {count} Person nodes.")
    return count


def ingest_teams(csv_path: str = "data/teams.csv") -> int:
    """Loads teams.csv into Team nodes and sets up team lead relationships."""
    graph = get_graph()
    count = 0
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = """
            MERGE (t:Team {id: $id})
            SET t.name = $name,
                t.lead_id = $lead_id,
                t.description = $description
            WITH t
            MATCH (p:Person {id: $lead_id})
            MERGE (p)-[:MEMBER_OF {role: 'Lead'}]->(t)
            """
            graph.query(query, {
                "id": row["id"].strip(),
                "name": row["name"].strip(),
                "lead_id": row["lead_id"].strip(),
                "description": row["description"].strip(),
            })
            count += 1
    print(f"[Ingest] Loaded {count} Team nodes.")
    return count


def ingest_projects(csv_path: str = "data/projects.csv") -> int:
    """Loads projects.csv and links teams and project leads."""
    graph = get_graph()
    count = 0
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = """
            MERGE (pr:Project {id: $id})
            SET pr.name = $name,
                pr.status = $status,
                pr.description = $description
            WITH pr
            MATCH (t:Team {id: $team_id})
            MERGE (t)-[:OWNS {since: '2026-01-01'}]->(pr)
            WITH pr
            MATCH (lead:Person {id: $lead_person_id})
            MERGE (lead)-[:WORKS_ON {role: 'Lead'}]->(pr)
            """
            graph.query(query, {
                "id": row["id"].strip(),
                "name": row["name"].strip(),
                "team_id": row["owner_team_id"].strip(),
                "lead_person_id": row["lead_person_id"].strip(),
                "status": row["status"].strip(),
                "description": row["description"].strip(),
            })
            count += 1
    print(f"[Ingest] Loaded {count} Project nodes.")
    return count


def ingest_tickets(json_path: str = "data/tickets.json") -> int:
    """Loads tickets.json into Ticket nodes, linking author and mentioned topics."""
    graph = get_graph()
    with open(json_path, mode="r", encoding="utf-8") as f:
        tickets = json.load(f)

    count = 0
    for tick in tickets:
        query = """
        MERGE (tk:Ticket {id: $id})
        SET tk.title = $title,
            tk.status = $status,
            tk.created_at = $created_at,
            tk.description = $description
        WITH tk
        MATCH (p:Person {id: $author_id})
        MERGE (p)-[:AUTHORED {timestamp: $created_at}]->(tk)
        WITH tk
        MATCH (pr:Project {id: $project_id})
        MERGE (tk)-[:PART_OF]->(pr)
        """
        graph.query(query, {
            "id": tick["id"],
            "title": tick["title"],
            "status": tick["status"],
            "created_at": tick["created_at"],
            "description": tick["description"],
            "author_id": tick["author_id"],
            "project_id": tick["project_id"],
        })

        # Link topics
        for topic in tick.get("topics", []):
            topic_query = """
            MATCH (tk:Ticket {id: $tick_id})
            MERGE (top:Topic {name: $topic})
            MERGE (tk)-[:ABOUT]->(top)
            """
            graph.query(topic_query, {"tick_id": tick["id"], "topic": topic})

        # Link BLOCKED_BY if present
        if "blocked_by" in tick and tick["blocked_by"]:
            blocked_query = """
            MATCH (tk:Ticket {id: $tick_id})
            MATCH (blocker:Ticket {id: $blocker_id})
            MERGE (tk)-[:BLOCKED_BY]->(blocker)
            """
            graph.query(blocked_query, {"tick_id": tick["id"], "blocker_id": tick["blocked_by"]})

        count += 1

    print(f"[Ingest] Loaded {count} Ticket nodes.")
    return count


def ingest_ownership_history(csv_path: str = "data/ownership_history.csv") -> int:
    """Loads ownership_history.csv to record valid_from, valid_to, and provenance."""
    graph = get_graph()
    if not os.path.exists(csv_path):
        return 0

    count = 0
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = """
            MATCH (pr:Project {id: $project_id})
            MATCH (owner {id: $owner_id})
            MERGE (owner)-[r:OWNS {valid_from: $valid_from}]->(pr)
            SET r.valid_to = $valid_to,
                r.source = $source_doc_id
            """
            graph.query(query, {
                "project_id": row["project_id"].strip(),
                "owner_id": row["owner_id"].strip(),
                "valid_from": row["valid_from"].strip(),
                "valid_to": row["valid_to"].strip() if row.get("valid_to") else "",
                "source_doc_id": row.get("source_doc_id", "").strip(),
            })
            count += 1

    print(f"[Ingest] Loaded {count} Ownership History records.")
    return count


def run_all_structured_ingestion() -> None:
    """Initializes schema and runs full structured data ingestion pipeline."""
    print("=== Starting Structured Data Ingestion ===")
    init_schema()
    ingest_people()
    ingest_teams()
    ingest_projects()
    ingest_tickets()
    ingest_ownership_history()
    print("=== Structured Ingestion Completed Successfully ===")


if __name__ == "__main__":
    run_all_structured_ingestion()
