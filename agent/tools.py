"""Gmail tools for the agent: search_email / read_thread / draft_reply.

TOOLS is the OpenAI function-calling schema; run_tool executes a call. Reads go through
client, drafting through client.create_draft. Nothing here sends mail.
"""

from __future__ import annotations

import base64
import html
import re

from adapters.gmail.gmail_reader import client
from digest.i18n import t

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_email",
            "description": (
                "Search email threads with Gmail query syntax; returns matching threads "
                "(thread_id + snippet). Examples: from:x@y.com, subject:invoice, newer_than:7d, "
                '"exact phrase".'
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Gmail query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_thread",
            "description": (
                "Read a full thread: sender, date, subject and body of every message, "
                "including the user's own earlier replies."
            ),
            "parameters": {
                "type": "object",
                "properties": {"thread_id": {"type": "string"}},
                "required": ["thread_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_reply",
            "description": (
                "Create a reply draft in the given thread. Not sent: it goes to the Gmail Drafts "
                "folder for the user to review."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string"},
                    "to": {"type": "string", "description": "recipient address (bare email)"},
                    "subject": {"type": "string"},
                    "body": {"type": "string", "description": "email body"},
                },
                "required": ["thread_id", "to", "subject", "body"],
            },
        },
    },
]


def _decode(part: dict) -> str:
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", "replace")
    except Exception:
        return ""


def _extract_text(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        return _decode(payload)
    if mime == "text/html":
        t_ = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", _decode(payload), flags=re.S)
        t_ = re.sub(r"<[^>]+>", " ", t_)
        return re.sub(r"[ \t]+", " ", html.unescape(t_)).strip()
    for p in payload.get("parts", []):
        txt = _extract_text(p)
        if txt:
            return txt
    return ""


def _hdr(msg: dict, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def run_tool(token: str, name: str, args: dict) -> dict:
    if name == "search_email":
        r = client.search_threads(token, query=args["query"], max_results=15)
        out = [
            {"thread_id": th["id"], "snippet": th.get("snippet", "")[:160]}
            for th in r.get("threads", [])
        ]
        return {"threads": out} if out else {"threads": [], "note": t("tool.no_threads")}
    if name == "read_thread":
        th = client.get_thread(token, args["thread_id"], fmt="full")
        msgs = [
            {
                "from": _hdr(m, "From"),
                "to": _hdr(m, "To"),
                "date": _hdr(m, "Date"),
                "subject": _hdr(m, "Subject"),
                "labels": m.get("labelIds", []),
                "body": _extract_text(m.get("payload", {}))[:4000],
            }
            for m in th.get("messages", [])
        ]
        return {"messages": msgs}
    if name == "draft_reply":
        th = client.get_thread(token, args["thread_id"], fmt="full")
        last_mid = ""
        for m in th.get("messages", []):
            mid = _hdr(m, "Message-ID")
            if mid:
                last_mid = mid
        d = client.create_draft(
            token,
            to=args["to"],
            subject=args["subject"],
            body=args["body"],
            thread_id=args["thread_id"],
            in_reply_to=last_mid or None,
        )
        return {"draft_id": d.get("id"), "status": t("tool.draft_created")}
    return {"error": f"unknown tool {name}"}
