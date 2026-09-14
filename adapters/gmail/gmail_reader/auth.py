"""Gmail OAuth credentials: load token.json, refresh when expired (and write back), return the access token.

First-time authorization is scripts/oauth_setup.py. Refresh uses google-auth's requests transport,
which honours proxy environment variables.
"""

from __future__ import annotations

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# gmail.modify: read, create/edit drafts, send, label/archive (no permanent delete).
# gmail.settings.basic: filters, forwarding, signature, vacation responder.
# Deliberately not https://mail.google.com/ (full access including permanent deletion): a leaked
# token would be far more dangerous, and the two scopes above cover everything whalemail does.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]


def load_access_token(token_path: str) -> str:
    """Return a valid access token; refresh with the refresh_token and write back when expired."""
    if not os.path.exists(token_path):
        raise RuntimeError(
            f"{token_path} not found; run `python scripts/oauth_setup.py` once to authorize."
        )
    # Refresh with the scopes already granted in token.json (do not pass SCOPES): after adding a
    # scope to SCOPES, a refresh that requests it would fail with invalid_scope. SCOPES is only
    # used by oauth_setup; to widen access, re-run it and the new token carries the new scope.
    creds = Credentials.from_authorized_user_file(token_path)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError(
                f"{token_path} is invalid and cannot be refreshed; re-run oauth_setup.py."
            )
    return creds.token
