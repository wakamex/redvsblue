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
    # Keep stable formatting across runs.
    return f"{v:.6f}"


def _fmt_int(v: int | None) -> str:
    return "" if v is None else str(v)


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


def _load_window_labels(path: Path) -> dict[str, dict[str, Any]]:
    labels: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            wid = (r.get("window_id") or "").strip()
            if not wid:
                continue
            labels[wid] = r
    return labels


def _compute_unified_summary(
    *,
    window_metrics_csv: Path,
    window_labels_csv: Path,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    # Returns (metric_id, pres_party, unified_flag) -> aggregate dict.
    labels = _load_window_labels(window_labels_csv)

    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    with window_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            wid = (r.get("term_id") or "").strip()
            metric_id = (r.get("metric_id") or "").strip()
            if not wid or not metric_id:
                continue

            lab = labels.get(wid)
            if not lab:
                continue

            v = _parse_float(r.get("value") or "")
            if v is None:
                continue

            pres_party = (lab.get("pres_party") or "").strip()
            unified = (lab.get("unified_government") or "").strip() or "0"
            days = _parse_int(lab.get("window_days") or "") or 0

            k = (metric_id, pres_party, unified)
            g = groups.get(k)
            if g is None:
                g = {
                    "metric_id": metric_id,
                    "metric_label": (r.get("metric_label") or "").strip(),
                    "metric_family": (r.get("metric_family") or "").strip(),
                    "metric_primary": (r.get("metric_primary") or "").strip(),
                    "agg_kind": (r.get("agg_kind") or "").strip(),
                    "units": (r.get("units") or "").strip(),
                    "pres_party": pres_party,
                    "unified_government": unified,
                    "n_windows": 0,
                    "total_days": 0,
                    "sum": 0.0,
                    "values": [],
                    "w_sum": 0.0,
                    "w": 0.0,
                }
                groups[k] = g

            g["n_windows"] += 1
            g["total_days"] += days
            g["sum"] += v
            g["values"].append(v)
            if days > 0:
                g["w_sum"] += v * days
                g["w"] += days

    # Finalize means.
    for g in groups.values():
        n = int(g["n_windows"])
        g["mean_unweighted"] = (g["sum"] / n) if n else None
        w = float(g["w"])
        g["mean_weighted_by_days"] = (g["w_sum"] / w) if w > 0 else None

    return groups


def _compute_alignment_summary(
    *,
    window_metrics_csv: Path,
    window_labels_csv: Path,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    # Returns (metric_id, pres_party, alignment_label) -> aggregate dict.
    # alignment_label ∈ {"aligned_both","aligned_house_only","aligned_senate_only","aligned_none"}.
    labels = _load_window_labels(window_labels_csv)

    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    with window_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            wid = (r.get("term_id") or "").strip()
            metric_id = (r.get("metric_id") or "").strip()
            if not wid or not metric_id:
                continue

            lab = labels.get(wid)
            if not lab:
                continue

            v = _parse_float(r.get("value") or "")
            if v is None:
                continue

            pres_party = (lab.get("pres_party") or "").strip()
            if pres_party not in {"D", "R"}:
                continue

            house = (lab.get("house_majority") or "").strip()
            senate = (lab.get("senate_majority") or "").strip()
            days = _parse_int(lab.get("window_days") or "") or 0

            aligned_house = "1" if house == pres_party else "0"
            aligned_senate = "1" if senate == pres_party else "0"
            aligned_chambers = int(aligned_house) + int(aligned_senate)

            if aligned_chambers == 2:
                alignment = "aligned_both"
            elif aligned_house == "1":
                alignment = "aligned_house_only"
            elif aligned_senate == "1":
                alignment = "aligned_senate_only"
            else:
                alignment = "aligned_none"

            k = (metric_id, pres_party, alignment)
            g = groups.get(k)
            if g is None:
                g = {
                    "metric_id": metric_id,
                    "metric_label": (r.get("metric_label") or "").strip(),
                    "metric_family": (r.get("metric_family") or "").strip(),
                    "metric_primary": (r.get("metric_primary") or "").strip(),
                    "agg_kind": (r.get("agg_kind") or "").strip(),
                    "units": (r.get("units") or "").strip(),
                    "pres_party": pres_party,
                    "alignment": alignment,
                    "aligned_house": aligned_house,
                    "aligned_senate": aligned_senate,
                    "aligned_chambers": aligned_chambers,
                    "n_windows": 0,
                    "total_days": 0,
                    "sum": 0.0,
                    "values": [],
                    "w_sum": 0.0,
                    "w": 0.0,
                }
                groups[k] = g

            g["n_windows"] += 1
            g["total_days"] += days
            g["sum"] += v
            g["values"].append(v)
            if days > 0:
                g["w_sum"] += v * days
                g["w"] += days

    # Finalize means.
    for g in groups.values():
        n = int(g["n_windows"])
        g["mean_unweighted"] = (g["sum"] / n) if n else None
        w = float(g["w"])
        g["mean_weighted_by_days"] = (g["w_sum"] / w) if w > 0 else None

    return groups


def write_scoreboard_md(
    *,
    spec_path: Path,
    party_summary_csv: Path,
    out_path: Path,
    primary_only: bool,
    window_metrics_csv: Path | None,
    window_labels_csv: Path | None,
) -> None:
    spec = load_spec(spec_path)
    metrics_cfg: list[dict] = spec.get("metrics") or []

    party = _load_party_summary(party_summary_csv)

    metric_ids: list[str] = []
    for m in metrics_cfg:
        mid = (m.get("id") or "").strip()
        if not mid:
            continue
        if primary_only and not bool(m.get("primary")):
            continue
        metric_ids.append(mid)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    lines: list[str] = []
    lines.append("# Scoreboard (v1)")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")
    lines.append("## Party Summary (President Party Only)")
    lines.append("")
    lines.append("Equal weight per presidential term/tenure window (not day-weighted).")
    lines.append("")
    lines.append("| Metric | Units | D mean | R mean | D-R mean | D median | R median | n(D) | n(R) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    missing_party_rows = 0
    for mid in metric_ids:
        d = party.get(("D", mid))
        r = party.get(("R", mid))
        label = d.label if d else (r.label if r else mid)
        units = d.units if d and d.units else (r.units if r and r.units else "")

        d_mean = d.mean if d else None
        r_mean = r.mean if r else None
        diff = (d_mean - r_mean) if (d_mean is not None and r_mean is not None) else None

        lines.append(
            "| "
            + " | ".join(
                [
                    label.replace("|", "\\|"),
                    units.replace("|", "\\|"),
                    _fmt(d_mean),
                    _fmt(r_mean),
                    _fmt(diff),
                    _fmt(d.median if d else None),
                    _fmt(r.median if r else None),
                    _fmt_int(d.n_terms if d else None),
                    _fmt_int(r.n_terms if r else None),
                ]
            )
            + " |"
        )
        if d is None or r is None:
            missing_party_rows += 1

    if missing_party_rows:
        lines.append("")
        lines.append(f"Note: {missing_party_rows} metric(s) are missing D or R rows in `{party_summary_csv}`.")

    if window_metrics_csv and window_labels_csv and window_metrics_csv.exists() and window_labels_csv.exists():
        groups = _compute_unified_summary(window_metrics_csv=window_metrics_csv, window_labels_csv=window_labels_csv)
        align_groups = _compute_alignment_summary(window_metrics_csv=window_metrics_csv, window_labels_csv=window_labels_csv)

        lines.append("")
        lines.append("## Unified vs Divided Government (Regime Windows)")
        lines.append("")
        lines.append("Windows are (President window) intersected with (Congress-control periods).")
        lines.append("")
        lines.append("| Metric | Units | P party | Unified? | Mean (day-weighted) | Mean (unweighted) | n(windows) | total_days |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")

        # Only show regimes where P is D or R, and only selected metrics.
        for mid in metric_ids:
            for pres_party in ("D", "R"):
                for unified in ("1", "0"):
                    g = groups.get((mid, pres_party, unified))
                    if not g:
                        continue
                    label = (g.get("metric_label") or mid).replace("|", "\\|")
                    units = (g.get("units") or "").replace("|", "\\|")
                    lines.append(
                        "| "
                        + " | ".join(
                            [
                                label,
                                units,
                                pres_party,
                                "yes" if unified == "1" else "no",
                                _fmt(g.get("mean_weighted_by_days")),
                                _fmt(g.get("mean_unweighted")),
                                str(int(g.get("n_windows") or 0)),
                                str(int(g.get("total_days") or 0)),
                            ]
                        )
                        + " |"
                    )

        lines.append("")
        lines.append("Caution: for window-aggregations that are *totals* (e.g., `end_minus_start`),")
        lines.append("day-weighting the window-level totals is not always meaningful; prefer per-year / CAGR variants for regime comparisons.")

        lines.append("")
        lines.append("## President Alignment With Congress (House vs Senate)")
        lines.append("")
        lines.append("Breakout by whether the president's party controls: both chambers, only House, only Senate, or neither.")
        lines.append("")
        lines.append("| Metric | Units | P party | Alignment | Mean (day-weighted) | Mean (unweighted) | n(windows) | total_days |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")

        alignment_order = ("aligned_both", "aligned_house_only", "aligned_senate_only", "aligned_none")
        alignment_label = {
            "aligned_both": "both",
            "aligned_house_only": "house only",
            "aligned_senate_only": "senate only",
            "aligned_none": "neither",
        }

        for mid in metric_ids:
            for pres_party in ("D", "R"):
                for a in alignment_order:
                    g = align_groups.get((mid, pres_party, a))
                    if not g:
                        continue
                    label = (g.get("metric_label") or mid).replace("|", "\\|")
                    units = (g.get("units") or "").replace("|", "\\|")
                    lines.append(
                        "| "
                        + " | ".join(
                            [
                                label,
                                units,
                                pres_party,
                                alignment_label.get(a, a),
                                _fmt(g.get("mean_weighted_by_days")),
                                _fmt(g.get("mean_unweighted")),
                                str(int(g.get("n_windows") or 0)),
                                str(int(g.get("total_days") or 0)),
                            ]
                        )
                        + " |"
                    )

    lines.append("")
    lines.append("## Data Appendix")
    lines.append("")
    lines.append("Generated from:")
    lines.append(f"- `{spec_path}`")
    lines.append(f"- `{party_summary_csv}`")
    if window_metrics_csv and window_labels_csv:
        lines.append(f"- `{window_metrics_csv}`")
        lines.append(f"- `{window_labels_csv}`")
    lines.append("")
    lines.append("Rebuild:")
    lines.append("```sh")
    lines.append("UV_CACHE_DIR=/tmp/uv-cache uv sync")
    lines.append(".venv/bin/rb ingest --refresh")
    lines.append(".venv/bin/rb presidents --source congress_legislators --granularity tenure --refresh")
    lines.append(".venv/bin/rb compute")
    lines.append(".venv/bin/rb congress --refresh")
    lines.append(".venv/bin/rb regimes --refresh")
    lines.append("```")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(out_path, "\n".join(lines) + "\n")
