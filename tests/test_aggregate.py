"""Digest / alert / heartbeat rendering and the active-window check (pure functions, no network)."""

from datetime import date

import pytest

from digest import aggregate as A

TODAY = date(2026, 6, 22)


@pytest.fixture(autouse=True)
def _chinese(monkeypatch):
    # Existing expectations were written against the Chinese strings.
    monkeypatch.setenv("WHALEMAIL_LANGUAGE", "zh")


class _Cl:
    def __init__(self, bucket, summary, action=""):
        self.bucket = bucket
        self.summary = summary
        self.action = action
        self.event_id = "e"


class _Ev:
    def __init__(self, name="Sender", ts="2026-06-22T09:30:00+08:00"):
        self.sender_name = name
        self.extras = {}
        self.timestamp = ts


def _pair(bucket, summary, action="", ts="2026-06-22T09:30:00+08:00"):
    return (_Cl(bucket, summary, action), _Ev(ts=ts))


def test_render_alerts_only_action_with_time():
    t = A.render_alerts(
        [_pair("action", "扣款失败", "去结清"), _pair("noise", "促销")], today=TODAY
    )
    assert "扣款失败" in t and "去结清" in t and "09:30" in t
    assert "促销" not in t


def test_render_alerts_empty_without_action():
    assert A.render_alerts([_pair("fyi", "x")], today=TODAY) == ""


def test_render_digest_sections_and_noise_count():
    items = [
        _pair("action", "A", "doA"),
        _pair("decision", "D"),
        _pair("verify", "V"),
        _pair("fyi", "F"),
        _pair("noise", "N1"),
        _pair("noise", "N2"),
    ]
    t = A.render_digest(items, date_str="2026-06-22", today=TODAY)
    assert "共 6 封" in t
    assert "要去操作" in t and "doA" in t
    assert "核实真伪" in t and "勿点信中链接" in t
    assert "噪声 2 封" in t


def test_render_digest_english(monkeypatch):
    monkeypatch.setenv("WHALEMAIL_LANGUAGE", "en")
    items = [_pair("action", "Card declined", "Update the card"), _pair("noise", "Promo")]
    t = A.render_digest(items, date_str="2026-06-22", today=TODAY)
    assert t.splitlines()[0] == "📬 Morning digest · 2026-06-22 · 2 emails"
    assert "Action needed (1)" in t and "• 09:30 Card declined (Sender) — Update the card" in t
    assert "1 noise emails archived" in t


def test_time_same_day_vs_crossday():
    items = [
        _pair("action", "今天的", "x", ts="2026-06-22T08:15:00+08:00"),
        _pair("fyi", "昨天的", ts="2026-06-21T23:00:00+08:00"),
    ]
    t = A.render_digest(items, date_str="2026-06-22", today=TODAY)
    assert "08:15" in t  # today: time only
    assert "06-21 23:00" in t  # another day: date and time


def test_active_window(monkeypatch):
    monkeypatch.setenv("WHALEMAIL_ACTIVE_START", "8")
    monkeypatch.setenv("WHALEMAIL_ACTIVE_END", "22")
    assert A.in_active_window(10) is True
    assert A.in_active_window(23) is False
    assert A.in_active_window(7) is False


def test_render_heartbeat_counts_and_detail():
    items = [_pair("fyi", "F 通知"), _pair("decision", "D 要决定")]
    t = A.render_heartbeat(items, hours=2, today=TODAY)
    assert t.splitlines()[0] == "🐋 过去 2h 2 封 · 🟡 1  🔵 1"
    assert "🔴" not in t  # buckets with zero count are hidden
    assert "D 要决定" in t and "F 通知" in t


def test_render_heartbeat_empty_still_renders():
    t = A.render_heartbeat([], hours=2, today=TODAY)
    assert t == "🐋 过去 2h 0 封"  # no trailing separator when every count is zero
