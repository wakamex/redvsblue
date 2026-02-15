from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rb.spec import load_spec
from rb.util import write_text_atomic


@dataclass(frozen=True)
class PartyMetricRow:
    party: str
    metric_id: str
    label: str
    family: str
    primary: bool
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



def _load_party_summary(path: Path) -> dict[tuple[str, str], PartyMetricRow]:
    out: dict[tuple[str, str], PartyMetricRow] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            party = (r.get("party_abbrev") or "").strip()
            metric_id = (r.get("metric_id") or "").strip()
            if not party or not metric_id:
                continue
            out[(party, metric_id)] = PartyMetricRow(
                party=party,
                metric_id=metric_id,
                family=(r.get("metric_family") or "").strip(),
                primary=((r.get("metric_primary") or "").strip() == "1"),
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
    spec_path: Path,
    party_summary_csv: Path,
    out_path: Path,
    primary_only: bool,
    term_randomization_csv: Path | None = Path("reports/permutation_party_term_v1.csv"),
) -> None:
    spec = load_spec(spec_path)
    metrics_cfg: list[dict] = spec.get("metrics") or []

    party = _load_party_summary(party_summary_csv)

    metric_cfg_by_id: dict[str, dict[str, Any]] = {}
    selected_metrics_cfg: list[dict[str, Any]] = []
    metric_ids: list[str] = []
    for m in metrics_cfg:
        mid = (m.get("id") or "").strip()
        if not mid:
            continue
        if primary_only and not bool(m.get("primary")):
            continue
        selected_metrics_cfg.append(m)
        metric_cfg_by_id[mid] = m
        metric_ids.append(mid)

    family_primary_metric_ids: list[tuple[str, str]] = []
    families_with_primary: set[str] = set()
    families_in_scope: set[str] = set()
    for m in selected_metrics_cfg:
        mid = (m.get("id") or "").strip()
        if not mid:
            continue
        family = (m.get("family") or "").strip() or "(none)"
        families_in_scope.add(family)
        if bool(m.get("primary")) and family not in families_with_primary:
            families_with_primary.add(family)
            family_primary_metric_ids.append((family, mid))
    families_without_primary = sorted(f for f in families_in_scope if f not in families_with_primary)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    term_rand_path: Path | None = None
    term_rand: dict[str, dict[str, str]] = {}
    if term_randomization_csv is not None and term_randomization_csv.exists():
        term_rand_path = term_randomization_csv
        term_rand = _load_term_randomization(term_randomization_csv)

    lines: list[str] = []
    lines.append("# Scoreboard (v1)")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")
    lines.append("## Family Headline Summary (Primary Metrics)")
    lines.append("")
    lines.append("One pre-declared primary metric per family, for a compact cross-family read.")
    lines.append("")
    family_header = [
        "Family",
        "Metric",
        "Units",
        "D-R mean",
        "q",
        "CI95(D-R)",
    ]
    family_sep = [
        "---",
        "---",
        "---:",
        "---:",
        "---:",
        "---:",
    ]

    lines.append("| " + " | ".join(family_header) + " |")
    lines.append("| " + " | ".join(family_sep) + " |")
    missing_family_rows = 0
    for family, mid in family_primary_metric_ids:
        d = party.get(("D", mid))
        r = party.get(("R", mid))
        cfg = metric_cfg_by_id.get(mid, {})
        label = d.label if d else (r.label if r else (str(cfg.get("label") or mid)))
        units = d.units if d and d.units else (r.units if r and r.units else "")
        d_mean = d.mean if d else None
        r_mean = r.mean if r else None
        diff = (d_mean - r_mean) if (d_mean is not None and r_mean is not None) else None
        tr = term_rand.get(mid, {})

        row_values = [
            family.replace("|", "\\|"),
            label.replace("|", "\\|"),
            units.replace("|", "\\|"),
            _fmt(diff),
            _fmt(_parse_float(tr.get("q_bh_fdr") or "")),
            _fmt_ci(
                _parse_float(tr.get("bootstrap_ci95_low") or ""),
                _parse_float(tr.get("bootstrap_ci95_high") or ""),
            ),
        ]

        lines.append("| " + " | ".join(row_values) + " |")
        if d is None or r is None:
            missing_family_rows += 1

    if not family_primary_metric_ids:
        placeholder_row = ["(none)", "(none)"] + [""] * max(0, len(family_header) - 2)
        lines.append("| " + " | ".join(placeholder_row) + " |")
    if missing_family_rows:
        lines.append("")
        lines.append(
            f"Note: {missing_family_rows} family headline row(s) are missing D or R values in `{party_summary_csv}`."
        )
    if families_without_primary:
        lines.append("")
        lines.append(
            "Note: families in scope without a declared primary metric are excluded from this headline table: "
            + ", ".join(f"`{f}`" for f in families_without_primary)
            + "."
        )
    lines.append("")
    lines.append("## Party Summary (President Party Only)")
    lines.append("")
    lines.append("Equal weight per presidential term/tenure window (not day-weighted).")
    lines.append("")
    party_header = [
        "Metric",
        "Units",
        "D mean",
        "R mean",
        "D-R mean",
        "D median",
        "R median",
        "n(D)",
        "n(R)",
        "q",
        "CI95(D-R)",
    ]
    party_sep = [
        "---",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
        "---:",
    ]

    lines.append("| " + " | ".join(party_header) + " |")
    lines.append("| " + " | ".join(party_sep) + " |")

    missing_party_rows = 0
    for mid in metric_ids:
        d = party.get(("D", mid))
        r = party.get(("R", mid))
        label = d.label if d else (r.label if r else mid)
        units = d.units if d and d.units else (r.units if r and r.units else "")

        d_mean = d.mean if d else None
        r_mean = r.mean if r else None
        diff = (d_mean - r_mean) if (d_mean is not None and r_mean is not None) else None

        tr = term_rand.get(mid, {})
        row_values = [
            label.replace("|", "\\|"),
            units.replace("|", "\\|"),
            _fmt(d_mean),
            _fmt(r_mean),
            _fmt(diff),
            _fmt(d.median if d else None),
            _fmt(r.median if r else None),
            _fmt_int(d.n_terms if d else None),
            _fmt_int(r.n_terms if r else None),
            _fmt(_parse_float(tr.get("q_bh_fdr") or "")),
            _fmt_ci(
                _parse_float(tr.get("bootstrap_ci95_low") or ""),
                _parse_float(tr.get("bootstrap_ci95_high") or ""),
            ),
        ]
        lines.append("| " + " | ".join(row_values) + " |")
        if d is None or r is None:
            missing_party_rows += 1

    if missing_party_rows:
        lines.append("")
        lines.append(f"Note: {missing_party_rows} metric(s) are missing D or R rows in `{party_summary_csv}`.")
    if term_rand_path is not None:
        lines.append("")
        lines.append(f"Significance columns sourced from `{term_rand_path}`.")
    else:
        lines.append("")
        lines.append("Significance columns are blank until `rb randomization` has been run.")

    lines.append("")
    lines.append("## Data Appendix")
    lines.append("")
    lines.append("Generated from:")
    lines.append(f"- `{spec_path}`")
    lines.append(f"- `{party_summary_csv}`")
    if term_rand_path is not None:
        lines.append(f"- `{term_rand_path}`")
    lines.append("")
    lines.append("Rebuild:")
    lines.append("```sh")
    lines.append("uv sync")
    lines.append(".venv/bin/rb ingest --refresh")
    lines.append(".venv/bin/rb presidents --refresh")
    lines.append(".venv/bin/rb compute")
    lines.append(".venv/bin/rb randomization")
    lines.append("```")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(out_path, "\n".join(lines) + "\n")
