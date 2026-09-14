"""config/gmail-allowlist.json: fetch scope (fetch_query) and labels to skip (exclude_labels)."""

from __future__ import annotations

import json
import os

# Default: everything received (All Mail minus spam/trash/chats/sent), which also covers mail
# that a filter archived past the inbox.
_DEFAULT_QUERY = "-in:spam -in:trash -in:chats -in:sent"


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {"account": "", "fetch_query": _DEFAULT_QUERY, "exclude_labels": set()}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return {
        "account": d.get("account", ""),
        "fetch_query": d.get("fetch_query", _DEFAULT_QUERY),
        "exclude_labels": set(d.get("exclude_labels", [])),
    }


def excluded(labels: list[str], exclude_set: set[str]) -> bool:
    """True when any of the email's labels is excluded (skipped entirely, not even counted as noise)."""
    return bool(set(labels) & exclude_set)
