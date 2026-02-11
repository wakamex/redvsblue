from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rb.spec import load_spec
from rb.util import write_text_atomic

_SNAPSHOT_NAME_RE = re.compile(r"^(\d{8}T\d{6}Z)__sha256_([0-9a-fA-F]+)\.json$")


def _snapshot_stamp(path: Path) -> tuple[str, str]:
    m = _SNAPSHOT_NAME_RE.match(path.name)
    if not m:
        return ("", "")
    return (m.group(1), m.group(2))


def _latest_snapshot_in_dir(path: Path) -> tuple[Path | None, str, str]:
    if not path.exists() or not path.is_dir():
        return (None, "", "")
    best_path: Path | None = None
    best_stamp = ""
    best_sha = ""
    for p in path.glob("*.json"):
        if p.name.endswith(".meta.json"):
            continue
        stamp, sha = _snapshot_stamp(p)
        if not stamp:
            continue
        if best_path is None or stamp > best_stamp:
            best_path = p
            best_stamp = stamp
            best_sha = sha
    return (best_path, best_stamp, best_sha)


def _load_fred_series_meta(path: Path) -> dict[str, str]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    top_rt_start = str(obj.get("realtime_start") or "").strip()
    top_rt_end = str(obj.get("realtime_end") or "").strip()
    first = {}
    seriess = obj.get("seriess")
    if isinstance(seriess, list) and seriess:
        first = seriess[0] or {}
    return {
        "top_realtime_start": top_rt_start,
        "top_realtime_end": top_rt_end,
        "series_realtime_start": str(first.get("realtime_start") or "").strip(),
        "series_realtime_end": str(first.get("realtime_end") or "").strip(),
        "observation_start": str(first.get("observation_start") or "").strip(),
        "observation_end": str(first.get("observation_end") or "").strip(),
        "last_updated": str(first.get("last_updated") or "").strip(),
        "frequency": str(first.get("frequency_short") or first.get("frequency") or "").strip(),
        "units": str(first.get("units_short") or first.get("units") or "").strip(),
        "seasonal_adjustment": str(first.get("seasonal_adjustment_short") or first.get("seasonal_adjustment") or "").strip(),
    }


def _build_rows(*, spec_path: Path, raw_root: Path) -> list[dict[str, str]]:
    spec = load_spec(spec_path)
    metrics: list[dict[str, Any]] = list(spec.get("metrics") or [])
    series_cfg: dict[str, dict[str, Any]] = dict(spec.get("series") or {})

    rows: list[dict[str, str]] = []
    for m in metrics:
        if not bool(m.get("primary")):
            continue

        metric_id = str(m.get("id") or "").strip()
        if not metric_id:
            continue
        inputs = m.get("inputs") or {}
        series_key = str(inputs.get("series") or "").strip()
        metric_family = str(m.get("family") or "").strip()
        metric_label = str(m.get("label") or metric_id).strip()

        row = {
            "metric_id": metric_id,
            "metric_family": metric_family,
            "metric_label": metric_label,
            "series_key": series_key,
            "source": "",
            "series_id": "",
            "status": "",
            "raw_snapshot_path": "",
            "artifact_timestamp_utc_compact": "",
            "artifact_sha256_from_name": "",
            "top_realtime_start": "",
            "top_realtime_end": "",
            "series_realtime_start": "",
            "series_realtime_end": "",
            "observation_start": "",
            "observation_end": "",
            "last_updated": "",
            "frequency": "",
            "units": "",
            "seasonal_adjustment": "",
        }

        if not series_key:
            row["status"] = "non_series_input"
            rows.append(row)
            continue

        sdef = series_cfg.get(series_key) or {}
        if not sdef:
            row["status"] = "missing_spec_series"
            rows.append(row)
            continue
        source = str(sdef.get("source") or "").strip()
        series_id = str(sdef.get("series_id") or "").strip()
        row["source"] = source
        row["series_id"] = series_id

        if source != "fred":
            row["status"] = "non_fred_source"
            rows.append(row)
            continue

        # In our cache layout, directories are usually keyed by series_id; some aliases may use series_key.
        candidates = []
        if series_id:
            candidates.append(raw_root / "series" / series_id)
        candidates.append(raw_root / "series" / series_key)

        best_path: Path | None = None
        best_stamp = ""
        best_sha = ""
        for c in candidates:
            p, stamp, sha = _latest_snapshot_in_dir(c)
            if p is None:
                continue
            if best_path is None or stamp > best_stamp:
                best_path = p
                best_stamp = stamp
                best_sha = sha

        if best_path is None:
            row["status"] = "missing_raw_snapshot"
            rows.append(row)
            continue

        row["status"] = "ok"
        row["raw_snapshot_path"] = str(best_path)
        row["artifact_timestamp_utc_compact"] = best_stamp
        row["artifact_sha256_from_name"] = best_sha
        row.update(_load_fred_series_meta(best_path))
        rows.append(row)

    rows.sort(key=lambda r: r["metric_id"])
    return rows


def write_fred_primary_metric_vintage_report(
    *,
    spec_path: Path,
    raw_root: Path,
    out_csv: Path,
    out_md: Path | None = None,
) -> None:
    rows = _build_rows(spec_path=spec_path, raw_root=raw_root)
    header = [
        "metric_id",
        "metric_family",
        "metric_label",
        "series_key",
        "source",
        "series_id",
        "status",
        "raw_snapshot_path",
        "artifact_timestamp_utc_compact",
        "artifact_sha256_from_name",
        "top_realtime_start",
        "top_realtime_end",
        "series_realtime_start",
        "series_realtime_end",
        "observation_start",
        "observation_end",
        "last_updated",
        "frequency",
        "units",
        "seasonal_adjustment",
    ]

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    tmp.replace(out_csv)

    if out_md is None:
        return

    n_ok = sum(1 for r in rows if r.get("status") == "ok")
    n_non_fred = sum(1 for r in rows if r.get("status") == "non_fred_source")
    n_missing = sum(1 for r in rows if r.get("status") == "missing_raw_snapshot")
    n_missing_spec = sum(1 for r in rows if r.get("status") == "missing_spec_series")
    n_non_series = sum(1 for r in rows if r.get("status") == "non_series_input")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines: list[str] = []
    lines.append("# FRED Vintage Report (Primary Metrics)")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")
    lines.append(f"- Primary metrics scanned: `{len(rows)}`")
    lines.append(f"- `ok`: `{n_ok}`")
    lines.append(f"- `non_fred_source`: `{n_non_fred}`")
    lines.append(f"- `missing_raw_snapshot`: `{n_missing}`")
    lines.append(f"- `missing_spec_series`: `{n_missing_spec}`")
    lines.append(f"- `non_series_input`: `{n_non_series}`")
    lines.append("")
    lines.append("| Metric | Series | Status | Realtime Start | Realtime End | Observation End | Last Updated | Snapshot UTC |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    (r.get("metric_id") or "").replace("|", "\\|"),
                    (r.get("series_id") or r.get("series_key") or "").replace("|", "\\|"),
                    (r.get("status") or "").replace("|", "\\|"),
                    (r.get("series_realtime_start") or r.get("top_realtime_start") or "").replace("|", "\\|"),
                    (r.get("series_realtime_end") or r.get("top_realtime_end") or "").replace("|", "\\|"),
                    (r.get("observation_end") or "").replace("|", "\\|"),
                    (r.get("last_updated") or "").replace("|", "\\|"),
                    (r.get("artifact_timestamp_utc_compact") or "").replace("|", "\\|"),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append(f"CSV: `{out_csv}`")
    write_text_atomic(out_md, "\n".join(lines) + "\n")
