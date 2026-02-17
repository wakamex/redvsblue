from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rb.scoreboard import _load_party_summary, _load_term_randomization, _parse_float
from rb.util import write_text_atomic


def write_site_json(
    *,
    party_summary_csv: Path,
    output_dir: Path = Path("site"),
    term_randomization_csv: Path | None = Path("reports/permutation_party_term_v1.csv"),
) -> None:
    party = _load_party_summary(party_summary_csv)

    metric_ids: list[str] = []
    seen: set[str] = set()
    for _p, mid in party:
        if mid not in seen:
            seen.add(mid)
            metric_ids.append(mid)

    term_rand: dict[str, dict[str, str]] = {}
    if term_randomization_csv is not None and term_randomization_csv.exists():
        term_rand = _load_term_randomization(term_randomization_csv)

    rows: list[tuple[float, dict]] = []
    for mid in metric_ids:
        d = party.get(("D", mid))
        r = party.get(("R", mid))
        full_label = d.label if d else (r.label if r else mid)
        paren_idx = full_label.find("(")
        label = full_label[:paren_idx].strip() if paren_idx > 0 else full_label
        family = d.family if d else (r.family if r else "")
        agg = d.agg_kind if d else (r.agg_kind if r else "")
        units = d.units if d and d.units else (r.units if r and r.units else "")

        d_mean = d.mean if d else None
        r_mean = r.mean if r else None
        diff = round(d_mean - r_mean, 6) if (d_mean is not None and r_mean is not None) else None

        tr = term_rand.get(mid, {})
        q_val = _parse_float(tr.get("q_bh_fdr") or "")
        ci_low = _parse_float(tr.get("bootstrap_ci95_low") or "")
        ci_high = _parse_float(tr.get("bootstrap_ci95_high") or "")

        if q_val is not None and q_val < 0.05:
            tier = "confirmatory"
        elif q_val is not None and q_val < 0.10:
            tier = "supportive"
        else:
            tier = "exploratory"

        row = {
            "metric": label,
            "family": family,
            "agg": agg,
            "units": units,
            "d_mean": _round_or_none(d_mean),
            "r_mean": _round_or_none(r_mean),
            "diff": _round_or_none(diff),
            "n_d": d.n_terms if d else None,
            "n_r": r.n_terms if r else None,
            "q": _round_or_none(q_val),
            "ci_low": _round_or_none(ci_low),
            "ci_high": _round_or_none(ci_high),
            "tier": tier,
        }
        rows.append((q_val if q_val is not None else 1e9, row))

    rows.sort(key=lambda t: t[0])

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": [row for _, row in rows],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "data.json"
    write_text_atomic(out_path, json.dumps(payload, indent=2) + "\n")


def _round_or_none(v: float | None, digits: int = 6) -> float | None:
    if v is None:
        return None
    return round(v, digits)
