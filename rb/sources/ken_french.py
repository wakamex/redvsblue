from __future__ import annotations

import csv
import re
import zipfile
from datetime import date
from io import StringIO
from pathlib import Path

from rb.cache import ArtifactCache
from rb.http import http_get
from rb.util import redact_url, write_text_atomic


def _yyyymm_to_date(s: str) -> date:
    s = s.strip()
    if len(s) != 6 or not s.isdigit():
        raise ValueError(f"invalid yyyymm: {s!r}")
    return date(int(s[:4]), int(s[4:6]), 1)


def ingest_ken_french_dataset(kf_cfg: dict, *, dataset_key: str, refresh: bool) -> None:
    url = kf_cfg.get("url")
    if not url:
        raise ValueError("Ken French source missing url")

    cache = ArtifactCache()
    raw_dir = cache.artifact_dir("ken_french", dataset_key)

    derived_dir = Path("data/derived/ken_french")
    derived_dir.mkdir(parents=True, exist_ok=True)
    derived_path = derived_dir / f"{dataset_key}.csv"

    if not refresh:
        have = cache.latest(raw_dir, suffix="zip")
        if have and derived_path.exists():
            return

    status, headers, body = http_get(url)
    cache.write(raw_dir, data=body, suffix="zip", meta={"url": redact_url(url), "status": status, "headers": headers})

    encoding = kf_cfg.get("encoding", "latin-1")
    hints = kf_cfg.get("parse_hints") or {}
    inner_re = re.compile(str(hints.get("inner_filename_regex") or r".*"), re.I)
    missing_values = {str(v) for v in (hints.get("missing_values") or [])}

    artifact = cache.latest(raw_dir, suffix="zip")
    if not artifact:
        raise RuntimeError("Ken French zip download missing from cache")

    with zipfile.ZipFile(artifact.path) as zf:
        names = zf.namelist()
        inner_name = next((n for n in names if inner_re.search(n)), None)
        if not inner_name:
            raise ValueError(f"Could not find inner CSV matching regex in zip: {names[:10]}")
        raw_csv = zf.read(inner_name).decode(encoding, errors="replace")

    # Skip preamble until we hit a YYYYMM row.
    skip_pat = str(hints.get("skip_rows_until") or "regex:^\\s*\\d{6}")
    if skip_pat.startswith("regex:"):
        row_re = re.compile(skip_pat[len("regex:") :])
    else:
        row_re = re.compile(r"^\\s*\\d{6}")

    lines = raw_csv.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if row_re.search(line):
            start_idx = i
            break
    if start_idx is None:
        raise ValueError("Ken French CSV: could not find first data row")

    # The monthly table is contiguous until the first blank line.
    table_lines: list[str] = []
    for line in lines[start_idx:]:
        if not line.strip():
            break
        table_lines.append(line)

    rdr = csv.reader(StringIO("\n".join(table_lines)))
    header_written = False
    out_rows: list[str] = []
    for row in rdr:
        if not row:
            continue
        yyyymm = row[0].strip()
        if not yyyymm.isdigit():
            continue
        d = _yyyymm_to_date(yyyymm)
        vals = [c.strip() for c in row[1:]]
        if not header_written:
            # Standard columns for this dataset (monthly factors): Mkt-RF, SMB, HML, RF
            out_rows.append("date,mkt_rf,smb,hml,rf")
            header_written = True

        # Some rows may be missing or malformed; skip if too short.
        if len(vals) < 4:
            continue
        cleaned = [(c if c not in missing_values else "") for c in vals[:4]]
        out_rows.append(f"{d.isoformat()},{cleaned[0]},{cleaned[1]},{cleaned[2]},{cleaned[3]}")

    if not out_rows:
        raise ValueError("Ken French CSV: parsed no rows")

    write_text_atomic(derived_path, "\n".join(out_rows) + "\n")
