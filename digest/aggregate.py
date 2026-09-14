"""Classification results → message text (digest / real-time alerts / heartbeat) + active-window check.

Input is a list of (Classification, Event) pairs (zipped by run.py).
Times: today's emails show HH:MM, older ones MM-DD HH:MM.
"""

from __future__ import annotations

import os
from datetime import date, datetime

import settings

from .i18n import t

BUCKET_EMOJI = {"action": "🔴", "decision": "🟡", "fyi": "🔵", "verify": "🔐", "noise": "⚪"}
_BUCKET_EMOJI = BUCKET_EMOJI  # backwards-compatible alias


def _label(bucket: str) -> str:
    return t(f"bucket.{bucket}")


def current_hour() -> int:
    return datetime.now(settings.tz()).hour


def in_active_window(hour: int | None = None) -> bool:
    h = current_hour() if hour is None else hour
    start = int(os.environ.get("WHALEMAIL_ACTIVE_START", "7"))
    end = int(os.environ.get("WHALEMAIL_ACTIVE_END", "23"))
    return start <= h < end


def _fmt_time(iso: str, today: date) -> str:
    """Today → HH:MM; other days → MM-DD HH:MM; unparsable → empty string."""
    try:
        dt = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""
    return dt.strftime("%H:%M") if dt.date() == today else dt.strftime("%m-%d %H:%M")


def _group(items: list) -> dict[str, list]:
    g: dict[str, list] = {b: [] for b in BUCKET_EMOJI}
    for cl, ev in items:
        g.get(cl.bucket, g["fyi"]).append((cl, ev))
    return g


def render_alerts(items: list, *, today: date | None = None) -> str:
    """Real-time alert: action bucket only. Empty string when there is nothing to alert."""
    acts = [(cl, ev) for cl, ev in items if cl.bucket == "action"]
    if not acts:
        return ""
    today = today or datetime.now(settings.tz()).date()
    lines = [t("alerts.header")]
    for cl, ev in acts:
        line = t(
            "item", time=_fmt_time(ev.timestamp, today), summary=cl.summary, sender=ev.sender_name
        )
        if cl.action:
            line += t("item.action", action=cl.action)
        lines.append(line)
    return "\n".join(lines)


def render_digest(items: list, *, date_str: str | None = None, today: date | None = None) -> str:
    """Digest: action/decision/verify listed in full, fyi one line each, noise as a count."""
    g = _group(items)
    total = len(items)
    now = datetime.now(settings.tz())
    today = today or now.date()
    date_str = date_str or now.strftime("%Y-%m-%d")
    out = [t("digest.header", date=date_str, total=total)]
    for b in ("action", "decision", "verify"):
        rows = g[b]
        if not rows:
            continue
        out.append(t("digest.section", emoji=BUCKET_EMOJI[b], label=_label(b), n=len(rows)))
        for cl, ev in rows:
            line = t(
                "item",
                time=_fmt_time(ev.timestamp, today),
                summary=cl.summary,
                sender=ev.sender_name,
            )
            if cl.action:
                line += t("digest.action_suffix", action=cl.action)
            if b == "verify":
                line += t("digest.verify_warn")
            out.append(line)
    if g["fyi"]:
        out.append(
            t("digest.section", emoji=BUCKET_EMOJI["fyi"], label=_label("fyi"), n=len(g["fyi"]))
        )
        for cl, ev in g["fyi"]:
            out.append(
                t("digest.fyi_item", time=_fmt_time(ev.timestamp, today), summary=cl.summary)
            )
    if g["noise"]:
        out.append(t("digest.noise", n=len(g["noise"])))
    return "\n".join(out)


def render_heartbeat(items: list, *, hours: int = 2, today: date | None = None) -> str:
    """Heartbeat: first line "total · per-bucket counts", then decision/fyi subjects.

    Sent even when there is no email. Silent delivery and keep-only-latest are handled by run.py.
    """
    g = _group(items)
    today = today or datetime.now(settings.tz()).date()
    counts = "  ".join(f"{BUCKET_EMOJI[b]} {len(g[b])}" for b in BUCKET_EMOJI if g[b])
    out = [t("heartbeat.header", hours=hours, n=len(items)) + (f" · {counts}" if counts else "")]
    for b in ("decision", "fyi"):
        if g[b]:
            out.append("")
            out.append(t("heartbeat.section", emoji=BUCKET_EMOJI[b], label=_label(b), n=len(g[b])))
            for cl, ev in g[b]:
                out.append(
                    t(
                        "item",
                        time=_fmt_time(ev.timestamp, today),
                        summary=cl.summary,
                        sender=ev.sender_name,
                    )
                )
    return "\n".join(out)
