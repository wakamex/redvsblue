from __future__ import annotations

import csv
import math
import random
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

STRICT_Q_DEFAULT = 0.05
SUPPORTIVE_Q_THRESHOLD = 0.10
DIAGNOSTIC_ONLY_METRIC_IDS = frozenset(
    {
        "sp500_backfilled_pre1957_term_pct_change",
        "sp500_backfilled_pre1957_term_cagr_pct",
        "ff_mkt_excess_return_ann_arith",
    }
)


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


def _classify_evidence(
    *,
    q: float | None,
    ci_lo: float | None,
    ci_hi: float | None,
    n: int,
    q_threshold: float,
    min_n: int,
) -> dict[str, str]:
    pass_q_threshold = q is not None and q < q_threshold
    pass_q_005 = q is not None and q < 0.05
    pass_q_010 = q is not None and q < SUPPORTIVE_Q_THRESHOLD
    pass_ci = ci_lo is not None and ci_hi is not None and ((ci_lo > 0 and ci_hi > 0) or (ci_lo < 0 and ci_hi < 0))
    pass_n = n >= min_n
    # Tier assignment uses multiplicity-aware q-values plus minimum sample-size checks.
    # CI exclusion is still reported, but not used as a hard gate.
    if pass_q_threshold and pass_n:
        tier = "confirmatory"
    elif pass_q_010 and pass_n:
        tier = "supportive"
    else:
        tier = "exploratory"
    return {
        "passes_q_threshold": "1" if pass_q_threshold else "0",
        "passes_q_lt_005": "1" if pass_q_005 else "0",
        "passes_q_lt_010": "1" if pass_q_010 else "0",
        "passes_ci_excludes_zero": "1" if pass_ci else "0",
        "passes_min_n": "1" if pass_n else "0",
        "evidence_tier": tier,
    }


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


def _load_term_metric_groups(
    *,
    term_metrics_csv: Path,
    primary_only: bool,
    include_diagnostic_metrics: bool,
) -> dict[tuple[str, str], dict[str, Any]]:
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
            if not include_diagnostic_metrics and metric_id in DIAGNOSTIC_ONLY_METRIC_IDS:
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
    q_threshold: float,
    min_n_obs: int,
    primary_only: bool,
    include_diagnostic_metrics: bool,
) -> None:
    groups = _load_term_metric_groups(
        term_metrics_csv=term_metrics_csv,
        primary_only=primary_only,
        include_diagnostic_metrics=include_diagnostic_metrics,
    )
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
        "passes_q_threshold",
        "passes_q_lt_005",
        "passes_q_lt_010",
        "passes_ci_excludes_zero",
        "passes_min_n",
        "evidence_tier",
        "q_threshold",
        "q_threshold_supportive",
        "min_n_threshold",
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
    for r in rows:
        q = _parse_float(r.get("q_bh_fdr") or "")
        lo = _parse_float(r.get("bootstrap_ci95_low") or "")
        hi = _parse_float(r.get("bootstrap_ci95_high") or "")
        n = _parse_int(r.get("n_obs") or "") or 0
        ev = _classify_evidence(
            q=q,
            ci_lo=lo,
            ci_hi=hi,
            n=n,
            q_threshold=q_threshold,
            min_n=min_n_obs,
        )
        r["passes_q_threshold"] = ev["passes_q_threshold"]
        r["passes_q_lt_005"] = ev["passes_q_lt_005"]
        r["passes_q_lt_010"] = ev["passes_q_lt_010"]
        r["passes_ci_excludes_zero"] = ev["passes_ci_excludes_zero"]
        r["passes_min_n"] = ev["passes_min_n"]
        r["evidence_tier"] = ev["evidence_tier"]
        r["q_threshold"] = _fmt(q_threshold)
        r["q_threshold_supportive"] = _fmt(SUPPORTIVE_Q_THRESHOLD)
        r["min_n_threshold"] = str(int(min_n_obs))

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
    q_threshold: float,
    min_n_within_both: int,
    primary_only: bool,
    include_diagnostic_metrics: bool,
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
            if not include_diagnostic_metrics and metric_id in DIAGNOSTIC_ONLY_METRIC_IDS:
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
        "passes_q_threshold",
        "passes_q_lt_005",
        "passes_q_lt_010",
        "passes_ci_excludes_zero",
        "passes_min_n",
        "evidence_tier",
        "q_threshold",
        "q_threshold_supportive",
        "min_n_threshold",
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
    for r in rows:
        q = _parse_float(r.get("q_bh_fdr") or "")
        lo = _parse_float(r.get("bootstrap_ci95_low") or "")
        hi = _parse_float(r.get("bootstrap_ci95_high") or "")
        n = _parse_int(r.get("n_presidents_with_both") or "") or 0
        ev = _classify_evidence(
            q=q,
            ci_lo=lo,
            ci_hi=hi,
            n=n,
            q_threshold=q_threshold,
            min_n=min_n_within_both,
        )
        r["passes_q_threshold"] = ev["passes_q_threshold"]
        r["passes_q_lt_005"] = ev["passes_q_lt_005"]
        r["passes_q_lt_010"] = ev["passes_q_lt_010"]
        r["passes_ci_excludes_zero"] = ev["passes_ci_excludes_zero"]
        r["passes_min_n"] = ev["passes_min_n"]
        r["evidence_tier"] = ev["evidence_tier"]
        r["q_threshold"] = _fmt(q_threshold)
        r["q_threshold_supportive"] = _fmt(SUPPORTIVE_Q_THRESHOLD)
        r["min_n_threshold"] = str(int(min_n_within_both))

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


def _write_evidence_summary(
    *,
    term_party_csv: Path | None,
    within_unified_csv: Path | None,
    out_csv: Path,
) -> None:
    analyses: list[tuple[str, Path]] = []
    if term_party_csv is not None and term_party_csv.exists():
        analyses.append(("term_party", term_party_csv))
    if within_unified_csv is not None and within_unified_csv.exists():
        analyses.append(("within_unified", within_unified_csv))

    tier_order = ("confirmatory", "supportive", "exploratory")
    aggregate: dict[tuple[str, str, str], dict[str, int]] = {}
    aggregate_primary: dict[tuple[str, str, str], dict[str, int]] = {}
    family_counts: dict[tuple[str, str], int] = {}
    family_counts_primary: dict[tuple[str, str], int] = {}
    analysis_counts: dict[str, int] = {}
    analysis_counts_primary: dict[str, int] = {}

    def _flag(v: str | None) -> bool:
        return (v or "").strip() == "1"

    for analysis, path in analyses:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rdr = csv.DictReader(handle)
            for r in rdr:
                fam = (r.get("metric_family") or "").strip() or "(none)"
                is_primary = (r.get("metric_primary") or "").strip() == "1"
                tier = (r.get("evidence_tier") or "").strip() or "exploratory"
                if tier not in tier_order:
                    tier = "exploratory"
                q = _parse_float(r.get("q_bh_fdr") or "")
                q_threshold = _parse_float(r.get("q_threshold") or "")
                if q_threshold is None:
                    q_threshold = STRICT_Q_DEFAULT
                pass_q_threshold = _flag(r.get("passes_q_threshold"))
                pass_q_005 = _flag(r.get("passes_q_lt_005")) or (q is not None and q < 0.05)
                pass_q_010 = _flag(r.get("passes_q_lt_010")) or (q is not None and q < SUPPORTIVE_Q_THRESHOLD)
                if (r.get("passes_q_threshold") or "").strip() == "":
                    pass_q_threshold = q is not None and q < q_threshold
                pass_ci = _flag(r.get("passes_ci_excludes_zero"))
                pass_min_n = _flag(r.get("passes_min_n"))

                k = (analysis, fam, tier)
                a = aggregate.get(k)
                if a is None:
                    a = {
                        "n_rows": 0,
                        "n_pass_q_threshold": 0,
                        "n_pass_q_005": 0,
                        "n_pass_q_010": 0,
                        "n_pass_ci": 0,
                        "n_pass_min_n": 0,
                    }
                    aggregate[k] = a
                a["n_rows"] += 1
                if pass_q_threshold:
                    a["n_pass_q_threshold"] += 1
                if pass_q_005:
                    a["n_pass_q_005"] += 1
                if pass_q_010:
                    a["n_pass_q_010"] += 1
                if pass_ci:
                    a["n_pass_ci"] += 1
                if pass_min_n:
                    a["n_pass_min_n"] += 1

                fam_all = (analysis, "__all__", tier)
                b = aggregate.get(fam_all)
                if b is None:
                    b = {
                        "n_rows": 0,
                        "n_pass_q_threshold": 0,
                        "n_pass_q_005": 0,
                        "n_pass_q_010": 0,
                        "n_pass_ci": 0,
                        "n_pass_min_n": 0,
                    }
                    aggregate[fam_all] = b
                b["n_rows"] += 1
                if pass_q_threshold:
                    b["n_pass_q_threshold"] += 1
                if pass_q_005:
                    b["n_pass_q_005"] += 1
                if pass_q_010:
                    b["n_pass_q_010"] += 1
                if pass_ci:
                    b["n_pass_ci"] += 1
                if pass_min_n:
                    b["n_pass_min_n"] += 1

                family_counts[(analysis, fam)] = family_counts.get((analysis, fam), 0) + 1
                family_counts[(analysis, "__all__")] = family_counts.get((analysis, "__all__"), 0) + 1
                analysis_counts[analysis] = analysis_counts.get(analysis, 0) + 1

                if is_primary:
                    kp = (analysis, fam, tier)
                    ap = aggregate_primary.get(kp)
                    if ap is None:
                        ap = {
                            "n_rows": 0,
                            "n_pass_q_threshold": 0,
                            "n_pass_q_005": 0,
                            "n_pass_q_010": 0,
                            "n_pass_ci": 0,
                            "n_pass_min_n": 0,
                        }
                        aggregate_primary[kp] = ap
                    ap["n_rows"] += 1
                    if pass_q_threshold:
                        ap["n_pass_q_threshold"] += 1
                    if pass_q_005:
                        ap["n_pass_q_005"] += 1
                    if pass_q_010:
                        ap["n_pass_q_010"] += 1
                    if pass_ci:
                        ap["n_pass_ci"] += 1
                    if pass_min_n:
                        ap["n_pass_min_n"] += 1

                    kp_all = (analysis, "__all__", tier)
                    bp = aggregate_primary.get(kp_all)
                    if bp is None:
                        bp = {
                            "n_rows": 0,
                            "n_pass_q_threshold": 0,
                            "n_pass_q_005": 0,
                            "n_pass_q_010": 0,
                            "n_pass_ci": 0,
                            "n_pass_min_n": 0,
                        }
                        aggregate_primary[kp_all] = bp
                    bp["n_rows"] += 1
                    if pass_q_threshold:
                        bp["n_pass_q_threshold"] += 1
                    if pass_q_005:
                        bp["n_pass_q_005"] += 1
                    if pass_q_010:
                        bp["n_pass_q_010"] += 1
                    if pass_ci:
                        bp["n_pass_ci"] += 1
                    if pass_min_n:
                        bp["n_pass_min_n"] += 1

                    family_counts_primary[(analysis, fam)] = family_counts_primary.get((analysis, fam), 0) + 1
                    family_counts_primary[(analysis, "__all__")] = family_counts_primary.get((analysis, "__all__"), 0) + 1
                    analysis_counts_primary[analysis] = analysis_counts_primary.get(analysis, 0) + 1

    header = [
        "scope",
        "analysis",
        "metric_family",
        "evidence_tier",
        "n_rows",
        "share_of_family_rows",
        "share_of_analysis_rows",
        "n_pass_q_lt_005",
        "n_pass_q_lt_010",
        "n_pass_q_threshold",
        "n_pass_ci_excludes_zero",
        "n_pass_min_n",
    ]
    rows: list[dict[str, str]] = []
    def _emit_scope(
        *,
        scope: str,
        agg: dict[tuple[str, str, str], dict[str, int]],
        fam_counts: dict[tuple[str, str], int],
        ana_counts: dict[str, int],
    ) -> None:
        for analysis, _path in analyses:
            families = sorted({fam for (a, fam) in fam_counts.keys() if a == analysis and fam != "__all__"})
            families = ["__all__"] + families
            for fam in families:
                fam_den = fam_counts.get((analysis, fam), 0)
                ana_den = ana_counts.get(analysis, 0)
                for tier in tier_order:
                    a = agg.get(
                        (analysis, fam, tier),
                        {
                            "n_rows": 0,
                            "n_pass_q_threshold": 0,
                            "n_pass_q_005": 0,
                            "n_pass_q_010": 0,
                            "n_pass_ci": 0,
                            "n_pass_min_n": 0,
                        },
                    )
                    n_rows = int(a["n_rows"])
                    share_f = (n_rows / fam_den) if fam_den > 0 else None
                    share_a = (n_rows / ana_den) if ana_den > 0 else None
                    rows.append(
                        {
                            "scope": scope,
                            "analysis": analysis,
                            "metric_family": fam,
                            "evidence_tier": tier,
                            "n_rows": str(n_rows),
                            "share_of_family_rows": _fmt(share_f),
                            "share_of_analysis_rows": _fmt(share_a),
                            "n_pass_q_lt_005": str(int(a["n_pass_q_005"])),
                            "n_pass_q_lt_010": str(int(a["n_pass_q_010"])),
                            "n_pass_q_threshold": str(int(a["n_pass_q_threshold"])),
                            "n_pass_ci_excludes_zero": str(int(a["n_pass_ci"])),
                            "n_pass_min_n": str(int(a["n_pass_min_n"])),
                        }
                    )

    _emit_scope(scope="all_metrics", agg=aggregate, fam_counts=family_counts, ana_counts=analysis_counts)
    _emit_scope(scope="primary_only", agg=aggregate_primary, fam_counts=family_counts_primary, ana_counts=analysis_counts_primary)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


def _write_evidence_markdown(
    *,
    term_party_csv: Path | None,
    within_unified_csv: Path | None,
    summary_csv: Path | None,
    out_md: Path,
) -> None:
    def _read_rows(path: Path | None) -> list[dict[str, str]]:
        if path is None or not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    term_rows = _read_rows(term_party_csv)
    within_rows = _read_rows(within_unified_csv)
    summary_rows = _read_rows(summary_csv)

    lines: list[str] = []
    lines.append("# Randomization Evidence Summary")
    lines.append("")
    lines.append("This report summarizes evidence tiers from `rb randomization`.")
    lines.append("")

    if summary_rows:
        def _render_tier_counts(scope: str, title: str) -> None:
            lines.append(f"## {title}")
            lines.append("")
            lines.append("| Analysis | Confirmatory | Supportive | Exploratory |")
            lines.append("|---|---:|---:|---:|")
            for analysis in sorted({r.get("analysis", "") for r in summary_rows}):
                if not analysis:
                    continue
                by_tier = {
                    r.get("evidence_tier", ""): r
                    for r in summary_rows
                    if (r.get("analysis") == analysis)
                    and (r.get("metric_family") == "__all__")
                    and ((r.get("scope") or "all_metrics") == scope)
                }
                c = by_tier.get("confirmatory", {}).get("n_rows", "0")
                s = by_tier.get("supportive", {}).get("n_rows", "0")
                e = by_tier.get("exploratory", {}).get("n_rows", "0")
                lines.append(f"| {analysis} | {c} | {s} | {e} |")
            lines.append("")

        _render_tier_counts("all_metrics", "Tier Counts (All Metrics)")
        _render_tier_counts("primary_only", "Tier Counts (Primary Metrics)")

    def _render_detail(title: str, rows: list[dict[str, str]], *, has_party: bool) -> None:
        if not rows:
            return
        lines.append(f"## {title}")
        lines.append("")
        sel = [r for r in rows if (r.get("evidence_tier") or "") in {"confirmatory", "supportive"}]
        if not sel:
            lines.append("No confirmatory/supportive rows under current thresholds.")
            lines.append("")
            return
        sel.sort(key=lambda r: (_parse_float(r.get("q_bh_fdr") or "") or 1e9, _parse_float(r.get("p_two_sided") or "") or 1e9))
        if has_party:
            lines.append("| Tier | Metric | Party | Family | q | p | CI95 | n |")
            lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
        else:
            lines.append("| Tier | Metric | Family | q | p | CI95 | n |")
            lines.append("|---|---|---:|---:|---:|---:|---:|")

        for r in sel:
            tier = (r.get("evidence_tier") or "").strip()
            metric = (r.get("metric_id") or "").strip()
            family = (r.get("metric_family") or "").strip()
            q = _fmt(_parse_float(r.get("q_bh_fdr") or ""))
            p = _fmt(_parse_float(r.get("p_two_sided") or ""))
            lo = _fmt(_parse_float(r.get("bootstrap_ci95_low") or ""))
            hi = _fmt(_parse_float(r.get("bootstrap_ci95_high") or ""))
            ci = f"[{lo}, {hi}]"
            n = (r.get("n_obs") or r.get("n_presidents_with_both") or "").strip()
            if has_party:
                party = (r.get("pres_party") or "").strip()
                lines.append(f"| {tier} | {metric} | {party} | {family} | {q} | {p} | {ci} | {n} |")
            else:
                lines.append(f"| {tier} | {metric} | {family} | {q} | {p} | {ci} | {n} |")
        lines.append("")

    _render_detail("Term-Level Party Differences", term_rows, has_party=False)
    _render_detail("Within-President Unified vs Divided", within_rows, has_party=True)

    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Confirmatory requires q < q_threshold (default 0.05) and minimum-n checks."
    )
    lines.append(
        "- Supportive requires q < 0.10 and minimum-n checks; treat as suggestive."
    )
    lines.append("- CI bounds are reported as effect-size uncertainty context, not as a hard tier gate.")
    lines.append("- Prefer continuous `q_bh_fdr` and CI width/sign when interpreting strength, not only tier buckets.")
    lines.append("")

    text = "\n".join(lines) + "\n"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_md.with_suffix(out_md.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out_md)


def run_randomization(
    *,
    term_metrics_csv: Path,
    output_party_term_csv: Path,
    permutations: int,
    bootstrap_samples: int,
    seed: int,
    term_block_years: int,
    q_threshold: float,
    min_term_n_obs: int,
    min_within_n_both: int,
    primary_only: bool,
    window_metrics_csv: Path | None,
    window_labels_csv: Path | None,
    output_unified_within_term_csv: Path | None,
    output_evidence_summary_csv: Path | None,
    output_evidence_md: Path | None,
    output_inversion_robustness_csv: Path | None,
    output_inversion_robustness_md: Path | None,
    output_cpi_robustness_csv: Path | None,
    output_cpi_robustness_md: Path | None,
    within_president_min_window_days: int,
    include_diagnostic_metrics: bool,
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
        q_threshold=float(q_threshold),
        min_n_obs=max(0, int(min_term_n_obs)),
        primary_only=bool(primary_only),
        include_diagnostic_metrics=bool(include_diagnostic_metrics),
    )

    generated_within_csv: Path | None = None
    if (
        window_metrics_csv is not None
        and window_labels_csv is not None
        and output_unified_within_term_csv is not None
        and window_metrics_csv.exists()
        and window_labels_csv.exists()
    ):
        _compute_unified_within_term_permutation(
            window_metrics_csv=window_metrics_csv,
            window_labels_csv=window_labels_csv,
            out_csv=output_unified_within_term_csv,
            permutations=max(0, int(permutations)),
            bootstrap_samples=max(0, int(bootstrap_samples)),
            seed=int(seed),
            min_window_days=max(0, int(within_president_min_window_days)),
            q_threshold=float(q_threshold),
            min_n_within_both=max(0, int(min_within_n_both)),
            primary_only=bool(primary_only),
            include_diagnostic_metrics=bool(include_diagnostic_metrics),
        )
        generated_within_csv = output_unified_within_term_csv

    if output_evidence_summary_csv is not None:
        _write_evidence_summary(
            term_party_csv=output_party_term_csv,
            within_unified_csv=generated_within_csv,
            out_csv=output_evidence_summary_csv,
        )
    if output_evidence_md is not None:
        _write_evidence_markdown(
            term_party_csv=output_party_term_csv,
            within_unified_csv=generated_within_csv,
            summary_csv=output_evidence_summary_csv,
            out_md=output_evidence_md,
        )

    # Inversion-definition robustness report is only meaningful when non-primary metrics are included.
    if (not primary_only) and output_inversion_robustness_csv is not None:
        write_inversion_definition_robustness(
            permutation_party_term_csv=output_party_term_csv,
            out_csv=output_inversion_robustness_csv,
            out_md=output_inversion_robustness_md,
        )
    if (not primary_only) and output_cpi_robustness_csv is not None:
        write_cpi_sa_nsa_level_robustness(
            permutation_party_term_csv=output_party_term_csv,
            out_csv=output_cpi_robustness_csv,
            out_md=output_cpi_robustness_md,
        )


def run_randomization_seed_stability(
    *,
    term_metrics_csv: Path,
    out_csv: Path,
    seeds: list[int],
    permutations: int,
    bootstrap_samples: int,
    term_block_years: int,
    q_threshold: float,
    min_term_n_obs: int,
    primary_only: bool,
    include_diagnostic_metrics: bool,
) -> None:
    if not term_metrics_csv.exists():
        raise FileNotFoundError(f"Missing term metrics CSV: {term_metrics_csv}")
    if not seeds:
        raise ValueError("seeds must contain at least one integer seed")

    by_metric: dict[str, list[dict[str, str]]] = {}
    for seed in seeds:
        with tempfile.NamedTemporaryFile(prefix="rb_seed_", suffix=".csv", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            _compute_term_party_permutation(
                term_metrics_csv=term_metrics_csv,
                out_csv=tmp_path,
                permutations=max(0, int(permutations)),
                bootstrap_samples=max(0, int(bootstrap_samples)),
                seed=int(seed),
                block_years=max(0, int(term_block_years)),
                q_threshold=float(q_threshold),
                min_n_obs=max(0, int(min_term_n_obs)),
                primary_only=bool(primary_only),
                include_diagnostic_metrics=bool(include_diagnostic_metrics),
            )
            with tmp_path.open("r", encoding="utf-8", newline="") as handle:
                rdr = csv.DictReader(handle)
                for r in rdr:
                    mid = (r.get("metric_id") or "").strip()
                    if not mid:
                        continue
                    rr = dict(r)
                    rr["run_seed"] = str(seed)
                    by_metric.setdefault(mid, []).append(rr)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _sign(v: float | None) -> str:
        if v is None:
            return "unknown"
        if v > 0:
            return "positive"
        if v < 0:
            return "negative"
        return "flat"

    header = [
        "metric_id",
        "metric_label",
        "metric_family",
        "metric_primary",
        "agg_kind",
        "units",
        "n_runs",
        "seeds",
        "q_min",
        "q_max",
        "q_range",
        "p_min",
        "p_max",
        "tier_values",
        "n_distinct_tiers",
        "tier_unstable",
        "effect_min",
        "effect_max",
        "effect_sign_values",
        "effect_sign_consistent",
    ]
    rows: list[dict[str, str]] = []
    for mid in sorted(by_metric.keys()):
        rs = by_metric[mid]
        q_vals = [_parse_float(r.get("q_bh_fdr") or "") for r in rs]
        p_vals = [_parse_float(r.get("p_two_sided") or "") for r in rs]
        eff_vals = [_parse_float(r.get("observed_diff_d_minus_r") or "") for r in rs]
        q_num = [x for x in q_vals if x is not None]
        p_num = [x for x in p_vals if x is not None]
        e_num = [x for x in eff_vals if x is not None]

        tier_values = sorted({(r.get("evidence_tier") or "").strip() or "missing" for r in rs}, key=_tier_rank, reverse=True)
        sign_values = sorted({_sign(v) for v in e_num})
        sign_non_unknown = [s for s in sign_values if s != "unknown"]
        sign_consistent = len(set(sign_non_unknown)) <= 1 if sign_non_unknown else False

        first = rs[0]
        q_min = min(q_num) if q_num else None
        q_max = max(q_num) if q_num else None
        p_min = min(p_num) if p_num else None
        p_max = max(p_num) if p_num else None
        e_min = min(e_num) if e_num else None
        e_max = max(e_num) if e_num else None
        q_range = (q_max - q_min) if (q_min is not None and q_max is not None) else None

        rows.append(
            {
                "metric_id": mid,
                "metric_label": (first.get("metric_label") or "").strip(),
                "metric_family": (first.get("metric_family") or "").strip(),
                "metric_primary": (first.get("metric_primary") or "").strip(),
                "agg_kind": (first.get("agg_kind") or "").strip(),
                "units": (first.get("units") or "").strip(),
                "n_runs": str(len(rs)),
                "seeds": ",".join(str(int(s)) for s in sorted({_parse_int(r.get("run_seed") or "") or 0 for r in rs})),
                "q_min": _fmt(q_min),
                "q_max": _fmt(q_max),
                "q_range": _fmt(q_range),
                "p_min": _fmt(p_min),
                "p_max": _fmt(p_max),
                "tier_values": "|".join(tier_values),
                "n_distinct_tiers": str(len(tier_values)),
                "tier_unstable": "1" if len(tier_values) > 1 else "0",
                "effect_min": _fmt(e_min),
                "effect_max": _fmt(e_max),
                "effect_sign_values": "|".join(sign_values),
                "effect_sign_consistent": "1" if sign_consistent else "0",
            }
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


def _load_evidence_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _tier_rank(tier: str) -> int:
    t = (tier or "").strip()
    if t == "confirmatory":
        return 2
    if t == "supportive":
        return 1
    return 0


def compare_randomization_outputs(
    *,
    base_party_term_csv: Path,
    alt_party_term_csv: Path,
    base_within_csv: Path | None,
    alt_within_csv: Path | None,
    out_csv: Path,
) -> None:
    header = [
        "analysis",
        "metric_id",
        "pres_party",
        "metric_family",
        "tier_base",
        "tier_alt",
        "tier_change",
        "q_base",
        "q_alt",
        "p_base",
        "p_alt",
        "n_base",
        "n_alt",
    ]
    rows: list[dict[str, str]] = []

    def _append_analysis(*, analysis: str, base_rows: list[dict[str, str]], alt_rows: list[dict[str, str]], has_party: bool) -> None:
        if not base_rows and not alt_rows:
            return
        bmap: dict[tuple[str, str], dict[str, str]] = {}
        amap: dict[tuple[str, str], dict[str, str]] = {}
        for r in base_rows:
            k = ((r.get("metric_id") or "").strip(), (r.get("pres_party") or "").strip() if has_party else "")
            bmap[k] = r
        for r in alt_rows:
            k = ((r.get("metric_id") or "").strip(), (r.get("pres_party") or "").strip() if has_party else "")
            amap[k] = r
        keys = sorted(set(bmap.keys()) | set(amap.keys()), key=lambda x: (x[0], x[1]))
        for k in keys:
            br = bmap.get(k, {})
            ar = amap.get(k, {})
            tier_b = (br.get("evidence_tier") or "").strip()
            tier_a = (ar.get("evidence_tier") or "").strip()
            rb = _tier_rank(tier_b)
            ra = _tier_rank(tier_a)
            if ra > rb:
                change = "stronger"
            elif ra < rb:
                change = "weaker"
            else:
                change = "same"
            family = (ar.get("metric_family") or br.get("metric_family") or "").strip()
            n_base = (br.get("n_obs") or br.get("n_presidents_with_both") or "").strip()
            n_alt = (ar.get("n_obs") or ar.get("n_presidents_with_both") or "").strip()
            rows.append(
                {
                    "analysis": analysis,
                    "metric_id": k[0],
                    "pres_party": k[1],
                    "metric_family": family,
                    "tier_base": tier_b or "missing",
                    "tier_alt": tier_a or "missing",
                    "tier_change": change,
                    "q_base": (br.get("q_bh_fdr") or "").strip(),
                    "q_alt": (ar.get("q_bh_fdr") or "").strip(),
                    "p_base": (br.get("p_two_sided") or "").strip(),
                    "p_alt": (ar.get("p_two_sided") or "").strip(),
                    "n_base": n_base,
                    "n_alt": n_alt,
                }
            )

    _append_analysis(
        analysis="term_party",
        base_rows=_load_evidence_rows(base_party_term_csv),
        alt_rows=_load_evidence_rows(alt_party_term_csv),
        has_party=False,
    )
    if base_within_csv is not None and alt_within_csv is not None:
        _append_analysis(
            analysis="within_unified",
            base_rows=_load_evidence_rows(base_within_csv),
            alt_rows=_load_evidence_rows(alt_within_csv),
            has_party=True,
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


def _direction_label(v: float | None) -> str:
    if v is None:
        return "unknown"
    if v > 0:
        return "positive"
    if v < 0:
        return "negative"
    return "flat"


def write_claims_table(
    *,
    baseline_party_term_csv: Path,
    strict_party_term_csv: Path,
    baseline_within_csv: Path | None,
    strict_within_csv: Path | None,
    out_csv: Path,
) -> None:
    header = [
        "analysis",
        "metric_id",
        "metric_label",
        "metric_family",
        "pres_party",
        "estimand_id",
        "estimand",
        "direction",
        "effect_baseline",
        "effect_strict",
        "q_baseline",
        "q_strict",
        "q_delta_strict_minus_baseline",
        "p_baseline",
        "p_strict",
        "tier_baseline",
        "tier_strict",
        "tier_change",
        "n_baseline",
        "n_strict",
    ]
    rows: list[dict[str, str]] = []

    def _append_analysis(
        *,
        analysis: str,
        base_rows: list[dict[str, str]],
        strict_rows: list[dict[str, str]],
        has_party: bool,
        effect_col: str,
        estimand_id: str,
        estimand_label: str,
    ) -> None:
        if not base_rows and not strict_rows:
            return
        bmap: dict[tuple[str, str], dict[str, str]] = {}
        smap: dict[tuple[str, str], dict[str, str]] = {}
        for r in base_rows:
            k = ((r.get("metric_id") or "").strip(), (r.get("pres_party") or "").strip() if has_party else "")
            bmap[k] = r
        for r in strict_rows:
            k = ((r.get("metric_id") or "").strip(), (r.get("pres_party") or "").strip() if has_party else "")
            smap[k] = r

        keys = sorted(set(bmap.keys()) | set(smap.keys()), key=lambda x: (x[0], x[1]))
        for k in keys:
            br = bmap.get(k, {})
            sr = smap.get(k, {})
            tier_b = (br.get("evidence_tier") or "").strip()
            tier_s = (sr.get("evidence_tier") or "").strip()
            rb = _tier_rank(tier_b)
            rs = _tier_rank(tier_s)
            if rs > rb:
                change = "stronger"
            elif rs < rb:
                change = "weaker"
            else:
                change = "same"

            effect_b = _parse_float(br.get(effect_col) or "")
            effect_s = _parse_float(sr.get(effect_col) or "")
            dir_v = effect_b if effect_b is not None else effect_s
            q_b = _parse_float(br.get("q_bh_fdr") or "")
            q_s = _parse_float(sr.get("q_bh_fdr") or "")
            q_delta = (q_s - q_b) if (q_b is not None and q_s is not None) else None

            rows.append(
                {
                    "analysis": analysis,
                    "metric_id": k[0],
                    "metric_label": (sr.get("metric_label") or br.get("metric_label") or "").strip(),
                    "metric_family": (sr.get("metric_family") or br.get("metric_family") or "").strip(),
                    "pres_party": k[1],
                    "estimand_id": estimand_id,
                    "estimand": estimand_label,
                    "direction": _direction_label(dir_v),
                    "effect_baseline": _fmt(effect_b),
                    "effect_strict": _fmt(effect_s),
                    "q_baseline": _fmt(q_b),
                    "q_strict": _fmt(q_s),
                    "q_delta_strict_minus_baseline": _fmt(q_delta),
                    "p_baseline": (br.get("p_two_sided") or "").strip(),
                    "p_strict": (sr.get("p_two_sided") or "").strip(),
                    "tier_baseline": tier_b or "missing",
                    "tier_strict": tier_s or "missing",
                    "tier_change": change,
                    "n_baseline": (br.get("n_obs") or br.get("n_presidents_with_both") or "").strip(),
                    "n_strict": (sr.get("n_obs") or sr.get("n_presidents_with_both") or "").strip(),
                }
            )

    _append_analysis(
        analysis="term_party",
        base_rows=_load_evidence_rows(baseline_party_term_csv),
        strict_rows=_load_evidence_rows(strict_party_term_csv),
        has_party=False,
        effect_col="observed_diff_d_minus_r",
        estimand_id="d_minus_r",
        estimand_label="mean(term_metric | D) - mean(term_metric | R)",
    )
    if baseline_within_csv is not None and strict_within_csv is not None:
        _append_analysis(
            analysis="within_unified",
            base_rows=_load_evidence_rows(baseline_within_csv),
            strict_rows=_load_evidence_rows(strict_within_csv),
            has_party=True,
            effect_col="observed_mean_delta_unified_minus_divided",
            estimand_id="unified_minus_divided_within_term",
            estimand_label="mean over president-terms of (unified - divided)",
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(out_csv)


def write_inversion_definition_robustness(
    *,
    permutation_party_term_csv: Path,
    out_csv: Path,
    out_md: Path | None = None,
) -> None:
    if not permutation_party_term_csv.exists():
        raise FileNotFoundError(f"Missing permutation term CSV: {permutation_party_term_csv}")

    rows_by_metric: dict[str, dict[str, str]] = {}
    with permutation_party_term_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            mid = (r.get("metric_id") or "").strip()
            if not mid:
                continue
            rows_by_metric[mid] = r

    groups: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "inversion_share",
            [
                ("daily", "yield_curve_t10y2y_inversion_share"),
                ("monthly_eop", "yield_curve_t10y2y_inversion_share_monthly_eop"),
                ("monthly_avg", "yield_curve_t10y2y_inversion_share_monthly_avg"),
            ],
        ),
        (
            "inversion_start_count",
            [
                ("daily", "yield_curve_t10y2y_inversion_start_count"),
                ("monthly_eop", "yield_curve_t10y2y_inversion_start_count_monthly_eop"),
                ("monthly_avg", "yield_curve_t10y2y_inversion_start_count_monthly_avg"),
            ],
        ),
    ]

    header = [
        "concept",
        "definition",
        "metric_id",
        "present_in_input",
        "n_obs",
        "effect_d_minus_r",
        "effect_delta_vs_daily",
        "q_bh_fdr",
        "q_delta_vs_daily",
        "p_two_sided",
        "evidence_tier",
        "bootstrap_ci95_low",
        "bootstrap_ci95_high",
    ]
    out_rows: list[dict[str, str]] = []

    for concept, defs in groups:
        daily_row = rows_by_metric.get(defs[0][1], {})
        daily_effect = _parse_float(daily_row.get("observed_diff_d_minus_r") or "")
        daily_q = _parse_float(daily_row.get("q_bh_fdr") or "")
        for definition, metric_id in defs:
            r = rows_by_metric.get(metric_id, {})
            effect = _parse_float(r.get("observed_diff_d_minus_r") or "")
            q = _parse_float(r.get("q_bh_fdr") or "")
            out_rows.append(
                {
                    "concept": concept,
                    "definition": definition,
                    "metric_id": metric_id,
                    "present_in_input": "1" if r else "0",
                    "n_obs": (r.get("n_obs") or "").strip(),
                    "effect_d_minus_r": _fmt(effect),
                    "effect_delta_vs_daily": _fmt((effect - daily_effect) if (effect is not None and daily_effect is not None) else None),
                    "q_bh_fdr": _fmt(q),
                    "q_delta_vs_daily": _fmt((q - daily_q) if (q is not None and daily_q is not None) else None),
                    "p_two_sided": (r.get("p_two_sided") or "").strip(),
                    "evidence_tier": (r.get("evidence_tier") or "").strip(),
                    "bootstrap_ci95_low": (r.get("bootstrap_ci95_low") or "").strip(),
                    "bootstrap_ci95_high": (r.get("bootstrap_ci95_high") or "").strip(),
                }
            )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp_csv.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    tmp_csv.replace(out_csv)

    if out_md is None:
        return

    lines: list[str] = []
    lines.append("# Inversion Definition Robustness")
    lines.append("")
    lines.append(f"Source: `{permutation_party_term_csv}`")
    lines.append("")
    lines.append("Compares D-R estimates for T10Y2Y inversion metrics under three definitions:")
    lines.append("- daily observations")
    lines.append("- monthly end-of-period (EOP)")
    lines.append("- monthly average (AVG)")
    lines.append("")

    for concept, defs in groups:
        lines.append(f"## {concept}")
        lines.append("")
        lines.append("| Definition | n_obs | Effect (D-R) | Delta vs daily | q | Delta q vs daily | Tier | CI95 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for definition, metric_id in defs:
            r = next((x for x in out_rows if x["metric_id"] == metric_id), None)
            if not r:
                continue
            ci = ""
            lo = (r.get("bootstrap_ci95_low") or "").strip()
            hi = (r.get("bootstrap_ci95_high") or "").strip()
            if lo or hi:
                ci = f"[{lo}, {hi}]"
            lines.append(
                "| "
                + " | ".join(
                    [
                        definition,
                        r.get("n_obs", ""),
                        r.get("effect_d_minus_r", ""),
                        r.get("effect_delta_vs_daily", ""),
                        r.get("q_bh_fdr", ""),
                        r.get("q_delta_vs_daily", ""),
                        r.get("evidence_tier", ""),
                        ci,
                    ]
                )
                + " |"
            )
        lines.append("")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    tmp_md = out_md.with_suffix(out_md.suffix + ".tmp")
    tmp_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp_md.replace(out_md)


def write_cpi_sa_nsa_level_robustness(
    *,
    permutation_party_term_csv: Path,
    out_csv: Path,
    out_md: Path | None = None,
) -> None:
    if not permutation_party_term_csv.exists():
        raise FileNotFoundError(f"Missing permutation term CSV: {permutation_party_term_csv}")

    rows_by_metric: dict[str, dict[str, str]] = {}
    with permutation_party_term_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            mid = (r.get("metric_id") or "").strip()
            if not mid:
                continue
            rows_by_metric[mid] = r

    groups: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "cpi_level_term_pct_change",
            [
                ("nsa", "cpi_price_level_term_pct_change_nsa"),
                ("sa", "cpi_price_level_term_pct_change_sa"),
            ],
        ),
        (
            "cpi_level_term_cagr_pct",
            [
                ("nsa", "cpi_price_level_term_cagr_pct_nsa"),
                ("sa", "cpi_price_level_term_cagr_pct_sa"),
            ],
        ),
    ]

    header = [
        "concept",
        "definition",
        "metric_id",
        "present_in_input",
        "n_obs",
        "effect_d_minus_r",
        "effect_delta_vs_nsa",
        "q_bh_fdr",
        "q_delta_vs_nsa",
        "p_two_sided",
        "evidence_tier",
        "bootstrap_ci95_low",
        "bootstrap_ci95_high",
    ]
    out_rows: list[dict[str, str]] = []

    for concept, defs in groups:
        nsa_row = rows_by_metric.get(defs[0][1], {})
        nsa_effect = _parse_float(nsa_row.get("observed_diff_d_minus_r") or "")
        nsa_q = _parse_float(nsa_row.get("q_bh_fdr") or "")
        for definition, metric_id in defs:
            r = rows_by_metric.get(metric_id, {})
            effect = _parse_float(r.get("observed_diff_d_minus_r") or "")
            q = _parse_float(r.get("q_bh_fdr") or "")
            out_rows.append(
                {
                    "concept": concept,
                    "definition": definition,
                    "metric_id": metric_id,
                    "present_in_input": "1" if r else "0",
                    "n_obs": (r.get("n_obs") or "").strip(),
                    "effect_d_minus_r": _fmt(effect),
                    "effect_delta_vs_nsa": _fmt((effect - nsa_effect) if (effect is not None and nsa_effect is not None) else None),
                    "q_bh_fdr": _fmt(q),
                    "q_delta_vs_nsa": _fmt((q - nsa_q) if (q is not None and nsa_q is not None) else None),
                    "p_two_sided": (r.get("p_two_sided") or "").strip(),
                    "evidence_tier": (r.get("evidence_tier") or "").strip(),
                    "bootstrap_ci95_low": (r.get("bootstrap_ci95_low") or "").strip(),
                    "bootstrap_ci95_high": (r.get("bootstrap_ci95_high") or "").strip(),
                }
            )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = out_csv.with_suffix(out_csv.suffix + ".tmp")
    with tmp_csv.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    tmp_csv.replace(out_csv)

    if out_md is None:
        return

    lines: list[str] = []
    lines.append("# CPI SA vs NSA Level Robustness")
    lines.append("")
    lines.append(f"Source: `{permutation_party_term_csv}`")
    lines.append("")
    lines.append("Compares D-R estimates for CPI level-term metrics under:")
    lines.append("- NSA CPI definitions")
    lines.append("- SA CPI alternate definitions")
    lines.append("")

    for concept, defs in groups:
        lines.append(f"## {concept}")
        lines.append("")
        lines.append("| Definition | n_obs | Effect (D-R) | Delta vs NSA | q | Delta q vs NSA | Tier | CI95 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for definition, metric_id in defs:
            r = next((x for x in out_rows if x["metric_id"] == metric_id), None)
            if not r:
                continue
            ci = ""
            lo = (r.get("bootstrap_ci95_low") or "").strip()
            hi = (r.get("bootstrap_ci95_high") or "").strip()
            if lo or hi:
                ci = f"[{lo}, {hi}]"
            lines.append(
                "| "
                + " | ".join(
                    [
                        definition,
                        r.get("n_obs", ""),
                        r.get("effect_d_minus_r", ""),
                        r.get("effect_delta_vs_nsa", ""),
                        r.get("q_bh_fdr", ""),
                        r.get("q_delta_vs_nsa", ""),
                        r.get("evidence_tier", ""),
                        ci,
                    ]
                )
                + " |"
            )
        lines.append("")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    tmp_md = out_md.with_suffix(out_md.suffix + ".tmp")
    tmp_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp_md.replace(out_md)
