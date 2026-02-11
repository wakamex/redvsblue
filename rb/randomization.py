from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


def _parse_float(s: str) -> float | None:
    txt = (s or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def _parse_int(s: str) -> int | None:
    txt = (s or "").strip()
    if not txt:
        return None
    try:
        return int(txt)
    except ValueError:
        return None


def _parse_date(s: str) -> date | None:
    txt = (s or "").strip()
    if not txt:
        return None
    try:
        return date.fromisoformat(txt[:10])
    except ValueError:
        return None


def _fmt(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:.6f}"


def _mean(xs: list[float]) -> float | None:
    if not xs:
        return None
    return sum(xs) / len(xs)


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    n = len(ys)
    if n % 2 == 1:
        return ys[n // 2]
    return 0.5 * (ys[n // 2 - 1] + ys[n // 2])


def _std_population(xs: list[float]) -> float | None:
    if not xs:
        return None
    mu = _mean(xs)
    if mu is None:
        return None
    var = sum((x - mu) ** 2 for x in xs) / len(xs)
    return var**0.5


def _percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    p = max(0.0, min(1.0, q)) * (len(ys) - 1)
    lo = int(math.floor(p))
    hi = int(math.ceil(p))
    if lo == hi:
        return ys[lo]
    w = p - lo
    return ys[lo] * (1.0 - w) + ys[hi] * w


def _bootstrap_diff_d_minus_r(
    *,
    d_vals: list[float],
    r_vals: list[float],
    n_samples: int,
    rng: random.Random,
) -> tuple[float | None, float | None]:
    if not d_vals or not r_vals or n_samples <= 0:
        return None, None
    stats: list[float] = []
    nd = len(d_vals)
    nr = len(r_vals)
    for _ in range(n_samples):
        ds = [d_vals[rng.randrange(nd)] for _ in range(nd)]
        rs = [r_vals[rng.randrange(nr)] for _ in range(nr)]
        md = _mean(ds)
        mr = _mean(rs)
        if md is None or mr is None:
            continue
        stats.append(md - mr)
    return _percentile(stats, 0.025), _percentile(stats, 0.975)


def _bootstrap_mean_ci(
    *,
    values: list[float],
    n_samples: int,
    rng: random.Random,
) -> tuple[float | None, float | None]:
    if not values or n_samples <= 0:
        return None, None
    n = len(values)
    stats: list[float] = []
    for _ in range(n_samples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        m = _mean(sample)
        if m is not None:
            stats.append(m)
    return _percentile(stats, 0.025), _percentile(stats, 0.975)


def _add_bh_q_values(rows: list[dict[str, str]], *, p_col: str, q_col: str) -> None:
    # Benjamini-Hochberg FDR adjustment over rows with numeric p-values.
    p_items: list[tuple[int, float]] = []
    for i, r in enumerate(rows):
        p = _parse_float(r.get(p_col) or "")
        if p is None:
            continue
        p_items.append((i, p))
    m = len(p_items)
    if m == 0:
        for r in rows:
            r[q_col] = ""
        return

    # Sort ascending by p, then apply monotone BH correction from the tail.
    ranked = sorted(p_items, key=lambda t: t[1])
    q_tmp = [0.0] * m
    prev = 1.0
    for k in range(m - 1, -1, -1):
        _, p = ranked[k]
        rank = k + 1
        q = min(prev, (p * m) / rank)
        prev = q
        q_tmp[k] = q

    idx_to_q: dict[int, float] = {}
    for k, (idx, _) in enumerate(ranked):
        idx_to_q[idx] = q_tmp[k]

    for i, r in enumerate(rows):
        q = idx_to_q.get(i)
        r[q_col] = _fmt(q) if q is not None else ""


def _diff_d_minus_r(values: list[float], labels: list[str]) -> float | None:
    sum_d = 0.0
    sum_r = 0.0
    n_d = 0
    n_r = 0
    for v, lab in zip(values, labels):
        if lab == "D":
            sum_d += v
            n_d += 1
        elif lab == "R":
            sum_r += v
            n_r += 1
    if n_d == 0 or n_r == 0:
        return None
    return (sum_d / n_d) - (sum_r / n_r)


@dataclass(frozen=True)
class _MetricObs:
    value: float
    party: str
    term_start: date | None


def _load_term_metric_groups(*, term_metrics_csv: Path, primary_only: bool) -> dict[tuple[str, str], dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    with term_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            metric_id = (row.get("metric_id") or "").strip()
            party = (row.get("party_abbrev") or "").strip()
            if not metric_id or party not in {"D", "R"}:
                continue
            if primary_only and (row.get("metric_primary") or "").strip() != "1":
                continue
            v = _parse_float(row.get("value") or "")
            if v is None:
                continue

            k = (metric_id, party)
            g = groups.get(k)
            if g is None:
                g = {
                    "metric_id": metric_id,
                    "metric_label": (row.get("metric_label") or metric_id).strip(),
                    "metric_family": (row.get("metric_family") or "").strip(),
                    "metric_primary": (row.get("metric_primary") or "").strip(),
                    "agg_kind": (row.get("agg_kind") or "").strip(),
                    "units": (row.get("units") or "").strip(),
                    "obs": [],
                }
                groups[k] = g
            g["obs"].append(
                _MetricObs(
                    value=v,
                    party=party,
                    term_start=_parse_date(row.get("term_start") or ""),
                )
            )

    # Collapse party-keyed groups into one metric-keyed structure.
    out: dict[str, dict[str, Any]] = {}
    for (metric_id, _party), g in groups.items():
        slot = out.get(metric_id)
        if slot is None:
            slot = {
                "metric_id": metric_id,
                "metric_label": g["metric_label"],
                "metric_family": g["metric_family"],
                "metric_primary": g["metric_primary"],
                "agg_kind": g["agg_kind"],
                "units": g["units"],
                "obs": [],
            }
            out[metric_id] = slot
        slot["obs"].extend(g["obs"])

    return {(m, "all"): g for m, g in out.items()}


def _compute_term_party_permutation(
    *,
    term_metrics_csv: Path,
    out_csv: Path,
    permutations: int,
    seed: int,
    block_years: int,
    bootstrap_samples: int,
    primary_only: bool,
) -> None:
    groups = _load_term_metric_groups(term_metrics_csv=term_metrics_csv, primary_only=primary_only)
    rng = random.Random(seed)
    boot_rng = random.Random(seed + 1000003)

    header = [
        "metric_id",
        "metric_label",
        "metric_family",
        "metric_primary",
        "agg_kind",
        "units",
        "n_obs",
        "n_d",
        "n_r",
        "observed_diff_d_minus_r",
        "perm_mean",
        "perm_std",
        "z_score",
        "bootstrap_ci95_low",
        "bootstrap_ci95_high",
        "p_two_sided",
        "q_bh_fdr",
        "permutations",
        "bootstrap_samples",
        "seed",
        "block_years",
        "min_term_start_year",
        "max_term_start_year",
    ]
    rows: list[dict[str, str]] = []

    for metric_id in sorted(k[0] for k in groups.keys()):
        g = groups[(metric_id, "all")]
        obs: list[_MetricObs] = list(g["obs"])
        if not obs:
            continue

        values = [o.value for o in obs]
        labels = [o.party for o in obs]
        years = [o.term_start.year for o in obs if o.term_start is not None]

        n_d = sum(1 for p in labels if p == "D")
        n_r = sum(1 for p in labels if p == "R")
        observed = _diff_d_minus_r(values, labels)
        d_vals = [v for v, p in zip(values, labels) if p == "D"]
        r_vals = [v for v, p in zip(values, labels) if p == "R"]

        perm_diffs: list[float] = []
        if observed is not None and n_d > 0 and n_r > 0 and permutations > 0:
            if block_years > 0:
                # Shuffle labels within coarse year blocks to preserve temporal composition.
                years_full = [(o.term_start.year if o.term_start is not None else None) for o in obs]
                valid_years = [y for y in years_full if y is not None]
                anchor = min(valid_years) if valid_years else 0
                block_to_idx: dict[int, list[int]] = {}
                for i, y in enumerate(years_full):
                    if y is None:
                        b = -1
                    else:
                        b = (y - anchor) // block_years
                    block_to_idx.setdefault(b, []).append(i)
            else:
                block_to_idx = {0: list(range(len(labels)))}

            for _ in range(permutations):
                perm_labels = list(labels)
                for idxs in block_to_idx.values():
                    sub = [perm_labels[i] for i in idxs]
                    rng.shuffle(sub)
                    for j, i in enumerate(idxs):
                        perm_labels[i] = sub[j]
                d = _diff_d_minus_r(values, perm_labels)
                if d is not None:
                    perm_diffs.append(d)

        perm_mean = _mean(perm_diffs)
        perm_std = _std_population(perm_diffs)
        z = None
        if observed is not None and perm_mean is not None and perm_std is not None and perm_std > 0:
            z = (observed - perm_mean) / perm_std
        p_two = None
        if observed is not None and perm_diffs:
            extreme = sum(1 for d in perm_diffs if abs(d) >= abs(observed))
            p_two = (1 + extreme) / (1 + len(perm_diffs))
        ci_lo, ci_hi = _bootstrap_diff_d_minus_r(
            d_vals=d_vals,
            r_vals=r_vals,
            n_samples=max(0, int(bootstrap_samples)),
            rng=boot_rng,
        )

        rows.append(
            {
                "metric_id": metric_id,
                "metric_label": g["metric_label"],
                "metric_family": g["metric_family"],
                "metric_primary": g["metric_primary"],
                "agg_kind": g["agg_kind"],
                "units": g["units"],
                "n_obs": str(len(obs)),
                "n_d": str(n_d),
                "n_r": str(n_r),
                "observed_diff_d_minus_r": _fmt(observed),
                "perm_mean": _fmt(perm_mean),
                "perm_std": _fmt(perm_std),
                "z_score": _fmt(z),
                "bootstrap_ci95_low": _fmt(ci_lo),
                "bootstrap_ci95_high": _fmt(ci_hi),
                "p_two_sided": _fmt(p_two),
                "permutations": str(permutations),
                "bootstrap_samples": str(bootstrap_samples),
                "seed": str(seed),
                "block_years": str(block_years),
                "min_term_start_year": str(min(years)) if years else "",
                "max_term_start_year": str(max(years)) if years else "",
            }
        )

    _add_bh_q_values(rows, p_col="p_two_sided", q_col="q_bh_fdr")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


@dataclass(frozen=True)
class _WindowObs:
    value: float
    unified: int
    days: int


def _load_window_labels(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            wid = (row.get("window_id") or "").strip()
            if not wid:
                continue
            out[wid] = {
                "president_term_id": (row.get("president_term_id") or "").strip(),
                "pres_party": (row.get("pres_party") or "").strip(),
                "unified_government": _parse_int(row.get("unified_government") or "") or 0,
                "window_days": _parse_int(row.get("window_days") or "") or 0,
            }
    return out


def _weighted_or_unweighted_mean(xs: list[tuple[float, int]]) -> float | None:
    if not xs:
        return None
    w_sum = sum(v * d for v, d in xs if d > 0)
    w = sum(d for _, d in xs if d > 0)
    if w > 0:
        return w_sum / w
    return _mean([v for v, _ in xs])


def _term_delta_from_entries(entries: list[_WindowObs], flags: list[int]) -> float | None:
    u = [(e.value, e.days) for e, f in zip(entries, flags) if f == 1]
    d = [(e.value, e.days) for e, f in zip(entries, flags) if f == 0]
    mu_u = _weighted_or_unweighted_mean(u)
    mu_d = _weighted_or_unweighted_mean(d)
    if mu_u is None or mu_d is None:
        return None
    return mu_u - mu_d


def _compute_unified_within_term_permutation(
    *,
    window_metrics_csv: Path,
    window_labels_csv: Path,
    out_csv: Path,
    permutations: int,
    seed: int,
    bootstrap_samples: int,
    min_window_days: int,
    primary_only: bool,
) -> None:
    labels = _load_window_labels(window_labels_csv)
    rng = random.Random(seed)
    boot_rng = random.Random(seed + 2000003)

    # (metric_id, pres_party) -> grouped metadata + per-president-term entries
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    with window_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            metric_id = (row.get("metric_id") or "").strip()
            if not metric_id:
                continue
            if primary_only and (row.get("metric_primary") or "").strip() != "1":
                continue
            wid = (row.get("term_id") or "").strip()
            lab = labels.get(wid)
            if not lab:
                continue
            pres_party = lab["pres_party"]
            if pres_party not in {"D", "R"}:
                continue
            days = int(lab["window_days"])
            if days < min_window_days:
                continue
            pres_term_id = lab["president_term_id"]
            if not pres_term_id:
                continue
            v = _parse_float(row.get("value") or "")
            if v is None:
                continue
            unified = int(lab["unified_government"])

            k = (metric_id, pres_party)
            g = groups.get(k)
            if g is None:
                g = {
                    "metric_id": metric_id,
                    "metric_label": (row.get("metric_label") or metric_id).strip(),
                    "metric_family": (row.get("metric_family") or "").strip(),
                    "metric_primary": (row.get("metric_primary") or "").strip(),
                    "agg_kind": (row.get("agg_kind") or "").strip(),
                    "units": (row.get("units") or "").strip(),
                    "pres_party": pres_party,
                    "terms": {},
                }
                groups[k] = g
            terms: dict[str, list[_WindowObs]] = g["terms"]
            terms.setdefault(pres_term_id, []).append(_WindowObs(value=v, unified=unified, days=days))

    header = [
        "metric_id",
        "metric_label",
        "metric_family",
        "metric_primary",
        "agg_kind",
        "units",
        "pres_party",
        "observed_mean_delta_unified_minus_divided",
        "observed_median_delta_unified_minus_divided",
        "n_presidents_with_both",
        "perm_mean",
        "perm_std",
        "z_score",
        "bootstrap_ci95_low",
        "bootstrap_ci95_high",
        "p_two_sided",
        "q_bh_fdr",
        "permutations",
        "bootstrap_samples",
        "seed",
        "min_window_days_filter",
    ]
    rows: list[dict[str, str]] = []

    for metric_id, pres_party in sorted(groups.keys(), key=lambda x: (x[0], x[1])):
        g = groups[(metric_id, pres_party)]
        terms: dict[str, list[_WindowObs]] = g["terms"]

        # Observed term-level deltas.
        observed_term_deltas: list[float] = []
        for entries in terms.values():
            flags = [e.unified for e in entries]
            d = _term_delta_from_entries(entries, flags)
            if d is not None:
                observed_term_deltas.append(d)

        observed_mean = _mean(observed_term_deltas)
        observed_median = _median(observed_term_deltas)
        n_both = len(observed_term_deltas)

        perm_stats: list[float] = []
        if observed_mean is not None and permutations > 0 and n_both > 0:
            term_items = list(terms.values())
            for _ in range(permutations):
                ds: list[float] = []
                for entries in term_items:
                    flags = [e.unified for e in entries]
                    rng.shuffle(flags)
                    d = _term_delta_from_entries(entries, flags)
                    if d is not None:
                        ds.append(d)
                m = _mean(ds)
                if m is not None:
                    perm_stats.append(m)

        perm_mean = _mean(perm_stats)
        perm_std = _std_population(perm_stats)
        z = None
        if observed_mean is not None and perm_mean is not None and perm_std is not None and perm_std > 0:
            z = (observed_mean - perm_mean) / perm_std
        p_two = None
        if observed_mean is not None and perm_stats:
            extreme = sum(1 for s in perm_stats if abs(s) >= abs(observed_mean))
            p_two = (1 + extreme) / (1 + len(perm_stats))
        ci_lo, ci_hi = _bootstrap_mean_ci(
            values=observed_term_deltas,
            n_samples=max(0, int(bootstrap_samples)),
            rng=boot_rng,
        )

        rows.append(
            {
                "metric_id": metric_id,
                "metric_label": g["metric_label"],
                "metric_family": g["metric_family"],
                "metric_primary": g["metric_primary"],
                "agg_kind": g["agg_kind"],
                "units": g["units"],
                "pres_party": pres_party,
                "observed_mean_delta_unified_minus_divided": _fmt(observed_mean),
                "observed_median_delta_unified_minus_divided": _fmt(observed_median),
                "n_presidents_with_both": str(n_both),
                "perm_mean": _fmt(perm_mean),
                "perm_std": _fmt(perm_std),
                "z_score": _fmt(z),
                "bootstrap_ci95_low": _fmt(ci_lo),
                "bootstrap_ci95_high": _fmt(ci_hi),
                "p_two_sided": _fmt(p_two),
                "permutations": str(permutations),
                "bootstrap_samples": str(bootstrap_samples),
                "seed": str(seed),
                "min_window_days_filter": str(min_window_days),
            }
        )

    _add_bh_q_values(rows, p_col="p_two_sided", q_col="q_bh_fdr")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


def run_randomization(
    *,
    term_metrics_csv: Path,
    output_party_term_csv: Path,
    permutations: int,
    bootstrap_samples: int,
    seed: int,
    term_block_years: int,
    primary_only: bool,
    window_metrics_csv: Path | None,
    window_labels_csv: Path | None,
    output_unified_within_term_csv: Path | None,
    within_president_min_window_days: int,
) -> None:
    if not term_metrics_csv.exists():
        raise FileNotFoundError(f"Missing term metrics CSV: {term_metrics_csv}")

    _compute_term_party_permutation(
        term_metrics_csv=term_metrics_csv,
        out_csv=output_party_term_csv,
        permutations=max(0, int(permutations)),
        bootstrap_samples=max(0, int(bootstrap_samples)),
        seed=int(seed),
        block_years=max(0, int(term_block_years)),
        primary_only=bool(primary_only),
    )

    if window_metrics_csv is None or window_labels_csv is None or output_unified_within_term_csv is None:
        return
    if not window_metrics_csv.exists() or not window_labels_csv.exists():
        return

    _compute_unified_within_term_permutation(
        window_metrics_csv=window_metrics_csv,
        window_labels_csv=window_labels_csv,
        out_csv=output_unified_within_term_csv,
        permutations=max(0, int(permutations)),
        bootstrap_samples=max(0, int(bootstrap_samples)),
        seed=int(seed),
        min_window_days=max(0, int(within_president_min_window_days)),
        primary_only=bool(primary_only),
    )
