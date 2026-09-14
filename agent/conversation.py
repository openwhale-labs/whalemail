"""Conversation state for the bot: persistence, a token budget, and compaction past the budget.

The session is never cleared by time; the only reset is reset() (the /new command).
Past the budget, the early part of the conversation is summarised by the LLM instead of
being cut by message count.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

_STORE = Path(__file__).resolve().parent.parent / "data/runtime/bot-conversation.json"


def _est_tokens(messages: list) -> int:
    """Rough token estimate without a tokenizer: characters / 3 plus a fixed per-message cost."""
    return sum(len(m.get("content") or "") // 3 + 8 for m in messages)


def load() -> list:
    try:
        return json.loads(_STORE.read_text(encoding="utf-8")).get("messages", [])
    except Exception:
        return []


def save(messages: list) -> None:
    try:
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"messages": messages}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_STORE)
    except Exception:
        pass


def reset() -> None:
    """/new: clear the conversation, including any summary."""
    save([])


def maybe_compact(messages: list, summarize: Callable[[str], str]) -> list:
    """Past the token budget, replace everything but the last `keep` messages with one summary.

    summarize(text) -> str is injected by the caller (an LLM call). Budget and keep count are
    configurable through the environment. If summarising fails or returns nothing, the
    conversation is returned unchanged and compaction is retried next turn.
    """
    budget = int(os.environ.get("WHALEMAIL_CONV_BUDGET", "40000"))
    keep = int(os.environ.get("WHALEMAIL_CONV_KEEP", "6"))
    if _est_tokens(messages) <= budget or len(messages) <= keep + 1:
        return messages
    head, tail = messages[:-keep], messages[-keep:]
    convo = "\n".join(f"{m.get('role')}: {m.get('content', '')}" for m in head)
    try:
        summary = summarize(convo).strip()
    except Exception:
        return messages
    if not summary:
        return messages
    return [{"role": "system", "content": f"[Summary of earlier conversation]\n{summary}"}, *tail]
