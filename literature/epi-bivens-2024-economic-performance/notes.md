# Notes: Economic Performance Is Stronger When Democrats Hold the White House

**URL:** https://epiaction.org/wp-content/uploads/2024/08/Full-Report_Economic-performance-is-stronger-when-Democrats-hold-the-White-House.pdf  
**Authors/Org:** Josh Bivens (Economic Policy Institute / EPI Action)  
**Published:** April 2, 2024 (report)  
**Retrieved:** 2026-02-09  
**Local files:** `literature/epi-bivens-2024-economic-performance/source.*`, `literature/epi-bivens-2024-economic-performance/source.txt`

## What It Claims
- Across a broad set of macro indicators since 1949, average performance is stronger under Democratic presidents than Republican presidents.
- The Democratic advantage is strongest in private-sector outcomes (business investment, job growth, market-based income growth).
- Distribution: income growth is faster and more equal under Democratic administrations, even for market-based income measures.
- The report explicitly does **not** claim to estimate causal effects of party control; it frames results as descriptive patterns that persist in the data.

## Data & Definitions
- Metrics:
  - Aggregate: real GDP growth, net domestic product per capita growth, total and private job growth, unemployment rate, real wage growth, real business investment growth, real personal income excluding transfers, inflation (headline and core), federal funds rate.
  - Distributional: household/money income growth by quantiles; WID post-tax/post-transfer income shares/groups.
- Time period:
  - Primary comparisons “since 1949” (Truman elected term onward); some variables begin later due to data availability (report annotates series availability).
- Party/presidency coding (important and nonstandard):
  - Aggregate variables collected quarterly; administration start is dated as **Q3 of the year following the election** (example given: Biden admin starts in June 2021).
  - Distributional variables use annual data; administration start is the **inauguration year** (example: Biden starts in 2021).
- Data sources (from Appendix):
  - BEA NIPA (GDP, NDP, investment, PCE deflator).
  - BLS CES/CPS (employment, unemployment).
  - EPI-derived wage series (production/nonsupervisory wages, with backcasting).
  - FRED (federal funds rate).
  - Census historical income tables (with adjustments for methodological breaks).
  - WID (Piketty/Saez/Zucman-style post-tax/post-transfer incomes by groups).

## Methodology / Identification
- Summary:
  - Compute quarterly year-over-year growth rates (for growth variables) and quarterly averages (for level variables), then collapse averages by party-of-president.
  - For distributional outcomes, compute annual growth rates by party-of-president (inauguration-year start).
  - No regression controls; explicitly descriptive.
- Lags / attribution window:
  - Uses the “start in Q3 after election” rule to allow “some scope” for policy to affect outcomes; states results are not sensitive to reasonable changes in the window.
- Controls / covariates:
  - None (by design); report notes luck/chance and limited presidential control.
- Robustness:
  - Provides multiple indicators and alternative measures (e.g., inflation advantage persists across CPI variants per appendix text).

## Results (Quantitative)
- Claims a Democratic advantage across essentially all listed aggregate indicators since 1949.
- Example explicitly stated: real GDP growth advantage of **~1.2 percentage points** under Democrats since 1949 (report’s narrative around Table 1).
- Also claims Democratic advantage in “negative” indicators (lower unemployment, lower inflation and interest rates on average) and stronger private investment growth.

## Strengths
- Broad coverage: aggregates + distributional outcomes, with explicit sources and methods appendix.
- Transparent about being descriptive (does not overclaim causality).
- Uses primary government data and describes series-break handling for income measures.

## Weaknesses / Risks
- The administration-window rule (Q3 after election) is a modeling choice that can materially affect measured performance; it should be treated as a parameter, not a fact.
- Collapsing quarterly observations by party without controls can overweight long presidencies and confounded periods; does not address inherited conditions or global shocks.
- Mixing partial administrations (“present”) can be misleading for comparisons (especially around large shocks like the pandemic).

## Replication Notes
- Code/data availability:
  - Appendix documents sources and windowing, but the extracted text does not include a code repository link. Replication should follow the appendix precisely.
- Gotchas:
  - Must replicate their specific dating convention (Q3 after election) to match their aggregates.
  - Some series availability starts later (e.g., funds rate, wage series backcasting); align series carefully.

## Takeaways For Our Pipeline
- Support multiple windowing conventions:
  - Inauguration-day based, first-quarter-to-predecessor (B&W), and EPI’s Q3-after-election rule.
  - Publish sensitivity tables across conventions.
- Consider adding distributional modules (income growth by quantiles, WID groups) with explicit break handling.
- Keep descriptive comparisons clearly separated from any causal claims.

## Open Questions
- How sensitive are EPI’s headline advantages to alternative dating (e.g., exact inauguration quarter, or 0–4 quarter lags)?
- Can we create a pipeline view that isolates “pandemic shock” effects so comparisons aren’t dominated by a single event?
