from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

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


def _add_bh_q_values(rows: list[dict[str, str]], *, p_col: str, q_col: str) -> None:
    """Benjamini-Hochberg FDR adjustment over rows with numeric p-values."""
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


def _p_two_sided(observed: float, perm_diffs: list[float]) -> float | None:
    if not perm_diffs:
        return None
    extreme = sum(1 for d in perm_diffs if abs(d) >= abs(observed))
    return (1 + extreme) / (1 + len(perm_diffs))


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
    term_metrics_csv: Path,
) -> dict[str, dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    with term_metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            metric_id = (row.get("metric_id") or "").strip()
            party = (row.get("party_abbrev") or "").strip()
            if not metric_id or party not in {"D", "R"}:
                continue
            if metric_id in DIAGNOSTIC_ONLY_METRIC_IDS:
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

    out: dict[str, dict[str, Any]] = {}
    for (metric_id, _party), g in groups.items():
        slot = out.get(metric_id)
        if slot is None:
            slot = {
                "metric_id": metric_id,
                "metric_label": g["metric_label"],
                "metric_family": g["metric_family"],
                "agg_kind": g["agg_kind"],
                "units": g["units"],
                "obs": [],
            }
            out[metric_id] = slot
        slot["obs"].extend(g["obs"])

    return out


def run_randomization(
    *,
    term_metrics_csv: Path,
    output_csv: Path,
    permutations: int,
    bootstrap_samples: int,
    seed: int,
    term_block_years: int,
    q_threshold: float,
    min_term_n_obs: int,
) -> None:
    if not term_metrics_csv.exists():
        raise FileNotFoundError(f"Missing term metrics CSV: {term_metrics_csv}")

    groups = _load_term_metric_groups(term_metrics_csv)
    rng = random.Random(seed)
    boot_rng = random.Random(seed + 1000003)

    header = [
        "metric_id",
        "metric_label",
        "metric_family",
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
        "evidence_tier",
        "q_threshold",
        "min_n_threshold",
        "permutations",
        "bootstrap_samples",
        "seed",
        "block_years",
        "min_term_start_year",
        "max_term_start_year",
    ]
    rows: list[dict[str, str]] = []

    for metric_id in sorted(groups.keys()):
        g = groups[metric_id]
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
            if term_block_years > 0:
                years_full = [(o.term_start.year if o.term_start is not None else None) for o in obs]
                valid_years = [y for y in years_full if y is not None]
                anchor = min(valid_years) if valid_years else 0
                block_to_idx: dict[int, list[int]] = {}
                for i, y in enumerate(years_full):
                    if y is None:
                        b = -1
                    else:
                        b = (y - anchor) // term_block_years
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
            p_two = _p_two_sided(observed, perm_diffs)
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
                "block_years": str(term_block_years),
                "min_term_start_year": str(min(years)) if years else "",
                "max_term_start_year": str(max(years)) if years else "",
            }
        )

    _add_bh_q_values(rows, p_col="p_two_sided", q_col="q_bh_fdr")
    for r in rows:
        q = _parse_float(r.get("q_bh_fdr") or "")
        ci_lo = _parse_float(r.get("bootstrap_ci95_low") or "")
        ci_hi = _parse_float(r.get("bootstrap_ci95_high") or "")
        n = _parse_int(r.get("n_obs") or "") or 0
        pass_q = q is not None and q < q_threshold
        pass_n = n >= min_term_n_obs
        pass_q_010 = q is not None and q < 0.10
        if pass_q and pass_n:
            tier = "confirmatory"
        elif pass_q_010 and pass_n:
            tier = "supportive"
        else:
            tier = "exploratory"
        r["evidence_tier"] = tier
        r["q_threshold"] = _fmt(q_threshold)
        r["min_n_threshold"] = str(int(min_term_n_obs))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_csv.with_suffix(output_csv.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(output_csv)
