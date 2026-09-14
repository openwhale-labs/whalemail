"""Bucket mapping, fallbacks and rules loading (LLM mocked, no network)."""

import json

from triage import classify as C


class _Ev:
    def __init__(self, eid, subject, snippet):
        self.event_id = eid
        self.sender_name = "X"
        self.sender_id = "x@e.com"
        self.content = snippet
        self.extras = {"subject": subject, "labels": []}


def test_maps_and_defaults_missing_to_fyi(monkeypatch):
    evs = [_Ev("e0", "Sub0", "s0"), _Ev("e1", "Sub1", "s1")]
    # The model answers for e0 only (e1 missing) and wraps the JSON in a ``` fence.
    fake = (
        "```json\n"
        + json.dumps({"results": [{"i": 0, "bucket": "action", "summary": "S", "action": "do"}]})
        + "\n```"
    )
    monkeypatch.setattr(C.llm, "chat", lambda *a, **k: fake)
    out = C.classify(evs)
    assert len(out) == 2
    assert out[0].bucket == "action" and out[0].action == "do"
    assert out[1].bucket == "fyi"  # missing → fyi (over-report rather than miss)


def test_illegal_bucket_falls_back_to_fyi(monkeypatch):
    evs = [_Ev("e0", "S", "s")]
    monkeypatch.setattr(
        C.llm, "chat", lambda *a, **k: json.dumps({"results": [{"i": 0, "bucket": "weird"}]})
    )
    assert C.classify(evs)[0].bucket == "fyi"


def test_extract_json_strips_fence():
    assert C._extract_json('```json\n{"results": []}\n```') == {"results": []}
    assert C._extract_json('prefix {"results": [{"i": 0}]} suffix') == {"results": [{"i": 0}]}


def test_local_rules_appended(monkeypatch, tmp_path):
    rules = tmp_path / "rules.md"
    rules.write_text("# base\n", encoding="utf-8")
    local = tmp_path / "rules.local.md"
    monkeypatch.setattr(C, "_RULES_PATH", rules)
    monkeypatch.setattr(C, "_LOCAL_RULES_PATH", local)
    assert C._load_rules() == "# base\n"
    local.write_text("My label `Later` means noise.\n", encoding="utf-8")
    out = C._load_rules()
    assert out.startswith("# base") and "## Owner-specific rules" in out and "`Later`" in out


def test_prompt_carries_language_and_rules(monkeypatch, tmp_path):
    rules = tmp_path / "rules.md"
    rules.write_text("RULES-MARKER\n", encoding="utf-8")
    monkeypatch.setattr(C, "_RULES_PATH", rules)
    monkeypatch.setattr(C, "_LOCAL_RULES_PATH", tmp_path / "none.md")
    monkeypatch.setenv("WHALEMAIL_LANGUAGE", "zh")
    seen = {}

    def fake_chat(messages, **k):
        seen["system"] = messages[0]["content"]
        return json.dumps({"results": [{"i": 0, "bucket": "fyi", "summary": "s", "action": ""}]})

    monkeypatch.setattr(C.llm, "chat", fake_chat)
    C.classify([_Ev("e0", "S", "s")])
    assert "RULES-MARKER" in seen["system"] and "Chinese" in seen["system"]
