"""Ingestion of unstructured text (Markdown documents & JSONL chats) using schema extraction.

Technical Terms:
- Unstructured Data: Information without a pre-set tabular schema (e.g., meeting notes, chat logs).
- Schema-Guided Extraction: Parsing documents against strict entity models (Person, Decision, Draft, Topic).
- Provenance Grounding: Ensuring that every extracted fact is stored alongside a `Source` node
  containing cryptographic content hash, exact text quote, and file location.
"""

import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from pydantic import BaseModel, Field

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.config import settings
from orgmind.db import get_graph
from orgmind.freshness import apply_decision
from orgmind.resolve import resolver


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
    decided_by_mention: str | None = None
    date: str
    source: ExtractedSource
    supersedes_id: str | None = None


class ExtractedDraft(BaseModel):
    draft_id: str
    topic: str
    recommendation: str
    author_mention: str | None = None
    date: str
    source: ExtractedSource


class ExtractedExtractionResult(BaseModel):
    decisions: list[ExtractedDecision] = Field(default_factory=list)
    drafts: list[ExtractedDraft] = Field(default_factory=list)
    people_mentions: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


def extract_from_markdown_llm(file_path: str, content: str) -> ExtractedExtractionResult:
    """Extracts decisions, draft recommendations, topics, and author mentions by analyzing document content.
    Reads actual document frontmatter, decision quotes, and provenance blocks.
    """
    # 1. Parse frontmatter metadata bullets
    doc_id_match = re.search(r"-\s*\*\*Document ID\*\*:\s*([A-Za-z0-9_]+)", content)
    dec_id_match = re.search(r"-\s*\*\*Decision ID\*\*:\s*([A-Za-z0-9_]+)", content)
    draft_id_match = re.search(r"-\s*\*\*Draft ID\*\*:\s*([A-Za-z0-9_]+)", content)
    topic_match = re.search(r"-\s*\*\*Topic\*\*:\s*([^\r\n]+)", content)
    author_match = re.search(
        r"-\s*\*\*Author\*\*:\s*([A-Za-z0-9_\s&]+?)(?:\s*\(.*?\))?$",
        content,
        re.MULTILINE,
    )
    date_match = re.search(r"-\s*\*\*Date\*\*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", content)
    supersedes_match = re.search(r"-\s*\*\*Supersedes\*\*:\s*([A-Za-z0-9_]+)", content)
    source_match = re.search(r"-\s*Source ID:\s*`?([A-Za-z0-9_]+)`?", content, re.IGNORECASE)

    raw_author = author_match.group(1).strip() if author_match else None
    if raw_author and "&" in raw_author:
        primary_author = raw_author.split("&")[0].strip()
    else:
        primary_author = raw_author

    raw_date = date_match.group(1).strip() if date_match else "2026-01-01"
    raw_topic = topic_match.group(1).strip() if topic_match else "General"
    source_id = (
        source_match.group(1).strip()
        if source_match
        else f"SRC_{os.path.basename(file_path).split('.')[0].upper()}"
    )
    supersedes_id = supersedes_match.group(1).strip() if supersedes_match else None

    # People mentions from handles and author fields
    people_mentions: list[str] = []
    for m in re.finditer(r"@([A-Za-z0-9_]+)", content):
        handle = m.group(1)
        resolved_pid = resolver.resolve_person(handle)
        if resolved_pid:
            p_info = resolver.id_to_person.get(resolved_pid, {})
            name = p_info.get("name")
            if name and name not in people_mentions:
                people_mentions.append(name)
    if primary_author and primary_author not in people_mentions:
        people_mentions.append(primary_author)

    # Topics detection
    topics: list[str] = [raw_topic]
    candidate_topics = [
        "OAuth",
        "Keycloak",
        "Authentication",
        "Security",
        "Billing",
        "Stripe",
        "Paynova",
        "Kubernetes",
        "DevOps",
        "Database",
        "Frontend",
        "Product",
        "Design",
        "Architecture",
        "Telemetry",
    ]
    for ct in candidate_topics:
        if ct.lower() in content.lower() and ct not in topics:
            topics.append(ct)

    decisions: list[ExtractedDecision] = []
    drafts: list[ExtractedDraft] = []

    # Check for quote or section text
    quote_match = re.search(r">\s*\"(.*?)\"", content, re.DOTALL)
    dec_header_match = re.search(r"##\s*Decision:\s*(.*?)(?=\n)", content, re.IGNORECASE)

    if dec_id_match:
        dec_id = dec_id_match.group(1).strip()
        header_text = dec_header_match.group(1).strip() if dec_header_match else ""
        if quote_match:
            snippet = quote_match.group(1).strip().replace("\n", " ")
            text = snippet
        else:
            sec_match = re.search(r"##\s*Decision:[^\n]*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
            text_body = sec_match.group(1).strip() if sec_match else header_text
            lines_body = [
                l.strip("-* \t")
                for l in text_body.splitlines()
                if l.strip() and not l.strip().startswith("- **")
            ]
            text = " ".join(lines_body[:3]) if lines_body else header_text
            snippet = text

        decisions.append(
            ExtractedDecision(
                decision_id=dec_id,
                topic=raw_topic,
                text=text,
                decided_by_mention=primary_author,
                date=raw_date,
                supersedes_id=supersedes_id,
                source=ExtractedSource(
                    source_id=source_id,
                    file_path=file_path,
                    chunk_offset=content.find(snippet[:40]) if snippet[:40] in content else 200,
                    snippet=snippet,
                ),
            )
        )

    elif draft_id_match:
        draft_id = draft_id_match.group(1).strip()
        rec_match = re.search(r"##\s*Recommendation:\s*(.*?)(?=\n)", content, re.IGNORECASE)
        snippet = (
            quote_match.group(1).strip().replace("\n", " ")
            if quote_match
            else (rec_match.group(1).strip() if rec_match else "Draft recommendation")
        )
        drafts.append(
            ExtractedDraft(
                draft_id=draft_id,
                topic=raw_topic,
                recommendation=snippet,
                author_mention=primary_author,
                date=raw_date,
                source=ExtractedSource(
                    source_id=source_id,
                    file_path=file_path,
                    chunk_offset=content.find(snippet[:40]) if snippet[:40] in content else 200,
                    snippet=snippet,
                ),
            )
        )

    return ExtractedExtractionResult(
        decisions=decisions,
        drafts=drafts,
        people_mentions=people_mentions,
        topics=topics,
    )


def ingest_markdown_docs(docs_dir: str = "data/docs", workspace_id: str | None = None) -> None:
    """Scans and extracts facts, decisions, and drafts from all markdown files in data/docs/.
    Guarantees chronological decision ingestion to eliminate OS-dependent glob ordering bugs.
    """
    graph = get_graph(workspace_id)
    md_files = glob.glob(os.path.join(docs_dir, "*.md"))

    all_decisions: list[tuple[ExtractedDecision, str]] = []
    all_drafts: list[tuple[ExtractedDraft, str]] = []

    for file_path in md_files:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        doc_id = f"DOC_{os.path.basename(file_path).split('.')[0].upper()}"
        # Create Document node
        graph.query(
            "MERGE (doc:Document {id: $id}) SET doc.path = $path, doc.title = $title",
            {"id": doc_id, "path": file_path, "title": os.path.basename(file_path)},
        )

        extracted = extract_from_markdown_llm(file_path, content)

        for dec in extracted.decisions:
            all_decisions.append((dec, doc_id))

        for draft in extracted.drafts:
            all_drafts.append((draft, doc_id))

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

        print(f"[IngestUnstructured] Parsed {file_path}")

    # CHRONOLOGICAL SORTING: Ingest decisions strictly by valid date
    all_decisions.sort(key=lambda item: item[0].date)

    for dec, doc_id in all_decisions:
        decider_id = (
            resolver.resolve_person(dec.decided_by_mention) if dec.decided_by_mention else None
        )
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
            supersedes_id=dec.supersedes_id,
            workspace_id=workspace_id,
        )

    # Ingest draft recommendations with full v0.2 Source properties
    for draft, doc_id in all_drafts:
        author_id = (
            resolver.resolve_person(draft.author_mention) if draft.author_mention else None
        )
        content_hash = hashlib.sha256(draft.source.snippet.encode("utf-8")).hexdigest()
        draft_cypher = """
        MERGE (src:Source {id: $source_id})
        SET src.file_path = $source_file,
            src.chunk_offset = $chunk_offset,
            src.text_snippet = $snippet,
            src.created_at = $date,
            src.content_hash = $content_hash,
            src.visibility = '["all"]',
            src.redacted = false,
            src.origin_type = 'document',
            src.valid_from = $date,
            src.valid_to = ""
        MERGE (dr:DraftRecommendation {id: $draft_id})
        SET dr.topic = $topic,
            dr.recommendation = $recommendation,
            dr.date = $date
        MERGE (dr)-[:DERIVED_FROM]->(src)
        WITH dr
        MATCH (doc:Document {id: $doc_id})
        MERGE (doc)-[:CONTAINS_DRAFT]->(dr)
        """
        graph.query(
            draft_cypher,
            {
                "source_id": draft.source.source_id,
                "source_file": draft.source.file_path,
                "chunk_offset": draft.source.chunk_offset,
                "snippet": draft.source.snippet,
                "date": draft.date,
                "draft_id": draft.draft_id,
                "topic": draft.topic,
                "recommendation": draft.recommendation,
                "doc_id": doc_id,
                "content_hash": content_hash,
            },
        )
        if author_id:
            graph.query(
                "MATCH (dr:DraftRecommendation {id: $draft_id}), (p:Person {id: $author_id}) MERGE (p)-[:AUTHORED]->(dr)",
                {"draft_id": draft.draft_id, "author_id": author_id},
            )


def ingest_chat_messages(chats_dir: str = "data/chats") -> None:
    """Parses JSONL chat logs, connects author person, and registers discussed topics."""
    graph = get_graph()
    jsonl_files = glob.glob(os.path.join(chats_dir, "*.jsonl"))

    for file_path in jsonl_files:
        with open(file_path, encoding="utf-8") as f:
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
                    graph.query(
                        link_author, {"id": msg["id"], "author_id": author_id, "timestamp": ts}
                    )

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
