from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from rb.congress_control import CongressControl, ensure_congress_control, load_congress_control_csv
from rb.metrics import compute_term_metrics
from rb.presidents import PresidentTerm, ensure_presidents, load_presidents_csv
from rb.util import write_text_atomic


@dataclass(frozen=True)
class RegimeWindow:
    window_id: str
    president_term_id: str
    congress: int
    start: date
    end: date
    president: str
    pres_party: str
    house_majority: str
    senate_majority: str


def _overlap(a0: date, a1: date, b0: date, b1: date) -> tuple[date, date] | None:
    s = max(a0, b0)
    e = min(a1, b1)
    if e <= s:
        return None
    return s, e


def build_regime_windows(
    *,
    presidents: list[PresidentTerm],
    congress: list[CongressControl],
) -> list[RegimeWindow]:
    windows: list[RegimeWindow] = []
    for t in presidents:
        for c in congress:
            ov = _overlap(t.term_start, t.term_end, c.start_date, c.end_date)
            if not ov:
                continue
            s, e = ov
            win_id = f"{t.term_id}__C{c.congress}"
            windows.append(
                RegimeWindow(
                    window_id=win_id,
                    president_term_id=t.term_id,
                    congress=c.congress,
                    start=s,
                    end=e,
                    president=t.president,
                    pres_party=t.party_abbrev,
                    house_majority=c.house_majority,
                    senate_majority=c.senate_majority,
                )
            )
    return sorted(windows, key=lambda w: (w.start, w.window_id))


def write_regime_windows(
    *,
    windows: list[RegimeWindow],
    out_labels_csv: Path,
    out_presidents_csv: Path,
) -> None:
    out_labels_csv.parent.mkdir(parents=True, exist_ok=True)
    out_presidents_csv.parent.mkdir(parents=True, exist_ok=True)

    # Labels/metadata for joining.
    labels_header = [
        "window_id",
        "president_term_id",
        "congress",
        "window_start",
        "window_end",
        "president",
        "pres_party",
        "house_majority",
        "senate_majority",
        "unified_government",
        "window_days",
    ]
    label_lines = [",".join(labels_header)]
    for w in windows:
        unified = "1" if (w.pres_party in {"D", "R"} and w.pres_party == w.house_majority == w.senate_majority) else "0"
        days = (w.end - w.start).days
        label_lines.append(
            ",".join(
                [
                    w.window_id,
                    w.president_term_id,
                    str(w.congress),
                    w.start.isoformat(),
                    w.end.isoformat(),
                    w.president.replace(",", " "),
                    w.pres_party,
                    w.house_majority,
                    w.senate_majority,
                    unified,
                    str(days),
                ]
            )
        )
    write_text_atomic(out_labels_csv, "\n".join(label_lines) + "\n")

    # Emit a "presidents.csv-shaped" file so we can reuse compute_term_metrics.
    pres_header = [
        "term_id",
        "person_qid",
        "president",
        "party_qid",
        "party",
        "party_abbrev",
        "term_number_for_person",
        "term_start",
        "term_end",
    ]
    pres_lines = [",".join(pres_header)]
    for w in windows:
        pres_lines.append(
            ",".join(
                [
                    w.window_id,
                    "",  # person_qid
                    w.president.replace(",", " "),
                    "",  # party_qid
                    "",  # party label
                    w.pres_party,
                    "0",
                    w.start.isoformat(),
                    w.end.isoformat(),
                ]
            )
        )
    write_text_atomic(out_presidents_csv, "\n".join(pres_lines) + "\n")


def _parse_float(s: str) -> float | None:
    try:
        x = float((s or "").strip())
    except ValueError:
        return None
    if x != x:  # nan
        return None
    return x


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    n = len(ys)
    if n % 2 == 1:
        return ys[n // 2]
    return 0.5 * (ys[n // 2 - 1] + ys[n // 2])


def compute_regime_summary(
    *,
    window_metrics_csv: Path,
    window_labels_csv: Path,
    out_csv: Path,
) -> None:
    # Load labels.
    labels: dict[str, dict[str, Any]] = {}
    with window_labels_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            labels[row["window_id"]] = row

    # Aggregate per (metric_id, P,H,S).
    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    with window_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            win_id = row.get("term_id", "") or ""
            lab = labels.get(win_id)
            if not lab:
                continue
            v = _parse_float(row.get("value", "") or "")
            if v is None:
                continue

            pres_party = lab.get("pres_party", "")
            house = lab.get("house_majority", "")
            senate = lab.get("senate_majority", "")
            days = int(lab.get("window_days") or "0")

            k = (row.get("metric_id", "") or "", pres_party, house, senate)
            g = groups.get(k)
            if g is None:
                g = {
                    "metric_id": row.get("metric_id", ""),
                    "metric_family": row.get("metric_family", ""),
                    "metric_primary": row.get("metric_primary", ""),
                    "metric_label": row.get("metric_label", ""),
                    "agg_kind": row.get("agg_kind", ""),
                    "units": row.get("units", ""),
                    "pres_party": pres_party,
                    "house_majority": house,
                    "senate_majority": senate,
                    "n_windows": 0,
                    "total_days": 0,
                    "values": [],
                    "sum": 0.0,
                    "w_sum": 0.0,
                    "w": 0.0,
                }
                groups[k] = g

            g["n_windows"] += 1
            g["total_days"] += days
            g["values"].append(v)
            g["sum"] += v
            if days > 0:
                g["w_sum"] += v * days
                g["w"] += days

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "metric_id",
        "metric_family",
        "metric_primary",
        "metric_label",
        "agg_kind",
        "units",
        "pres_party",
        "house_majority",
        "senate_majority",
        "regime",
        "n_windows",
        "total_days",
        "mean_unweighted",
        "median_unweighted",
        "mean_weighted_by_days",
    ]
    rows: list[dict[str, Any]] = []
    for _, g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
        n = int(g["n_windows"])
        mean = (g["sum"] / n) if n else None
        med = _median(list(g["values"]))
        w = float(g["w"])
        wmean = (g["w_sum"] / w) if w > 0 else None
        rows.append(
            {
                "metric_id": g["metric_id"],
                "metric_family": g["metric_family"],
                "metric_primary": g["metric_primary"],
                "metric_label": g["metric_label"],
                "agg_kind": g["agg_kind"],
                "units": g["units"],
                "pres_party": g["pres_party"],
                "house_majority": g["house_majority"],
                "senate_majority": g["senate_majority"],
                "regime": f"P={g['pres_party']};H={g['house_majority']};S={g['senate_majority']}",
                "n_windows": str(n),
                "total_days": str(int(g["total_days"])),
                "mean_unweighted": "" if mean is None else f"{mean:.6f}",
                "median_unweighted": "" if med is None else f"{med:.6f}",
                "mean_weighted_by_days": "" if wmean is None else f"{wmean:.6f}",
            }
        )

    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


def compute_regime_alignment_summary(
    *,
    window_metrics_csv: Path,
    window_labels_csv: Path,
    out_csv: Path,
) -> None:
    # Load labels.
    labels: dict[str, dict[str, Any]] = {}
    with window_labels_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            labels[row["window_id"]] = row

    # Aggregate per (metric_id, pres_party, aligned_house, aligned_senate).
    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    with window_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            win_id = row.get("term_id", "") or ""
            lab = labels.get(win_id)
            if not lab:
                continue
            v = _parse_float(row.get("value", "") or "")
            if v is None:
                continue

            pres_party = (lab.get("pres_party") or "").strip()
            if pres_party not in {"D", "R"}:
                continue

            house = (lab.get("house_majority") or "").strip()
            senate = (lab.get("senate_majority") or "").strip()
            days = int(lab.get("window_days") or "0")

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

            k = (row.get("metric_id", "") or "", pres_party, aligned_house, aligned_senate)
            g = groups.get(k)
            if g is None:
                g = {
                    "metric_id": row.get("metric_id", ""),
                    "metric_family": row.get("metric_family", ""),
                    "metric_primary": row.get("metric_primary", ""),
                    "metric_label": row.get("metric_label", ""),
                    "agg_kind": row.get("agg_kind", ""),
                    "units": row.get("units", ""),
                    "pres_party": pres_party,
                    "aligned_house": aligned_house,
                    "aligned_senate": aligned_senate,
                    "aligned_chambers": aligned_chambers,
                    "alignment": alignment,
                    "n_windows": 0,
                    "total_days": 0,
                    "values": [],
                    "sum": 0.0,
                    "w_sum": 0.0,
                    "w": 0.0,
                }
                groups[k] = g

            g["n_windows"] += 1
            g["total_days"] += days
            g["values"].append(v)
            g["sum"] += v
            if days > 0:
                g["w_sum"] += v * days
                g["w"] += days

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "metric_id",
        "metric_family",
        "metric_primary",
        "metric_label",
        "agg_kind",
        "units",
        "pres_party",
        "aligned_house",
        "aligned_senate",
        "aligned_chambers",
        "alignment",
        "n_windows",
        "total_days",
        "mean_unweighted",
        "median_unweighted",
        "mean_weighted_by_days",
    ]
    rows: list[dict[str, Any]] = []
    for _, g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
        n = int(g["n_windows"])
        mean = (g["sum"] / n) if n else None
        med = _median(list(g["values"]))
        w = float(g["w"])
        wmean = (g["w_sum"] / w) if w > 0 else None
        rows.append(
            {
                "metric_id": g["metric_id"],
                "metric_family": g["metric_family"],
                "metric_primary": g["metric_primary"],
                "metric_label": g["metric_label"],
                "agg_kind": g["agg_kind"],
                "units": g["units"],
                "pres_party": g["pres_party"],
                "aligned_house": g["aligned_house"],
                "aligned_senate": g["aligned_senate"],
                "aligned_chambers": str(int(g["aligned_chambers"])),
                "alignment": g["alignment"],
                "n_windows": str(n),
                "total_days": str(int(g["total_days"])),
                "mean_unweighted": "" if mean is None else f"{mean:.6f}",
                "median_unweighted": "" if med is None else f"{med:.6f}",
                "mean_weighted_by_days": "" if wmean is None else f"{wmean:.6f}",
            }
        )

    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


def ensure_regime_pipeline(
    *,
    refresh: bool,
    spec_path: Path,
    attribution_path: Path,
    presidents_csv: Path,
    president_source: str,
    president_granularity: str,
    congress_csv: Path,
    output_windows_labels_csv: Path,
    output_windows_presidents_csv: Path,
    output_window_metrics_csv: Path,
    output_regime_summary_csv: Path,
    output_alignment_summary_csv: Path,
    output_party_summary_csv: Path,
) -> None:
    if not presidents_csv.exists():
        ensure_presidents(refresh=refresh, source=president_source, output_csv=presidents_csv, granularity=president_granularity)
    if not congress_csv.exists():
        out = ensure_congress_control(refresh=refresh)
        if out != congress_csv:
            congress_csv.parent.mkdir(parents=True, exist_ok=True)
            congress_csv.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")

    presidents = load_presidents_csv(presidents_csv)
    congress = load_congress_control_csv(congress_csv)

    windows = build_regime_windows(presidents=presidents, congress=congress)
    write_regime_windows(windows=windows, out_labels_csv=output_windows_labels_csv, out_presidents_csv=output_windows_presidents_csv)

    compute_term_metrics(
        spec_path=spec_path,
        attribution_path=attribution_path,
        presidents_csv=output_windows_presidents_csv,
        output_terms_csv=output_window_metrics_csv,
        output_party_csv=output_party_summary_csv,
    )

    compute_regime_summary(
        window_metrics_csv=output_window_metrics_csv,
        window_labels_csv=output_windows_labels_csv,
        out_csv=output_regime_summary_csv,
    )

    compute_regime_alignment_summary(
        window_metrics_csv=output_window_metrics_csv,
        window_labels_csv=output_windows_labels_csv,
        out_csv=output_alignment_summary_csv,
    )
