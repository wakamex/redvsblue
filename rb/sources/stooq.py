from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from pathlib import Path

from rb.cache import ArtifactCache
from rb.net import http_get
from rb.util import redact_url, write_text_atomic


def _parse_date(s: str) -> date:
    y, m, d = s.split("-", 2)
    return date(int(y), int(m), int(d))


def ingest_stooq_series(*, series_key: str, series_cfg: dict, stooq_cfg: dict, refresh: bool) -> None:
    symbol = series_cfg.get("symbol")
    if not symbol:
        raise ValueError(f"Stooq series missing symbol: {series_key}")

    url_tmpl = stooq_cfg.get("url_template")
    if not url_tmpl:
        raise ValueError("Stooq source missing url_template")

    url = url_tmpl.format(symbol=symbol)

    cache = ArtifactCache()
    raw_dir = cache.artifact_dir("stooq", "daily", symbol.replace("^", ""))

    derived_dir = Path("data/derived/stooq")
    derived_dir.mkdir(parents=True, exist_ok=True)
    # Use series_key so multiple spec series can reuse one symbol with different filters.
    derived_path = derived_dir / f"{series_key}.csv"

    if not refresh:
        have = cache.latest(raw_dir, suffix="csv")
        if have and derived_path.exists():
            return

    status, headers, body = http_get(url)
    cache.write(raw_dir, data=body, suffix="csv", meta={"url": redact_url(url), "status": status, "headers": headers})

    text = body.decode("utf-8", errors="replace")
    rdr = csv.DictReader(StringIO(text))
    out_rows: list[str] = ["date,value"]

    start_date: date | None = None
    end_date: date | None = None
    filters = series_cfg.get("filters") or {}
    if isinstance(filters, dict) and filters.get("start_date"):
        start_date = _parse_date(str(filters["start_date"]))
    if isinstance(filters, dict) and filters.get("end_date"):
        end_date = _parse_date(str(filters["end_date"]))

    col = series_cfg.get("column", "Close")
    for row in rdr:
        if not row:
            continue
        ds = (row.get("Date") or "").strip()
        if not ds:
            continue
        d = _parse_date(ds)
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        vs = (row.get(col) or "").strip()
        if not vs:
            continue
        out_rows.append(f"{ds},{vs}")

    write_text_atomic(derived_path, "\n".join(out_rows) + "\n")
