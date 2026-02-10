from __future__ import annotations

from pathlib import Path

from rb.cache import ArtifactCache
from rb.http import http_get
from rb.util import redact_url, write_bytes_atomic, write_text_atomic


def ingest_nber_cycles(nber_cfg: dict, *, refresh: bool) -> None:
    url = nber_cfg.get("url")
    if not url:
        raise ValueError("NBER source missing url")

    cache = ArtifactCache()
    raw_dir = cache.artifact_dir("nber", "business_cycle_dates")
    derived_path = Path("data/derived/nber")
    derived_path.mkdir(parents=True, exist_ok=True)
    derived_path = derived_path / "business_cycle_dates.json"

    if not refresh:
        have = cache.latest(raw_dir, suffix="json")
        if have and derived_path.exists():
            return

    status, headers, body = http_get(url)
    cache.write(raw_dir, data=body, suffix="json", meta={"url": redact_url(url), "status": status, "headers": headers})
    write_bytes_atomic(derived_path, body)
    if not body.endswith(b"\n"):
        # Keep JSON files newline-terminated.
        write_text_atomic(derived_path, body.decode("utf-8") + "\n")

