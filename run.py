#!/usr/bin/env python3
"""whalemail entry point.

  python run.py --test-last N   fetch the last N emails → classify → print (dry run: no push, no cursor)
  python run.py --once          fetch new mail → classify → store; push 🔴 alerts in the active window
  python run.py --digest        fetch the recent window → classify → push the morning digest
  python run.py --heartbeat     push a silent summary (bucket counts + subjects), replacing the last one
  python run.py --ask "..."     one agent task (search / read / draft) from the command line
  python run.py --bot           run the Telegram bot (listens for instructions in the group)

Fetch scope and excluded labels come from config/gmail-allowlist.json (fetch_query / exclude_labels).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import os  # noqa: E402

from adapters.gmail.gmail_reader import (  # noqa: E402
    allowlist,
    auth,
    client,
    poll as pollmod,
    sync_to_events,
)
from adapters.gmail.gmail_reader.normalize import normalize  # noqa: E402
from digest import aggregate, notify  # noqa: E402
from digest.i18n import t  # noqa: E402
from settings import load_env  # noqa: E402
from triage import classify as classifier  # noqa: E402

EVENTS = str(ROOT / "data/events/gmail-events.jsonl")
CURSOR = str(ROOT / "data/runtime/gmail-cursor.json")
ALLOWLIST = str(ROOT / "config/gmail-allowlist.json")
HEARTBEAT_MSG = str(ROOT / "data/runtime/heartbeat-msg.json")


def _token_account() -> tuple[str, str]:
    load_env()
    token_path = os.environ.get("WHALEMAIL_GMAIL_TOKEN", "config/token.json")
    account = os.environ.get("WHALEMAIL_GMAIL_ACCOUNT", "")
    return auth.load_access_token(token_path), account


def _cfg() -> dict:
    return allowlist.load(os.environ.get("WHALEMAIL_ALLOWLIST", ALLOWLIST))


def _alert(msg: str) -> None:
    try:
        notify.post(msg)
    except Exception:
        pass


def _auth_or_alert() -> tuple[str, str]:
    try:
        return _token_account()
    except RuntimeError as e:
        _alert(t("auth.failed", err=e))
        raise


def _fetch_recent(token: str, account: str, *, extra: str = "", n: int = 50) -> list:
    cfg = _cfg()
    query = (cfg["fetch_query"] + " " + extra).strip()
    listing = client.list_messages(token, query=query, max_results=n)
    evs = [
        normalize(client.get_message(token, m["id"]), account=account)
        for m in listing.get("messages", [])
    ]
    return [
        e for e in evs if not allowlist.excluded(e.extras.get("labels", []), cfg["exclude_labels"])
    ]


def cmd_test_last(n: int) -> None:
    token, account = _token_account()
    events = _fetch_recent(token, account, n=n)
    cls = classifier.classify(events)
    for c, e in zip(cls, events):
        emoji = aggregate.BUCKET_EMOJI.get(c.bucket, "?")
        print(f"[{emoji} {c.bucket:8}] {e.extras.get('subject', '')[:48]:48} | {e.sender_name}")
        print(f"    {c.summary}" + (f"  → {c.action}" if c.action else ""))


def cmd_once() -> None:
    token, account = _auth_or_alert()
    cfg = _cfg()
    events_all, new_ms = pollmod.poll(
        token,
        account=account,
        cursor_path=CURSOR,
        query=cfg["fetch_query"],
        max_results=50,
        advance=False,
    )
    if not events_all:
        print("no new email")
        return
    events = [
        e
        for e in events_all
        if not allowlist.excluded(e.extras.get("labels", []), cfg["exclude_labels"])
    ]
    skipped = len(events_all) - len(events)
    if events:
        sync_to_events.append_events(events, EVENTS)
        cls = classifier.classify(events)
        pairs = list(zip(cls, events))
        n_action = sum(1 for c in cls if c.bucket == "action")
        if aggregate.in_active_window():
            text = aggregate.render_alerts(pairs)
            if text:
                notify.post(text)
                print(
                    f"active window: pushed {n_action} 🔴 "
                    f"({len(events)} stored / {skipped} excluded)"
                )
            else:
                print(f"active window: {len(events)} stored, no 🔴 / {skipped} excluded")
        else:
            print(f"quiet hours: {len(events)} stored / {skipped} excluded")
    else:
        print(f"{len(events_all)} emails all in excluded labels, skipped")
    pollmod.save_cursor(CURSOR, new_ms)


def cmd_digest() -> None:
    token, account = _auth_or_alert()
    events = _fetch_recent(token, account, extra="newer_than:14h", n=50)
    if not events:
        notify.post(t("digest.empty"))
        print("digest pushed (empty)")
        return
    cls = classifier.classify(events)
    notify.post(aggregate.render_digest(list(zip(cls, events))))
    print(f"digest pushed ({len(events)} emails)")


def _load_heartbeat_id() -> int | None:
    try:
        with open(HEARTBEAT_MSG, encoding="utf-8") as f:
            return int(json.load(f)["message_id"])
    except (OSError, ValueError, KeyError):
        return None


def _save_heartbeat_id(mid: int) -> None:
    with open(HEARTBEAT_MSG, "w", encoding="utf-8") as f:
        json.dump({"message_id": mid}, f)


def cmd_heartbeat() -> None:
    token, account = _auth_or_alert()
    if not aggregate.in_active_window():
        print("quiet hours, heartbeat skipped")
        return
    hours = int(os.environ.get("WHALEMAIL_HEARTBEAT_EVERY", "2"))
    events = _fetch_recent(token, account, extra=f"newer_than:{hours}h", n=50)
    text = aggregate.render_heartbeat(list(zip(classifier.classify(events), events)), hours=hours)
    # Delete the previous heartbeat before posting the new one, so no failure path piles up
    # messages (a failed post is retried against the same id next round, idempotently).
    # Only the id recorded in HEARTBEAT_MSG is deleted; digests and alerts never go there.
    old = _load_heartbeat_id()
    if old is not None:
        notify.delete(old)
    mid = notify.post(text, silent=True)
    _save_heartbeat_id(mid)
    print(f"heartbeat pushed ({len(events)} emails · silent, deleted previous {old})")


def cmd_ask(text: str) -> None:
    token, _ = _auth_or_alert()
    from agent import loop

    reply, drafts = loop.run(text, token)
    print(reply)
    for d in drafts:
        print(f"[draft {d['draft_id']}] → {d['to']} | {d['subject']}")


def cmd_bot() -> None:
    from agent import bot

    bot.main()


def main() -> None:
    ap = argparse.ArgumentParser(description="whalemail")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--test-last", type=int, metavar="N", help="classify the last N emails and print"
    )
    g.add_argument("--once", action="store_true", help="fetch new mail, classify, alert on 🔴")
    g.add_argument("--digest", action="store_true", help="push the morning digest")
    g.add_argument("--heartbeat", action="store_true", help="push the silent heartbeat summary")
    g.add_argument("--ask", type=str, metavar="TEXT", help="one agent task (search/read/draft)")
    g.add_argument("--bot", action="store_true", help="run the Telegram bot")
    a = ap.parse_args()
    if a.test_last:
        cmd_test_last(a.test_last)
    elif a.once:
        cmd_once()
    elif a.digest:
        cmd_digest()
    elif a.heartbeat:
        cmd_heartbeat()
    elif a.ask:
        cmd_ask(a.ask)
    elif a.bot:
        cmd_bot()


if __name__ == "__main__":
    main()
