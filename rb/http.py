from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Any

import certifi


def http_get(url: str, *, timeout_s: int = 60, headers: dict[str, str] | None = None, retries: int = 3) -> tuple[int, dict[str, Any], bytes]:
    """Simple GET with retries. Returns (status, headers, body)."""
    hdrs = {"User-Agent": "rb/0.1 (+https://example.invalid)"}
    if headers:
        hdrs.update(headers)

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs, method="GET")
            ctx = None
            # Ensure HTTPS requests work even in minimal environments.
            if url.startswith("https://"):
                import ssl

                ctx = ssl.create_default_context(cafile=certifi.where())

            with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
                status = getattr(resp, "status", 200)
                resp_headers = dict(resp.headers.items())
                body = resp.read()
                return status, resp_headers, body
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise

    raise RuntimeError(f"http_get failed: {last_err}")

