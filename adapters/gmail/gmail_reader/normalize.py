"""Gmail message (metadata format) → Event."""

from __future__ import annotations

import email.utils
from datetime import datetime

import settings

from .events import Event, make_event_id


def _headers_map(msg: dict) -> dict[str, str]:
    payload = msg.get("payload", {})
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _parse_from(value: str) -> tuple[str, str]:
    name, addr = email.utils.parseaddr(value)
    return (addr or value), (name or addr or value)


def normalize(msg: dict, *, account: str, label_names: dict[str, str] | None = None) -> Event:
    h = _headers_map(msg)
    sender_id, sender_name = _parse_from(h.get("from", ""))
    internal_ms = int(msg.get("internalDate", "0") or "0")
    ts = datetime.fromtimestamp(internal_ms / 1000, settings.tz()).isoformat()
    label_ids = msg.get("labelIds", [])
    chat_id = "INBOX" if "INBOX" in label_ids else (label_ids[0] if label_ids else "INBOX")
    names = label_names or {}
    chat_name = names.get(chat_id, "Inbox" if chat_id == "INBOX" else chat_id)
    return Event(
        event_id=make_event_id(account, msg["id"]),
        account=account,
        chat_type="email",
        chat_id=chat_id,
        chat_name=chat_name,
        sender_id=sender_id,
        sender_name=sender_name,
        timestamp=ts,
        content_type="text",  # the metadata format carries no body; the snippet stands in
        content=msg.get("snippet", ""),
        extras={
            "subject": h.get("subject", ""),
            "from": h.get("from", ""),
            "to": h.get("to", ""),
            "cc": h.get("cc", ""),
            "date": h.get("date", ""),
            "labels": label_ids,
            "thread_id": msg.get("threadId", ""),
            "snippet": msg.get("snippet", ""),
            "internal_ms": internal_ms,
        },
        raw={"msg_id": msg["id"], "thread_id": msg.get("threadId", ""), "label_ids": label_ids},
    )
