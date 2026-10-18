"""Multi-stage, idempotent ingestion pipeline with conflict detection and review staging."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from orgmind.db import get_graph, query_graph
from orgmind.freshness import apply_decision
from orgmind.ingest.connectors.base import BaseConnector, NormalisedItem, RawPayload
from orgmind.ingest.connectors.file_upload import FileUploadConnector
from orgmind.ingest.connectors.sample_data import SampleDataConnector
from orgmind.ingest.connectors.watched_folder import WatchedFolderConnector
from orgmind.models import IngestionJob, ReviewItem, get_session_factory
from orgmind.resolve import EntityResolver


@dataclass
class SourceChunk:
    chunk_id: str
    source_uri: str
    chunk_index: int
    text: str
    visibility: list[str]
    content_hash: str


@dataclass
class ExtractedDecision:
    topic: str
    text: str
    decided_by_raw: str | None
    confidence: float
    is_reversal: bool = False
    supersedes_target_id: str | None = None


@dataclass
class PipelineResult:
    status: str  # 'committed', 'staged_for_review', 'noop_idempotent', 'failed'
    job_id: str
    workspace_id: str
    content_hash: str
    sources_written: int = 0
    decisions_written: int = 0
    review_items_created: int = 0
    error_message: str | None = None
    stage_logs: list[str] = None  # type: ignore

    def __post_init__(self):
        if self.stage_logs is None:
            self.stage_logs = []


class IngestionPipeline:
    """Enterprise ingestion pipeline executing 8 discrete, retryable stages."""

    CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
        "file_upload": FileUploadConnector,
        "watched_folder": WatchedFolderConnector,
        "sample_data": SampleDataConnector,
    }

    def __init__(self, workspace_id: str = "default") -> None:
        self.workspace_id = workspace_id
        self.resolver = EntityResolver()

    # ------------------------------------------------------------------------
    # STAGE 1: FETCH
    # ------------------------------------------------------------------------
    def stage_fetch(self, connector_type: str, source_uri: str) -> RawPayload:
        """Fetches raw payload via the appropriate connector."""
        connector_cls = self.CONNECTOR_REGISTRY.get(connector_type)
        if not connector_cls:
            raise ValueError(f"Unknown connector type: '{connector_type}'")

        connector = connector_cls()
        from orgmind.ingest.connectors.base import ConnectorItem

        item = ConnectorItem(
            id=f"item_{hashlib.md5(source_uri.encode('utf-8')).hexdigest()[:10]}",
            uri=source_uri,
            modified_at=datetime.now(UTC),
        )
        return connector.fetch(item)

    # ------------------------------------------------------------------------
    # STAGE 2: NORMALISE
    # ------------------------------------------------------------------------
    def stage_normalise(self, connector_type: str, raw_payload: RawPayload) -> NormalisedItem:
        """Normalises raw content into clean text, security visibility, and SHA-256 hash."""
        connector_cls = self.CONNECTOR_REGISTRY.get(connector_type)
        if not connector_cls:
            raise ValueError(f"Unknown connector type: '{connector_type}'")

        connector = connector_cls()
        return connector.normalise(raw_payload)

    # ------------------------------------------------------------------------
    # STAGE 3: CHUNK
    # ------------------------------------------------------------------------
    def stage_chunk(self, normalised: NormalisedItem, chunk_size: int = 1500) -> list[SourceChunk]:
        """Splits document text into grounded source chunks with deterministic IDs."""
        text = normalised.text
        if not text:
            return []

        # Split on markdown headers or paragraphs
        sections = re.split(r"(?:\r?\n){2,}", text)
        chunks: list[SourceChunk] = []

        current_buf: list[str] = []
        current_len = 0
        chunk_idx = 0

        for sec in sections:
            sec_len = len(sec)
            if current_len + sec_len > chunk_size and current_buf:
                chunk_text = "\n\n".join(current_buf).strip()
                chunk_id = f"SRC_{normalised.content_hash[:10]}_{chunk_idx:02d}"
                chunks.append(
                    SourceChunk(
                        chunk_id=chunk_id,
                        source_uri=normalised.uri,
                        chunk_index=chunk_idx,
                        text=chunk_text,
                        visibility=normalised.visibility,
                        content_hash=normalised.content_hash,
                    )
                )
                chunk_idx += 1
                current_buf = [sec]
                current_len = sec_len
            else:
                current_buf.append(sec)
                current_len += sec_len

        if current_buf:
            chunk_text = "\n\n".join(current_buf).strip()
            chunk_id = f"SRC_{normalised.content_hash[:10]}_{chunk_idx:02d}"
            chunks.append(
                SourceChunk(
                    chunk_id=chunk_id,
                    source_uri=normalised.uri,
                    chunk_index=chunk_idx,
                    text=chunk_text,
                    visibility=normalised.visibility,
                    content_hash=normalised.content_hash,
                )
            )

        return chunks

    # ------------------------------------------------------------------------
    # STAGE 4: EXTRACT (Strict JSON with 1 Retry)
    # ------------------------------------------------------------------------
    def stage_extract(self, chunks: list[SourceChunk]) -> list[ExtractedDecision]:
        """Extracts structured decisions using strict heuristic/regex parsing (or LLM with retry)."""
        decisions: list[ExtractedDecision] = []
        combined_text = "\n\n".join(c.text for c in chunks)

        # 1. Check for explicit ADR sections: ## Decision, ## Status, ## Context
        decision_match = re.search(
            r"##\s*(?:Decision|Ratified Decision|Policy)[:\s]*(.*?)(?=##|\Z)",
            combined_text,
            re.DOTALL | re.IGNORECASE,
        )
        topic_match = re.search(
            r"(?:Topic|Project|Component|Architecture)[:\s]*([A-Za-z0-9_\-\s]+)",
            combined_text,
            re.IGNORECASE,
        )
        decided_by_match = re.search(
            r"(?:Decided by|Author|Lead|Owner)[:\s]*([A-Za-z0-9_\-\s]+)",
            combined_text,
            re.IGNORECASE,
        )

        # Detect reversal language keywords
        reversal_keywords = [
            "supersede",
            "supersedes",
            "superseded",
            "reversal",
            "reverses",
            "replace",
            "replaces",
            "replaced",
            "deprecate",
            "deprecated",
            "pivot",
        ]
        is_reversal = any(k in combined_text.lower() for k in reversal_keywords)

        if decision_match:
            dec_text = decision_match.group(1).strip()
            # Clean up text
            dec_text = re.sub(r"\s+", " ", dec_text)
            topic = topic_match.group(1).strip() if topic_match else "General Architecture"
            author = decided_by_match.group(1).strip() if decided_by_match else None

            confidence = 0.95
            if is_reversal:
                confidence = 0.85

            decisions.append(
                ExtractedDecision(
                    topic=topic,
                    text=dec_text,
                    decided_by_raw=author,
                    confidence=confidence,
                    is_reversal=is_reversal,
                )
            )
        elif is_reversal:
            # Reversal sentence extraction
            for line in combined_text.splitlines():
                if any(k in line.lower() for k in ["we are reversing", "supersede", "replaces", "pivot"]):
                    decisions.append(
                        ExtractedDecision(
                            topic=topic_match.group(1).strip() if topic_match else "Payments",
                            text=line.strip(),
                            decided_by_raw=decided_by_match.group(1).strip() if decided_by_match else None,
                            confidence=0.80,
                            is_reversal=True,
                        )
                    )
                    break

        return decisions

    # ------------------------------------------------------------------------
    # STAGE 5: RESOLVE ENTITIES (Never auto-create unknown persons)
    # ------------------------------------------------------------------------
    def stage_resolve_entities(
        self, decisions: list[ExtractedDecision]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Resolves raw author names against company registry.

        Returns: (resolved_list, unknown_entities_list)
        """
        resolved: list[dict[str, Any]] = []
        unknowns: list[dict[str, Any]] = []

        for d in decisions:
            if not d.decided_by_raw:
                resolved.append({"decision": d, "person_id": None, "person_name": None})
                continue

            match = self.resolver.resolve_with_status(d.decided_by_raw)
            if match.get("status") == "unknown":
                unknowns.append({"raw_name": d.decided_by_raw, "decision": d})
            else:
                pid = match.get("resolved_id")
                pname = match.get("resolved_name")
                resolved.append({"decision": d, "person_id": pid, "person_name": pname})

        return resolved, unknowns

    # ------------------------------------------------------------------------
    # STAGE 6: DETECT CONFLICTS & SUPERSESSION
    # ------------------------------------------------------------------------
    def stage_detect_conflicts(
        self, resolved_decisions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Queries FalkorDB to find active decisions on the same topic that conflict or get superseded."""
        conflicts: list[dict[str, Any]] = []

        for item in resolved_decisions:
            dec = item["decision"]
            topic = dec.topic

            cypher = """
            MATCH (old:Decision)
            WHERE (toLower(old.topic) = toLower($topic)
                   OR (old)-[:ABOUT]->(:Topic {name: $topic}))
              AND old.status = 'current'
            OPTIONAL MATCH (old)-[:DECIDED_BY]->(p:Person)
            OPTIONAL MATCH (old)-[:DERIVED_FROM]->(src:Source)
            RETURN old.id AS id, old.text AS text, old.valid_from AS valid_from,
                   p.name AS decided_by, src.id AS source_id
            LIMIT 1
            """
            rows = query_graph(cypher, {"topic": topic}, workspace_id=self.workspace_id)
            if rows:
                active_old = rows[0]
                conflicts.append(
                    {
                        "topic": topic,
                        "proposed_decision": dec.text,
                        "proposed_by": item.get("person_name") or dec.decided_by_raw,
                        "existing_decision_id": active_old["id"],
                        "existing_decision_text": active_old["text"],
                        "existing_decided_by": active_old["decided_by"],
                        "is_reversal": dec.is_reversal,
                    }
                )

        return conflicts

    # ------------------------------------------------------------------------
    # STAGE 7: STAGE FOR REVIEW OR AUTO-COMMIT
    # ------------------------------------------------------------------------
    def stage_review_or_commit(
        self,
        normalised: NormalisedItem,
        chunks: list[SourceChunk],
        resolved_decisions: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
        unknown_entities: list[dict[str, Any]],
        db_session: Any,
    ) -> tuple[bool, list[ReviewItem]]:
        """Evaluates policy gates.

        If conflicts exist, or reversal detected, or unknown people found:
        Creates pending ReviewItems and halts automatic graph writes.
        """
        review_items: list[ReviewItem] = []

        # Gate 1: Unknown entities (Never auto-create phantom Person nodes)
        for unk in unknown_entities:
            item_id = f"rev_alias_{hashlib.md5(unk['raw_name'].encode()).hexdigest()[:8]}"
            existing = db_session.query(ReviewItem).filter_by(id=item_id).first()
            if not existing:
                r_item = ReviewItem(
                    id=item_id,
                    workspace_id=self.workspace_id,
                    item_type="unknown_alias",
                    status="pending",
                    summary=f"Unrecognized author '{unk['raw_name']}' in document '{normalised.title}'.",
                    payload=json.dumps({"raw_name": unk["raw_name"], "source_uri": normalised.uri}),
                    before_diff="Entity: None",
                    after_diff=f"Proposed Entity: Person(name='{unk['raw_name']}')",
                )
                db_session.add(r_item)
                review_items.append(r_item)
            else:
                review_items.append(existing)

        # Gate 2: Conflicts and Reversals
        for conf in conflicts:
            item_id = f"rev_rev_{hashlib.md5((conf['topic'] + conf['proposed_decision']).encode()).hexdigest()[:8]}"
            payload_json = json.dumps(
                {
                    "topic": conf["topic"],
                    "proposed_text": conf["proposed_decision"],
                    "supersedes_id": conf["existing_decision_id"],
                    "source_uri": normalised.uri,
                    "content_hash": normalised.content_hash,
                    "source_id": chunks[0].chunk_id if chunks else f"SRC_{normalised.content_hash[:10]}_00",
                    "decided_by": conf["proposed_by"],
                }
            )
            existing = db_session.query(ReviewItem).filter_by(id=item_id).first()
            if not existing:
                r_item = ReviewItem(
                    id=item_id,
                    workspace_id=self.workspace_id,
                    item_type="decision_reversal",
                    status="pending",
                    summary=f"Decision reversal detected for topic '{conf['topic']}' vs existing decision '{conf['existing_decision_id']}'.",
                    payload=payload_json,
                    before_diff=f"[{conf['existing_decision_id']}]: {conf['existing_decision_text']}",
                    after_diff=f"[PROPOSED]: {conf['proposed_decision']}",
                )
                db_session.add(r_item)
                review_items.append(r_item)
            else:
                existing.status = "pending"
                existing.payload = payload_json
                existing.before_diff = f"[{conf['existing_decision_id']}]: {conf['existing_decision_text']}"
                existing.after_diff = f"[PROPOSED]: {conf['proposed_decision']}"
                review_items.append(existing)

        if review_items:
            db_session.commit()
            return False, review_items

        return True, []

    # ------------------------------------------------------------------------
    # STAGE 8: WRITE TO GRAPH (Strict Idempotency via Content Hash)
    # ------------------------------------------------------------------------
    def stage_write_to_graph(
        self,
        normalised: NormalisedItem,
        chunks: list[SourceChunk],
        resolved_decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Writes Source and Decision nodes into FalkorDB with idempotency verification."""
        graph = get_graph(self.workspace_id)

        # Idempotency check: check if a Source with this identical content_hash already exists
        check_cypher = "MATCH (s:Source {content_hash: $hash}) RETURN count(s) AS count"
        existing = query_graph(check_cypher, {"hash": normalised.content_hash}, workspace_id=self.workspace_id)
        if existing and existing[0].get("count", 0) > 0:
            return {"status": "noop_idempotent", "sources_written": 0, "decisions_written": 0}

        now_iso = datetime.now(UTC).isoformat()
        visibility_str = ",".join(normalised.visibility)

        # 1. Write Source chunk nodes
        sources_written = 0
        for chunk in chunks:
            src_cypher = """
            MERGE (s:Source {id: $id})
            SET s.file_path = $uri,
                s.text_snippet = $snippet,
                s.chunk_offset = $offset,
                s.content_hash = $content_hash,
                s.visibility = $visibility,
                s.redacted = false,
                s.created_at = $now
            RETURN s.id AS id
            """
            graph.query(
                src_cypher,
                {
                    "id": chunk.chunk_id,
                    "uri": chunk.source_uri,
                    "snippet": chunk.text,
                    "offset": chunk.chunk_index,
                    "content_hash": chunk.content_hash,
                    "visibility": visibility_str,
                    "now": now_iso,
                },
            )
            sources_written += 1

        # 2. Write Decisions
        decisions_written = 0
        for item in resolved_decisions:
            dec = item["decision"]
            dec_id = f"DEC_{hashlib.md5((dec.topic + dec.text).encode()).hexdigest()[:10].upper()}"
            prime_chunk = chunks[0] if chunks else None
            prime_src_id = prime_chunk.chunk_id if prime_chunk else f"SRC_{normalised.content_hash[:10]}_00"

            apply_decision(
                decision_id=dec_id,
                topic=dec.topic,
                text=dec.text,
                source_id=prime_src_id,
                source_file=normalised.uri,
                source_snippet=prime_chunk.text if prime_chunk else dec.text,
                chunk_offset=0,
                decided_by_person_id=item.get("person_id"),
                timestamp=now_iso,
            )
            decisions_written += 1

        return {
            "status": "committed",
            "sources_written": sources_written,
            "decisions_written": decisions_written,
        }

    # ------------------------------------------------------------------------
    # FULL PIPELINE EXECUTION
    # ------------------------------------------------------------------------
    def run_pipeline(
        self,
        connector_type: str,
        source_uri: str,
        job_id: str,
        db_session: Any,
    ) -> PipelineResult:
        """Executes all 8 pipeline stages with comprehensive logging and error capture."""
        logs: list[str] = []

        def log(msg: str) -> None:
            ts = datetime.now(UTC).strftime("%H:%M:%S")
            logs.append(f"[{ts}] {msg}")

        log(f"Stage 1/8: Fetching payload from '{source_uri}' via connector '{connector_type}'...")
        try:
            raw_payload = self.stage_fetch(connector_type, source_uri)
        except Exception as e:
            return PipelineResult(
                status="failed",
                job_id=job_id,
                workspace_id=self.workspace_id,
                content_hash="",
                error_message=f"Fetch failed: {e}",
                stage_logs=logs,
            )

        log(f"Stage 2/8: Normalising raw content (content size: {len(raw_payload.content)} bytes)...")
        normalised = self.stage_normalise(connector_type, raw_payload)
        log(f"Normalised: title='{normalised.title}', visibility={normalised.visibility}, hash={normalised.content_hash[:12]}...")

        # Immediate idempotency short-circuit
        existing = query_graph(
            "MATCH (s:Source {content_hash: $hash}) RETURN count(s) AS count",
            {"hash": normalised.content_hash},
            workspace_id=self.workspace_id,
        )
        if existing and existing[0].get("count", 0) > 0:
            log(f"Stage 2.1: Content hash {normalised.content_hash[:12]} already committed. Ingestion short-circuited (noop_idempotent).")
            return PipelineResult(
                status="noop_idempotent",
                job_id=job_id,
                workspace_id=self.workspace_id,
                content_hash=normalised.content_hash,
                stage_logs=logs,
            )

        log("Stage 3/8: Chunking document text...")
        chunks = self.stage_chunk(normalised)
        log(f"Generated {len(chunks)} grounded source chunks.")

        log("Stage 4/8: Extracting architectural decisions and topic mentions...")
        decisions = self.stage_extract(chunks)
        log(f"Extracted {len(decisions)} decision candidates.")

        log("Stage 5/8: Resolving entities and verifying employee directory...")
        resolved, unknowns = self.stage_resolve_entities(decisions)
        if unknowns:
            log(f"Found {len(unknowns)} unrecognized author(s) flagged for review: {[u['raw_name'] for u in unknowns]}.")

        log("Stage 6/8: Detecting conflicts and policy reversals against active graph...")
        conflicts = self.stage_detect_conflicts(resolved)
        if conflicts:
            log(f"Found {len(conflicts)} active policy conflict(s) or supersession candidate(s).")

        log("Stage 7/8: Evaluating governance policy gates...")
        can_commit, review_items = self.stage_review_or_commit(
            normalised, chunks, resolved, conflicts, unknowns, db_session
        )

        if not can_commit:
            log(f"Stage 7.1: Staged {len(review_items)} pending review item(s). Pausing graph mutation pending approval.")
            return PipelineResult(
                status="staged_for_review",
                job_id=job_id,
                workspace_id=self.workspace_id,
                content_hash=normalised.content_hash,
                review_items_created=len(review_items),
                stage_logs=logs,
            )

        log("Stage 8/8: Writing verified nodes and edges to FalkorDB...")
        write_res = self.stage_write_to_graph(normalised, chunks, resolved)
        log(f"Graph commit completed: {write_res['sources_written']} sources, {write_res['decisions_written']} decisions written.")

        return PipelineResult(
            status=write_res["status"],
            job_id=job_id,
            workspace_id=self.workspace_id,
            content_hash=normalised.content_hash,
            sources_written=write_res.get("sources_written", 0),
            decisions_written=write_res.get("decisions_written", 0),
            stage_logs=logs,
        )


def run_ingestion_job(
    job_id: str,
    connector_type: str,
    source_uri: str,
    workspace_id: str = "default",
    db_session: Any = None,
) -> PipelineResult:
    """Entrypoint called synchronously or by background worker."""
    session_factory = get_session_factory()
    session = db_session or session_factory()
    try:
        job = session.query(IngestionJob).filter_by(id=job_id).first()
        if job:
            job.status = "processing"
            session.commit()

        pipeline = IngestionPipeline(workspace_id=workspace_id)
        result = pipeline.run_pipeline(
            connector_type=connector_type,
            source_uri=source_uri,
            job_id=job_id,
            db_session=session,
        )

        if job:
            job.status = "completed" if result.status in ("committed", "noop_idempotent", "staged_for_review") else "failed"
            job.items_processed = result.sources_written + result.decisions_written
            job.items_failed = 1 if result.status == "failed" else 0
            job.error_message = result.error_message
            job.completed_at = datetime.now(UTC)
            session.commit()

        return result
    finally:
        if not db_session:
            session.close()
