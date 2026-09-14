"""Event → data/events/gmail-events.jsonl (append-only, de-duplicated by event_id)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable

from .events import Event


def _seen_ids(path: str) -> set[str]:
    ids: set[str] = set()
    if not os.path.exists(path):
        return ids
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["event_id"])
            except (ValueError, KeyError):
                continue
    return ids


def append_events(events: Iterable[Event], path: str) -> int:
    """Append events not seen before; returns the number added."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    seen = _seen_ids(path)
    n = 0
    with open(path, "a", encoding="utf-8") as f:
        for ev in events:
            if ev.event_id in seen:
                continue
            f.write(ev.to_json() + "\n")
            seen.add(ev.event_id)
            n += 1
    return n
