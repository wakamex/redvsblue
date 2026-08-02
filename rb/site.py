from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from rb.scoreboard import _load_party_summary, _load_term_randomization, _parse_float
from rb.spec import load_spec
from rb.util import write_text_atomic


_FREQUENCY_LABELS = {
    "A": "Annual",
    "D": "Daily",
    "M": "Monthly",
    "Q": "Quarterly",
}


def _load_metric_sources(spec_path: Path) -> dict[str, dict[str, str]]:
    spec = load_spec(spec_path)
    series_registry = spec.get("series") or {}
    source_registry = spec.get("sources") or {}
    metric_sources: dict[str, dict[str, str]] = {}

    for metric in spec.get("metrics") or []:
        metric_id = str(metric.get("id") or "").strip()
        inputs = metric.get("inputs") or {}
        input_id = inputs.get("series") or inputs.get("table")
        if not metric_id or not input_id:
            continue

        series = series_registry.get(input_id)
        if series is None:
            raise ValueError(f"Metric {metric_id!r} references unknown input {input_id!r}")
        source_id = series.get("source")
        source = source_registry.get(source_id) or {}
        provenance = {
            **(source.get("provenance") or {}),
            **(series.get("provenance") or {}),
        }

        required = ("label", "publisher", "program", "access_provider", "url")
        missing = [field for field in required if not provenance.get(field)]
        if missing:
            raise ValueError(
                f"Input {input_id!r} is missing provenance fields: {', '.join(missing)}"
            )

        url = str(provenance["url"]).format(**series)
        access_id = (
            provenance.get("access_id")
            or series.get("series_id")
            or series.get("dataset")
            or input_id
        )
        frequency_code = str(series.get("frequency") or "")
        frequency = _FREQUENCY_LABELS.get(frequency_code, frequency_code)
        metric_sources[metric_id] = {
            "label": str(provenance["label"]),
            "publisher": str(provenance["publisher"]),
            "program": str(provenance["program"]),
            "access_provider": str(provenance["access_provider"]),
            "access_id": str(access_id),
            "url": url,
            "frequency": frequency,
            "units": str(series.get("units") or ""),
        }
        for optional in ("source_id", "note"):
            if provenance.get(optional):
                metric_sources[metric_id][optional] = str(provenance[optional])

    return metric_sources


def _load_term_details(
    term_metrics_csv: Path,
) -> dict[str, list[dict]]:
    """Load per-term values grouped by metric_id.

    Returns {metric_id: [{president, party, term_start, term_end, value}, ...]}
    sorted chronologically within each metric.
    """
    groups: dict[str, list[dict]] = {}
    with term_metrics_csv.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            mid = (row.get("metric_id") or "").strip()
            party = (row.get("party_abbrev") or "").strip()
            error = (row.get("error") or "").strip()
            if not mid or party not in ("D", "R") or error:
                continue
            val = _parse_float(row.get("value") or "")
            if val is None:
                continue
            groups.setdefault(mid, []).append({
                "president": (row.get("president") or "").strip(),
                "party": party,
                "term_start": (row.get("term_start") or "").strip(),
                "term_end": (row.get("term_end") or "").strip(),
                "value": round(val, 4),
            })
    for terms in groups.values():
        terms.sort(key=lambda t: t["term_start"])
    return groups


def write_site_json(
    *,
    party_summary_csv: Path,
    output_dir: Path = Path("site"),
    term_randomization_csv: Path | None = Path("reports/permutation_party_term_v1.csv"),
    term_metrics_csv: Path | None = Path("reports/term_metrics_v1.csv"),
    spec_path: Path | None = Path("spec/metrics_v1.yaml"),
) -> None:
    party = _load_party_summary(party_summary_csv)
    metric_sources = _load_metric_sources(spec_path) if spec_path is not None else {}

    term_details: dict[str, list[dict]] = {}
    if term_metrics_csv is not None and term_metrics_csv.exists():
        term_details = _load_term_details(term_metrics_csv)

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
        source = metric_sources.get(mid)
        if spec_path is not None and source is None:
            raise ValueError(f"Metric {mid!r} has no source provenance in {spec_path}")

        d_mean = d.mean if d else None
        r_mean = r.mean if r else None
        diff = round(d_mean - r_mean, 6) if (d_mean is not None and r_mean is not None) else None

        tr = term_rand.get(mid, {})
        p_val = _parse_float(tr.get("p_two_sided") or "")
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
            "source": source,
            "d_mean": _round_or_none(d_mean),
            "r_mean": _round_or_none(r_mean),
            "diff": _round_or_none(diff),
            "n_d": d.n_terms if d else None,
            "n_r": r.n_terms if r else None,
            "p": _round_or_none(p_val),
            "q": _round_or_none(q_val),
            "ci_low": _round_or_none(ci_low),
            "ci_high": _round_or_none(ci_high),
            "tier": tier,
            "terms": term_details.get(mid, []),
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
