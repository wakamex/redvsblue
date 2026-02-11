from __future__ import annotations

import csv
import json
import os
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode

from rb.cache import ArtifactCache
from rb.net import http_get
from rb.util import redact_url, write_text_atomic


def _fred_api_key(fred_cfg: dict) -> str | None:
    env_key = fred_cfg.get("api_key_env", "FRED_API_KEY")
    val = os.getenv(env_key, "")
    return val.strip() or None


def _fred_api_url(fred_cfg: dict, endpoint: str, params: dict[str, str]) -> str:
    base = fred_cfg.get("api_base_url", "https://api.stlouisfed.org/fred").rstrip("/")
    return f"{base}/{endpoint}?{urlencode(params)}"


def ingest_fred_series(*, series_key: str, series_cfg: dict, fred_cfg: dict, refresh: bool) -> None:
    series_id = series_cfg.get("series_id")
    if not series_id:
        raise ValueError(f"FRED series missing series_id: {series_key}")

    cache = ArtifactCache()

    api_key = _fred_api_key(fred_cfg)

    raw_obs_dir = cache.artifact_dir("fred", "observations", series_key)
    raw_meta_dir = cache.artifact_dir("fred", "series", series_key)
    derived_obs_path = Path("data/derived/fred/observations")
    derived_obs_path.mkdir(parents=True, exist_ok=True)
    derived_obs_path = derived_obs_path / f"{series_key}.csv"
    derived_series_path = Path("data/derived/fred/series")
    derived_series_path.mkdir(parents=True, exist_ok=True)
    derived_series_path = derived_series_path / f"{series_key}.json"

    api_params_raw = series_cfg.get("api_params") or {}
    if not isinstance(api_params_raw, dict):
        raise ValueError(f"FRED series api_params must be a mapping: {series_key}")
    api_params: dict[str, str] = {}
    for k, v in api_params_raw.items():
        ks = str(k).strip()
        if not ks:
            continue
        api_params[ks] = str(v).strip()

    if not refresh:
        have_obs = cache.latest(raw_obs_dir, suffix="json" if api_key else "csv")
        have_meta = cache.latest(raw_meta_dir, suffix="json") if api_key else None
        if have_obs and derived_obs_path.exists() and (not api_key or (have_meta and derived_series_path.exists())):
            return

    if api_key:
        # Observations
        obs_params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": fred_cfg.get("api_default_file_type", "json"),
        }
        obs_params.update(api_params)
        obs_url = _fred_api_url(
            fred_cfg,
            "series/observations",
            obs_params,
        )
        status, headers, body = http_get(obs_url)
        cache.write(
            raw_obs_dir,
            data=body,
            suffix="json",
            meta={"url": redact_url(obs_url), "status": status, "headers": headers},
        )

        payload = json.loads(body.decode("utf-8"))
        obs = payload.get("observations", [])
        # Normalize to a tiny CSV for downstream parsing: date,value,realtime_start,realtime_end
        rows = ["date,value,realtime_start,realtime_end"]
        for o in obs:
            date = o.get("date", "")
            value = o.get("value", "")
            rs = o.get("realtime_start", "")
            re_ = o.get("realtime_end", "")
            rows.append(f"{date},{value},{rs},{re_}")
        write_text_atomic(derived_obs_path, "\n".join(rows) + "\n")

        # Series metadata
        series_url = _fred_api_url(
            fred_cfg,
            "series",
            {"series_id": series_id, "api_key": api_key, "file_type": fred_cfg.get("api_default_file_type", "json")},
        )
        status, headers, body = http_get(series_url)
        cache.write(
            raw_meta_dir,
            data=body,
            suffix="json",
            meta={"url": redact_url(series_url), "status": status, "headers": headers},
        )
        write_text_atomic(derived_series_path, body.decode("utf-8") + ("\n" if not body.endswith(b"\n") else ""))
    else:
        if api_params:
            raise ValueError(f"FRED series {series_key} requires API params but no API key is configured.")
        # Fallback: graph CSV (no API key) for observations only.
        tmpl = fred_cfg.get("graph_csv_url_template") or fred_cfg.get("url_template")
        if not tmpl:
            raise ValueError("FRED graph CSV template missing from spec")
        url = tmpl.format(series_id=series_id)
        status, headers, body = http_get(url)
        cache.write(raw_obs_dir, data=body, suffix="csv", meta={"url": url, "status": status, "headers": headers})

        # Normalize to the same derived schema as the API variant.
        txt = body.decode("utf-8", errors="replace")
        rdr = csv.DictReader(StringIO(txt))
        out_rows = ["date,value,realtime_start,realtime_end"]
        for row in rdr:
            ds = (row.get("DATE") or "").strip()
            if not ds:
                continue
            vs = (row.get(series_id) or "").strip()
            out_rows.append(f"{ds},{vs},,")
        write_text_atomic(derived_obs_path, "\n".join(out_rows) + "\n")
