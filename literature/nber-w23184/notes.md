# Notes: Political Cycles and Stock Returns

**URL:** https://www.nber.org/system/files/working_papers/w23184/w23184.pdf  
**Authors/Org:** Lubos Pastor; Pietro Veronesi (NBER Working Paper 23184)  
**Published:** February 2017 (revised May 2019)  
**Retrieved:** 2026-02-09  
**Local files:** `literature/nber-w23184/source.*`, `literature/nber-w23184/source.txt`

## What It Claims
- The “presidential puzzle” in US stock returns (higher average returns under Democratic presidents) can arise endogenously from time-varying risk aversion.
- Causal direction is largely *not* “Democrats cause higher returns”; instead, high risk aversion raises risk premia and also increases the likelihood of electing Democrats (redistribution party). Risk aversion then mean-reverts, contributing to higher realized returns early in Democratic terms.
- The same mechanism can help explain faster average economic growth under Democratic presidencies and several micro-political patterns (risk aversion differences across voters, occupational voting patterns).

## Data & Definitions
- Metrics:
  - Excess stock market returns (value-weighted market return minus 3-month T-bill, log returns), plus volatility/Sharpe ratios.
  - Real GDP growth comparisons by party (as a macro “gap” parallel to stock returns).
  - International stock return comparisons conditioned on US president’s party.
- Time period:
  - Stock returns: monthly, 1927–2015 in their extension of Santa-Clara & Valkanov’s earlier sample.
  - GDP growth: reported for 1930–2015 (and post-WWII subset).
- Party/presidency coding:
  - Monthly Democrat dummy `D=1` if a Democratic president is in office.
  - Transition rule: assign the month in which a term ends to the outgoing president (e.g., January inauguration -> January credited to prior president; February to new president).
- Data sources:
  - CRSP: value-weighted market returns and T-bill returns (for excess returns).
  - BEA: real GDP growth.
  - FRED used for some international rate series (mentioned in international evidence section).

## Methodology / Identification
- Summary:
  - Structural model: general equilibrium political-economy + asset pricing with time-varying risk aversion; endogenous election outcomes; equilibrium risk premia.
  - Empirics: party dummy regressions for returns/growth; comparisons across subperiods; HAC-robust inference.
- Lags / attribution window:
  - Uses a specific month assignment convention at transitions (see above); notes that switching January assignment yields similar results.
  - For returns, highlights that the party return gap is larger early in presidential terms (consistent with mean reversion in risk aversion).
- Controls / covariates:
  - Not primarily a “controls” paper; instead provides a mechanism and then checks multiple empirical implications (including risk/volatility and uncertainty channels, and international spillovers).
- Robustness:
  - t-stats based on standard errors robust to heteroscedasticity and autocorrelation.
  - Subsample splits (two and three equal subperiods) and out-of-sample extensions through 2015.

## Results (Quantitative)
- US excess stock returns (1927–2015):
  - ~10.69%/year under Democrats vs ~-0.21%/year under Republicans (gap ~10.90%/year; t ≈ 2.73, HAC-robust).
  - Gap persists across subperiods; reported as larger in 1999–2015 (~17.39%/year; t ≈ 2.14).
  - Volatility lower under Democrats (~17.33% vs ~20.00%); Sharpe ratio much higher under Democrats (~0.62 vs ~-0.01).
  - Return gap is largest early in terms (e.g., first-year gap reported as very large).
- Real GDP growth (1930–2015):
  - ~4.86%/year under Democrats vs ~1.70%/year under Republicans (gap ~3.16%/year; t ≈ 2.40); post-WWII gap smaller but still positive.
- International: for five large developed countries, average excess returns are higher when the US president is a Democrat (differences ~7–14%/year; significant in most).

## Strengths
- Provides a coherent mechanism that links elections to risk premia without requiring implausibly large “policy causes returns” assumptions.
- Extends and stress-tests the presidential return gap through 2015; checks volatility/uncertainty explanations and rejects simple “higher risk under Democrats” stories.
- Transparent party-coding convention and use of HAC-robust inference.

## Weaknesses / Risks
- Strong structural assumptions (risk aversion process, occupational choice/voting, redistribution mapping to parties); mechanism plausibility depends on these.
- Risk aversion is not directly observable; empirical validation rests on proxies and auxiliary predictions.
- Stock-return “party effects” are sensitive to sample endpoints and rare events; need to validate persistence in newer data (post-2015).

## Replication Notes
- Code/data availability:
- Gotchas:
  - Transition month assignment affects headline numbers slightly; must match their convention for replication.
  - Use of log returns + excess returns (vs simple returns) is a specific choice (they note simple returns are similar).

## Takeaways For Our Pipeline
- If we include finance metrics, implement stock return computations exactly (CRSP series, excess log returns) and report party differences with HAC-robust SEs.
- Make party-coding and transition conventions explicit and parameterized (month/quarter attribution; “first-month/quarter belongs to predecessor” toggles).
- Keep “mechanism” and “measurement” separate:
  - Measurement: party-conditional averages.
  - Mechanism module: risk aversion proxies (e.g., VIX, survey-based risk tolerance) and mean-reversion tests, if we want to reproduce their explanatory story.

## Open Questions
- Does the Democratic-vs-Republican excess return gap persist when updated through 2025/2026? How much is driven by a small number of administrations?
- Which risk-aversion proxies best operationalize their mechanism in a modern, fully automated pipeline?
