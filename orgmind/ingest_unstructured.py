"""Ingestion of unstructured text (Markdown documents & JSONL chats) using LLM extraction.

Technical Terms:
- Unstructured Data: Information without a pre-set tabular schema (e.g., meeting notes, chat logs).
- Schema-Guided Extraction: Prompting an LLM with a strict JSON format (or Pydantic schema)
  to identify specific entities (Person, Decision, Topic) and relationships.
- Provenance Grounding: Ensuring that every extracted fact is stored alongside a `Source` node
  containing the exact text quote and file location.
"""

import glob
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.db import get_graph
from orgmind.resolve import resolver
from orgmind.freshness import apply_decision


# Pydantic models for structured output validation
class ExtractedSource(BaseModel):
    source_id: str
    file_path: str
    chunk_offset: int = 0
    snippet: str


class ExtractedDecision(BaseModel):
    decision_id: str
    topic: str
    text: str
    decided_by_mention: Optional[str] = None
    date: str
    source: ExtractedSource


class ExtractedExtractionResult(BaseModel):
    decisions: List[ExtractedDecision] = Field(default_factory=list)
    people_mentions: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)


def extract_from_markdown_llm(file_path: str, content: str) -> ExtractedExtractionResult:
    """Uses LiteLLM to extract decisions, topics, and author mentions from markdown documents.

    TODO (Person A):
    1. Call litellm.completion(model=os.getenv('LLM_MODEL'), response_format={'type': 'json_object'})
    2. Enforce strict JSON schema matching ExtractedExtractionResult.
    3. Return validated Pydantic model.
    """
    # Placeholder extraction logic for bootstrapping / offline mode
    print(f"[IngestUnstructured] Parsing markdown doc: {file_path}")

    # Simulated deterministic extraction for docs/auth_architecture.md
    if "auth_architecture" in file_path:
        return ExtractedExtractionResult(
            decisions=[
                ExtractedDecision(
                    decision_id="DEC_AUTH_2026_01",
                    topic="OAuth",
                    text="Adopt OAuth 2.1 with PKCE for all web/mobile apps backed by Keycloak.",
                    decided_by_mention="Alice Chen",
                    date="2026-01-15",
                    source=ExtractedSource(
                        source_id="SRC_DOC_AUTH_01",
                        file_path=file_path,
                        chunk_offset=280,
                        snippet="We have decided to adopt OAuth 2.1 with PKCE for all user-facing web and mobile applications, backed by Keycloak as our Identity Provider.",
                    ),
                )
            ],
            people_mentions=["Alice Chen", "Elena Rostova", "Bob Martinez"],
            topics=["OAuth", "Keycloak", "Authentication", "Security"],
        )
    elif "billing_migration" in file_path:
        return ExtractedExtractionResult(
            decisions=[
                ExtractedDecision(
                    decision_id="DEC_BILLING_2026_01",
                    topic="Billing",
                    text="Adopt Stripe Elements for checkout; use PostgreSQL for webhook reconciliation.",
                    decided_by_mention="Bob Martinez",
                    date="2026-01-20",
                    source=ExtractedSource(
                        source_id="SRC_DOC_BILL_01",
                        file_path=file_path,
                        chunk_offset=210,
                        snippet="On 2026-01-20, Bob Martinez and Carol Danvers decided: We will use Stripe Elements for the frontend checkout flow... Database chosen for transaction reconciliation is PostgreSQL.",
                    ),
                )
            ],
            people_mentions=["Bob Martinez", "Carol Danvers"],
            topics=["Billing", "Stripe", "PostgreSQL"],
        )

    return ExtractedExtractionResult()


def ingest_markdown_docs(docs_dir: str = "data/docs") -> None:
    """Scans and extracts facts and decisions from all markdown files in data/docs/."""
    graph = get_graph()
    md_files = glob.glob(os.path.join(docs_dir, "*.md"))

    for file_path in md_files:
        with open(file_path, mode="r", encoding="utf-8") as f:
            content = f.read()

        doc_id = f"DOC_{os.path.basename(file_path).split('.')[0].upper()}"
        # Create Document node
        graph.query(
            "MERGE (doc:Document {id: $id}) SET doc.path = $path, doc.title = $title",
            {"id": doc_id, "path": file_path, "title": os.path.basename(file_path)},
        )

        extracted = extract_from_markdown_llm(file_path, content)

        # Ingest decisions with mandatory Source and superseding check
        for dec in extracted.decisions:
            decider_id = resolver.resolve_person(dec.decided_by_mention) if dec.decided_by_mention else None
            apply_decision(
                decision_id=dec.decision_id,
                topic=dec.topic,
                text=dec.text,
                source_id=dec.source.source_id,
                source_file=dec.source.file_path,
                source_snippet=dec.source.snippet,
                chunk_offset=dec.source.chunk_offset,
                decided_by_person_id=decider_id,
                timestamp=dec.date,
            )

        # Ingest topic mentions
        for topic in extracted.topics:
            graph.query(
                """
                MATCH (doc:Document {id: $doc_id})
                MERGE (top:Topic {name: $topic})
                MERGE (doc)-[:MENTIONS]->(top)
                """,
                {"doc_id": doc_id, "topic": topic},
            )

        print(f"[IngestUnstructured] Processed {file_path}")


def ingest_chat_messages(chats_dir: str = "data/chats") -> None:
    """Parses JSONL chat logs, connects author person, and registers discussed topics."""
    graph = get_graph()
    jsonl_files = glob.glob(os.path.join(chats_dir, "*.jsonl"))

    for file_path in jsonl_files:
        with open(file_path, mode="r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                msg = json.loads(line)
                author_id = resolver.resolve_person(msg.get("author", ""))
                ts = msg.get("ts") or msg.get("timestamp") or ""

                query = """
                MERGE (m:Message {id: $id})
                SET m.channel = $channel,
                    m.timestamp = $timestamp,
                    m.text = $text
                """
                params = {
                    "id": msg["id"],
                    "channel": msg.get("channel", "#general"),
                    "timestamp": ts,
                    "text": msg.get("text", ""),
                }
                graph.query(query, params)

                # Link author if resolved
                if author_id:
                    link_author = """
                    MATCH (m:Message {id: $id})
                    MATCH (p:Person {id: $author_id})
                    MERGE (p)-[:AUTHORED {timestamp: $timestamp}]->(m)
                    """
                    graph.query(link_author, {"id": msg["id"], "author_id": author_id, "timestamp": ts})

                # Simple topic detection in chat for who-knows evidence
                text_lower = msg.get("text", "").lower()
                topics_map = [
                    ("oauth", "OAuth"),
                    ("stripe", "Stripe"),
                    ("billing", "Billing"),
                    ("kubernetes", "Kubernetes"),
                    ("paynova", "Paynova"),
                ]
                for keyword, topic_name in topics_map:
                    if keyword in text_lower:
                        link_top = """
                        MATCH (m:Message {id: $id})
                        MERGE (top:Topic {name: $topic})
                        MERGE (m)-[:MENTIONS]->(top)
                        """
                        graph.query(link_top, {"id": msg["id"], "topic": topic_name})

        print(f"[IngestUnstructured] Processed chats in {file_path}")


def run_all_unstructured_ingestion() -> None:
    """Runs complete unstructured ingestion for docs and chats."""
    print("=== Starting Unstructured Data Ingestion ===")
    ingest_markdown_docs()
    ingest_chat_messages()
    print("=== Unstructured Ingestion Completed Successfully ===")


if __name__ == "__main__":
    run_all_unstructured_ingestion()
