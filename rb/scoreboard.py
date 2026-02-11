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


def _fmt_ci(lo: float | None, hi: float | None) -> str:
    if lo is None or hi is None:
        return ""
    return f"[{_fmt(lo)}, {_fmt(hi)}]"


def _derive_q_flag(row: dict[str, str], *, key: str, threshold: float) -> str:
    raw = (row.get(key) or "").strip()
    if raw in {"0", "1"}:
        return raw
    q = _parse_float(row.get("q_bh_fdr") or "")
    if q is None:
        return ""
    return "1" if q < threshold else "0"


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    n = len(ys)
    if n % 2 == 1:
        return ys[n // 2]
    return 0.5 * (ys[n // 2 - 1] + ys[n // 2])


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


def _load_within_randomization(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            mid = (r.get("metric_id") or "").strip()
            pres_party = (r.get("pres_party") or "").strip()
            if not mid or not pres_party:
                continue
            out[(mid, pres_party)] = r
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


def _compute_within_president_unified_deltas(
    *,
    window_metrics_csv: Path,
    window_labels_csv: Path,
    min_window_days: int = 0,
) -> dict[tuple[str, str], dict[str, Any]]:
    # Returns (metric_id, pres_party) -> aggregate of within-president (unified - divided) deltas.
    # For each president term and metric, compute mean metric in unified windows and in divided windows.
    # Then aggregate deltas across president terms that experienced both states.
    labels = _load_window_labels(window_labels_csv)

    # (metric_id, pres_party, president_term_id, unified_flag) -> accumulator
    by_pres_status: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    metric_meta: dict[str, dict[str, str]] = {}

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
            pres_term_id = (lab.get("president_term_id") or "").strip()
            if not pres_term_id:
                continue

            unified = (lab.get("unified_government") or "").strip() or "0"
            days = _parse_int(lab.get("window_days") or "") or 0
            if days < min_window_days:
                continue

            k = (metric_id, pres_party, pres_term_id, unified)
            g = by_pres_status.get(k)
            if g is None:
                g = {"sum": 0.0, "n": 0, "w_sum": 0.0, "w": 0}
                by_pres_status[k] = g

            g["sum"] += v
            g["n"] += 1
            if days > 0:
                g["w_sum"] += v * days
                g["w"] += days

            if metric_id not in metric_meta:
                metric_meta[metric_id] = {
                    "metric_label": (r.get("metric_label") or "").strip(),
                    "metric_family": (r.get("metric_family") or "").strip(),
                    "metric_primary": (r.get("metric_primary") or "").strip(),
                    "agg_kind": (r.get("agg_kind") or "").strip(),
                    "units": (r.get("units") or "").strip(),
                }

    # Collapse to per-president term means by unified status.
    per_pres: dict[tuple[str, str, str], dict[str, float | None]] = {}
    for (metric_id, pres_party, pres_term_id, unified), g in by_pres_status.items():
        mean: float | None
        if int(g["w"]) > 0:
            mean = float(g["w_sum"]) / float(g["w"])
        else:
            n = int(g["n"])
            mean = (float(g["sum"]) / n) if n > 0 else None
        tkey = (metric_id, pres_party, pres_term_id)
        slot = per_pres.get(tkey)
        if slot is None:
            slot = {"u": None, "d": None}
            per_pres[tkey] = slot
        if unified == "1":
            slot["u"] = mean
        else:
            slot["d"] = mean

    out: dict[tuple[str, str], dict[str, Any]] = {}
    # Pre-seed groups to preserve rows even when n_with_both is zero.
    for metric_id, meta in metric_meta.items():
        for pres_party in ("D", "R"):
            out[(metric_id, pres_party)] = {
                "metric_id": metric_id,
                "metric_label": meta.get("metric_label") or metric_id,
                "metric_family": meta.get("metric_family") or "",
                "metric_primary": meta.get("metric_primary") or "",
                "agg_kind": meta.get("agg_kind") or "",
                "units": meta.get("units") or "",
                "pres_party": pres_party,
                "n_with_unified": 0,
                "n_with_divided": 0,
                "n_with_both": 0,
                "deltas": [],
                "mean_delta": None,
                "median_delta": None,
            }

    for (metric_id, pres_party, _pres_term_id), states in per_pres.items():
        grp = out.get((metric_id, pres_party))
        if not grp:
            continue
        u = states.get("u")
        d = states.get("d")
        if u is not None:
            grp["n_with_unified"] += 1
        if d is not None:
            grp["n_with_divided"] += 1
        if u is not None and d is not None:
            grp["n_with_both"] += 1
            grp["deltas"].append(u - d)

    for grp in out.values():
        ds = list(grp["deltas"])
        n = len(ds)
        if n > 0:
            grp["mean_delta"] = sum(ds) / n
            grp["median_delta"] = _median(ds)

    return out


def _write_within_president_unified_deltas_csv(
    *,
    metric_ids: list[str],
    deltas: dict[tuple[str, str], dict[str, Any]],
    out_path: Path,
    min_window_days: int = 0,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "metric_id",
        "metric_label",
        "metric_family",
        "metric_primary",
        "agg_kind",
        "units",
        "pres_party",
        "mean_delta_unified_minus_divided",
        "median_delta_unified_minus_divided",
        "n_presidents_with_both",
        "n_presidents_with_unified",
        "n_presidents_with_divided",
        "min_window_days_filter",
    ]
    rows: list[dict[str, str]] = []
    for mid in metric_ids:
        for pres_party in ("D", "R"):
            g = deltas.get((mid, pres_party))
            if not g:
                rows.append(
                    {
                        "metric_id": mid,
                        "metric_label": mid,
                        "metric_family": "",
                        "metric_primary": "",
                        "agg_kind": "",
                        "units": "",
                        "pres_party": pres_party,
                        "mean_delta_unified_minus_divided": "",
                        "median_delta_unified_minus_divided": "",
                        "n_presidents_with_both": "0",
                        "n_presidents_with_unified": "0",
                        "n_presidents_with_divided": "0",
                        "min_window_days_filter": str(int(min_window_days)),
                    }
                )
                continue

            rows.append(
                {
                    "metric_id": str(g.get("metric_id") or mid),
                    "metric_label": str(g.get("metric_label") or mid),
                    "metric_family": str(g.get("metric_family") or ""),
                    "metric_primary": str(g.get("metric_primary") or ""),
                    "agg_kind": str(g.get("agg_kind") or ""),
                    "units": str(g.get("units") or ""),
                    "pres_party": pres_party,
                    "mean_delta_unified_minus_divided": _fmt(_parse_float(str(g.get("mean_delta") or ""))),
                    "median_delta_unified_minus_divided": _fmt(_parse_float(str(g.get("median_delta") or ""))),
                    "n_presidents_with_both": str(int(g.get("n_with_both") or 0)),
                    "n_presidents_with_unified": str(int(g.get("n_with_unified") or 0)),
                    "n_presidents_with_divided": str(int(g.get("n_with_divided") or 0)),
                    "min_window_days_filter": str(int(min_window_days)),
                }
            )

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_path)


def write_scoreboard_md(
    *,
    spec_path: Path,
    party_summary_csv: Path,
    out_path: Path,
    primary_only: bool,
    window_metrics_csv: Path | None,
    window_labels_csv: Path | None,
    term_randomization_csv: Path | None = Path("reports/permutation_party_term_v1.csv"),
    within_randomization_csv: Path | None = Path("reports/permutation_unified_within_term_v1.csv"),
    output_within_president_deltas_csv: Path | None = None,
    within_president_min_window_days: int = 0,
    show_robustness_links: bool = True,
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

    term_rand_path: Path | None = None
    term_rand: dict[str, dict[str, str]] = {}
    if term_randomization_csv is not None and term_randomization_csv.exists():
        term_rand_path = term_randomization_csv
        term_rand = _load_term_randomization(term_randomization_csv)

    within_rand_path: Path | None = None
    within_rand: dict[tuple[str, str], dict[str, str]] = {}
    if within_randomization_csv is not None and within_randomization_csv.exists():
        within_rand_path = within_randomization_csv
        within_rand = _load_within_randomization(within_randomization_csv)

    lines: list[str] = []
    lines.append("# Scoreboard (v1)")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")
    lines.append("## Party Summary (President Party Only)")
    lines.append("")
    lines.append("Equal weight per presidential term/tenure window (not day-weighted).")
    lines.append("")
    lines.append("| Metric | Units | D mean | R mean | D-R mean | D median | R median | n(D) | n(R) | q | p | CI95(D-R) | q<0.05 | q<0.10 | Tier |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

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
                    _fmt(_parse_float(tr.get("q_bh_fdr") or "")),
                    _fmt(_parse_float(tr.get("p_two_sided") or "")),
                    _fmt_ci(
                        _parse_float(tr.get("bootstrap_ci95_low") or ""),
                        _parse_float(tr.get("bootstrap_ci95_high") or ""),
                    ),
                    _derive_q_flag(tr, key="passes_q_lt_005", threshold=0.05),
                    _derive_q_flag(tr, key="passes_q_lt_010", threshold=0.10),
                    (tr.get("evidence_tier") or "").strip(),
                ]
            )
            + " |"
        )
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

    if show_robustness_links:
        robustness_links: list[tuple[str, Path]] = []
        cpi_robust_path = Path("reports/cpi_sa_nsa_robustness_v1.md")
        if cpi_robust_path.exists():
            robustness_links.append(("CPI SA-vs-NSA sensitivity", cpi_robust_path))
        inversion_robust_path = Path("reports/inversion_definition_robustness_v1.md")
        if inversion_robust_path.exists():
            robustness_links.append(("Yield-curve inversion-definition sensitivity", inversion_robust_path))

        if robustness_links:
            lines.append("")
            lines.append("## Robustness Artifacts")
            lines.append("")
            for label, path in robustness_links:
                lines.append(f"- {label}: `{path}`")

    within_pres_deltas: dict[tuple[str, str], dict[str, Any]] = {}

    if window_metrics_csv and window_labels_csv and window_metrics_csv.exists() and window_labels_csv.exists():
        groups = _compute_unified_summary(window_metrics_csv=window_metrics_csv, window_labels_csv=window_labels_csv)
        align_groups = _compute_alignment_summary(window_metrics_csv=window_metrics_csv, window_labels_csv=window_labels_csv)
        within_pres_deltas = _compute_within_president_unified_deltas(
            window_metrics_csv=window_metrics_csv,
            window_labels_csv=window_labels_csv,
            min_window_days=within_president_min_window_days,
        )

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
        lines.append("## Within-President Unified vs Divided Check")
        lines.append("")
        lines.append("Each president-term acts as its own control: compute (unified mean - divided mean) within the same term, then average those deltas.")
        lines.append(f"Applied filter: include only regime windows with `window_days >= {int(within_president_min_window_days)}`.")
        lines.append("")
        lines.append("| Metric | Units | P party | Mean delta (U-D) | Median delta (U-D) | n(pres with both) | n(with unified) | n(with divided) | q | p | CI95(U-D) | q<0.05 | q<0.10 | Tier |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

        for mid in metric_ids:
            for pres_party in ("D", "R"):
                g = within_pres_deltas.get((mid, pres_party))
                if not g:
                    continue
                label = (g.get("metric_label") or mid).replace("|", "\\|")
                units = (g.get("units") or "").replace("|", "\\|")
                wr = within_rand.get((mid, pres_party), {})
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            label,
                            units,
                            pres_party,
                            _fmt(g.get("mean_delta")),
                            _fmt(g.get("median_delta")),
                            str(int(g.get("n_with_both") or 0)),
                            str(int(g.get("n_with_unified") or 0)),
                            str(int(g.get("n_with_divided") or 0)),
                            _fmt(_parse_float(wr.get("q_bh_fdr") or "")),
                            _fmt(_parse_float(wr.get("p_two_sided") or "")),
                            _fmt_ci(
                                _parse_float(wr.get("bootstrap_ci95_low") or ""),
                                _parse_float(wr.get("bootstrap_ci95_high") or ""),
                            ),
                            _derive_q_flag(wr, key="passes_q_lt_005", threshold=0.05),
                            _derive_q_flag(wr, key="passes_q_lt_010", threshold=0.10),
                            (wr.get("evidence_tier") or "").strip(),
                        ]
                    )
                    + " |"
                )

        lines.append("")
        lines.append("Caution: small `n(pres with both)` means unstable estimates; interpret as a diagnostic, not a causal estimate.")
        if within_rand_path is not None:
            lines.append(f"Significance columns in this section are sourced from `{within_rand_path}`.")

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

    if output_within_president_deltas_csv is not None:
        _write_within_president_unified_deltas_csv(
            metric_ids=metric_ids,
            deltas=within_pres_deltas,
            out_path=output_within_president_deltas_csv,
            min_window_days=within_president_min_window_days,
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
    if term_rand_path is not None:
        lines.append(f"- `{term_rand_path}`")
    if within_rand_path is not None:
        lines.append(f"- `{within_rand_path}`")
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
