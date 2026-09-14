"""Conversation compaction (pure functions, no network)."""

from agent import conversation as C


def test_no_compact_under_budget(monkeypatch):
    monkeypatch.setenv("WHALEMAIL_CONV_BUDGET", "100000")
    msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    assert C.maybe_compact(msgs, lambda t: "S") == msgs


def test_compact_over_budget(monkeypatch):
    monkeypatch.setenv("WHALEMAIL_CONV_BUDGET", "10")
    monkeypatch.setenv("WHALEMAIL_CONV_KEEP", "2")
    msgs = [
        {"role": "user", "content": "x" * 100},
        {"role": "assistant", "content": "y" * 100},
        {"role": "user", "content": "recent1"},
        {"role": "assistant", "content": "recent2"},
    ]
    out = C.maybe_compact(msgs, lambda t: "SUMMARY")
    assert out[0]["role"] == "system" and "SUMMARY" in out[0]["content"]
    assert out[-2:] == msgs[-2:]  # the last 2 messages survive verbatim
    assert len(out) == 3  # summary + last 2


def test_compact_failure_keeps_original(monkeypatch):
    monkeypatch.setenv("WHALEMAIL_CONV_BUDGET", "10")
    monkeypatch.setenv("WHALEMAIL_CONV_KEEP", "2")

    def boom(_):
        raise RuntimeError("llm down")

    msgs = [
        {"role": "user", "content": "x" * 100},
        {"role": "assistant", "content": "y" * 100},
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
    ]
    assert C.maybe_compact(msgs, boom) == msgs  # a failed compaction never loses the conversation
