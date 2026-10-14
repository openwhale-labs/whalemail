"""Chat completion through any OpenAI-compatible endpoint (stdlib urllib, honours proxy env vars).

Base URL, key and model come from the environment. Requests go through net.urlopen_json,
which retries transient network errors. Rejected chat requests with HTTP 503
are retried up to three attempts before any downstream action is executed.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
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
    for attempt in range(3):
        try:
            d = net.urlopen_json(req, timeout=timeout)
            return d["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            # Retry only a rejected inference request. Never replay Gmail/Telegram writes.
            if exc.code != 503 or attempt == 2:
                raise
            delay = 1.5 * (2**attempt)
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if retry_after and retry_after.strip().isdigit():
                delay = max(delay, int(retry_after.strip()))
            if delay > 30:
                # Respect a longer server cooldown by leaving this run failed.
                raise
            exc.close()
            time.sleep(delay)
    raise AssertionError("unreachable")
