"""File Upload Connector for markdown, text, and PDF files."""

import io
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orgmind.ingest.connectors.base import BaseConnector, ConnectorItem, NormalisedItem, RawPayload


class FileUploadConnector(BaseConnector):
    """Handles manual file uploads for .md, .txt, and .pdf documents."""

    connector_type: str = "file_upload"

    SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}

    def list_changes(self, since: datetime | None = None) -> list[ConnectorItem]:
        """File upload is on-demand, so list_changes returns items from configured upload directory if set."""
        upload_dir = self.config.get("upload_dir")
        if not upload_dir or not os.path.exists(upload_dir):
            return []

        items: list[ConnectorItem] = []
        for root, _, files in os.walk(upload_dir):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    full_path = os.path.join(root, f)
                    mtime = datetime.fromtimestamp(os.path.getmtime(full_path), tz=UTC)
                    if since is None or mtime > since:
                        items.append(
                            ConnectorItem(
                                id=f"upload_{Path(f).stem}",
                                uri=full_path,
                                modified_at=mtime,
                                metadata={"filename": f, "extension": ext},
                            )
                        )
        return items

    def fetch(self, item: ConnectorItem) -> RawPayload:
        """Reads raw binary content from disk."""
        path = Path(item.uri)
        if not path.exists():
            raise FileNotFoundError(f"Uploaded file not found: {item.uri}")

        raw_bytes = path.read_bytes()
        ext = path.suffix.lower()

        content_type = "text/plain"
        if ext == ".md":
            content_type = "text/markdown"
        elif ext == ".pdf":
            content_type = "application/pdf"

        return RawPayload(
            id=item.id,
            uri=item.uri,
            content=raw_bytes,
            content_type=content_type,
            metadata={"filename": path.name, "extension": ext, **item.metadata},
        )

    def normalise(self, payload: RawPayload) -> NormalisedItem:
        """Extracts text, metadata, and visibility from raw content."""
        ext = payload.metadata.get("extension", "").lower()
        if not ext and payload.uri:
            ext = Path(payload.uri).suffix.lower()

        text = ""
        author_raw: str | None = None
        visibility: list[str] = ["all"]
        title = payload.metadata.get("filename", payload.id)

        if ext == ".pdf":
            text = self._extract_pdf_text(payload.content)
        else:
            if isinstance(payload.content, bytes):
                try:
                    text = payload.content.decode("utf-8")
                except UnicodeDecodeError:
                    text = payload.content.decode("latin-1", errors="replace")
            else:
                text = str(payload.content)

        # Parse markdown frontmatter or header metadata if present
        if ext == ".md" or "---" in text[:100]:
            frontmatter_meta, body = self._parse_frontmatter(text)
            if frontmatter_meta:
                text = body
                if "author" in frontmatter_meta:
                    author_raw = str(frontmatter_meta["author"])
                if "title" in frontmatter_meta:
                    title = str(frontmatter_meta["title"])
                if "visibility" in frontmatter_meta:
                    vis_val = frontmatter_meta["visibility"]
                    if isinstance(vis_val, list):
                        visibility = [str(v) for v in vis_val]
                    elif isinstance(vis_val, str):
                        visibility = [v.strip() for v in vis_val.split(",")]

        # If title is still a filename, try extracting the first Markdown H1
        if title == payload.metadata.get("filename"):
            h1_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()

        # Check for inline author annotations (e.g., "Author: Alice Chen", "Decided by: Priya")
        if not author_raw:
            author_match = re.search(
                r"(?:Author|Decided by|Owner|Lead):\s*([A-Za-z0-9_\s]+)", text, re.IGNORECASE
            )
            if author_match:
                author_raw = author_match.group(1).strip()

        content_bytes = (
            payload.content if isinstance(payload.content, bytes) else text.encode("utf-8")
        )
        content_hash = NormalisedItem.compute_hash(content_bytes)

        return NormalisedItem(
            id=payload.id,
            item_type="document",
            title=title,
            text=text.strip(),
            uri=payload.uri,
            author_raw=author_raw,
            visibility=visibility,
            content_hash=content_hash,
            created_at=datetime.now(UTC),
            metadata=payload.metadata,
        )

    def _extract_pdf_text(self, content: bytes | str) -> str:
        """Extracts text content from PDF binary using pypdf."""
        try:
            import pypdf

            stream = io.BytesIO(content if isinstance(content, bytes) else content.encode("latin-1"))
            reader = pypdf.PdfReader(stream)
            pages_text = []
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                pages_text.append(f"--- Page {idx + 1} ---\n{page_text}")
            return "\n\n".join(pages_text)
        except Exception as e:
            return f"[PDF Extraction Error: {e}]"

    def _parse_frontmatter(self, text: str) -> tuple[dict[str, Any], str]:
        """Simple YAML frontmatter parser without requiring full PyYAML."""
        if not text.startswith("---"):
            return {}, text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text

        raw_yaml = parts[1]
        body = parts[2].lstrip("\r\n")

        meta: dict[str, Any] = {}
        for line in raw_yaml.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if v.startswith("[") and v.endswith("]"):
                    items = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                    meta[k] = items
                else:
                    meta[k] = v

        return meta, body
