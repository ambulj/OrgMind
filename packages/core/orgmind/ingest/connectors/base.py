"""Base Connector Interface and Standard Normalised Data Models."""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConnectorItem:
    """Represents a discovered item from an external data source."""

    id: str
    uri: str
    modified_at: datetime
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPayload:
    """Represents the raw, unparsed payload fetched from a connector."""

    id: str
    uri: str
    content: bytes | str
    content_type: str  # e.g., 'text/markdown', 'text/plain', 'application/pdf', 'application/json'
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalisedItem:
    """Represents a standardized document or message with security visibility and hash."""

    id: str
    item_type: str  # 'document' or 'message'
    title: str
    text: str
    uri: str
    author_raw: str | None
    visibility: list[str]  # e.g. ['all'] or ['Admin', 'Auditor']
    content_hash: str
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def compute_hash(cls, content: bytes | str) -> str:
        """Computes a SHA-256 hexadecimal hash over raw content."""
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content
        return hashlib.sha256(content_bytes).hexdigest()


class BaseConnector(ABC):
    """Abstract interface contract for all OrgMind data connectors."""

    connector_type: str = "base"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    def list_changes(self, since: datetime | None = None) -> list[ConnectorItem]:
        """Lists items created or modified since the specified timestamp.

        If since is None, performs a full initial catalog listing.
        """
        pass

    @abstractmethod
    def fetch(self, item: ConnectorItem) -> RawPayload:
        """Fetches the raw file or message payload for the specified item."""
        pass

    @abstractmethod
    def normalise(self, payload: RawPayload) -> NormalisedItem:
        """Normalises the raw payload into a standard NormalisedItem.

        Must extract plain text, determine visibility ACL, and compute a cryptographic
        content_hash (SHA-256).
        """
        pass
