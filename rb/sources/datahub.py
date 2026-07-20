from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from pathlib import Path

from rb.cache import ArtifactCache
from rb.net import http_get
from rb.util import redact_url, write_text_atomic


def _configured_date(value: object) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(str(value))


def ingest_datahub_series(
    *,
    source_name: str,
    series_key: str,
    series_cfg: dict,
    source_cfg: dict,
    refresh: bool,
) -> None:
    """Fetch one DataHub CSV and materialize a filtered date/value series."""
    url = source_cfg.get("url")
    if not url:
        raise ValueError(f"DataHub source missing url: {source_name}")

    date_column = str(series_cfg.get("date_column") or "Date")
    value_column = str(series_cfg.get("value_column") or "")
    if not value_column:
        raise ValueError(f"DataHub series missing value_column: {series_key}")

    cache = ArtifactCache()
    raw_dir = cache.artifact_dir("datahub", source_name)
    derived_dir = Path("data/derived/datahub")
    derived_dir.mkdir(parents=True, exist_ok=True)
    derived_path = derived_dir / f"{series_key}.csv"

    artifact = cache.latest(raw_dir, suffix="csv")
    if not refresh and artifact and derived_path.exists():
        return

    if refresh or artifact is None:
        status, headers, body = http_get(str(url))
        cache.write(
            raw_dir,
            data=body,
            suffix="csv",
            meta={"url": redact_url(str(url)), "status": status, "headers": headers},
        )
    else:
        body = artifact.path.read_bytes()

    reader = csv.DictReader(StringIO(body.decode("utf-8", errors="strict")))
    fieldnames = set(reader.fieldnames or [])
    missing_columns = {date_column, value_column} - fieldnames
    if missing_columns:
        raise ValueError(
            f"DataHub series {series_key} missing CSV columns: {sorted(missing_columns)}"
        )

    filters = series_cfg.get("filters") or {}
    start_date = _configured_date(filters.get("start_date"))
    end_date = _configured_date(filters.get("end_date"))
    output = ["date,value"]

    for row in reader:
        date_text = (row.get(date_column) or "").strip()
        value_text = (row.get(value_column) or "").strip()
        if not date_text or not value_text:
            continue
        observation_date = date.fromisoformat(date_text)
        if start_date and observation_date < start_date:
            continue
        if end_date and observation_date > end_date:
            continue
        float(value_text)  # Fail clearly if the upstream schema changes.
        output.append(f"{observation_date.isoformat()},{value_text}")

    if len(output) == 1:
        raise ValueError(f"DataHub series {series_key} produced no observations")

    write_text_atomic(derived_path, "\n".join(output) + "\n")
