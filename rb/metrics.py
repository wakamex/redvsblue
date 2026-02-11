from __future__ import annotations

import ast
import csv
import math
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from rb.presidents import PresidentTerm, load_presidents_csv
from rb.spec import load_spec
from rb.util import write_text_atomic


@dataclass(frozen=True)
class TimeSeries:
    # Dates are sorted ascending; values may be None for missing.
    dates: list[date]
    values: list[float | None]

    def __post_init__(self) -> None:
        if len(self.dates) != len(self.values):
            raise ValueError("dates/values length mismatch")


def _parse_date(s: str) -> date:
    return date.fromisoformat(s.strip()[:10])


def _parse_float(s: str) -> float | None:
    txt = (s or "").strip()
    if not txt or txt in {".", "NA", "NaN", "nan"}:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def _load_csv_timeseries(path: Path, *, date_col: str, value_col: str) -> TimeSeries:
    if not path.exists():
        raise FileNotFoundError(f"Missing derived data: {path}")
    dates: list[date] = []
    values: list[float | None] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        for row in rdr:
            ds = (row.get(date_col) or "").strip()
            if not ds:
                continue
            dates.append(_parse_date(ds))
            values.append(_parse_float(row.get(value_col) or ""))
    # Enforce sorted input (most upstream data is sorted already).
    if dates != sorted(dates):
        pairs = sorted(zip(dates, values), key=lambda t: t[0])
        dates = [d for d, _ in pairs]
        values = [v for _, v in pairs]
    return TimeSeries(dates=dates, values=values)


def _load_csv_table(path: Path) -> tuple[list[date], list[dict[str, float | None]]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing derived data: {path}")
    rows: list[dict[str, float | None]] = []
    dates: list[date] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rdr = csv.DictReader(handle)
        if not rdr.fieldnames:
            raise ValueError(f"Empty CSV: {path}")
        for row in rdr:
            ds = (row.get("date") or "").strip()
            if not ds:
                continue
            d = _parse_date(ds)
            out: dict[str, float | None] = {}
            for k, v in row.items():
                if k == "date":
                    continue
                out[k] = _parse_float(v or "")
            dates.append(d)
            rows.append(out)
    if dates != sorted(dates):
        pairs = sorted(zip(dates, rows), key=lambda t: t[0])
        dates = [d for d, _ in pairs]
        rows = [r for _, r in pairs]
    return dates, rows


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def _month_period(d: date) -> tuple[date, date]:
    start = _month_start(d)
    end = _add_months(start, 1)
    return start, end


def _quarter_period(d: date) -> tuple[date, date]:
    q0 = ((d.month - 1) // 3) * 3 + 1
    start = date(d.year, q0, 1)
    end = _add_months(start, 3)
    return start, end


def _year_period(d: date) -> tuple[date, date]:
    start = date(d.year, 1, 1)
    end = date(d.year + 1, 1, 1)
    return start, end


def _us_fiscal_year_period(label_year: int, *, start_month: int, start_day: int) -> tuple[date, date]:
    # Fiscal year labeled by its end-year. Example: FY2020 = [2019-10-01, 2020-10-01).
    start = date(label_year - 1, start_month, start_day)
    end = date(label_year, start_month, start_day)
    return start, end


def _term_for_day(terms: list[PresidentTerm], d: date) -> PresidentTerm | None:
    # Terms are non-overlapping; linear scan is fine (~60 terms).
    for t in terms:
        if t.term_start <= d < t.term_end:
            return t
    return None


def _overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    s = max(a_start, b_start)
    e = min(a_end, b_end)
    if e <= s:
        return 0
    return (e - s).days


def _assign_term_for_period(
    terms: list[PresidentTerm],
    period_start: date,
    period_end: date,
    *,
    tie_breaker: str,
) -> PresidentTerm | None:
    best: PresidentTerm | None = None
    best_days = -1
    tied: list[PresidentTerm] = []
    for t in terms:
        days = _overlap_days(period_start, period_end, t.term_start, t.term_end)
        if days <= 0:
            continue
        if days > best_days:
            best_days = days
            best = t
            tied = [t]
        elif days == best_days:
            tied.append(t)

    if not tied:
        return None
    if len(tied) == 1:
        return tied[0]

    if tie_breaker == "president_on_period_end":
        day = period_end - timedelta(days=1)
        return _term_for_day(terms, day)

    # Fallback: stable choice.
    return sorted(tied, key=lambda x: x.term_start)[-1]


def _attrib_series_to_terms(
    terms: list[PresidentTerm],
    ts: TimeSeries,
    *,
    freq: str,
    period_kind: str | None,
    fiscal_year_start_month: int | None,
    fiscal_year_start_day: int | None,
    period_rule: str,
    tie_breaker: str,
) -> dict[str, list[tuple[date, float | None]]]:
    by_term: dict[str, list[tuple[date, float | None]]] = {}

    if freq == "D" and (period_kind is None or period_kind == "instant"):
        for d, v in zip(ts.dates, ts.values):
            t = _term_for_day(terms, d)
            if not t:
                continue
            by_term.setdefault(t.term_id, []).append((d, v))
        return by_term

    # Period-valued attribution.
    if period_rule != "majority_of_days_in_period":
        raise ValueError(f"Unsupported period attribution rule: {period_rule!r}")

    for d, v in zip(ts.dates, ts.values):
        if freq == "M":
            p_start, p_end = _month_period(d)
        elif freq == "Q":
            p_start, p_end = _quarter_period(d)
        elif freq == "A":
            if period_kind == "us_fiscal_year":
                if not (fiscal_year_start_month and fiscal_year_start_day):
                    raise ValueError("Fiscal-year period missing start month/day")
                p_start, p_end = _us_fiscal_year_period(d.year, start_month=fiscal_year_start_month, start_day=fiscal_year_start_day)
            else:
                p_start, p_end = _year_period(d)
        else:
            raise ValueError(f"Unsupported frequency for period attribution: {freq!r}")

        t = _assign_term_for_period(terms, p_start, p_end, tie_breaker=tie_breaker)
        if not t:
            continue
        by_term.setdefault(t.term_id, []).append((d, v))

    return by_term


def _transform_identity(ts: TimeSeries) -> TimeSeries:
    return ts


def _transform_pct_change(ts: TimeSeries, *, lag: int, scale: float) -> TimeSeries:
    out: list[float | None] = [None] * len(ts.values)
    for i in range(len(ts.values)):
        if i < lag:
            continue
        a = ts.values[i]
        b = ts.values[i - lag]
        if a is None or b is None or b == 0:
            continue
        out[i] = scale * (a / b - 1.0)
    return TimeSeries(dates=ts.dates, values=out)


def _transform_growth_rate_logdiff(
    ts: TimeSeries,
    *,
    lag: int,
    annualize_periods_per_year: int,
    scale: float,
) -> TimeSeries:
    out: list[float | None] = [None] * len(ts.values)
    for i in range(len(ts.values)):
        if i < lag:
            continue
        a = ts.values[i]
        b = ts.values[i - lag]
        if a is None or b is None:
            continue
        if a <= 0 or b <= 0:
            continue
        out[i] = scale * float(annualize_periods_per_year) * math.log(a / b)
    return TimeSeries(dates=ts.dates, values=out)


def _transform_indicator_lt(ts: TimeSeries, *, threshold: float) -> TimeSeries:
    out: list[float | None] = [None] * len(ts.values)
    for i, v in enumerate(ts.values):
        if v is None:
            continue
        out[i] = 1.0 if float(v) < threshold else 0.0
    return TimeSeries(dates=ts.dates, values=out)


def _std_sample(xs: list[float]) -> float:
    if len(xs) < 2:
        raise ValueError("need at least 2 observations for std")
    mu = sum(xs) / len(xs)
    var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


def _safe_eval_expr(expr: str, env: dict[str, float | None]) -> float | None:
    """Evaluate a very small arithmetic expression over env values (or None)."""

    def _eval(node: ast.AST) -> float | None:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("unsupported constant")
        if isinstance(node, ast.Name):
            return env.get(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = _eval(node.operand)
            if v is None:
                return None
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a = _eval(node.left)
            b = _eval(node.right)
            if a is None or b is None:
                return None
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b if b != 0 else None
        raise ValueError(f"unsupported expression node: {type(node).__name__}")

    parsed = ast.parse(expr, mode="eval")
    return _eval(parsed)


def _select_last_date_strictly_before(ts: TimeSeries, boundary: date) -> tuple[date, float] | None:
    best_idx: int | None = None
    for i, d in enumerate(ts.dates):
        if d < boundary:
            best_idx = i
        else:
            break
    if best_idx is None:
        return None
    v = ts.values[best_idx]
    if v is None:
        # Walk backwards to find the last non-missing observation.
        j = best_idx
        while j >= 0 and ts.values[j] is None:
            j -= 1
        if j < 0:
            return None
        return ts.dates[j], float(ts.values[j])  # type: ignore[arg-type]
    return ts.dates[best_idx], float(v)


def _fmt_float(v: float | None) -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return ""
    # Keep stable-ish formatting for diffs across runs.
    return f"{v:.6f}"


def _write_csv_atomic(path: Path, *, header: list[str], rows: Iterable[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(path)


def compute_term_metrics(
    *,
    spec_path: Path,
    attribution_path: Path,
    presidents_csv: Path,
    output_terms_csv: Path,
    output_party_csv: Path,
) -> None:
    spec = load_spec(spec_path)
    attribution = load_spec(attribution_path)
    terms = load_presidents_csv(presidents_csv)

    series_cfg: dict[str, dict] = spec.get("series", {})
    metrics_cfg: list[dict] = spec.get("metrics") or []

    # Attribution defaults.
    defaults = attribution.get("defaults") or {}
    year_basis_days = float(defaults.get("year_basis_days") or 365.25)
    period_attr = defaults.get("period_attribution") or {}
    period_rule = str(period_attr.get("rule") or "majority_of_days_in_period")
    tie_breaker = str(period_attr.get("tie_breaker") or "president_on_period_end")
    daily_boundary_rule = defaults.get("daily_boundary_rule") or {}
    daily_start_rule = str(daily_boundary_rule.get("start") or "last_trading_day_strictly_before")
    daily_end_rule = str(daily_boundary_rule.get("end") or "last_trading_day_strictly_before")

    if daily_start_rule != "last_trading_day_strictly_before" or daily_end_rule != "last_trading_day_strictly_before":
        raise ValueError("Only last_trading_day_strictly_before daily boundary rule is implemented in v1")

    freq_sem = attribution.get("frequency_semantics") or {}
    overrides = attribution.get("series_overrides") or {}

    # Load all required base inputs.
    need_series: set[str] = set()
    need_tables: set[str] = set()
    for m in metrics_cfg:
        inputs = m.get("inputs") or {}
        if "series" in inputs:
            need_series.add(str(inputs["series"]))
        if "table" in inputs:
            need_tables.add(str(inputs["table"]))

    series_data: dict[str, TimeSeries] = {}
    table_rows: dict[str, tuple[list[date], list[dict[str, float | None]]]] = {}

    for sk in sorted(need_series):
        cfg = series_cfg.get(sk)
        if not cfg:
            raise KeyError(f"Metric references unknown series key: {sk}")
        src = cfg.get("source")
        freq = str(cfg.get("frequency") or "").strip()
        if not freq:
            raise ValueError(f"Series missing frequency: {sk}")

        if src == "fred":
            series_id = cfg.get("series_id")
            if not series_id:
                raise ValueError(f"FRED series missing series_id: {sk}")
            path = Path("data/derived/fred/observations") / f"{sk}.csv"
            if not path.exists():
                if isinstance(cfg.get("api_params"), dict) and cfg.get("api_params"):
                    raise FileNotFoundError(f"Missing derived data: {path}. Run `rb ingest` for series {sk!r}.")
                # Back-compat fallback to prior series-id keyed filenames.
                path = Path("data/derived/fred/observations") / f"{series_id}.csv"
            series_data[sk] = _load_csv_timeseries(path, date_col="date", value_col="value")
        elif src == "stooq":
            symbol = cfg.get("symbol")
            if not symbol:
                raise ValueError(f"Stooq series missing symbol: {sk}")
            sym = str(symbol).replace("^", "")
            # Prefer per-series derived file so we can reuse one symbol with different filters.
            path = Path("data/derived/stooq") / f"{sk}.csv"
            if not path.exists():
                # Back-compat fallback to the historical symbol-based filename.
                path = Path("data/derived/stooq") / f"{sym}.csv"
            series_data[sk] = _load_csv_timeseries(path, date_col="date", value_col="value")
        else:
            raise ValueError(f"Unsupported series source for compute: {sk} source={src!r}")

    for tk in sorted(need_tables):
        cfg = series_cfg.get(tk)
        if not cfg:
            raise KeyError(f"Metric references unknown table key: {tk}")
        src = cfg.get("source")
        if src != "ken_french_ff_factors":
            raise ValueError(f"Unsupported table source for compute: {tk} source={src!r}")
        path = Path("data/derived/ken_french") / f"{tk}.csv"
        table_rows[tk] = _load_csv_table(path)

    # Helper: extract a column series from a loaded table (including derived columns).
    def _table_column_series(table_key: str, col: str) -> TimeSeries:
        dates, rows = table_rows[table_key]
        cfg = series_cfg.get(table_key) or {}
        derived = cfg.get("derived_columns") or {}

        # Precompute derived columns row-wise as requested.
        out_vals: list[float | None] = []
        for r in rows:
            env = dict(r)
            for dcol, dcfg in derived.items():
                expr = str((dcfg or {}).get("expr") or "")
                if not expr:
                    continue
                try:
                    env[dcol] = _safe_eval_expr(expr, env)
                except Exception:
                    env[dcol] = None
            out_vals.append(env.get(col))
        return TimeSeries(dates=list(dates), values=out_vals)

    # Compute term-level results in long format.
    term_rows: list[dict[str, Any]] = []

    for m in metrics_cfg:
        metric_id = str(m.get("id") or "")
        if not metric_id:
            raise ValueError("Metric missing id")
        family = str(m.get("family") or "")
        label = str(m.get("label") or "")
        primary = bool(m.get("primary"))

        inputs = m.get("inputs") or {}
        if "series" in inputs:
            series_key = str(inputs["series"])
            base_ts = series_data[series_key]
            base_freq = str((series_cfg.get(series_key) or {}).get("frequency") or "")
            series_override = overrides.get(series_key) if isinstance(overrides, dict) else None
        elif "table" in inputs:
            table_key = str(inputs["table"])
            col = str(inputs.get("column") or "")
            if not col:
                raise ValueError(f"Metric {metric_id} missing inputs.column")
            base_ts = _table_column_series(table_key, col)
            base_freq = str((series_cfg.get(table_key) or {}).get("frequency") or "")
            series_override = overrides.get(table_key) if isinstance(overrides, dict) else None
            series_key = table_key
        else:
            raise ValueError(f"Metric {metric_id} missing inputs.series or inputs.table")

        # Period transform.
        pt = m.get("period_transform") or {}
        pt_kind = str(pt.get("kind") or "identity")
        if pt_kind == "identity":
            ts = _transform_identity(base_ts)
        elif pt_kind == "pct_change":
            lag = int(pt.get("lag") or 1)
            scale = float(pt.get("scale") or 100.0)
            ts = _transform_pct_change(base_ts, lag=lag, scale=scale)
        elif pt_kind == "growth_rate":
            method = str(pt.get("method") or "logdiff")
            if method != "logdiff":
                raise ValueError(f"Unsupported growth_rate method: {method!r}")
            lag = int(pt.get("lag") or 1)
            ann = int(pt.get("annualize_periods_per_year") or 1)
            scale = float(pt.get("scale") or 100.0)
            ts = _transform_growth_rate_logdiff(base_ts, lag=lag, annualize_periods_per_year=ann, scale=scale)
        elif pt_kind == "indicator_lt":
            threshold = float(pt.get("threshold") or 0.0)
            ts = _transform_indicator_lt(base_ts, threshold=threshold)
        else:
            raise ValueError(f"Unsupported period_transform.kind: {pt_kind!r} for metric {metric_id}")

        # Frequency semantics.
        freq = base_freq
        if not freq:
            raise ValueError(f"Missing frequency for series/table {series_key}")

        sem = freq_sem.get(freq) or {}
        sem_kind = str(sem.get("kind") or ("instant" if freq == "D" else "period"))
        period_kind = None
        fiscal_year_start_month = None
        fiscal_year_start_day = None
        if sem_kind == "period":
            period_kind = str(sem.get("period") or "")

        # Series override can change period semantics (e.g., fiscal year).
        if isinstance(series_override, dict):
            if series_override.get("kind") == "period" and series_override.get("period"):
                period_kind = str(series_override["period"])
                if period_kind == "us_fiscal_year":
                    fiscal_year_start_month = int(series_override.get("fiscal_year_start_month") or 10)
                    fiscal_year_start_day = int(series_override.get("fiscal_year_start_day") or 1)

        # Attribute observations to terms (needed for window-based aggregations).
        by_term = _attrib_series_to_terms(
            terms,
            ts,
            freq=freq,
            period_kind=period_kind if sem_kind == "period" else "instant",
            fiscal_year_start_month=fiscal_year_start_month,
            fiscal_year_start_day=fiscal_year_start_day,
            period_rule=period_rule,
            tie_breaker=tie_breaker,
        )

        # Term aggregation.
        agg = m.get("term_aggregation") or {}
        agg_kind = str(agg.get("kind") or "mean")

        for t in terms:
            obs = sorted(by_term.get(t.term_id, []), key=lambda x: x[0])

            # For daily level metrics, use boundary rule rather than window membership.
            use_daily_boundaries = (freq == "D") and agg_kind in {
                "end_minus_start",
                "end_minus_start_per_year",
                "pct_change_from_levels",
                "cagr_from_levels",
            }

            value: float | None = None
            n_obs = 0
            start_obs_date: date | None = None
            end_obs_date: date | None = None
            start_obs_value: float | None = None
            end_obs_value: float | None = None
            error: str = ""

            try:
                if agg_kind == "mean":
                    xs = [v for _, v in obs if v is not None]
                    n_obs = len(xs)
                    if n_obs < 1:
                        raise ValueError("empty window")
                    value = sum(xs) / n_obs
                    if "post_scale" in agg:
                        value *= float(agg.get("post_scale") or 1.0)
                elif agg_kind == "last":
                    # Last non-missing value in the attributed window.
                    for d, v in reversed(obs):
                        if v is not None:
                            value = float(v)
                            n_obs = 1
                            end_obs_date = d
                            end_obs_value = value
                            break
                    if value is None:
                        raise ValueError("empty window")
                elif agg_kind in {"end_minus_start", "end_minus_start_per_year", "pct_change_from_levels", "cagr_from_levels"}:
                    if use_daily_boundaries:
                        # End boundary for ongoing term: allow it to extend to the latest observation.
                        max_d = ts.dates[-1] if ts.dates else None
                        if not max_d:
                            raise ValueError("empty series")
                        effective_end = min(t.term_end, max_d + timedelta(days=1))
                        start_sel = _select_last_date_strictly_before(ts, t.term_start)
                        end_sel = _select_last_date_strictly_before(ts, effective_end)
                        if not start_sel or not end_sel:
                            raise ValueError("missing boundary observation")
                        start_obs_date, start_obs_value = start_sel
                        end_obs_date, end_obs_value = end_sel
                    else:
                        # Use first/last non-missing observation within the attributed window.
                        first = next(((d, v) for d, v in obs if v is not None), None)
                        last = next(((d, v) for d, v in reversed(obs) if v is not None), None)
                        if not first or not last:
                            raise ValueError("missing boundary observation")
                        start_obs_date, start_obs_value = first[0], float(first[1])  # type: ignore[arg-type]
                        end_obs_date, end_obs_value = last[0], float(last[1])  # type: ignore[arg-type]

                    assert start_obs_date and end_obs_date and start_obs_value is not None and end_obs_value is not None
                    if agg_kind == "end_minus_start":
                        value = end_obs_value - start_obs_value
                    elif agg_kind == "pct_change_from_levels":
                        scale = float(agg.get("scale") or 100.0)
                        if start_obs_value == 0:
                            raise ValueError("start value is 0")
                        value = scale * (end_obs_value / start_obs_value - 1.0)
                    else:
                        years = (end_obs_date - start_obs_date).days / year_basis_days
                        if years <= 0:
                            raise ValueError("non-positive elapsed time")
                        if agg_kind == "end_minus_start_per_year":
                            value = (end_obs_value - start_obs_value) / years
                        elif agg_kind == "cagr_from_levels":
                            scale = float(agg.get("scale") or 100.0)
                            if start_obs_value <= 0 or end_obs_value <= 0:
                                raise ValueError("non-positive level for CAGR")
                            value = scale * ((end_obs_value / start_obs_value) ** (1.0 / years) - 1.0)
                        else:
                            raise ValueError(f"unhandled agg kind: {agg_kind}")
                elif agg_kind == "mean_times_periods_per_year":
                    periods_per_year = int(agg.get("periods_per_year") or 0)
                    if periods_per_year <= 0:
                        raise ValueError("periods_per_year required")
                    xs = [v for _, v in obs if v is not None]
                    n_obs = len(xs)
                    if n_obs < 1:
                        raise ValueError("empty window")
                    value = (sum(xs) / n_obs) * periods_per_year
                elif agg_kind == "compound_total":
                    scale = float(agg.get("scale") or 100.0)
                    rs = [float(v) for _, v in obs if v is not None]
                    n_obs = len(rs)
                    if n_obs < 1:
                        raise ValueError("empty window")
                    total = 1.0
                    for r in rs:
                        total *= 1.0 + r / scale
                    value = scale * (total - 1.0)
                elif agg_kind == "compound_annualized":
                    periods_per_year = int(agg.get("periods_per_year") or 0)
                    if periods_per_year <= 0:
                        raise ValueError("periods_per_year required")
                    scale = float(agg.get("scale") or 100.0)
                    rs = [float(v) for _, v in obs if v is not None]
                    n_obs = len(rs)
                    if n_obs < 1:
                        raise ValueError("empty window")
                    total = 1.0
                    for r in rs:
                        total *= 1.0 + r / scale
                    value = scale * (total ** (periods_per_year / n_obs) - 1.0)
                elif agg_kind == "count_transitions":
                    from_value = float(agg.get("from_value"))
                    to_value = float(agg.get("to_value"))
                    xs = [v for _, v in obs]
                    n_obs = len([v for v in xs if v is not None])
                    cnt = 0
                    prev: float | None = None
                    for v in xs:
                        if v is None:
                            prev = None
                            continue
                        if prev is not None and abs(prev - from_value) < 1e-9 and abs(float(v) - to_value) < 1e-9:
                            cnt += 1
                        prev = float(v)
                    value = float(cnt)
                elif agg_kind == "annualized_std":
                    periods_per_year = int(agg.get("periods_per_year") or 0)
                    if periods_per_year <= 0:
                        raise ValueError("periods_per_year required")
                    rs = [float(v) for _, v in obs if v is not None]
                    n_obs = len(rs)
                    if n_obs < 2:
                        raise ValueError("need at least 2 observations")
                    value = _std_sample(rs) * math.sqrt(periods_per_year)
                elif agg_kind == "sharpe_ratio_annualized":
                    periods_per_year = int(agg.get("periods_per_year") or 0)
                    if periods_per_year <= 0:
                        raise ValueError("periods_per_year required")
                    rs = [float(v) for _, v in obs if v is not None]
                    n_obs = len(rs)
                    if n_obs < 2:
                        raise ValueError("need at least 2 observations")
                    mu = sum(rs) / n_obs
                    sd = _std_sample(rs)
                    if sd == 0:
                        raise ValueError("zero std")
                    value = (mu * periods_per_year) / (sd * math.sqrt(periods_per_year))
                else:
                    raise ValueError(f"Unsupported term_aggregation.kind: {agg_kind!r}")
            except Exception as exc:
                error = str(exc)
                value = None

            if obs:
                start_obs_date = start_obs_date or obs[0][0]
                end_obs_date = end_obs_date or obs[-1][0]

            units = str(agg.get("units") or agg.get("output_units") or "")
            term_rows.append(
                {
                    "metric_id": metric_id,
                    "metric_family": family,
                    "metric_primary": "1" if primary else "0",
                    "metric_label": label,
                    "term_id": t.term_id,
                    "president": t.president,
                    "party_abbrev": t.party_abbrev,
                    "term_start": t.term_start.isoformat(),
                    "term_end": t.term_end.isoformat(),
                    "freq": freq,
                    "agg_kind": agg_kind,
                    "value": _fmt_float(value),
                    "units": units,
                    "n_obs": str(n_obs) if n_obs else "",
                    "start_obs_date": start_obs_date.isoformat() if start_obs_date else "",
                    "end_obs_date": end_obs_date.isoformat() if end_obs_date else "",
                    "start_obs_value": _fmt_float(start_obs_value),
                    "end_obs_value": _fmt_float(end_obs_value),
                    "error": error,
                }
            )

    # Write outputs.
    output_terms_csv.parent.mkdir(parents=True, exist_ok=True)
    output_party_csv.parent.mkdir(parents=True, exist_ok=True)

    term_header = [
        "metric_id",
        "metric_family",
        "metric_primary",
        "metric_label",
        "term_id",
        "president",
        "party_abbrev",
        "term_start",
        "term_end",
        "freq",
        "agg_kind",
        "value",
        "units",
        "n_obs",
        "start_obs_date",
        "end_obs_date",
        "start_obs_value",
        "end_obs_value",
        "error",
    ]
    _write_csv_atomic(output_terms_csv, header=term_header, rows=term_rows)

    # Party summary: mean/median across term-level values.
    def _as_float(s: str) -> float | None:
        return _parse_float(s)

    by_party_metric: dict[tuple[str, str], list[float]] = {}
    meta: dict[tuple[str, str], dict[str, str]] = {}
    for r in term_rows:
        party = str(r.get("party_abbrev") or "")
        metric_id = str(r.get("metric_id") or "")
        v = _as_float(str(r.get("value") or ""))
        if v is None:
            continue
        by_party_metric.setdefault((party, metric_id), []).append(v)
        meta[(party, metric_id)] = {
            "metric_family": str(r.get("metric_family") or ""),
            "metric_primary": str(r.get("metric_primary") or ""),
            "metric_label": str(r.get("metric_label") or ""),
            "units": str(r.get("units") or ""),
            "agg_kind": str(r.get("agg_kind") or ""),
        }

    party_rows: list[dict[str, Any]] = []
    for (party, metric_id), xs in sorted(by_party_metric.items(), key=lambda t: (t[0][0], t[0][1])):
        xs_sorted = sorted(xs)
        n = len(xs_sorted)
        mean = sum(xs_sorted) / n if n else None
        med = xs_sorted[n // 2] if n % 2 == 1 else (xs_sorted[n // 2 - 1] + xs_sorted[n // 2]) / 2.0
        m = meta.get((party, metric_id), {})
        party_rows.append(
            {
                "party_abbrev": party,
                "metric_id": metric_id,
                "metric_family": m.get("metric_family", ""),
                "metric_primary": m.get("metric_primary", ""),
                "metric_label": m.get("metric_label", ""),
                "agg_kind": m.get("agg_kind", ""),
                "units": m.get("units", ""),
                "n_terms": str(n),
                "mean": _fmt_float(mean),
                "median": _fmt_float(med),
            }
        )

    party_header = [
        "party_abbrev",
        "metric_id",
        "metric_family",
        "metric_primary",
        "metric_label",
        "agg_kind",
        "units",
        "n_terms",
        "mean",
        "median",
    ]
    _write_csv_atomic(output_party_csv, header=party_header, rows=party_rows)

    # Small sidecar so humans can quickly see what was produced without opening CSVs.
    summary_lines = [
        f"Computed {len(metrics_cfg)} metrics over {len(terms)} terms.",
        f"Wrote: {output_terms_csv}",
        f"Wrote: {output_party_csv}",
        "",
        "Note: Reports are derived artifacts and are gitignored by default.",
    ]
    write_text_atomic(output_terms_csv.with_suffix(".summary.txt"), "\n".join(summary_lines) + "\n")
