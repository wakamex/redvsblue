from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rb.util import write_text_atomic



@dataclass(frozen=True)
class _PartyMetricRow:
    party: str
    metric_id: str
    label: str
    family: str
    agg_kind: str
    units: str
    n_terms: int | None
    mean: float | None
    median: float | None


def _parse_int(s: str) -> int | None:
    txt = (s or "").strip()
    if not txt:
        return None
    try:
        return int(txt)
    except ValueError:
        return None


def _parse_float(s: str) -> float | None:
    txt = (s or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def _fmt(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:.6f}"


def _fmt_int(v: int | None) -> str:
    return "" if v is None else str(v)


def _fmt_ci(lo: float | None, hi: float | None) -> str:
    if lo is None or hi is None:
        return ""
    return f"[{_fmt(lo)}, {_fmt(hi)}]"


def _load_party_summary(path: Path) -> dict[tuple[str, str], _PartyMetricRow]:
    out: dict[tuple[str, str], _PartyMetricRow] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            party = (r.get("party_abbrev") or "").strip()
            metric_id = (r.get("metric_id") or "").strip()
            if not party or not metric_id:
                continue
            out[(party, metric_id)] = _PartyMetricRow(
                party=party,
                metric_id=metric_id,
                family=(r.get("metric_family") or "").strip(),
                label=(r.get("metric_label") or "").strip(),
                agg_kind=(r.get("agg_kind") or "").strip(),
                units=(r.get("units") or "").strip(),
                n_terms=_parse_int(r.get("n_terms") or ""),
                mean=_parse_float(r.get("mean") or ""),
                median=_parse_float(r.get("median") or ""),
            )
    return out


def _load_term_randomization(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            mid = (r.get("metric_id") or "").strip()
            if not mid:
                continue
            out[mid] = r
    return out


def write_scoreboard_md(
    *,
    party_summary_csv: Path,
    out_path: Path,
    term_randomization_csv: Path | None = Path("reports/permutation_party_term_v1.csv"),
) -> None:
    party = _load_party_summary(party_summary_csv)

    # Collect unique metric IDs in the order they appear for D rows.
    metric_ids: list[str] = []
    seen: set[str] = set()
    for (p, mid) in party:
        if mid not in seen:
            seen.add(mid)
            metric_ids.append(mid)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    term_rand_path: Path | None = None
    term_rand: dict[str, dict[str, str]] = {}
    if term_randomization_csv is not None and term_randomization_csv.exists():
        term_rand_path = term_randomization_csv
        term_rand = _load_term_randomization(term_randomization_csv)

    lines: list[str] = []
    lines.append("# Scoreboard")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")
    lines.append("All metrics, sorted by FDR-corrected q-value (BH). Equal weight per presidential term.")
    lines.append("")

    header = [
        "Metric",
        "Family",
        "Agg",
        "Units",
        "D mean",
        "R mean",
        "D-R",
        "n(D)",
        "n(R)",
        "q",
        "CI95(D-R)",
    ]
    sep = [
        "---",
        "---",
        "---",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
    ]

    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(sep) + " |")

    rows_data: list[tuple[float, str]] = []
    for mid in metric_ids:
        d = party.get(("D", mid))
        r = party.get(("R", mid))
        full_label = d.label if d else (r.label if r else mid)
        # Strip parenthetical — agg/units/source are in their own columns now.
        paren_idx = full_label.find("(")
        label = full_label[:paren_idx].strip() if paren_idx > 0 else full_label
        family = d.family if d else (r.family if r else "")
        agg = d.agg_kind if d else (r.agg_kind if r else "")
        units = d.units if d and d.units else (r.units if r and r.units else "")

        d_mean = d.mean if d else None
        r_mean = r.mean if r else None
        diff = (d_mean - r_mean) if (d_mean is not None and r_mean is not None) else None

        tr = term_rand.get(mid, {})
        q_val = _parse_float(tr.get("q_bh_fdr") or "")
        row_values = [
            label.replace("|", "\\|"),
            family.replace("|", "\\|"),
            agg.replace("|", "\\|"),
            units.replace("|", "\\|"),
            _fmt(d_mean),
            _fmt(r_mean),
            _fmt(diff),
            _fmt_int(d.n_terms if d else None),
            _fmt_int(r.n_terms if r else None),
            _fmt(q_val),
            _fmt_ci(
                _parse_float(tr.get("bootstrap_ci95_low") or ""),
                _parse_float(tr.get("bootstrap_ci95_high") or ""),
            ),
        ]
        row_line = "| " + " | ".join(row_values) + " |"
        rows_data.append((q_val if q_val is not None else 1e9, row_line))
    rows_data.sort(key=lambda t: t[0])
    for _, row_line in rows_data:
        lines.append(row_line)

    if term_rand_path is not None:
        lines.append("")
        lines.append(f"q-values sourced from `{term_rand_path}`.")
    else:
        lines.append("")
        lines.append("q-values are blank until `rb randomization` has been run.")

    lines.append("")
    lines.append("## Rebuild")
    lines.append("")
    lines.append("```sh")
    lines.append("uv sync")
    lines.append(".venv/bin/rb ingest --refresh")
    lines.append(".venv/bin/rb presidents --refresh")
    lines.append(".venv/bin/rb compute")
    lines.append(".venv/bin/rb randomization")
    lines.append(".venv/bin/rb scoreboard")
    lines.append("```")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(out_path, "\n".join(lines) + "\n")
