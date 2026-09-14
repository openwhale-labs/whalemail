"""Thin Gmail REST client (stdlib urllib, proxy from the environment, retries via net.urlopen_json).

Read: messages.list/get, threads.list/get. Write: drafts.create, drafts.send (gmail.modify scope).
No google-api-python-client: fewer dependencies and one proxy configuration for everything.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from email.message import EmailMessage

import net

_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _get(token: str, path: str, params: dict | None = None) -> dict:
    url = f"{_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    return net.urlopen_json(req, timeout=30)


def _post(token: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{_BASE}{path}", data=json.dumps(body).encode("utf-8"), method="POST"
    )
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    return net.urlopen_json(req, timeout=30)


def list_messages(
    token: str, *, query: str, max_results: int = 50, page_token: str | None = None
) -> dict:
    params: dict = {"q": query, "maxResults": max_results}
    if page_token:
        params["pageToken"] = page_token
    return _get(token, "/messages", params)


def get_message(
    token: str,
    msg_id: str,
    *,
    fmt: str = "metadata",
    headers: tuple[str, ...] = ("From", "To", "Cc", "Subject", "Date"),
) -> dict:
    params: dict = {"format": fmt}
    if fmt == "metadata":
        params["metadataHeaders"] = list(headers)
    return _get(token, f"/messages/{msg_id}", params)


def search_threads(token: str, *, query: str, max_results: int = 20) -> dict:
    """Search threads; returns {threads: [{id, snippet, ...}]} (use get_thread for the bodies)."""
    return _get(token, "/threads", {"q": query, "maxResults": max_results})


def get_thread(token: str, thread_id: str, *, fmt: str = "full") -> dict:
    """Fetch a whole thread (fmt=full includes every message's payload/body)."""
    return _get(token, f"/threads/{thread_id}", {"format": fmt})


def create_draft(
    token: str,
    *,
    to: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> dict:
    """Create a draft (gmail.modify). For a reply pass thread_id and in_reply_to (the RFC 822 Message-ID)."""
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references or in_reply_to
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload: dict = {"message": {"raw": raw}}
    if thread_id:
        payload["message"]["threadId"] = thread_id
    return _post(token, "/drafts", payload)


def send_draft(token: str, draft_id: str) -> dict:
    """Send an existing draft (gmail.modify). Returns the sent message."""
    return _post(token, "/drafts/send", {"id": draft_id})
