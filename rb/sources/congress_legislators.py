from __future__ import annotations

from pathlib import Path

from rb.cache import ArtifactCache
from rb.net import http_get
from rb.util import redact_url, write_bytes_atomic


def fetch_executive_json(*, refresh: bool) -> Path:
    """Fetch unitedstates/congress-legislators executive.json; return path to cached raw artifact."""
    url = "https://unitedstates.github.io/congress-legislators/executive.json"

    cache = ArtifactCache()
    raw_dir = cache.artifact_dir("congress_legislators", "executive")

    if not refresh:
        have = cache.latest(raw_dir, suffix="json")
        if have:
            return have.path

    status, headers, body = http_get(url, headers={"Accept": "application/json"})
    cache.write(raw_dir, data=body, suffix="json", meta={"url": redact_url(url), "status": status, "headers": headers})

    # Stable derived copy for debugging/inspection (still reproducible via data/raw).
    derived_dir = Path("data/derived/congress_legislators")
    derived_dir.mkdir(parents=True, exist_ok=True)
    derived_path = derived_dir / "executive.json"
    if not body.endswith(b"\n"):
        body = body + b"\n"
    write_bytes_atomic(derived_path, body)

    latest = cache.latest(raw_dir, suffix="json")
    if not latest:
        raise RuntimeError("executive.json download missing from cache")
    return latest.path

