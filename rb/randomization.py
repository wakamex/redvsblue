from __future__ import annotations

import csv
import math
import random
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
        "inference_scope",
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
                "inference_scope": "primary" if bool(primary_only) else "all",
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


def _write_evidence_summary(
    *,
    term_party_csv: Path | None,
    out_csv: Path,
) -> None:
    analyses: list[tuple[str, Path]] = []
    if term_party_csv is not None and term_party_csv.exists():
        analyses.append(("term_party", term_party_csv))

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

                for scope_label, agg_dict, fc_dict, ac_dict in (
                    ("all", aggregate, family_counts, analysis_counts),
                    ("primary" if is_primary else None, aggregate_primary, family_counts_primary, analysis_counts_primary),
                ):
                    if scope_label is None:
                        continue
                    for fam_key in (fam, "__all__"):
                        k = (analysis, fam_key, tier)
                        a = agg_dict.get(k)
                        if a is None:
                            a = {"n_rows": 0, "n_pass_q_threshold": 0, "n_pass_q_005": 0, "n_pass_q_010": 0, "n_pass_ci": 0, "n_pass_min_n": 0}
                            agg_dict[k] = a
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
                    fc_dict[(analysis, fam)] = fc_dict.get((analysis, fam), 0) + 1
                    fc_dict[(analysis, "__all__")] = fc_dict.get((analysis, "__all__"), 0) + 1
                    ac_dict[analysis] = ac_dict.get(analysis, 0) + 1

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
        fam_counts_d: dict[tuple[str, str], int],
        ana_counts_d: dict[str, int],
    ) -> None:
        for analysis, _path in analyses:
            families = sorted({fam for (a, fam) in fam_counts_d.keys() if a == analysis and fam != "__all__"})
            families = ["__all__"] + families
            for fam in families:
                fam_den = fam_counts_d.get((analysis, fam), 0)
                ana_den = ana_counts_d.get(analysis, 0)
                for tier in tier_order:
                    a = agg.get(
                        (analysis, fam, tier),
                        {"n_rows": 0, "n_pass_q_threshold": 0, "n_pass_q_005": 0, "n_pass_q_010": 0, "n_pass_ci": 0, "n_pass_min_n": 0},
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

    _emit_scope(scope="all_metrics", agg=aggregate, fam_counts_d=family_counts, ana_counts_d=analysis_counts)
    _emit_scope(scope="primary_only", agg=aggregate_primary, fam_counts_d=family_counts_primary, ana_counts_d=analysis_counts_primary)

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
    summary_csv: Path | None,
    out_md: Path,
) -> None:
    def _read_rows(path: Path | None) -> list[dict[str, str]]:
        if path is None or not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    term_rows = _read_rows(term_party_csv)
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

    if term_rows:
        sel = [r for r in term_rows if (r.get("evidence_tier") or "") in {"confirmatory", "supportive"}]
        lines.append("## Term-Level Party Differences")
        lines.append("")
        if not sel:
            lines.append("No confirmatory/supportive rows under current thresholds.")
            lines.append("")
        else:
            sel.sort(key=lambda r: (_parse_float(r.get("q_bh_fdr") or "") or 1e9, _parse_float(r.get("p_two_sided") or "") or 1e9))
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
                n = (r.get("n_obs") or "").strip()
                lines.append(f"| {tier} | {metric} | {family} | {q} | {p} | {ci} | {n} |")
            lines.append("")

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
    primary_only: bool,
    output_evidence_summary_csv: Path | None,
    output_evidence_md: Path | None,
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

    if output_evidence_summary_csv is not None:
        _write_evidence_summary(
            term_party_csv=output_party_term_csv,
            out_csv=output_evidence_summary_csv,
        )
    if output_evidence_md is not None:
        _write_evidence_markdown(
            term_party_csv=output_party_term_csv,
            summary_csv=output_evidence_summary_csv,
            out_md=output_evidence_md,
        )


def _sign_float(v: float | None) -> int:
    if v is None:
        return 0
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


def _load_inference_rows(path: Path | None) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if path is None or not path.exists():
        return out
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            mid = (row.get("metric_id") or "").strip()
            if not mid:
                continue
            out[mid] = row
    return out


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


def _publication_tier_with_hac_gate(
    *,
    tier: str,
    has_hac_row: bool,
    hac_p: float | None,
    direction_agree: bool | None,
    hac_p_threshold: float,
) -> tuple[str, str]:
    txt = (tier or "").strip() or "missing"
    if txt != "confirmatory":
        return txt, ""
    if direction_agree is False:
        return "exploratory", "direction_disagree"
    if not has_hac_row:
        return "supportive", "no_hac_row"
    if direction_agree is None:
        return "supportive", "missing_hac_effect"
    if hac_p is None:
        return "supportive", "missing_hac_p"
    if hac_p >= hac_p_threshold:
        return "supportive", "hac_not_significant"
    return txt, "pass"


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
    out_csv: Path,
    inference_table_csv: Path | None = None,
    publication_mode: bool = False,
    publication_hac_p_threshold: float = 0.05,
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
        "hac_p_two_sided_norm",
        "hac_p_lt_threshold",
        "hac_direction_agree_with_claim_effect",
        "tier_baseline_publication",
        "tier_strict_publication",
        "publication_gate_reason_baseline",
        "publication_gate_reason_strict",
    ]
    rows: list[dict[str, str]] = []
    inference_rows = _load_inference_rows(inference_table_csv)
    p_thr = max(0.0, min(1.0, float(publication_hac_p_threshold)))

    base_rows = _load_evidence_rows(baseline_party_term_csv)
    strict_rows = _load_evidence_rows(strict_party_term_csv)

    bmap: dict[str, dict[str, str]] = {}
    smap: dict[str, dict[str, str]] = {}
    for r in base_rows:
        k = (r.get("metric_id") or "").strip()
        if k:
            bmap[k] = r
    for r in strict_rows:
        k = (r.get("metric_id") or "").strip()
        if k:
            smap[k] = r

    keys = sorted(set(bmap.keys()) | set(smap.keys()))
    for k in keys:
        br = bmap.get(k, {})
        sr = smap.get(k, {})
        tier_b = (br.get("evidence_tier") or "").strip()
        tier_s = (sr.get("evidence_tier") or "").strip()
        rb_rank = _tier_rank(tier_b)
        rs_rank = _tier_rank(tier_s)
        if rs_rank > rb_rank:
            change = "stronger"
        elif rs_rank < rb_rank:
            change = "weaker"
        else:
            change = "same"

        effect_b = _parse_float(br.get("observed_diff_d_minus_r") or "")
        effect_s = _parse_float(sr.get("observed_diff_d_minus_r") or "")
        dir_v = effect_b if effect_b is not None else effect_s
        q_b = _parse_float(br.get("q_bh_fdr") or "")
        q_s = _parse_float(sr.get("q_bh_fdr") or "")
        q_delta = (q_s - q_b) if (q_b is not None and q_s is not None) else None

        inf = inference_rows.get(k, {})
        hac_p = _parse_float(inf.get("hac_nw_p_two_sided_norm") or "")
        hac_effect = _parse_float(inf.get("effect_d_minus_r") or "")
        claim_effect_for_sign = effect_s if effect_s is not None else effect_b
        direction_agree: bool | None = None
        s_hac = _sign_float(hac_effect)
        s_claim = _sign_float(claim_effect_for_sign)
        if inf:
            if s_hac != 0 and s_claim != 0:
                direction_agree = s_hac == s_claim
            else:
                direction_agree = None
        b_pub_tier = tier_b or "missing"
        s_pub_tier = tier_s or "missing"
        b_gate_reason = ""
        s_gate_reason = ""
        if publication_mode:
            b_pub_tier, b_gate_reason = _publication_tier_with_hac_gate(
                tier=tier_b,
                has_hac_row=bool(inf),
                hac_p=hac_p,
                direction_agree=direction_agree,
                hac_p_threshold=p_thr,
            )
            s_pub_tier, s_gate_reason = _publication_tier_with_hac_gate(
                tier=tier_s,
                has_hac_row=bool(inf),
                hac_p=hac_p,
                direction_agree=direction_agree,
                hac_p_threshold=p_thr,
            )

        rows.append(
            {
                "analysis": "term_party",
                "metric_id": k,
                "metric_label": (sr.get("metric_label") or br.get("metric_label") or "").strip(),
                "metric_family": (sr.get("metric_family") or br.get("metric_family") or "").strip(),
                "pres_party": "",
                "estimand_id": "d_minus_r",
                "estimand": "mean(term_metric | D) - mean(term_metric | R)",
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
                "n_baseline": (br.get("n_obs") or "").strip(),
                "n_strict": (sr.get("n_obs") or "").strip(),
                "hac_p_two_sided_norm": _fmt(hac_p),
                "hac_p_lt_threshold": "1" if (hac_p is not None and hac_p < p_thr) else ("0" if hac_p is not None else ""),
                "hac_direction_agree_with_claim_effect": (
                    "1" if direction_agree is True else ("0" if direction_agree is False else "")
                ),
                "tier_baseline_publication": b_pub_tier,
                "tier_strict_publication": s_pub_tier,
                "publication_gate_reason_baseline": b_gate_reason,
                "publication_gate_reason_strict": s_gate_reason,
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
