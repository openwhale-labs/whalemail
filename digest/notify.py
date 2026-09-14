"""Telegram delivery (stdlib urllib through net.urlopen_json, which retries transient errors).

Posts to the chat in WHALEMAIL_TG_CHANNEL; when WHALEMAIL_TG_THREAD is set, into that forum topic.
"""

from __future__ import annotations

import json
import os
import urllib.request

import net


def _require(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise RuntimeError(f"{name} is not set (see .env)")
    return v


def post(text: str, *, silent: bool = False) -> int:
    """Send a message and return its message_id. silent=True delivers without a notification sound."""
    token = _require("WHALEMAIL_BOT_TOKEN")
    channel = _require("WHALEMAIL_TG_CHANNEL")
    thread = os.environ.get("WHALEMAIL_TG_THREAD", "")
    body: dict = {"chat_id": channel, "text": text, "disable_web_page_preview": True}
    if silent:
        body["disable_notification"] = True
    if thread:
        body["message_thread_id"] = int(thread)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    d = net.urlopen_json(req, timeout=15)
    if not d.get("ok"):
        raise RuntimeError(f"telegram: {d.get('description')}")
    return int(d["result"]["message_id"])


def delete(message_id: int) -> bool:
    """Delete one of the bot's own messages (Telegram allows this within 48h). Never raises."""
    try:
        token = _require("WHALEMAIL_BOT_TOKEN")
        channel = _require("WHALEMAIL_TG_CHANNEL")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/deleteMessage",
            data=json.dumps({"chat_id": channel, "message_id": message_id}).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        return bool(net.urlopen_json(req, timeout=15).get("ok"))
    except Exception:
        return False
