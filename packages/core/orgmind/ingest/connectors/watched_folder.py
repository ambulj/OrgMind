"""Watched Folder Connector for continuous directory synchronization."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orgmind.ingest.connectors.base import BaseConnector, ConnectorItem, NormalisedItem, RawPayload
from orgmind.ingest.connectors.file_upload import FileUploadConnector


class WatchedFolderConnector(BaseConnector):
    """Monitors a specified filesystem directory for added or modified files."""

    connector_type: str = "watched_folder"

    SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".json", ".jsonl"}

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.watch_dir = self.config.get("watch_dir", "data/watched")
        self._file_normaliser = FileUploadConnector()

    def list_changes(self, since: datetime | None = None) -> list[ConnectorItem]:
        """Lists files in the watched directory created or modified since timestamp."""
        dir_path = Path(self.watch_dir)
        if not dir_path.exists():
            return []

        changes: list[ConnectorItem] = []
        for root, _, files in os.walk(dir_path):
            for file_name in files:
                ext = Path(file_name).suffix.lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    full_path = Path(root) / file_name
                    mtime = datetime.fromtimestamp(full_path.stat().st_mtime, tz=UTC)
                    if since is None or mtime > since:
                        changes.append(
                            ConnectorItem(
                                id=f"watched_{full_path.stem}",
                                uri=str(full_path),
                                modified_at=mtime,
                                metadata={"filename": file_name, "extension": ext},
                            )
                        )
        return changes

    def fetch(self, item: ConnectorItem) -> RawPayload:
        """Fetches raw payload from the watched file path."""
        path = Path(item.uri)
        if not path.exists():
            raise FileNotFoundError(f"Watched file not found: {item.uri}")

        content_bytes = path.read_bytes()
        ext = path.suffix.lower()

        content_type = "text/plain"
        if ext == ".md":
            content_type = "text/markdown"
        elif ext == ".pdf":
            content_type = "application/pdf"
        elif ext in (".json", ".jsonl"):
            content_type = "application/json"

        return RawPayload(
            id=item.id,
            uri=item.uri,
            content=content_bytes,
            content_type=content_type,
            metadata={"filename": path.name, "extension": ext, **item.metadata},
        )

    def normalise(self, payload: RawPayload) -> NormalisedItem:
        """Normalises the payload using the file upload parser."""
        return self._file_normaliser.normalise(payload)
