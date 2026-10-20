"""urllib with retries for the transient SSL/network errors an unattended job will meet.

Connection-level errors are retried. Idempotent GET callers may also opt into
bounded retries for 500/502/503/504 and truncated response bodies; these failures
on writes and other callers are raised immediately.
"""

from __future__ import annotations

import http.client
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
    retry_server_errors: bool = False,
) -> dict:
    """Send the request and parse the JSON body; retry transient errors, re-raise the last one."""
    last: Exception | None = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if (
                not retry_server_errors
                or req.get_method() != "GET"
                or e.code not in {500, 502, 503, 504}
                or i == retries - 1
            ):
                raise
            # Release failed responses before retrying. Keep the final error intact.
            last = e
            e.close()
            time.sleep(backoff * (2**i))
        except http.client.IncompleteRead as e:
            if (
                not retry_server_errors
                or req.get_method() != "GET"
                or i == retries - 1
            ):
                raise
            last = e
            time.sleep(backoff * (2**i))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if i < retries - 1:
                time.sleep(backoff * (i + 1))
    raise last  # type: ignore[misc]
