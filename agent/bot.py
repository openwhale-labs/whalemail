"""Telegram bot: long-poll the group for instructions → agent → reply + draft approval card.

Uses its own WHALEMAIL_BOT_TOKEN (a bot can have only one getUpdates consumer). Runs
continuously (launchd KeepAlive). After the agent drafts a reply, an approval card with
✅ Send / ❌ Cancel is posted; only ✅ calls send_draft. The send decision stays with the user.
The update offset is persisted (bot-offset.json) so a restart does not replay messages.
Conversation context: agent/conversation.py (persisted, compacted past a token budget, /new resets).
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from pathlib import Path

import net
from adapters.gmail.gmail_reader import auth, client
from agent import conversation, loop
from digest.i18n import t
from settings import load_env

_OFFSET = Path(__file__).resolve().parent.parent / "data/runtime/bot-offset.json"
_RESET_COMMANDS = ("/new", "/reset", "新话题")


def _api(token: str, method: str, params: dict, *, timeout: int = 70) -> dict:
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(params).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    return net.urlopen_json(req, timeout=timeout, retries=2)


def _load_offset() -> int | None:
    try:
        return int(json.loads(_OFFSET.read_text(encoding="utf-8"))["offset"])
    except Exception:
        return None


def _save_offset(o: int) -> None:
    try:
        _OFFSET.parent.mkdir(parents=True, exist_ok=True)
        _OFFSET.write_text(json.dumps({"offset": o}), encoding="utf-8")
    except Exception:
        pass


def _drop_pending(token: str) -> int:
    """First start: skip the backlog of unacknowledged updates and begin after the newest one."""
    try:
        r = _api(token, "getUpdates", {"offset": -1, "timeout": 0}, timeout=20)
        res = r.get("result", [])
        return (res[-1]["update_id"] + 1) if res else 0
    except Exception:
        return 0


def _send(token: str, chat: str, thread: str, text: str, reply_to: int | None = None) -> None:
    p: dict = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
    if thread:
        p["message_thread_id"] = int(thread)
    if reply_to:
        p["reply_to_message_id"] = reply_to
    try:
        _api(token, "sendMessage", p, timeout=20)
    except Exception:
        pass


def _send_approval(
    token: str, chat: str, thread: str, draft: dict, reply_to: int | None = None
) -> None:
    body = draft.get("body", "")
    text = t("bot.approval", to=draft["to"], subject=draft["subject"], body=body[:1500])
    kb = {
        "inline_keyboard": [
            [
                {"text": t("bot.btn_send"), "callback_data": f"wmsend:{draft['draft_id']}"},
                {"text": t("bot.btn_cancel"), "callback_data": f"wmcancel:{draft['draft_id']}"},
            ]
        ]
    }
    p: dict = {"chat_id": chat, "text": text, "reply_markup": kb, "disable_web_page_preview": True}
    if thread:
        p["message_thread_id"] = int(thread)
    if reply_to:
        p["reply_to_message_id"] = reply_to
    try:
        _api(token, "sendMessage", p, timeout=20)
    except Exception:
        pass


def _handle_callback(bot: str, chan: str, gmail_token_path: str, cq: dict) -> None:
    m = cq.get("message", {})
    if str(m.get("chat", {}).get("id")) != str(chan):
        return
    data = cq.get("data", "")
    cqid = cq["id"]
    chat = m.get("chat", {}).get("id")
    mid = m.get("message_id")
    if data.startswith("wmsend:"):
        did = data.split(":", 1)[1]
        try:
            gtoken = auth.load_access_token(gmail_token_path)
            client.send_draft(gtoken, did)
            _api(
                bot,
                "answerCallbackQuery",
                {"callback_query_id": cqid, "text": t("bot.sent_toast")},
                timeout=20,
            )
            _api(
                bot,
                "editMessageText",
                {"chat_id": chat, "message_id": mid, "text": t("bot.sent")},
                timeout=20,
            )
        except Exception as e:
            _api(
                bot,
                "answerCallbackQuery",
                {"callback_query_id": cqid, "text": t("bot.send_failed", err=e)[:190]},
                timeout=20,
            )
    elif data.startswith("wmcancel:"):
        _api(
            bot,
            "answerCallbackQuery",
            {"callback_query_id": cqid, "text": t("bot.cancelled_toast")},
            timeout=20,
        )
        _api(
            bot,
            "editMessageText",
            {"chat_id": chat, "message_id": mid, "text": t("bot.cancelled")},
            timeout=20,
        )


def main() -> None:
    load_env()
    bot = os.environ["WHALEMAIL_BOT_TOKEN"]
    chan = os.environ["WHALEMAIL_TG_CHANNEL"]
    thread = os.environ.get("WHALEMAIL_TG_THREAD", "")
    gmail_token_path = os.environ.get("WHALEMAIL_GMAIL_TOKEN", "config/token.json")
    offset = _load_offset()
    if offset is None:
        offset = _drop_pending(bot)  # first start: listen to new messages only
        _save_offset(offset)
    print("whalemail bot listening…", flush=True)
    while True:
        try:
            r = _api(
                bot,
                "getUpdates",
                {"offset": offset, "timeout": 60, "allowed_updates": ["message", "callback_query"]},
            )
        except Exception:
            time.sleep(5)
            continue
        for upd in r.get("result", []):
            offset = upd["update_id"] + 1
            _save_offset(offset)  # acknowledge on receipt: never replayed after a crash
            if "callback_query" in upd:
                try:
                    _handle_callback(bot, chan, gmail_token_path, upd["callback_query"])
                except Exception:
                    pass
                continue
            msg = upd.get("message") or {}
            print(
                f"[recv] chat={msg.get('chat', {}).get('id')} "
                f"thread={msg.get('message_thread_id')} "
                f"from=@{msg.get('from', {}).get('username')} "
                f"text={(msg.get('text') or '')[:50]!r}",
                flush=True,
            )
            if str(msg.get("chat", {}).get("id")) != str(chan):
                print(f"  skip: chat mismatch (expected {chan})", flush=True)
                continue
            if thread and str(msg.get("message_thread_id", "")) != str(thread):
                print(f"  skip: thread mismatch (expected {thread})", flush=True)
                continue
            if msg.get("from", {}).get("is_bot"):
                print("  skip: from a bot (digests and alerts)", flush=True)
                continue
            text = re.sub(r"@\w+", "", msg.get("text") or "").strip()
            if not text:
                continue
            mid = msg.get("message_id")
            if text in _RESET_COMMANDS:
                conversation.reset()
                _send(bot, chan, thread, t("bot.new_topic"), reply_to=mid)
                continue
            _send(bot, chan, thread, t("bot.ack"), reply_to=mid)
            try:
                gtoken = auth.load_access_token(gmail_token_path)
                history = conversation.maybe_compact(conversation.load(), loop.summarize)
                reply, drafts = loop.run(text, gtoken, history=history)
                conversation.save(
                    [
                        *history,
                        {"role": "user", "content": text},
                        {"role": "assistant", "content": reply},
                    ]
                )
            except Exception as e:
                reply, drafts = t("bot.error", err=f"{type(e).__name__}: {e}"), []
            _send(bot, chan, thread, reply, reply_to=mid)
            for d in drafts:
                _send_approval(bot, chan, thread, d, reply_to=mid)


if __name__ == "__main__":
    main()
