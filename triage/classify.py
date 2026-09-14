"""Five-bucket email classification through an OpenAI-compatible chat endpoint.

Input: a batch of Events. Output: bucket / summary / action per email.
The system prompt is rules.md (bucket definitions, priority, safety lines) plus
rules.local.md when present (owner-specific rules, git-ignored).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import settings

from . import llm

BUCKETS = ("action", "decision", "fyi", "verify", "noise")
_ROOT = Path(__file__).resolve().parent.parent
_RULES_PATH = _ROOT / "rules.md"
_LOCAL_RULES_PATH = _ROOT / "rules.local.md"

_SYS_TMPL = """You are an email triage assistant. Using the rules below, put each email into exactly one bucket, \
write a one-sentence summary, and, when something needs doing, a one-sentence action.
Write summary and action in {language}.

{rules}

Output JSON only, in this shape:
{{"results": [{{"i": <index>, "bucket": "action|decision|fyi|verify|noise", "summary": "<one sentence>", "action": "<what to do, or empty string>"}}]}}
Exactly one result per email; i is the input index. Output nothing outside the JSON."""


@dataclass
class Classification:
    event_id: str
    bucket: str
    summary: str
    action: str


def _load_rules() -> str:
    """rules.md followed by rules.local.md (if it exists)."""
    try:
        rules = _RULES_PATH.read_text(encoding="utf-8")
    except OSError:
        rules = "(rules.md missing)"
    try:
        local = _LOCAL_RULES_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        local = ""
    if local:
        rules = f"{rules.rstrip()}\n\n## Owner-specific rules\n\n{local}\n"
    return rules


def _event_line(i: int, ev) -> str:
    ex = ev.extras
    return (
        f"[{i}] From: {ev.sender_name} <{ev.sender_id}>\n"
        f"    Subject: {ex.get('subject', '')}\n"
        f"    Labels: {', '.join(ex.get('labels', []))}\n"
        f"    Snippet: {ev.content[:300]}"
    )


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a model reply (tolerates ``` fences and surrounding noise)."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def classify(events: list, *, model: str | None = None) -> list[Classification]:
    """Classify a batch of Events; returns one Classification per input, in input order."""
    if not events:
        return []
    sys_prompt = _SYS_TMPL.format(rules=_load_rules(), language=settings.language_name())
    user_prompt = "Emails:\n\n" + "\n\n".join(_event_line(i, ev) for i, ev in enumerate(events))
    raw = llm.chat(
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
    )
    data = _extract_json(raw)
    by_i = {int(r["i"]): r for r in data.get("results", []) if "i" in r}
    out: list[Classification] = []
    for i, ev in enumerate(events):
        r = by_i.get(i, {})
        bucket = r.get("bucket", "fyi")
        if bucket not in BUCKETS:
            bucket = "fyi"  # unknown or missing → fyi (over-report rather than miss)
        out.append(
            Classification(
                event_id=ev.event_id,
                bucket=bucket,
                summary=r.get("summary", ""),
                action=r.get("action", ""),
            )
        )
    return out
