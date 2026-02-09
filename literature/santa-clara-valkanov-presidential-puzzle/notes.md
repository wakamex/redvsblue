# Notes: Political Cycles and the Stock Market

**URL:** https://www.escholarship.org/uc/item/00n6f3ph.pdf  
**Authors/Org:** Pedro Santa-Clara; Rossen Valkanov (UCLA Anderson)  
**Published:** June 2001 (working paper PDF; eScholarship record lists “Publication Date 2000-06-01”)  
**Retrieved:** 2026-02-09  
**Local files:** `literature/santa-clara-valkanov-presidential-puzzle/source.*`, `literature/santa-clara-valkanov-presidential-puzzle/source.txt`

## What It Claims
- U.S. stock market **excess returns are substantially higher under Democratic presidents** than Republican presidents (1927-1998), by about **9 percentage points/year** for the value-weighted portfolio and **16 percentage points/year** for the equal-weighted portfolio.
- The “presidential puzzle” is **robust** (subsamples, different inference procedures) and **not explained** by (a) business-cycle proxy variables, (b) election-day surprise returns, or (c) higher risk/volatility under Democrats.
- Party control of Congress (House/Senate majorities) and interactions with the presidency do **not** show a statistically significant relationship with excess stock returns (in their tests), suggesting most of the pattern is about the White House indicator in this dataset.
- The effect is **larger for small firms** (monotone size-decile pattern) and varies by **industry**, suggesting possible channels via fiscal/regulatory policy (though they do not claim a definitive mechanism).

## Data & Definitions
- Metrics:
  - Monthly log returns for CRSP value-weighted and equal-weighted market portfolios; excess returns over 3-month T-bill; “real” returns net of inflation.
  - Cross-sectional returns: 10 size-decile portfolios + 48 industry portfolios (Kenneth French data library).
  - Volatility: within-month daily return volatility (French-Schwert-Stambaugh style).
- Time period:
  - Main sample: 1927:01-1998:12 (863 monthly obs; 18 elections).
  - Subsamples: post-WWII (1946:01-1998:12), post-WWII excluding 1994-1998, and 1960:01-1998:12.
- Party/presidency coding:
  - Monthly indicator variables `RD_t` (=1 if Republican president in office) and `DD_t` (=1 if Democratic president in office).
  - Note: the PDF does not clearly spell out how “inauguration months” are coded at monthly frequency (important for attribution in any replication).
- Data sources:
  - CRSP (market returns); Ibbotson (3-month T-bill + inflation); Kenneth French (size/industry portfolios); Schwert (daily returns); NBER (business cycle dates used as a control).

## Methodology / Identification
- Summary:
  - Regression of next-month returns on presidential-party dummy (equivalent to comparing mean returns under each party), with Newey-West standard errors.
  - Robustness checks: randomization-bootstrap/permutation-style inference (10,000 draws resampling returns and political variables independently under the null) + quantile regressions to reduce outlier sensitivity.
- Lags / attribution window:
  - Monthly analysis aligned to “presidential mandates” (party-in-office dummies). Also tests whether effects concentrate around elections vs accruing gradually over the term.
- Controls / covariates:
  - “Proxy” test adds standard return predictors / business-cycle proxies: dividend-price ratio, term spread, default spread, relative interest rate, and NBER business cycle indicator/dates.
- Robustness:
  - Multiple subsamples, alternative inference (Newey-West vs bootstrap), outlier checks (quantile regression), cross-sectional (size/industry) patterns.

## Results (Quantitative)
- Excess return gap (Dem minus Rep): ~**+9%/year** (value-weighted) and **+16%/year** (equal-weighted) for 1927-1998.
- Size monotonicity: gap rises from ~**+7%** for largest firms to ~**+22%** for smallest firms (size-decile portfolios).
- Volatility is not higher under Democrats; if anything, volatility is higher under Republicans (weakening a “risk compensation” story).

## Strengths
- Clear baseline statistic (mean return differences) plus multiple robustness layers that explicitly target small-sample inference issues.
- Uses both market-wide and cross-sectional evidence (size/industry), which helps constrain plausible mechanisms.

## Weaknesses / Risks
- Largely an **association** study; party-in-office dummies could pick up other correlated forces (global shocks, policy regimes, war/peace, Fed reaction functions, etc.).
- Small number of independent “regime switches” (presidencies) remains a fundamental limitation even with bootstrap-style inference.
- Sample ends in 1998 (important for any “current era” claims); replication should extend to present and evaluate stability.
- Presidency-to-month assignment rules around inauguration dates are not explicit in the extracted text (replication ambiguity).

## Replication Notes
- Code/data availability:
  - Data sources are standard (CRSP, Ken French, NBER dates); paper does not bundle a full replication package in this PDF.
- Any gotchas:
  - Ensure consistent use of log returns vs simple returns; annualize correctly; define excess/real returns as in the paper.
  - Decide (and document) the exact rule mapping monthly returns to presidents during inauguration months.

## Takeaways For Our Pipeline
- Treat “D vs R performance” as a **small-sample regime comparison** problem: include randomization/permutation tests and report uncertainty bands.
- Pre-register and publish the **attribution rule** (when a term “starts” for each metric, lags, inauguration handling).
- Keep “scoreboard” (raw differences by party) separate from “explanations” (controls, mechanisms), and test stability across time and subsamples.

## Open Questions
- Does the magnitude/pattern persist post-1998 (including 2000s-2020s), and does it survive alternative term-start rules (Q1/Q2/Q3 after inauguration/election)?
- Are the cross-sectional patterns (size, industries) stable, and do they line up with plausible fiscal/regulatory channels in a way we can test?
