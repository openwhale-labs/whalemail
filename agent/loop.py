"""Agent loop: user instruction → LLM with Gmail tools → search / read / draft → report + drafts.

The LLM endpoint comes from the environment (WHALEMAIL_LLM_BASE_URL / _API_KEY); the model is
WHALEMAIL_AGENT_MODEL, falling back to the classification model.
run() returns (report text, drafts created this turn). Drafts go to the bot's approval step.
history is the multi-turn context injected by the bot (see agent/conversation.py).
"""

from __future__ import annotations

import json
import os
import urllib.request

import net
import settings
from digest.i18n import t

from . import tools

_SYS_TMPL = """You are the email assistant of {owner} ({account}). The user gives you an email task; complete it with the tools:
- Use search_email to find relevant threads (Gmail query syntax) and read_thread to read the full exchange, including the user's own earlier replies.
- When a reply is needed, use draft_reply to create a draft. Never send anything: the draft goes to the Gmail Drafts folder and the user decides in the approval step.
- Formal business email should be professional, concise, polite, and cite the key facts. Draft in the language of the thread unless told otherwise.
- When done, report briefly in {language}: what you found and the key points of anything you drafted.
- If the recipient or intent is unclear, read_thread first; do not guess.
- Reply in plain text without Markdown markup (no ** bold, no # headings): Telegram does not render it. Use "1. 2. 3." or line breaks for lists."""


def _system_prompt() -> str:
    return _SYS_TMPL.format(
        owner=settings.owner_name(),
        account=os.environ.get("WHALEMAIL_GMAIL_ACCOUNT", "") or "Gmail",
        language=settings.language_name(),
    )


def _llm(messages: list, tools_schema: list | None = None) -> dict:
    base = os.environ.get("WHALEMAIL_LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("WHALEMAIL_LLM_API_KEY", "")
    model = os.environ.get("WHALEMAIL_AGENT_MODEL") or os.environ.get("WHALEMAIL_CLASSIFY_MODEL")
    if not key or not base or not model:
        raise RuntimeError("WHALEMAIL_LLM_BASE_URL / WHALEMAIL_LLM_API_KEY / model are not all set")
    body: dict = {"model": model, "messages": messages, "temperature": 0.2}
    if tools_schema:
        body["tools"] = tools_schema
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {key}")
    return net.urlopen_json(req, timeout=90)


def summarize(text: str) -> str:
    """Compress a conversation into a short bullet summary (no tools); used for compaction."""
    messages = [
        {
            "role": "system",
            "content": (
                "Summarise the email-assistant conversation below into a few concise bullet points, "
                "keeping: what the user asked, key facts found, emails drafted, open items. "
                f"Write in {settings.language_name()}. A few lines, no elaboration."
            ),
        },
        {"role": "user", "content": text},
    ]
    resp = _llm(messages)
    return resp["choices"][0]["message"].get("content") or ""


def run(
    instruction: str, token: str, *, history: list | None = None, max_steps: int = 8
) -> tuple[str, list]:
    """Run the agent loop. Returns (report, drafts created as [{draft_id, to, subject, body}]).

    history: earlier {role, content} turns (user/assistant alternating) for follow-up questions.
    """
    messages: list = [{"role": "system", "content": _system_prompt()}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": instruction})
    drafts: list = []
    for _ in range(max_steps):
        resp = _llm(messages, tools.TOOLS)
        msg = resp["choices"][0]["message"]
        messages.append(msg)
        tcs = msg.get("tool_calls")
        if not tcs:
            return (msg.get("content", "") or t("agent.no_output")), drafts
        for tc in tcs:
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
                result = tools.run_tool(token, fn, args)
                if fn == "draft_reply" and result.get("draft_id"):
                    drafts.append(
                        {
                            "draft_id": result["draft_id"],
                            "to": args.get("to", ""),
                            "subject": args.get("subject", ""),
                            "body": args.get("body", ""),
                        }
                    )
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    return t("agent.step_limit"), drafts
