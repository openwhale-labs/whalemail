"""Gmail message → Event (stdlib only, no network)."""

from adapters.gmail.gmail_reader.normalize import normalize

_MSG = {
    "id": "abc123",
    "threadId": "t1",
    "labelIds": ["INBOX", "IMPORTANT"],
    "snippet": "Hello world",
    "internalDate": "1750000000000",
    "payload": {
        "headers": [
            {"name": "From", "value": "Alice <alice@example.com>"},
            {"name": "Subject", "value": "Hi there"},
            {"name": "To", "value": "me@example.com"},
        ]
    },
}


def test_normalize_basic():
    ev = normalize(_MSG, account="me@example.com")
    assert ev.platform == "gmail"
    assert ev.source == "gmail_api"
    assert ev.event_id.startswith("gmail_")
    assert ev.sender_id == "alice@example.com"
    assert ev.sender_name == "Alice"
    assert ev.chat_type == "email"
    assert ev.chat_id == "INBOX"
    assert ev.content == "Hello world"
    assert ev.extras["subject"] == "Hi there"
    assert ev.extras["thread_id"] == "t1"
    assert "IMPORTANT" in ev.extras["labels"]


def test_timestamp_follows_configured_timezone(monkeypatch):
    monkeypatch.setenv("WHALEMAIL_TZ", "Asia/Shanghai")
    assert normalize(_MSG, account="a").timestamp.endswith("+08:00")
    monkeypatch.setenv("WHALEMAIL_TZ", "")
    assert normalize(_MSG, account="a").timestamp.endswith("+00:00")
    monkeypatch.setenv("WHALEMAIL_TZ", "Not/AZone")
    assert normalize(_MSG, account="a").timestamp.endswith("+00:00")


def test_field_order_is_stable():
    keys = list(normalize(_MSG, account="me@example.com").to_dict().keys())
    assert keys[:5] == ["event_id", "platform", "account", "chat_type", "chat_id"]
    assert keys[-1] == "raw"
