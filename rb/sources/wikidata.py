from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from rb.cache import ArtifactCache
from rb.net import http_get
from rb.util import redact_url, write_bytes_atomic


def fetch_sparql_json(*, query: str, refresh: bool, cache_key: str) -> Path:
    """Fetch a Wikidata SPARQL query result as JSON; return path to cached raw artifact."""
    base = "https://query.wikidata.org/sparql"
    url = f"{base}?{urlencode({'format': 'json', 'query': query})}"

    cache = ArtifactCache()
    raw_dir = cache.artifact_dir("wikidata", cache_key)

    if not refresh:
        have = cache.latest(raw_dir, suffix="json")
        if have:
            return have.path

    status, headers, body = http_get(url, headers={"Accept": "application/sparql-results+json"})
    artifact = cache.write(raw_dir, data=body, suffix="json", meta={"url": redact_url(url), "status": status, "headers": headers})
    return artifact.path


def fetch_presidents_terms(*, refresh: bool) -> Path:
    query_path = Path("queries/wikidata_presidents.sparql")
    query = query_path.read_text(encoding="utf-8")
    raw_path = fetch_sparql_json(query=query, refresh=refresh, cache_key="presidents_terms")

    # Copy the raw json to a stable derived location too (useful for debugging, but still reproducible via raw/).
    derived_dir = Path("data/derived/wikidata")
    derived_dir.mkdir(parents=True, exist_ok=True)
    derived_raw_path = derived_dir / "presidents_terms.json"

    body = raw_path.read_bytes()
    # Keep a stable, newline-terminated copy for debugging (still reproducible via data/raw).
    if not body.endswith(b"\n"):
        body = body + b"\n"
    write_bytes_atomic(derived_raw_path, body)

    # Also store the query text alongside derived artifacts for transparency.
    query_out = derived_dir / "presidents_terms.sparql"
    query_out.write_text(query, encoding="utf-8")

    return raw_path
