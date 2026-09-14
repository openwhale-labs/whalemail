"""Event schema for Gmail messages and event_id generation.

The field set and order are shared with sibling source adapters (chat platforms use the same
shape), so events from different sources can be aggregated. Email-specific data
(subject/to/cc/labels/thread_id) lives in extras.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


# Gmail's top-level MIME type only distinguishes plain text from HTML; anything else is "other".
def content_type_of(mime: str) -> str:
    m = (mime or "").lower()
    if m == "text/plain":
        return "text"
    if m == "text/html":
        return "html"
    return "other"


def make_event_id(account: str, msg_id: str) -> str:
    """Gmail message ids are globally unique; an account hash prefix supports multi-account merging."""
    acct8 = hashlib.md5(account.encode("utf-8")).hexdigest()[:8]
    return f"gmail_{acct8}_{msg_id}"


@dataclass
class Event:
    event_id: str
    account: str  # receiving Gmail address
    chat_type: str  # always "email"
    chat_id: str  # primary label id (e.g. INBOX)
    chat_name: str  # label display name
    sender_id: str  # From address
    sender_name: str  # From display name
    timestamp: str  # ISO 8601 with offset
    content_type: str  # "text" | "html" | "other"
    content: str  # body text (the snippet in the metadata-only fetch)
    extras: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    platform: str = "gmail"
    source: str = "gmail_api"
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Stable field order for diffs and human reading.
        ordered = [
            "event_id",
            "platform",
            "account",
            "chat_type",
            "chat_id",
            "chat_name",
            "sender_id",
            "sender_name",
            "timestamp",
            "content_type",
            "content",
            "extras",
            "source",
            "confidence",
            "raw",
        ]
        return {k: d[k] for k in ordered}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
