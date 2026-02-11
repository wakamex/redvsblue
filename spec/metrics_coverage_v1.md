# Metrics Coverage Matrix (v1)

This file records judgment calls for which transforms we include per source series.
It is designed to reduce hidden opinion and make "why not this metric?" auditable.

## Coverage Policy (Unopinionated Default)

Default stance: include a broad transform set unless a transform is clearly non-interpretable for that series type.

Series-type defaults:

- Level/index series (GDP, prices, wages, stock levels):
  - Prefer: `mean` (where meaningful), `end_minus_start`, `end_minus_start_per_year`, `pct_change_from_levels`, `cagr_from_levels`.
  - Optional: short-horizon growth transforms (MoM/QoQ/YoY) when they are standard for that domain.
- Rate series already in percent (e.g., unemployment rate, debt-to-GDP):
  - Prefer: `mean`, `last`, `end_minus_start`, `end_minus_start_per_year`.
  - Avoid percent-change-on-percent-rate transforms unless specifically justified.
- Return series:
  - Prefer: annualized compound return, term-total compound return, volatility, Sharpe.
- Binary indicator series:
  - Prefer: share/time-in-state (`mean`), transition counts (`count_transitions`).

## Current v1 Coverage Review

Legend:
- `covered`: transform class is represented in `spec/metrics_v1.yaml`.
- `partial`: some analogous transforms exist, but not a full symmetric set.
- `intentionally_omitted`: excluded for interpretability or data-definition reasons.
- `candidate`: reasonable addition for a later spec version.

### Output

- `gdpc1_real_gdp`
  - `covered`: QoQ annualized growth mean, term total percent change, term CAGR.
- `a939rx0q048sbea_real_gdp_per_capita`
  - `covered`: QoQ annualized growth mean, term total percent change, term CAGR.

### Labor

- `payems_payroll_employment`, `ce16ov_household_employment`
  - `covered`: total change, per-year change, term percent change, term CAGR.
- `unrate_unemployment_rate`
  - `covered`: mean, end-of-term value, pp change, pp change per year.
  - `intentionally_omitted`: percent-change transform on unemployment rate (not policy-intuitive).
- `civpart_labor_force_participation`
  - `covered`: mean, end-of-term value, pp change, pp change per year.
  - `intentionally_omitted`: percent-change transform on participation rate (same interpretability concern as unemployment rate).

### Wages

- `les1252881600q_real_median_weekly_earnings`
  - `covered`: mean, end-of-term value, term percent change, term CAGR.

### Prices / Inflation

- `cpiaucns_cpi_unadjusted`
  - `covered`: YoY mean, term percent change, term CAGR.
- `cpiaucsl_cpi`
  - `covered`: YoY mean (alternate), MoM annualized log-diff mean, term percent change, term CAGR.
  - `note`: SA level-term metrics are alternates; NSA remains the default headline CPI level pair.
- `pcepi_pce_price_index`
  - `covered`: YoY mean, MoM annualized log-diff mean, term percent change, term CAGR.
- `cpilfesl_core_cpi`
  - `covered`: YoY mean, MoM annualized log-diff mean, term percent change, term CAGR.
- `pcepilfe_core_pce_price_index`
  - `covered`: YoY mean, MoM annualized log-diff mean, term percent change, term CAGR.

### Finance

- `ff_factors_monthly` (`mkt_rf`, `mkt_total`)
  - `covered`: annualized returns, excess/total term-total returns, volatility, Sharpe.
- `sp500_sp500_index`, `djia_dow_jones`
  - `covered`: term percent change and CAGR.
- `sp500_spx_backfilled_pre1957`
  - `covered`: separate historical-composite term percent change and CAGR.
  - `intentionally_omitted`: stitched modern+historical headline series.

### Interest Rates / Yield Curve

- `fedfunds_policy_rate`
  - `covered`: mean, end-of-term value, pp change, pp change per year.
- `dgs10_treasury_10y_rate`
  - `covered`: mean, end-of-term value, pp change, pp change per year.
- `t10y2y_yield_spread`
  - `covered`: mean, end-of-term value, pp change, pp change per year, inversion share, inversion start count.
  - `note`: inversion metrics are based on trading-day observations (`T10Y2Y < 0`) and are descriptive recession-risk proxies.
- `t10y2y_yield_spread_monthly_eop`
  - `covered`: inversion share, inversion start count (monthly EOP resample via FRED API).
  - `note`: used as a robustness comparison against trading-day inversion definitions.
- `t10y2y_yield_spread_monthly_avg`
  - `covered`: inversion share, inversion start count (monthly average resample via FRED API).
  - `note`: smoothing variant to compare with EOP and trading-day definitions.

### Recessions

- `usrec_recession_indicator`
  - `covered`: recession month share, recession start count.
  - `intentionally_omitted`: "severity" metrics from `USREC` alone (not identifiable from a binary indicator).

### Fiscal

- `gfdegdq188s_federal_debt_pct_gdp`
  - `covered`: mean, end, pp change, pp change per year.
- `fyfsgda188s_federal_surplus_deficit_pct_gdp`
  - `covered`: mean, end, pp change, pp change per year.

## Suggested v2 Additions (Priority Order)

1. Add a `--no-robustness-links` scoreboard option for cleaner exports when consumers want only core tables.
2. Add a fixed report artifact comparing inversion definitions (daily, monthly-EOP, monthly-AVG) each run.
3. Add local caching for CI smoke downloads between steps/jobs to reduce provider dependence and runtime.

## Change-Control Rule

If we reject a candidate transform, record:
- reason for exclusion,
- expected bias if excluded,
- and where the alternate evidence is represented.

This avoids silent opinionated pruning.
