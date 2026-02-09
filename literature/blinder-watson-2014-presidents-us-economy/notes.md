# Notes: Presidents and the U.S. Economy: An Econometric Exploration

**URL:** https://www.nber.org/system/files/working_papers/w20324/w20324.pdf  
**Authors/Org:** Alan S. Blinder; Mark W. Watson (NBER Working Paper 20324)  
**Published:** July 2014 (working paper; later published in *American Economic Review* 106(4), April 2016)  
**Retrieved:** 2026-02-09  
**Local files:** `literature/blinder-watson-2014-presidents-us-economy/source.*`, `literature/blinder-watson-2014-presidents-us-economy/source.txt`

## What It Claims
- Postwar US macro performance is systematically better under Democratic presidents than Republican presidents (most notably real GDP growth).
- The GDP growth gap is statistically significant despite the small number of presidential terms.
- The gap is *not* explained by technical time-series issues (trends, mean reversion) nor by systematically more expansionary fiscal/monetary policy under Democrats.
- A substantial fraction of the gap is associated with “luck/mechanisms” like oil shocks, TFP/productivity, international conditions, and consumer expectations; the remainder is not fully explained.

## Data & Definitions
- Metrics (examples reported in Table 1 and discussion):
  - Real GDP growth (main focus); GDP per capita; nonfarm business output; industrial production.
  - Employment growth (payroll, hours); unemployment level and change.
  - Stock market returns (S&P 500); corporate profit share; productivity/TFP; inflation; interest rates; structural deficit (CBO).
  - Recession incidence using NBER recession dating.
- Time period:
  - Main postwar sample: quarterly data starting 1947:Q1 / 1949:Q2 through ~2013:Q1 (varies slightly by series).
  - They also discuss longer historical extensions using reconstructed pre-1947 GDP (Owyang, Ramey, Zubairy building on Balke & Gordon).
- Party/presidency coding:
  - Group observations into 4-year presidential terms; default “one-quarter lag”: the first quarter of an incoming president is attributed to the predecessor.
  - They show sensitivity to alternative lags (0,2,3,4 quarters).
- Data sources:
  - BEA NIPA for GDP and components; BLS for labor market series; NBER for recession dates; CBO for structural deficits; other sources for identified shocks (oil, TFP, etc.).

## Methodology / Identification
- Summary:
  - Mostly descriptive comparisons (Dem vs Rep averages) plus statistical inference tailored to small samples.
  - Then regress/decompose the partisan gap using identified shocks and policy measures to see what correlates with the gap.
- Lags / attribution window:
  - Baseline assigns the first quarter of a presidency to the previous president; alternative lags tested and reported to be qualitatively similar but smaller.
- Controls / covariates (for “why”):
  - Initial conditions and inherited growth.
  - Congress party / Fed chair appointment (they find presidency party matters most).
  - “Luck/mechanisms”: oil shocks, productivity/TFP shocks, international growth shocks, consumer expectations shocks; defense spending/war dynamics.
  - Fiscal and monetary policy shocks/reaction functions are examined and found not to explain the GDP gap (and sometimes point the “wrong” way).
- Robustness / inference:
  - Term-clustered standard errors (effective sample size is #terms), HAC/Newey-West, and a nonparametric random-assignment (permutation) test re-labeling terms as D/R.

## Results (Quantitative)
- Real GDP growth (postwar, terms 1949–2013): ~4.35% annualized under Democrats vs ~2.54% under Republicans (gap ~1.80 percentage points; statistically significant).
- Recession incidence (same postwar window, using NBER dating): far more recession quarters under Republicans than Democrats (reported as 41 vs 8 recession quarters in their 16-term sample; also expressed as ~4.6 quarters/term Rep vs ~1.1 quarters/term Dem).
- Other “directional” results highlighted:
  - Payroll employment growth higher under Democrats; unemployment rate tends to fall under Dem terms and rise under Rep terms (change in unemployment is a large gap).
  - S&P 500 returns higher under Democrats (large point estimate but weaker significance due to volatility).
  - TFP faster under Democrats in raw measures, but gap shrinks when adjusting for utilization (important caveat).

## Strengths
- Explicitly confronts small-sample inference (term clustering, HAC, permutation tests).
- Separates “fact of gap” from “causal attribution,” and tests a wide menu of candidate explanations.
- Clear documentation of coding choices (term boundaries, lags) and sensitivity checks.
- Provides replication materials (see below), making it a good anchor paper for a reproducible pipeline.

## Weaknesses / Risks
- Fundamental identification limit: party-of-president is not randomly assigned; “better under Democrats” is a robust association, but causal channels remain uncertain.
- Results are sensitive (in magnitude) to attribution windows, sample endpoints, and whether partial terms / unusual shocks (e.g., wars, pandemics) are included.
- “Explaining the gap” via observed shocks risks post-treatment bias or misattribution (some shocks may themselves be endogenous to policy/geo events).

## Replication Notes
- Code/data availability:
  - Paper states replication files are available from Mark Watson’s Princeton page (includes a zip labeled replication files and a PDF appendix).
- Gotchas:
  - Their baseline allocates the first quarter of each presidency to the prior president; many popular summaries ignore this (so we should parameterize it).
  - Multiple series have different start dates; exact replication requires careful alignment and use of their shock series definitions.

## Takeaways For Our Pipeline
- Implement *parameterized* presidency windows (term vs presidency; lags 0–4 quarters; month/quarter assignment rules) and report sensitivity tables.
- Use small-sample-robust inference:
  - Term-clustered SEs and/or Ibragimov-Müller-style “few clusters” inference.
  - A permutation/random-label test over 4-year blocks as a nonparametric check.
- Maintain an “association” dashboard (party averages) *separate* from any “explanation” module (shock decomposition, policy attribution).
- Track recession dating using a canonical series (NBER peaks/troughs) and define “recession started under X” carefully (month/quarter boundaries).

## Open Questions
- How does the GDP gap evolve when extending beyond 2013 (Obama-2, Trump, Biden, and post-pandemic normalization)? How sensitive are results to including the pandemic recession?
- Can we design a decomposition that avoids post-treatment bias and communicates uncertainty (e.g., Bayesian structural time series / synthetic controls / forecast error decompositions)?
