# Metrics Rationale (v1)

This document explains the key measurement choices in `spec/metrics_v1.yaml`. The goal is to make disagreements about "Dem vs Rep performance" explicit and auditable: if you disagree, you can point to a specific metric id or spec field, propose an alternative, and we can add it as an alternate definition rather than silently changing results.

## General Conventions

- Prefer pulling **level series** (indexes/levels) from upstream and computing transforms locally. This keeps formulas explicit and avoids ambiguous upstream "units" transformations.
- Prefer **log-diff annualization** for growth rates when starting from level series:
  - QoQ annualized growth: `100 * 4 * ln(x_t / x_{t-1})`
  - MoM annualized inflation: `100 * 12 * ln(x_t / x_{t-1})`
- For rates already expressed in percent (e.g., `UNRATE`), use levels and differences (percentage points) rather than re-scaling.
- Term attribution (lag rules, inauguration/boundary handling, etc.) is **not** a metric decision; it is controlled by the join/attribution config and recorded in the run manifest.
  - We formalize these rules in `spec/attribution_v1.yaml` so “start/end” are deterministic across implementations.
  - Term-aggregation semantics are formalized in `spec/aggregation_kinds_v1.yaml` so the metric engine is testable.

## Prices / Inflation (MoM, QoQ, YoY, SAAR)

Question: should we use precomputed MoM/QoQ/YoY series vs computing from price levels?

Choice (v1): **compute inflation from price index levels** (e.g., CPI, PCEPI), and explicitly support both seasonally adjusted (SA) and not seasonally adjusted (NSA) CPI where it matters.

Rationale:
- CPI/PCE are published as **index levels**, not SAAR levels. "SAAR" is an annualization convention typically applied to growth rates (and to some BEA flow/level series like GDP levels), not to CPI levels.
- Computing locally makes the exact formula unambiguous (pct-change vs log-diff; annualized vs not).
- Many "precomputed inflation" series are either not available as plain downloads without special API parameters, or embed transformation assumptions we still need to document.

We include multiple inflation definitions because people argue about them:
- `cpi_inflation_yoy_mean_nsa` (primary): YoY inflation from the **unadjusted** CPI index, averaged over the attributed window.
  - Pros: YoY does not require seasonal adjustment; avoids annual revision of seasonally adjusted CPI levels due to seasonal factor updates.
  - Caveat: if the attribution/join rules produce windows that start/end on different calendar months (e.g., partial-month attribution), NSA YoY can retain residual seasonal bias. We treat SA vs NSA as a measurable sensitivity rather than a hidden choice.
- `cpi_inflation_yoy_mean` (alternate): YoY inflation from the **seasonally adjusted** CPI index, averaged over the attributed window.
  - Pros: included for completeness; should be very close to the NSA YoY in most periods.
- `cpi_inflation_mom_ann_logdiff_mean` (alternate): MoM annualized log-diff inflation, averaged over the window.
  - Pros: faster-moving signal; matches common "annualized monthly inflation" discussions.
  - Note: for MoM measures, we prefer SA CPI because NSA MoM is dominated by seasonal patterns.
- `pce_inflation_yoy_mean` (alternate): PCE-based inflation.

We also include cumulative price-level change metrics:
- `cpi_price_level_term_pct_change_nsa`: total percent change in the CPI index over the term window (end vs start).
- `cpi_price_level_term_cagr_pct_nsa`: annualized percent change (CAGR) from start/end levels.
These are often more intuitive for “prices went up X% during this term” claims than an average YoY rate.

Seasonal adjustment:
- The BLS produces **both unadjusted and seasonally adjusted CPI data**; SA data are intended for short-term trend analysis, while unadjusted data are widely used for escalation/indexation and other applications.
- SA CPI series are revised when seasonal factors are updated (typically revising recent history), so “latest data” pulls can change SA values in the recent window; caching raw downloads keeps our runs reproducible, but we still surface this as a choice.
- For the PCE price index (`PCEPI`), the monthly series in FRED is **seasonally adjusted**. We compute YoY from that level series; if we later want a non-seasonally-adjusted PCE price index, FRED provides other formats (e.g., annual NSA) but those are not a drop-in replacement for monthly term windows.

## Output (GDP)

`GDPC1` is a **quarterly level in SAAR units** (real GDP at an annual rate). We still compute growth locally from the level series (log-diff annualized). This is standard and keeps the growth formula consistent with other growth metrics.

We include alternates:
- real GDP per capita growth
- term CAGR computed from start/end levels (useful for start/end comparisons, but more sensitive to window rules)

## Stock Market: Returns vs Levels (MoM/QoQ/YoY)

Question: do we need levels, not just returns?

Choice (v1): use **Ken French monthly returns** as the primary stock market source, and **derive level-like metrics** via compounding.

Rationale:
- Returns are the cleanest unit for comparisons (stationary-ish, not dependent on an arbitrary base year).
- "Level" comparisons (e.g., S&P 500 start vs end) are common in popular claims, so we should support them, but they are highly sensitive to window endpoints. We treat those as **alternate views**.

Ken French dataset:
- Monthly observations start in **1926-07**; the latest available month depends on when the file is downloaded.
- Our pipeline should cache the raw zip and record the observed date range + header metadata in the run manifest so results can be reproduced even if the upstream file changes later.

Metrics included:
- `ff_mkt_excess_return_ann_compound` (primary): annualized compound excess return (Mkt-RF).
- `ff_mkt_total_return_ann_compound` (alternate): annualized compound total return (Mkt-RF + RF).
- `ff_mkt_total_return_term_total` (alternate): compounded total return over the term window (end/start in percent terms).

Price index levels (Dow and S&P):
- For popular/press-style “the market went up/down under X” claims, we also include **price index levels** from Stooq:
- We fetch:
  - S&P 500 (`^spx` from Stooq)
  - Dow Jones Industrial Average (`^dji` from Stooq)
- These are **price-only** indices (exclude dividends), so they are not directly comparable to total return measures. We treat them as alternates for public-facing level claims, not the primary return metric.
- Boundary alignment for daily series (inaugurations on weekends/holidays, etc.) is handled by the attribution spec (`spec/attribution_v1.yaml`). v1 default is to use the **close of the last trading day strictly before** the inauguration boundary, to avoid time-of-day ambiguity on inauguration day.
- Stooq is a third-party data source; we should treat it as a convenience feed for “popular claim” metrics (S&P/Dow levels), record retrieval metadata/hashes, and avoid redistributing raw data unless licensing is confirmed.

Risk context for returns:
- To reduce “recovery-from-crash” cherry-picking and provide context, we include:
  - annualized volatility of monthly excess returns (`ff_mkt_excess_return_volatility_ann`)
  - annualized Sharpe ratio of monthly excess returns (`ff_mkt_excess_return_sharpe_ann`)

Level-style term metrics included:
- Term total percent change (end vs start): `sp500_term_pct_change`, `djia_term_pct_change`
- Term percent change per year (CAGR, annualized from start/end using elapsed time): `sp500_term_cagr_pct`, `djia_term_cagr_pct`

MoM/QoQ/YoY:
- MoM is the monthly return itself.
- QoQ/YoY are rolling compounded returns over 3/12 months. We have not made these primary scoreboard metrics yet; they are better suited for plots/diagnostics because they overlap heavily over time.

## Employment: End-minus-start vs Per-year

Question: why include `end_minus_start_per_year`?

Choice (v1): keep **total change** as primary and per-year as an alternate, and apply the same pairing across comparable series to avoid cherry-picking accusations.

Rationale:
- Total change (`end_minus_start`) is the most direct answer to “how many jobs were added during this window.”
- Per-year normalization helps when:
  - we compare windows of different lengths (partial terms, alternate lag rules),
  - we want a rough rate comparable across terms.
- Per-year implicitly assumes linearity; it’s not a structural model. We treat it as a convenience view, not the canonical truth.

Anti-cherry-picking policy:
- If we include a per-year version for a metric family, we also include the total-change version (and vice versa).
- Reports should display both side-by-side for the same underlying series to prevent “we picked the normalization that looks best” critiques.

We include both payroll (CES) and household (CPS) employment series to reflect the measurement split in labor statistics.

## Wages / Real Earnings

If the goal is “how did typical workers do,” GDP and stocks are incomplete: they can rise while typical wages stagnate.

Choice (v1): include one real-earnings series with term percent change + CAGR:
- `LES1252881600Q` (CPS; real median weekly earnings for full-time workers; CPI-adjusted).

Notes:
- This series is quarterly and can be noisy; it’s still valuable as a reality check against purely macro/market metrics.
- If/when we add nominal wage series (e.g., average hourly earnings) we should also add explicit deflators (CPI/PCE) rather than relying on upstream “real” adjustments.

## Fiscal: Percent of GDP vs Dollars

Choice (v1): start with percent-of-GDP series when available (`GFDEGDQ188S`, `FYFSGDA188S`) because it reduces inflation/scale issues and matches much of the public discourse.

Notes:
- Fiscal series are often annual or fiscal-year based; mapping to presidential windows requires extra care (and must be documented in the attribution manifest).

## What We Still Need To Decide (Likely v2)

- Whether daily stock level endpoints should use close-before-inauguration vs close-on-inauguration, and whether to also provide an end-of-month-based variant as a robustness check.
- Whether to support point-in-time/vintage data for key series (ALFRED) to avoid revision effects in historical reproducibility.
