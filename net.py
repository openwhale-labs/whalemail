"""urllib with retries for the transient SSL/network errors an unattended job will meet.

Only connection-level errors are retried. HTTPError (4xx/5xx, e.g. a wrong model name)
is raised immediately so it is never masked.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


def urlopen_json(
    req: urllib.request.Request,
    *,
    timeout: int = 30,
    retries: int = 3,
    backoff: float = 1.5,
) -> dict:
    """Send the request and parse the JSON body; retry transient errors, re-raise the last one."""
    last: Exception | None = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError:
            raise  # explicit server error: do not retry
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if i < retries - 1:
                time.sleep(backoff * (i + 1))
    raise last  # type: ignore[misc]
