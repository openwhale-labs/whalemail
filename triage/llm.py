"""Chat completion through any OpenAI-compatible endpoint (stdlib urllib, honours proxy env vars).

Base URL, key and model come from the environment. Requests go through net.urlopen_json,
which retries transient network errors.
"""

from __future__ import annotations

import json
import os
import urllib.request

import net

_DEFAULT_BASE = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "deepseek/deepseek-v4-flash"


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    response_json: bool = False,
    timeout: int = 60,
) -> str:
    """Call chat/completions and return the first message's content."""
    base = os.environ.get("WHALEMAIL_LLM_BASE_URL", _DEFAULT_BASE).rstrip("/")
    key = os.environ.get("WHALEMAIL_LLM_API_KEY", "")
    if not key:
        raise RuntimeError("WHALEMAIL_LLM_API_KEY is not set")
    model = model or os.environ.get("WHALEMAIL_CLASSIFY_MODEL", _DEFAULT_MODEL)
    body: dict = {"model": model, "messages": messages, "temperature": temperature}
    if response_json:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {key}")
    # Optional attribution headers used by OpenRouter's dashboard; harmless elsewhere.
    req.add_header("HTTP-Referer", "https://github.com/openwhale-labs/whalemail")
    req.add_header("X-Title", "whalemail")
    d = net.urlopen_json(req, timeout=timeout)
    return d["choices"][0]["message"]["content"]
