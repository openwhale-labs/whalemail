"""Incremental fetch: list → keep messages newer than the cursor (internalDate) → get metadata → normalize.

Cursor: data/runtime/gmail-cursor.json = {"last_internal_ms": int}.
save_cursor is public so run.py can advance the cursor only after processing succeeded
(a failure never silently drops mail).
"""

from __future__ import annotations

import json
import os

from . import client
from .events import Event
from .normalize import normalize


def _load_cursor(path: str) -> int:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return int(json.load(f).get("last_internal_ms", 0))
    return 0


def save_cursor(path: str, last_ms: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"last_internal_ms": last_ms}, f)
    os.replace(tmp, path)


def poll(
    token: str,
    *,
    account: str,
    cursor_path: str,
    query: str = "in:inbox",
    max_results: int = 50,
    advance: bool = True,
) -> tuple[list[Event], int]:
    """Return (new events in ascending time order, new cursor in ms).

    advance=True: write the cursor here (simple callers).
    advance=False: leave the cursor; the caller calls save_cursor(cursor_path, new_ms) after success.
    """
    last_ms = _load_cursor(cursor_path)
    # Narrow the list call to the day before the cursor onwards, which avoids needless gets.
    # Anchoring on the cursor (not the clock) means a restart after downtime misses nothing;
    # the one-day buffer absorbs Date/internalDate skew. The exact internalDate filter below
    # keeps the "never drop" guarantee (Gmail does not guarantee list order, so no early break).
    q = query
    if last_ms > 0:
        q = f"{query} after:{last_ms // 1000 - 86400}"
    listing = client.list_messages(token, query=q, max_results=max_results)
    events: list[Event] = []
    max_ms = last_ms
    for m in listing.get("messages", []):
        msg = client.get_message(token, m["id"], fmt="metadata")
        ims = int(msg.get("internalDate", "0") or "0")
        if ims <= last_ms:
            continue
        events.append(normalize(msg, account=account))
        max_ms = max(max_ms, ims)
    events.sort(key=lambda e: e.extras.get("internal_ms", 0))
    if advance and max_ms > last_ms:
        save_cursor(cursor_path, max_ms)
    return events, max_ms
