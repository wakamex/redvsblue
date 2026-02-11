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


def write_publication_narrative_template(
    *,
    claims_table_csv: Path,
    inference_table_csv: Path,
    out_md: Path,
) -> None:
    if not claims_table_csv.exists():
        raise FileNotFoundError(f"Missing claims table CSV: {claims_table_csv}")
    if not inference_table_csv.exists():
        raise FileNotFoundError(f"Missing inference table CSV: {inference_table_csv}")

    claims_by_metric: dict[str, dict[str, str]] = {}
    within_claim_rows: list[dict[str, str]] = []
    with claims_table_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            analysis = (row.get("analysis") or "").strip()
            if analysis == "within_unified":
                within_claim_rows.append(row)
                continue
            if analysis != "term_party":
                continue
            mid = (row.get("metric_id") or "").strip()
            if not mid:
                continue
            claims_by_metric[mid] = row

    merged_rows: list[dict[str, str]] = []
    with inference_table_csv.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for inf in rdr:
            mid = (inf.get("metric_id") or "").strip()
            if not mid:
                continue
            claim = claims_by_metric.get(mid, {})
            tier = _best_claim_tier(claim)
            merged_rows.append(
                {
                    "metric_id": mid,
                    "metric_family": (inf.get("metric_family") or "").strip(),
                    "metric_label": (inf.get("metric_label") or "").strip(),
                    "tier": tier,
                    "q_strict": (claim.get("q_strict") or "").strip(),
                    "hac_p": (inf.get("hac_nw_p_two_sided_norm") or "").strip(),
                    "effect": (inf.get("effect_d_minus_r") or "").strip(),
                    "direction": (claim.get("direction") or "").strip(),
                    "rough_mde": (inf.get("rough_mde_abs_alpha005_power080") or "").strip(),
                    "effect_over_mde": (inf.get("rough_effect_over_mde_abs") or "").strip(),
                }
            )

    merged_rows.sort(
        key=lambda r: (
            -_tier_rank(r.get("tier") or ""),
            _parse_float(r.get("q_strict") or "") if _parse_float(r.get("q_strict") or "") is not None else 1e9,
            r.get("metric_id") or "",
        )
    )

    by_tier: dict[str, list[dict[str, str]]] = {"confirmatory": [], "supportive": [], "exploratory": [], "missing": []}
    for r in merged_rows:
        t = (r.get("tier") or "").strip()
        if t not in by_tier:
            t = "missing"
        by_tier[t].append(r)
    n_primary = len(merged_rows)
    n_confirm = len(by_tier["confirmatory"])
    n_support = len(by_tier["supportive"])
    n_expl = len(by_tier["exploratory"])
    n_missing = len(by_tier["missing"])

    within_rows: list[dict[str, str]] = []
    for row in within_claim_rows:
        eff = (row.get("effect_strict") or "").strip() or (row.get("effect_baseline") or "").strip()
        q = (row.get("q_strict") or "").strip() or (row.get("q_baseline") or "").strip()
        mde = (row.get("mde_strict") or "").strip() or (row.get("mde_baseline") or "").strip()
        ratio = (row.get("effect_over_mde_strict") or "").strip() or (row.get("effect_over_mde_baseline") or "").strip()
        n = (row.get("n_strict") or "").strip() or (row.get("n_baseline") or "").strip()
        within_rows.append(
            {
                "metric_id": (row.get("metric_id") or "").strip(),
                "metric_family": (row.get("metric_family") or "").strip(),
                "pres_party": (row.get("pres_party") or "").strip(),
                "tier": _best_claim_tier(row),
                "effect": eff,
                "q": q,
                "mde": mde,
                "effect_over_mde": ratio,
                "n": n,
            }
        )
    within_rows.sort(
        key=lambda r: (
            -_tier_rank(r.get("tier") or ""),
            _parse_float(r.get("q") or "") if _parse_float(r.get("q") or "") is not None else 1e9,
            r.get("metric_id") or "",
            r.get("pres_party") or "",
        )
    )

    lines: list[str] = []
    lines.append("# Publication Narrative Template")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}")
    lines.append("")
    lines.append("Inputs:")
    lines.append(f"- Claims table: `{claims_table_csv}`")
    lines.append(f"- Inference table: `{inference_table_csv}`")
    lines.append("")
    lines.append("Use this as a fill-in template; keep numeric values copied directly from generated tables.")
    lines.append("")
    lines.append("## Headline Summary (Fill In)")
    lines.append("")
    lines.append(f"- Primary metrics evaluated: `{n_primary}`")
    lines.append(f"- Confirmatory metrics (publication tier): `{n_confirm}`")
    lines.append(f"- Supportive metrics (publication tier): `{n_support}`")
    lines.append(f"- Exploratory metrics (publication tier): `{n_expl}`")
    if n_missing:
        lines.append(f"- Primary metrics with missing tier assignment: `{n_missing}`")
    lines.append("- Main claim sentence: `[INSERT ONE SENTENCE BASED ONLY ON CONFIRMATORY/SUPPORTIVE ROWS]`")
    lines.append("")
    lines.append("## Confirmatory Rows")
    lines.append("")
    if by_tier["confirmatory"]:
        for r in by_tier["confirmatory"]:
            lines.append(
                "- `{metric_id}` ({metric_family}): effect={effect}, direction={direction}, "
                "q_strict={q_strict}, HAC p={hac_p}, |effect|/MDE={effect_over_mde}".format(**r)
            )
    else:
        lines.append("- None under current strict/publication settings.")
    lines.append("")
    lines.append("## Supportive Rows")
    lines.append("")
    if by_tier["supportive"]:
        for r in by_tier["supportive"]:
            lines.append(
                "- `{metric_id}` ({metric_family}): effect={effect}, direction={direction}, "
                "q_strict={q_strict}, HAC p={hac_p}, |effect|/MDE={effect_over_mde}".format(**r)
            )
    else:
        lines.append("- None under current strict/publication settings.")
    lines.append("")
    lines.append("## Exploratory / Non-Claim Rows")
    lines.append("")
    if by_tier["exploratory"]:
        for r in by_tier["exploratory"]:
            lines.append(
                "- `{metric_id}` ({metric_family}): effect={effect}, q_strict={q_strict}, HAC p={hac_p}, rough MDE={rough_mde}".format(
                    **r
                )
            )
    else:
        lines.append("- None.")
    if by_tier["missing"]:
        lines.append("")
        lines.append("Rows with missing tier assignment:")
        for r in by_tier["missing"]:
            lines.append("- `{metric_id}` ({metric_family})".format(**r))
    lines.append("")
    lines.append("## Within-President Diagnostics (Publication Tier)")
    lines.append("")
    if within_rows:
        lines.append(f"- Rows available: `{len(within_rows)}`")
        for r in within_rows:
            lines.append(
                "- `{metric_id}` ({metric_family}, P={pres_party}): tier={tier}, "
                "effect={effect}, q={q}, n={n}, rough MDE={mde}, |effect|/MDE={effect_over_mde}".format(**r)
            )
    else:
        lines.append("- None (claims table did not include `analysis=within_unified` rows).")
    lines.append("")
    lines.append("## Standard Caveats (Keep)")
    lines.append("")
    lines.append("- Results are associational, not causal identification.")
    lines.append("- Publication claims should rely on strict profile + publication-tier gating, not baseline-only tiers.")
    lines.append("- Small-cell metrics and high MDE ratios imply low power; treat those as exploratory diagnostics.")
    lines.append("- Multiple transforms are correlated; family-level interpretation should be preferred over raw metric counts.")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_md.with_suffix(out_md.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(out_md)
