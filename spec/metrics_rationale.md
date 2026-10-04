# Metrics Rationale (v1)

This document explains the key measurement choices in `spec/metrics_v1.yaml`. The goal is to make disagreements about "Dem vs Rep performance" explicit and auditable: if you disagree, you can point to a specific metric id or spec field, propose an alternative, and we can add it as an alternate definition rather than silently changing results.

Per-series transform inclusion/exclusion decisions are tracked in `spec/metrics_coverage_v1.md` so judgment calls are explicit instead of implicit.

## General Conventions

- Prefer pulling **level series** (indexes/levels) from upstream and computing transforms locally. This keeps formulas explicit and avoids ambiguous upstream "units" transformations.
- Prefer **log-diff annualization** for growth rates when starting from level series:
  - QoQ annualized growth: `100 * 4 * ln(x_t / x_{t-1})`
  - MoM annualized inflation: `100 * 12 * ln(x_t / x_{t-1})`
- For rates already expressed in percent (e.g., `UNRATE`), use levels and differences (percentage points) rather than re-scaling.
- Term attribution (lag rules, inauguration/boundary handling, etc.) is **not** a metric decision; it is controlled by the join/attribution config and recorded in the run manifest.
  - We formalize these rules in `spec/attribution_v1.yaml` so “start/end” are deterministic across implementations.
  - Term-aggregation semantics are formalized in `spec/aggregation_kinds_v1.yaml` so the metric engine is testable.
- Data fetching:
  - For FRED series, prefer the official FRED API when an API key is configured (metadata, stability, vintage support).
  - Fall back to `fredgraph.csv` only when an API key is unavailable; always cache raw downloads and record retrieval metadata.

## Prices / Inflation (MoM, QoQ, YoY, SAAR)

Question: should we use precomputed MoM/QoQ/YoY series vs computing from price levels?

Choice (v1): **compute inflation from price index levels** (e.g., CPI, PCEPI), and explicitly support both seasonally adjusted (SA) and not seasonally adjusted (NSA) CPI where it matters.

Rationale:
- CPI/PCE are published as **index levels**, not SAAR levels. "SAAR" is an annualization convention typically applied to growth rates (and to some BEA flow/level series like GDP levels), not to CPI levels.
- Computing locally makes the exact formula unambiguous (pct-change vs log-diff; annualized vs not).
- Many "precomputed inflation" series are either not available as plain downloads without special API parameters, or embed transformation assumptions we still need to document.

We include multiple inflation definitions because people argue about them:
- `cpi_inflation_yoy_mean_nsa`: YoY inflation from the **unadjusted** CPI index, averaged over the attributed window.
  - Pros: YoY does not require seasonal adjustment; avoids annual revision of seasonally adjusted CPI levels due to seasonal factor updates.
  - Caveat: if the attribution/join rules produce windows that start/end on different calendar months (e.g., partial-month attribution), NSA YoY can retain residual seasonal bias. We treat SA vs NSA as a measurable sensitivity rather than a hidden choice.
- `cpi_inflation_yoy_mean`: YoY inflation from the **seasonally adjusted** CPI index, averaged over the attributed window.
  - Pros: included for completeness; should be very close to the NSA YoY in most periods.
- `cpi_inflation_mom_ann_logdiff_mean`: MoM annualized log-diff inflation, averaged over the window.
  - Pros: faster-moving signal; matches common "annualized monthly inflation" discussions.
  - Note: for MoM measures, we prefer SA CPI because NSA MoM is dominated by seasonal patterns.
- `pce_inflation_yoy_mean`: PCE-based YoY inflation.
- `pce_inflation_mom_ann_logdiff_mean`: PCE MoM annualized log-diff inflation.
- `core_cpi_inflation_yoy_mean` and `core_cpi_inflation_mom_ann_logdiff_mean`: core CPI variants that remove food/energy noise.
- `core_pce_inflation_yoy_mean` and `core_pce_inflation_mom_ann_logdiff_mean`: core PCE variants often used in policy discussions.

We also include cumulative price-level change metrics:
- `cpi_price_level_term_pct_change_nsa`: total percent change in the CPI index over the term window (end vs start).
- `cpi_price_level_term_cagr_pct_nsa`: annualized percent change (CAGR) from start/end levels.
- `cpi_price_level_term_pct_change_sa` and `cpi_price_level_term_cagr_pct_sa`: SA CPI level-term alternates for direct SA-vs-NSA sensitivity checks.
- `pce_price_level_term_pct_change`: total percent change in PCEPI over the term window.
- `pce_price_level_term_cagr_pct`: annualized percent change (CAGR) from PCEPI start/end levels.
- `core_cpi_price_level_term_pct_change`, `core_cpi_price_level_term_cagr_pct`: cumulative core CPI level change over the term window.
- `core_pce_price_level_term_pct_change`, `core_pce_price_level_term_cagr_pct`: cumulative core PCE level change over the term window.
These are often more intuitive for “prices went up X% during this term” claims than an average YoY rate.

Seasonal adjustment:
- The BLS produces **both unadjusted and seasonally adjusted CPI data**; SA data are intended for short-term trend analysis, while unadjusted data are widely used for escalation/indexation and other applications.
- SA CPI series are revised when seasonal factors are updated (typically revising recent history), so “latest data” pulls can change SA values in the recent window; caching raw downloads keeps our runs reproducible, but we still surface this as a choice.
- For the PCE price index (`PCEPI`), the monthly series in FRED is **seasonally adjusted**. We compute YoY from that level series; if we later want a non-seasonally-adjusted PCE price index, FRED provides other formats (e.g., annual NSA) but those are not a drop-in replacement for monthly term windows.

## Output (GDP)

`GDPC1` is a **quarterly level in SAAR units** (real GDP at an annual rate). We still compute growth locally from the level series (log-diff annualized). This is standard and keeps the growth formula consistent with other growth metrics.

We include alternates:
- real GDP per capita growth
- term total percent change from start/end levels
- term CAGR computed from start/end levels (useful for start/end comparisons, but more sensitive to window rules)
- per-capita term total percent change and per-capita term CAGR for symmetry with aggregate GDP

## Stock Market: Returns vs Levels (MoM/QoQ/YoY)

Question: do we need levels, not just returns?

Choice (v1): use **Ken French monthly returns** for investor-return comparisons and a recognizable **S&P price-only series** for public verification.

Rationale:
- Returns are the cleanest unit for comparisons (stationary-ish, not dependent on an arbitrary base year).
- "Level" comparisons (e.g., S&P 500 start vs end) are common in popular claims and easier for readers to verify independently, so we retain them as alternate views.

Ken French dataset:
- Monthly observations start in **1926-07**; the latest available month depends on when the file is downloaded.
- Our pipeline should cache the raw zip and record the observed date range + header metadata in the run manifest so results can be reproduced even if the upstream file changes later.

Metrics included:
- `ff_mkt_excess_return_ann_compound`: annualized compound excess return (Mkt-RF).
- `ff_mkt_total_return_ann_compound`: annualized compound total return (Mkt-RF + RF).
- `ff_mkt_total_return_term_total`: compounded total return over the term window (end/start in percent terms).
- `ff_mkt_excess_return_term_total`: compounded excess return over the term window.

Price index levels (Dow and S&P):
- The former Stooq feed was removed because its API and redistribution terms could not be confirmed.
- The replacement is DataHub Core's versioned monthly S&P CSV. Its data package is offered under ODC-PDDL-1.0 and is directly browsable by users; the package README also discloses that the original Shiller data has no exact license statement.
- The modern view begins in 1957. The pre-1957 Shiller composite remains a separately labeled historical view so it is not presented as the modern 500-stock index.
- The values are price-only and exclude dividends. They complement rather than replace the Ken French total-return metrics.
- We dropped the redundant Dow metrics because no equally transparent, suitably licensed replacement was identified.

Risk context for returns:
- To reduce “recovery-from-crash” cherry-picking and provide context, we include:
  - annualized volatility of monthly excess returns (`ff_mkt_excess_return_volatility_ann`)
  - annualized Sharpe ratio of monthly excess returns (`ff_mkt_excess_return_sharpe_ann`)

Level-style term metrics included:
- S&P 500 price percent change and CAGR: `sp500_term_pct_change`, `sp500_term_cagr_pct`
- Pre-1957 historical composite price percent change and CAGR: `sp500_backfilled_pre1957_term_pct_change`, `sp500_backfilled_pre1957_term_cagr_pct`

MoM/QoQ/YoY:
- MoM is the monthly return itself.
- QoQ/YoY are rolling compounded returns over 3/12 months. We have not included these as scoreboard metrics; they are better suited for plots/diagnostics because they overlap heavily over time.

## Interest Rates / Yield Curve

Question: should rates be treated as explanatory variables only, or also as outcome descriptors under a presidency?

Choice (v1): include rates/spreads as descriptive macro-financial state variables, with level-preserving transforms:

- `fedfunds_policy_rate` (`FEDFUNDS`)
- `dgs10_treasury_10y_rate` (`DGS10`)
- `t10y2y_yield_spread` (`T10Y2Y`)

For each, we include:

- term mean,
- end-of-term level,
- end-minus-start (percentage points), and
- end-minus-start per year.
- for `T10Y2Y` specifically, inversion diagnostics:
  - inversion share of trading days (`T10Y2Y < 0`)
  - inversion start count (`0->1` transitions in the inversion indicator)
  - monthly-EOP inversion share/starts and monthly-AVG inversion share/starts as resampled robustness views

Rationale:

- These series are central to claims about inflation control, financing conditions, and recession risk.
- Level and pp-change transforms are interpretable and avoid percent-change-on-rate confusion.
- Keeping a symmetric transform set across all three avoids one-off metric selection.
- Explicit inversion metrics make recession-risk signaling auditable instead of implicit in spread means.
- Monthly-EOP and monthly-AVG variants reduce sensitivity to daily noise and provide coarser-horizon cross-checks against trading-day definitions.

Guardrail:

- These are not interpreted as direct policy causal effects of the president; monetary policy independence and macro endogeneity remain explicit caveats.

## Employment: End-minus-start vs Per-year

Question: why include `end_minus_start_per_year`?

Choice (v1): include **both total change and per-year** variants, and apply the same pairing across comparable series to avoid cherry-picking accusations.

Rationale:
- Total change (`end_minus_start`) is the most direct answer to “how many jobs were added during this window.”
- Per-year normalization helps when:
  - we compare windows of different lengths (partial terms, alternate lag rules),
  - we want a rough rate comparable across terms.
- Per-year implicitly assumes linearity; it’s not a structural model. We treat it as a convenience view, not the canonical truth.

Anti-cherry-picking policy:
- If we include a per-year version for a metric family, we also include the total-change version (and vice versa).
- Reports should display both side-by-side for the same underlying series to prevent “we picked the normalization that looks best” critiques.
- We now also include percent-change and CAGR variants for payroll, manufacturing, and household employment so level and rate-style narratives can be cross-checked.

We include total payroll (CES) and household (CPS) employment series to reflect the measurement split in labor statistics. Manufacturing employment (`MANEMP`, BLS CES) adds a transparent sector-specific view that readers can verify independently. It is a subset of total payroll employment rather than an independent signal, and remains in the same BH-FDR universe as every other displayed metric.

For unemployment (`UNRATE`), we use level-preserving transforms:
- term mean,
- end-of-term level,
- percentage-point change, and
- percentage-point change per year.
This keeps interpretation in labor-market units and avoids percent-change-on-rate ambiguity.

We now apply the same level-preserving transform family to labor force participation (`CIVPART`):

- term mean,
- end-of-term level,
- percentage-point change, and
- percentage-point change per year.

This adds a labor-utilization lens that is not captured by unemployment alone (for example, decline in participation can mechanically lower unemployment).

## Wages / Real Earnings

If the goal is “how did typical workers do,” GDP and stocks are incomplete: they can rise while typical wages stagnate.

Choice (v1): include one real-earnings series with both level and change views:
- `LES1252881600Q` (CPS; real median weekly earnings for full-time workers; CPI-adjusted).

Metrics include:
- mean and end-of-term levels (context metrics),
- term percent change,
- term CAGR.

Notes:
- This series is quarterly and can be noisy; it’s still valuable as a reality check against purely macro/market metrics.
- If/when we add nominal wage series (e.g., average hourly earnings) we should also add explicit deflators (CPI/PCE) rather than relying on upstream “real” adjustments.

## Fiscal: Percent of GDP vs Dollars

Choice (v1): start with percent-of-GDP series when available (`GFDEGDQ188S`, `FYFSGDA188S`) because it reduces inflation/scale issues and matches much of the public discourse.

Notes:
- Fiscal series are often annual or fiscal-year based; mapping to presidential windows requires extra care (and must be documented in the attribution manifest).
- For symmetry, we now include mean/end/change/change-per-year transforms for both debt and surplus/deficit percent-of-GDP series.

## What We Still Need To Decide (Likely v2)

- Whether daily stock level endpoints should use close-before-inauguration vs close-on-inauguration, and whether to also provide an end-of-month-based variant as a robustness check.
- Whether to support point-in-time/vintage data for key series (ALFRED) to avoid revision effects in historical reproducibility.


## Household income, inequality, and poverty

Four annual national series add household purchasing power, income dispersion, and hardship to the registry. Each has two change views: total and annualized percentage growth for real median income, ratio-point change and change per year for inequality, and percentage-point change and change per year for each poverty measure. This adds eight metrics to the existing joint multiple-comparison correction. Individual percentiles, quintile averages, and additional level views are omitted to keep the household additions compact.

The [U.S. Census Bureau's 2025 income tables](https://www.census.gov/data/tables/2026/demo/income-poverty/p60-289.html), Table 6, supply real median household income and the published 90th-to-10th-percentile income ratio for 1967–2025. These estimates come from the [Current Population Survey Annual Social and Economic Supplement (CPS ASEC)](https://www.census.gov/programs-surveys/cps.html). Median income uses the table's 2025 dollars. The dimensionless ratio divides the upper income cutoff by the lower cutoff; larger values indicate greater dispersion between those positions. Its change is in ratio points, not percentage points. The pipeline reads the published ratio directly without registering individual percentile series. The ratio does not measure extreme-top income concentration, and an increase can reflect faster income growth at the top even while lower incomes rise.

The official poverty rate uses Census's all-person percentage series [HSTPOVARAPBPP](https://fred.stlouisfed.org/series/HSTPOVARAPBPP), delivered through [Federal Reserve Economic Data (FRED)](https://fred.stlouisfed.org/). Coverage begins in 1959. The measure uses pretax money income and excludes tax credits and noncash benefits.

The [Columbia historical Supplemental Poverty Measure (SPM)](https://povertycenter.columbia.edu/historical-spm-data) supplies the total-population rate after taxes and transfers for 1967–2024. The selected column is “Historical SPM Poverty Rate,” whose thresholds vary over time. Values are stored as fractions in the workbook and multiplied by 100 for percentage units. The September 9, 2025 workbook predates the [2026 corrections to SPM thresholds](https://www.census.gov/library/stories/2023/09/income-inequality.html); its source note identifies this vintage. It reconstructs 1967–2008 and uses public-use survey data from 2009 onward. Recent estimates can differ from published Census rates because of public-use versus internal data differences. The pipeline retains the coherent published research series rather than splicing releases.

### Period change baselines

Endpoint-change metrics use the last nonmissing observation before the first attributed period as their baseline and the last nonmissing observation inside the attributed window as their endpoint. This applies to monthly, quarterly, and annual absolute changes, percentage changes, changes per year, and compound annual growth. Calendar-year majority-of-days attribution is unchanged: a 2021–2024 income window compares 2020 with 2024 and annualizes over the actual elapsed time, approximately four years. The next term can compare 2024 with 2025 as soon as that first annual observation exists. Means, end levels, growth-rate averages, compounded returns, and daily boundary selection retain their definitions.

The baseline is selected relative to the first attributed period's timestamp, not inauguration day. For example, an annual observation labeled January 1, 2025 describes calendar year 2025 and belongs inside the new term; it cannot also serve as that term's preceding baseline. Fiscal-year series keep their existing period assignment and use the preceding fiscal-year observation. If no preceding baseline exists, the first nonmissing observation inside the term becomes the baseline. The result then describes partial coverage, with actual observation dates and a partial-coverage label in the chart. At least two distinct observations are required for this fallback; a lone value cannot yield zero change. Missing endpoint data makes the change unavailable. Missing values are skipped when finding a baseline, and the selected dates are recorded in the term results. The attribution setting `period_change_baseline: previous_observation_or_first_available` records this rule. Older attribution files without that setting retain `first_attributed_observation`, allowing saved runs to be reproduced.

### Source versions and survey revisions

The spreadsheet releases are pinned by their registered download addresses, expected headers, units, and year coverage. New annual releases require updating the registry and verifying their headers and footnotes; refreshing a pinned address alone does not discover a newer release. Raw workbooks are cached with retrieval metadata and content hashes. Derived metadata records the selected year labels, parser settings, units, and source hash. The spreadsheets are read with [openpyxl](https://openpyxl.readthedocs.io/).

Census publishes two rows for 2013 and 2017. The selected labels, “2013 4” and “2017 3,” use the redesigned questionnaire and updated processing system respectively. Columbia's selected labels are “2013b,” “2017b,” and “2019b*,” reflecting the redesigned questionnaire, updated processing, and revised SPM methodology. Its pandemic nonresponse adjustments are retained. These choices do not eliminate historical measurement breaks. Unknown duplicate years, missing years, changed headers, and invalid values fail ingestion rather than silently selecting another column or row.
