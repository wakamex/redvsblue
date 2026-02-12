from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path


def _parse_float(s: str) -> float | None:
    txt = (s or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def _fmt(x: float | None, digits: int = 3) -> str:
    if x is None:
        return ""
    return f"{x:.{digits}f}"


def _tier_rank(t: str) -> int:
    txt = (t or "").strip()
    if txt == "confirmatory":
        return 3
    if txt == "supportive":
        return 2
    if txt == "exploratory":
        return 1
    return 0


def _best_claim_tier(row: dict[str, str]) -> str:
    return (
        (row.get("tier_strict_publication") or "").strip()
        or (row.get("tier_strict") or "").strip()
        or (row.get("tier_baseline_publication") or "").strip()
        or (row.get("tier_baseline") or "").strip()
        or "missing"
    )


def _preferred_q(row: dict[str, str]) -> float | None:
    return _parse_float((row.get("q_strict") or "").strip()) or _parse_float((row.get("q_baseline") or "").strip())


def _preferred_effect(row: dict[str, str]) -> float | None:
    return _parse_float((row.get("effect_strict") or "").strip()) or _parse_float((row.get("effect_baseline") or "").strip())


def _preferred_n(row: dict[str, str]) -> int:
    txt = (row.get("n_strict") or "").strip() or (row.get("n_baseline") or "").strip()
    try:
        return int(txt)
    except ValueError:
        return 0


def _dir_label(effect: float | None) -> str:
    if effect is None:
        return ""
    if effect > 0:
        return "D > R"
    if effect < 0:
        return "R > D"
    return "tie"


def _load_primary_metric_ids(inference_table_csv: Path) -> set[str]:
    out: set[str] = set()
    with inference_table_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            mid = (row.get("metric_id") or "").strip()
            if mid:
                out.add(mid)
    return out


def _load_vintage_bounds(vintage_csv: Path) -> tuple[str, str, str, str]:
    obs_end: list[str] = []
    snap_ts: list[str] = []
    rt_end: list[str] = []
    last_upd: list[str] = []
    with vintage_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            if (row.get("status") or "").strip() != "ok":
                continue
            oe = (row.get("observation_end") or "").strip()
            ts = (row.get("artifact_timestamp_utc_compact") or "").strip()
            re_ = (row.get("top_realtime_end") or "").strip()
            lu = (row.get("last_updated") or "").strip()
            if oe:
                obs_end.append(oe)
            if ts:
                snap_ts.append(ts)
            if re_:
                rt_end.append(re_)
            if lu:
                last_upd.append(lu)
    return (
        min(obs_end) if obs_end else "",
        max(obs_end) if obs_end else "",
        max(snap_ts) if snap_ts else "",
        max(rt_end) if rt_end else "",
    )


def write_final_product_report(
    *,
    claims_table_csv: Path,
    inference_table_csv: Path,
    congress_binary_csv: Path | None,
    vintage_csv: Path | None,
    out_md: Path,
) -> None:
    if not claims_table_csv.exists():
        raise FileNotFoundError(f"Missing claims table CSV: {claims_table_csv}")
    if not inference_table_csv.exists():
        raise FileNotFoundError(f"Missing inference table CSV: {inference_table_csv}")

    primary_ids = _load_primary_metric_ids(inference_table_csv)
    term_rows: list[dict[str, str]] = []
    within_rows: list[dict[str, str]] = []
    congress_claim_rows: list[dict[str, str]] = []

    with claims_table_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            mid = (row.get("metric_id") or "").strip()
            if not mid or mid not in primary_ids:
                continue
            analysis = (row.get("analysis") or "").strip()
            if analysis == "term_party":
                term_rows.append(row)
            elif analysis == "within_unified":
                within_rows.append(row)
            elif analysis == "congress_unified_binary" and (row.get("pres_party") or "").strip() == "all":
                congress_claim_rows.append(row)

    term_counts = {"confirmatory": 0, "supportive": 0, "exploratory": 0, "missing": 0}
    n_pos = 0
    n_neg = 0
    n_tie = 0
    for row in term_rows:
        t = _best_claim_tier(row)
        term_counts[t if t in term_counts else "missing"] += 1
        eff = _preferred_effect(row)
        if eff is None:
            continue
        if eff > 0:
            n_pos += 1
        elif eff < 0:
            n_neg += 1
        else:
            n_tie += 1

    term_rows_sorted = sorted(
        term_rows,
        key=lambda r: (
            -_tier_rank(_best_claim_tier(r)),
            _preferred_q(r) if _preferred_q(r) is not None else 1e9,
            (r.get("metric_id") or "").strip(),
        ),
    )

    within_counts = {"confirmatory": 0, "supportive": 0, "exploratory": 0, "missing": 0}
    for row in within_rows:
        t = _best_claim_tier(row)
        within_counts[t if t in within_counts else "missing"] += 1

    congress_counts = {"confirmatory": 0, "supportive": 0, "exploratory": 0, "missing": 0}
    for row in congress_claim_rows:
        t = _best_claim_tier(row)
        congress_counts[t if t in congress_counts else "missing"] += 1

    congress_diag_rows: list[dict[str, str]] = []
    if congress_binary_csv is not None and congress_binary_csv.exists():
        with congress_binary_csv.open("r", encoding="utf-8", newline="") as handle:
            rdr = csv.DictReader(handle)
            for row in rdr:
                if (row.get("pres_party") or "").strip() != "all":
                    continue
                mid = (row.get("metric_id") or "").strip()
                if not mid or mid not in primary_ids:
                    continue
                congress_diag_rows.append(row)
    congress_small_cell = sum(1 for r in congress_diag_rows if (r.get("small_cell_warning") or "").strip() == "1")

    vintage_obs_end_min = ""
    vintage_obs_end_max = ""
    vintage_snap_max = ""
    vintage_rt_max = ""
    if vintage_csv is not None and vintage_csv.exists():
        vintage_obs_end_min, vintage_obs_end_max, vintage_snap_max, vintage_rt_max = _load_vintage_bounds(vintage_csv)

    lines: list[str] = []
    lines.append("# Final Product Summary")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}")
    lines.append("")
    lines.append("Inputs:")
    lines.append(f"- `{claims_table_csv}`")
    lines.append(f"- `{inference_table_csv}`")
    if congress_binary_csv is not None and congress_binary_csv.exists():
        lines.append(f"- `{congress_binary_csv}`")
    if vintage_csv is not None and vintage_csv.exists():
        lines.append(f"- `{vintage_csv}`")
    lines.append("")

    lines.append("## Bottom Line")
    lines.append("")
    lines.append(
        f"- Primary term-level metrics: `{len(term_rows)}` "
        f"(`confirmatory={term_counts['confirmatory']}`, `supportive={term_counts['supportive']}`, "
        f"`exploratory={term_counts['exploratory']}`, `missing={term_counts['missing']}`)."
    )
    lines.append(
        f"- Directional split among primary term metrics (`D-R` effect): "
        f"`D > R: {n_pos}`, `R > D: {n_neg}`, `tie: {n_tie}`."
    )
    if term_counts["confirmatory"] + term_counts["supportive"] == 0:
        lines.append("- Claim-grade read: no primary metric clears confirmatory/supportive publication tier under current strict settings.")
    else:
        lines.append("- Claim-grade read: at least one primary metric is confirmatory/supportive under current strict publication tiers.")
    if vintage_obs_end_max:
        lines.append(
            f"- Data recency (FRED-backed primary metrics): observations through `{vintage_obs_end_max}` "
            f"(min across series `{vintage_obs_end_min}`), latest realtime end `{vintage_rt_max}`, latest raw snapshot `{vintage_snap_max}`."
        )
    lines.append("")

    lines.append("## Primary Metric Grid")
    lines.append("")
    lines.append("| Family | Metric | D-R effect | Direction | q (strict) | Tier (publication) | n |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in term_rows_sorted:
        label = (row.get("metric_label") or row.get("metric_id") or "").replace("|", "\\|")
        family = (row.get("metric_family") or "").strip().replace("|", "\\|")
        eff = _preferred_effect(row)
        q = _preferred_q(row)
        tier = _best_claim_tier(row)
        n = _preferred_n(row)
        lines.append(
            "| {family} | {label} | {effect} | {direction} | {q} | {tier} | {n} |".format(
                family=family,
                label=label,
                effect=_fmt(eff, 3),
                direction=_dir_label(eff),
                q=_fmt(q, 4),
                tier=tier,
                n=n,
            )
        )
    lines.append("")

    lines.append("## Congress Control Diagnostic (Unified vs Divided)")
    lines.append("")
    lines.append(
        f"- Primary congress-binary rows (P party = all): `{len(congress_claim_rows)}` "
        f"(`confirmatory={congress_counts['confirmatory']}`, `supportive={congress_counts['supportive']}`, "
        f"`exploratory={congress_counts['exploratory']}`, `missing={congress_counts['missing']}`)."
    )
    if congress_diag_rows:
        lines.append(
            f"- Small-cell flagged rows in congress binary diagnostic: `{congress_small_cell}/{len(congress_diag_rows)}`."
        )
    lines.append("- Interpretation: treat this as a confounding robustness check, not a causal decomposition.")
    lines.append("")
    lines.append("| Metric | U-D effect | q | p | Small-cell? | Tier |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    diag_sorted = sorted(
        congress_diag_rows,
        key=lambda r: (
            _parse_float((r.get("q_bh_fdr") or "").strip()) if _parse_float((r.get("q_bh_fdr") or "").strip()) is not None else 1e9,
            (r.get("metric_id") or "").strip(),
        ),
    )
    if diag_sorted:
        for row in diag_sorted:
            lines.append(
                "| {label} | {eff} | {q} | {p} | {small} | {tier} |".format(
                    label=(row.get("metric_label") or row.get("metric_id") or "").replace("|", "\\|"),
                    eff=_fmt(_parse_float((row.get("observed_diff_unified_minus_divided") or "").strip()), 3),
                    q=_fmt(_parse_float((row.get("q_bh_fdr") or "").strip()), 4),
                    p=_fmt(_parse_float((row.get("p_two_sided") or "").strip()), 4),
                    small=("yes" if (row.get("small_cell_warning") or "").strip() == "1" else "no"),
                    tier=(row.get("evidence_tier") or "").strip(),
                )
            )
    else:
        lines.append("| (no rows) |  |  |  |  |  |")
    lines.append("")

    lines.append("## What This Is For")
    lines.append("")
    lines.append("- Use this file as the first-stop publication artifact for the current pipeline run.")
    lines.append("- Use `reports/scoreboard.md` for detailed tables and `reports/claims_table_v1.csv` for machine-readable tiers.")
    lines.append("- Keep headline claims anchored to publication tiers (strict + gating), not raw p-values.")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_md.with_suffix(out_md.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(out_md)
