#!/usr/bin/env python3
"""One-time Gmail authorization: sign in through the browser, save token.json.

Usage:
  python scripts/oauth_setup.py

Reads WHALEMAIL_GMAIL_CLIENT_SECRET / WHALEMAIL_GMAIL_TOKEN from .env. The token exchange
talks to Google's endpoints, so a proxy (if you need one) must be set in the environment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from settings import load_env  # noqa: E402

# Scopes live in auth.py; this script picks them up from there.
from adapters.gmail.gmail_reader.auth import SCOPES  # noqa: E402


def main() -> None:
    load_env()
    client_secret = os.environ.get("WHALEMAIL_GMAIL_CLIENT_SECRET", "config/client_secret.json")
    token_path = os.environ.get("WHALEMAIL_GMAIL_TOKEN", "config/token.json")
    if not os.path.exists(client_secret):
        sys.exit(
            f"{client_secret} not found: create a Desktop OAuth client in Google Cloud, "
            "download its JSON to this path, then re-run."
        )
    flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
    creds = flow.run_local_server(port=0)
    os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"✅ Authorized; token saved to {token_path}")


if __name__ == "__main__":
    main()
