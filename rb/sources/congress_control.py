from __future__ import annotations

from pathlib import Path

from rb.cache import ArtifactCache
from rb.net import http_get
from rb.util import redact_url, write_bytes_atomic


def fetch_house_party_divisions_html(*, refresh: bool) -> Path:
    """Fetch House party divisions HTML table (history.house.gov)."""
    url = "https://history.house.gov/Institution/Party-Divisions/Party-Divisions/"

    cache = ArtifactCache()
    raw_dir = cache.artifact_dir("congress_control", "house_party_divisions")

    if not refresh:
        have = cache.latest(raw_dir, suffix="html")
        if have:
            return have.path

    status, headers, body = http_get(url, headers={"Accept": "text/html"})
    cache.write(raw_dir, data=body, suffix="html", meta={"url": redact_url(url), "status": status, "headers": headers})

    # Stable derived copy for debugging (still reproducible via data/raw).
    derived_dir = Path("data/derived/congress_control")
    derived_dir.mkdir(parents=True, exist_ok=True)
    derived_path = derived_dir / "house_party_divisions.html"
    if not body.endswith(b"\n"):
        body = body + b"\n"
    write_bytes_atomic(derived_path, body)

    latest = cache.latest(raw_dir, suffix="html")
    if not latest:
        raise RuntimeError("house party divisions download missing from cache")
    return latest.path


def fetch_senate_party_divisions_html(*, refresh: bool) -> Path:
    """Fetch Senate party division HTML (senate.gov)."""
    url = "https://www.senate.gov/history/partydiv.htm"

    cache = ArtifactCache()
    raw_dir = cache.artifact_dir("congress_control", "senate_party_divisions")

    if not refresh:
        have = cache.latest(raw_dir, suffix="html")
        if have:
            return have.path

    status, headers, body = http_get(url, headers={"Accept": "text/html"})
    cache.write(raw_dir, data=body, suffix="html", meta={"url": redact_url(url), "status": status, "headers": headers})

    # Stable derived copy for debugging (still reproducible via data/raw).
    derived_dir = Path("data/derived/congress_control")
    derived_dir.mkdir(parents=True, exist_ok=True)
    derived_path = derived_dir / "senate_party_divisions.html"
    if not body.endswith(b"\n"):
        body = body + b"\n"
    write_bytes_atomic(derived_path, body)

    latest = cache.latest(raw_dir, suffix="html")
    if not latest:
        raise RuntimeError("senate party divisions download missing from cache")
    return latest.path

