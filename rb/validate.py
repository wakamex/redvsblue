from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from rb.congress_control import _congress_end_date, _congress_start_date
from rb.spec import load_spec


@dataclass(frozen=True)
class ValidationIssue:
    level: str  # "ERROR" or "WARN"
    message: str


def _parse_date(s: str) -> date:
    return date.fromisoformat((s or "").strip()[:10])


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


def validate_presidents_csv(path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not path.exists():
        return [ValidationIssue("ERROR", f"missing presidents CSV: {path}")]

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            rows.append({k: (v or "") for k, v in r.items()})

    if not rows:
        return [ValidationIssue("ERROR", f"empty presidents CSV: {path}")]

    seen_ids: set[str] = set()
    terms: list[tuple[date, date, str]] = []
    for r in rows:
        term_id = (r.get("term_id") or "").strip()
        if not term_id:
            issues.append(ValidationIssue("ERROR", "presidents.csv: blank term_id"))
            continue
        if term_id in seen_ids:
            issues.append(ValidationIssue("ERROR", f"presidents.csv: duplicate term_id={term_id!r}"))
        seen_ids.add(term_id)

        try:
            s = _parse_date(r.get("term_start") or "")
            e = _parse_date(r.get("term_end") or "")
        except Exception:
            issues.append(ValidationIssue("ERROR", f"presidents.csv: invalid date for term_id={term_id!r}"))
            continue

        if e <= s:
            issues.append(ValidationIssue("ERROR", f"presidents.csv: non-positive window for term_id={term_id!r}: {s}..{e}"))

        party = (r.get("party_abbrev") or "").strip()
        if party not in {"D", "R", "Other"}:
            issues.append(ValidationIssue("WARN", f"presidents.csv: unexpected party_abbrev={party!r} for term_id={term_id!r}"))

        terms.append((s, e, term_id))

    # Overlap check (should not overlap for a single timeline).
    terms_sorted = sorted(terms, key=lambda t: (t[0], t[1], t[2]))
    for (s0, e0, id0), (s1, e1, id1) in zip(terms_sorted, terms_sorted[1:], strict=False):
        if s1 < e0:
            issues.append(ValidationIssue("ERROR", f"presidents.csv: overlapping terms: {id0} ({s0}..{e0}) overlaps {id1} ({s1}..{e1})"))
        if s1 > e0:
            issues.append(ValidationIssue("WARN", f"presidents.csv: gap between terms: {id0} ends {e0} then {id1} starts {s1}"))

    return issues


def validate_congress_control_csv(path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not path.exists():
        return [ValidationIssue("ERROR", f"missing congress control CSV: {path}")]

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            rows.append({k: (v or "") for k, v in r.items()})

    if not rows:
        return [ValidationIssue("ERROR", f"empty congress control CSV: {path}")]

    by_cong: dict[int, list[tuple[date, date, dict[str, str]]]] = {}
    for r in rows:
        c = _parse_int(r.get("congress") or "")
        if c is None:
            issues.append(ValidationIssue("ERROR", f"congress_control.csv: invalid congress={r.get('congress')!r}"))
            continue
        try:
            s = _parse_date(r.get("start_date") or "")
            e = _parse_date(r.get("end_date") or "")
        except Exception:
            issues.append(ValidationIssue("ERROR", f"congress_control.csv: invalid date for congress={c}"))
            continue
        if e <= s:
            issues.append(ValidationIssue("ERROR", f"congress_control.csv: non-positive window for congress={c}: {s}..{e}"))
        if not (r.get("house_majority") or "").strip():
            issues.append(ValidationIssue("ERROR", f"congress_control.csv: blank house_majority for congress={c} {s}..{e}"))
        if not (r.get("senate_majority") or "").strip():
            issues.append(ValidationIssue("ERROR", f"congress_control.csv: blank senate_majority for congress={c} {s}..{e}"))
        by_cong.setdefault(c, []).append((s, e, r))

    for cong, spans in sorted(by_cong.items()):
        spans_sorted = sorted(spans, key=lambda t: (t[0], t[1]))
        s_min = spans_sorted[0][0]
        e_max = max(e for _, e, _ in spans_sorted)

        # Congresses are two-year windows.
        start_year = s_min.year
        exp_s = _congress_start_date(cong, start_year)
        exp_e = _congress_end_date(cong, start_year + 2)
        if s_min != exp_s:
            issues.append(ValidationIssue("WARN", f"congress_control.csv: congress={cong} start_date={s_min} != expected {exp_s}"))
        if e_max != exp_e:
            issues.append(ValidationIssue("WARN", f"congress_control.csv: congress={cong} end_date={e_max} != expected {exp_e}"))

        # Validate no overlaps/gaps within a Congress (Senate periods).
        for (s0, e0, _), (s1, e1, _) in zip(spans_sorted, spans_sorted[1:], strict=False):
            if s1 < e0:
                issues.append(ValidationIssue("ERROR", f"congress_control.csv: congress={cong} overlapping periods: {s0}..{e0} overlaps {s1}..{e1}"))
            if s1 > e0:
                issues.append(ValidationIssue("WARN", f"congress_control.csv: congress={cong} gap between periods: {e0}..{s1}"))

    return issues


def validate_term_metrics_csv(path: Path, *, expected_metrics: int | None = None, expected_terms: int | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not path.exists():
        return [ValidationIssue("ERROR", f"missing term metrics CSV: {path}")]

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            rows.append({k: (v or "") for k, v in r.items()})

    if not rows:
        return [ValidationIssue("ERROR", f"empty term metrics CSV: {path}")]

    seen: set[tuple[str, str]] = set()
    dup = 0
    err_cnt = 0
    err_kinds: dict[str, int] = {}
    err_by_metric: dict[str, int] = {}
    metrics: set[str] = set()
    terms: set[str] = set()

    for r in rows:
        metric_id = (r.get("metric_id") or "").strip()
        term_id = (r.get("term_id") or "").strip()
        if metric_id:
            metrics.add(metric_id)
        if term_id:
            terms.add(term_id)
        key = (metric_id, term_id)
        if key in seen:
            dup += 1
        seen.add(key)

        if (r.get("error") or "").strip():
            err_cnt += 1
            err = (r.get("error") or "").strip()
            err_kinds[err] = err_kinds.get(err, 0) + 1
            err_by_metric[metric_id] = err_by_metric.get(metric_id, 0) + 1

        # Quick numeric sanity (value is allowed to be blank if error).
        v = (r.get("value") or "").strip()
        if v and _parse_float(v) is None:
            issues.append(ValidationIssue("ERROR", f"term_metrics: non-numeric value={v!r} metric_id={metric_id!r} term_id={term_id!r}"))

    if dup:
        issues.append(ValidationIssue("ERROR", f"term_metrics: duplicate (metric_id,term_id) rows: {dup}"))

    if expected_metrics is not None and expected_terms is not None:
        exp_rows = expected_metrics * expected_terms
        if len(rows) != exp_rows:
            issues.append(ValidationIssue("ERROR", f"term_metrics: row_count={len(rows)} != expected {exp_rows} (= {expected_metrics} metrics * {expected_terms} terms)"))

    if err_cnt:
        top = sorted(err_kinds.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        top_metrics = sorted(err_by_metric.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
        issues.append(
            ValidationIssue(
                "WARN",
                "term_metrics: "
                f"{err_cnt}/{len(rows)} rows have errors; top_errors={top}; top_metrics={top_metrics}. "
                "This is usually expected when presidents.csv spans eras earlier than a series' data coverage.",
            )
        )

    # If the file exists at all, it should cover at least D and R terms for D/R comparisons.
    if "D" not in {(r.get('party_abbrev') or '').strip() for r in rows}:
        issues.append(ValidationIssue("WARN", "term_metrics: no party_abbrev='D' rows found"))
    if "R" not in {(r.get('party_abbrev') or '').strip() for r in rows}:
        issues.append(ValidationIssue("WARN", "term_metrics: no party_abbrev='R' rows found"))

    return issues


def validate_party_summary_csv(path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not path.exists():
        return [ValidationIssue("ERROR", f"missing party summary CSV: {path}")]

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for r in rdr:
            rows.append({k: (v or "") for k, v in r.items()})

    if not rows:
        return [ValidationIssue("ERROR", f"empty party summary CSV: {path}")]

    for r in rows:
        metric_id = (r.get("metric_id") or "").strip()
        party = (r.get("party_abbrev") or "").strip()
        n_terms = (r.get("n_terms") or "").strip()
        if n_terms and _parse_int(n_terms) is None:
            issues.append(ValidationIssue("ERROR", f"party_summary: bad n_terms={n_terms!r} metric_id={metric_id!r} party={party!r}"))
        for k in ("mean", "median"):
            v = (r.get(k) or "").strip()
            if v and _parse_float(v) is None:
                issues.append(ValidationIssue("ERROR", f"party_summary: non-numeric {k}={v!r} metric_id={metric_id!r} party={party!r}"))

    return issues


def validate_metric_spec_symmetry(spec_path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not spec_path.exists():
        return [ValidationIssue("ERROR", f"missing metric spec YAML: {spec_path}")]

    spec = load_spec(spec_path)
    metrics_cfg: list[dict] = spec.get("metrics") or []
    series_cfg: dict[str, dict] = spec.get("series") or {}

    by_input: dict[tuple[str, str], list[dict]] = {}
    for m in metrics_cfg:
        inputs = m.get("inputs") or {}
        if "series" in inputs:
            k = ("series", str(inputs["series"]))
        elif "table" in inputs:
            k = ("table", str(inputs["table"]))
        else:
            continue
        by_input.setdefault(k, []).append(m)

    for (kind, key), ms in sorted(by_input.items()):
        agg_kinds = {
            str(((m.get("term_aggregation") or {}).get("kind") or "")).strip()
            for m in ms
        }
        if "end_minus_start" in agg_kinds and "end_minus_start_per_year" not in agg_kinds:
            issues.append(
                ValidationIssue(
                    "WARN",
                    f"metrics spec symmetry: {kind}={key!r} has end_minus_start but missing end_minus_start_per_year.",
                )
            )
        if "end_minus_start_per_year" in agg_kinds and "end_minus_start" not in agg_kinds:
            issues.append(
                ValidationIssue(
                    "WARN",
                    f"metrics spec symmetry: {kind}={key!r} has end_minus_start_per_year but missing end_minus_start.",
                )
            )
        if "pct_change_from_levels" in agg_kinds and "cagr_from_levels" not in agg_kinds:
            issues.append(
                ValidationIssue(
                    "WARN",
                    f"metrics spec symmetry: {kind}={key!r} has pct_change_from_levels but missing cagr_from_levels.",
                )
            )
        if "cagr_from_levels" in agg_kinds and "pct_change_from_levels" not in agg_kinds:
            issues.append(
                ValidationIssue(
                    "WARN",
                    f"metrics spec symmetry: {kind}={key!r} has cagr_from_levels but missing pct_change_from_levels.",
                )
            )

    # Inflation symmetry check for seasonally-adjusted index series:
    # if we define a YoY mean metric, also require a MoM annualized log-diff mean metric.
    for series_key, cfg in sorted(series_cfg.items()):
        if str((cfg or {}).get("seasonal_adjustment") or "").strip() != "SA":
            continue
        if str((cfg or {}).get("units") or "").strip().lower() != "index":
            continue
        ms = by_input.get(("series", series_key), [])
        if not ms:
            continue

        has_yoy_mean = False
        has_mom_ann_mean = False
        for m in ms:
            pt = m.get("period_transform") or {}
            agg = m.get("term_aggregation") or {}
            pt_kind = str(pt.get("kind") or "").strip()
            agg_kind = str(agg.get("kind") or "").strip()
            if pt_kind == "pct_change" and int(pt.get("lag") or 0) == 12 and agg_kind == "mean":
                has_yoy_mean = True
            if (
                pt_kind == "growth_rate"
                and str(pt.get("method") or "logdiff").strip() == "logdiff"
                and int(pt.get("lag") or 0) == 1
                and int(pt.get("annualize_periods_per_year") or 0) == 12
                and agg_kind == "mean"
            ):
                has_mom_ann_mean = True

        if has_yoy_mean and not has_mom_ann_mean:
            issues.append(
                ValidationIssue(
                    "WARN",
                    f"metrics spec symmetry: series={series_key!r} has YoY mean inflation but missing MoM annualized log-diff mean.",
                )
            )

    return issues


def _format_issues(issues: Iterable[ValidationIssue]) -> str:
    lines: list[str] = []
    for it in issues:
        lines.append(f"{it.level}: {it.message}")
    return "\n".join(lines)


def validate_all(
    *,
    spec_path: Path,
    presidents_csv: Path,
    congress_control_csv: Path | None,
    term_metrics_csv: Path | None,
    party_summary_csv: Path | None,
) -> tuple[int, str]:
    issues: list[ValidationIssue] = []

    issues.extend(validate_metric_spec_symmetry(spec_path))
    issues.extend(validate_presidents_csv(presidents_csv))

    if congress_control_csv is not None:
        issues.extend(validate_congress_control_csv(congress_control_csv))

    # If we have presidents.csv, we can derive expected term count for report sanity checks.
    n_terms: int | None = None
    if presidents_csv.exists():
        with presidents_csv.open("r", encoding="utf-8", newline="") as handle:
            n_terms = sum(1 for _ in csv.DictReader(handle))

    if term_metrics_csv is not None:
        issues.extend(validate_term_metrics_csv(term_metrics_csv, expected_terms=n_terms, expected_metrics=None))

    if party_summary_csv is not None:
        issues.extend(validate_party_summary_csv(party_summary_csv))

    n_err = sum(1 for it in issues if it.level == "ERROR")
    n_warn = sum(1 for it in issues if it.level == "WARN")
    status = 0 if n_err == 0 else 1
    header = f"validate: {n_err} error(s), {n_warn} warning(s)"
    body = _format_issues(issues)
    out = header if not body else (header + "\n" + body)
    return status, out
