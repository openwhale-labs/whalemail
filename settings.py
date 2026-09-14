"""Environment loading and small shared settings (no python-dotenv dependency)."""

from __future__ import annotations

import os
from datetime import timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent

# UI language for Telegram messages and LLM output. Two built-in string sets: "en" and "zh".
_SUPPORTED_LANGUAGES = ("en", "zh")
_LANGUAGE_NAMES = {"en": "English", "zh": "Chinese (简体中文)"}


def load_env(path: str | os.PathLike | None = None) -> None:
    """Read KEY=VALUE lines from .env into os.environ.

    Existing environment variables win, so a scheduler (launchd, systemd) can override values.
    """
    p = Path(path) if path else ROOT / ".env"
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val


def language() -> str:
    """Language code for user-facing text: "en" (default) or "zh"."""
    code = (os.environ.get("WHALEMAIL_LANGUAGE") or "en").strip().lower()[:2]
    return code if code in _SUPPORTED_LANGUAGES else "en"


def language_name() -> str:
    """Human-readable language name, used inside LLM prompts."""
    return _LANGUAGE_NAMES[language()]


def tz() -> tzinfo:
    """Timezone from WHALEMAIL_TZ (IANA name); UTC when unset or unknown."""
    name = (os.environ.get("WHALEMAIL_TZ") or "").strip()
    if not name:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def owner_name() -> str:
    """How the agent refers to its owner in prompts."""
    return (os.environ.get("WHALEMAIL_OWNER_NAME") or "").strip() or "the user"
