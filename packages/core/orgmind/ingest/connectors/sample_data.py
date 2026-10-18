"""Sample Data Connector for ingesting repository seed datasets."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orgmind.ingest.connectors.base import BaseConnector, ConnectorItem, NormalisedItem, RawPayload
from orgmind.ingest.connectors.file_upload import FileUploadConnector


class SampleDataConnector(BaseConnector):
    """Ingests baseline seed datasets (docs, chat logs, tickets) from the repository data folder."""

    connector_type: str = "sample_data"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.data_dir = Path(self.config.get("data_dir", "data"))
        self._file_normaliser = FileUploadConnector()

    def list_changes(self, since: datetime | None = None) -> list[ConnectorItem]:
        """Lists all sample files available in data/docs and data/chat."""
        items: list[ConnectorItem] = []
        if not self.data_dir.exists():
            return items

        # 1. Documents
        docs_dir = self.data_dir / "docs"
        if docs_dir.exists():
            for doc_file in docs_dir.glob("*.md"):
                mtime = datetime.fromtimestamp(doc_file.stat().st_mtime, tz=UTC)
                if since is None or mtime > since:
                    items.append(
                        ConnectorItem(
                            id=f"doc_{doc_file.stem}",
                            uri=str(doc_file),
                            modified_at=mtime,
                            metadata={"category": "document", "filename": doc_file.name},
                        )
                    )

        # 2. Chat JSONL files
        chat_dir = self.data_dir / "chat"
        if chat_dir.exists():
            for chat_file in chat_dir.glob("*.jsonl"):
                mtime = datetime.fromtimestamp(chat_file.stat().st_mtime, tz=UTC)
                if since is None or mtime > since:
                    items.append(
                        ConnectorItem(
                            id=f"chat_{chat_file.stem}",
                            uri=str(chat_file),
                            modified_at=mtime,
                            metadata={"category": "chat", "filename": chat_file.name},
                        )
                    )

        # 3. Tickets JSON
        tickets_file = self.data_dir / "tickets.json"
        if tickets_file.exists():
            mtime = datetime.fromtimestamp(tickets_file.stat().st_mtime, tz=UTC)
            if since is None or mtime > since:
                items.append(
                    ConnectorItem(
                        id="tickets_catalog",
                        uri=str(tickets_file),
                        modified_at=mtime,
                        metadata={"category": "tickets", "filename": tickets_file.name},
                    )
                )

        return items

    def fetch(self, item: ConnectorItem) -> RawPayload:
        """Fetches raw content for the specified seed item."""
        path = Path(item.uri)
        if not path.exists():
            raise FileNotFoundError(f"Sample data file not found: {item.uri}")

        raw_bytes = path.read_bytes()
        ext = path.suffix.lower()
        content_type = "text/markdown" if ext == ".md" else "application/json"

        return RawPayload(
            id=item.id,
            uri=item.uri,
            content=raw_bytes,
            content_type=content_type,
            metadata={"filename": path.name, **item.metadata},
        )

    def normalise(self, payload: RawPayload) -> NormalisedItem:
        """Normalises documents or chat messages into standard schema."""
        category = payload.metadata.get("category", "")
        if category == "chat":
            return self._normalise_chat(payload)
        elif category == "tickets":
            return self._normalise_tickets(payload)
        else:
            return self._file_normaliser.normalise(payload)

    def _normalise_chat(self, payload: RawPayload) -> NormalisedItem:
        raw_text = (
            payload.content.decode("utf-8")
            if isinstance(payload.content, bytes)
            else str(payload.content)
        )
        messages_text = []
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                author = msg.get("author") or msg.get("user") or "unknown"
                ts = msg.get("timestamp") or ""
                text = msg.get("text") or msg.get("message") or ""
                messages_text.append(f"[{ts}] {author}: {text}")
            except Exception:
                messages_text.append(line)

        combined_text = "\n".join(messages_text)
        content_hash = NormalisedItem.compute_hash(combined_text)

        channel_name = payload.metadata.get("filename", "").replace(".jsonl", "")
        return NormalisedItem(
            id=payload.id,
            item_type="message",
            title=f"Chat Log #{channel_name}",
            text=combined_text,
            uri=payload.uri,
            author_raw=None,
            visibility=["all"],
            content_hash=content_hash,
            created_at=datetime.now(UTC),
            metadata={"channel": channel_name, **payload.metadata},
        )

    def _normalise_tickets(self, payload: RawPayload) -> NormalisedItem:
        raw_text = (
            payload.content.decode("utf-8")
            if isinstance(payload.content, bytes)
            else str(payload.content)
        )
        tickets_data = []
        try:
            tickets_data = json.loads(raw_text)
        except Exception:
            pass

        summary_lines = []
        for t in tickets_data:
            tid = t.get("id") or t.get("ticket_id")
            title = t.get("title") or ""
            desc = t.get("description") or ""
            status = t.get("status") or ""
            summary_lines.append(f"Ticket [{tid}] ({status}): {title} - {desc}")

        combined_text = "\n".join(summary_lines)
        content_hash = NormalisedItem.compute_hash(combined_text)

        return NormalisedItem(
            id=payload.id,
            item_type="document",
            title="Tickets Catalog",
            text=combined_text,
            uri=payload.uri,
            author_raw=None,
            visibility=["all"],
            content_hash=content_hash,
            created_at=datetime.now(UTC),
            metadata={"ticket_count": len(tickets_data), **payload.metadata},
        )
