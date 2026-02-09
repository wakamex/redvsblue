# Notes: Why does the economy do better when Democrats are in the White House?

**URL:** https://www.aeaweb.org/research/why-does-the-economy-do-better-democrats-white-house  
**Authors/Org:** Tim Hyde (American Economic Association “Research Highlights”)  
**Published:** June 20, 2016  
**Retrieved:** 2026-02-09  
**Local files:** `literature/aea-why-economy-better-under-democrats/source.*`, `literature/aea-why-economy-better-under-democrats/source.txt`

## What It Claims
- Summarizes Blinder & Watson’s finding that postwar US economic performance (especially GDP growth) is better under Democratic presidents than Republican presidents.
- Argues the sample size objection can be addressed with a random-reassignment / permutation thought experiment: the observed GDP gap is rare under random party labeling.
- Suggests key correlates of the gap include external factors (oil price shocks, wars/defense spending, foreign growth), productivity, and consumer confidence; fiscal and monetary policy do not explain the gap.

## Data & Definitions
- Metrics:
  - Real GDP growth (core); also unemployment changes, productivity/wages, stock returns, inflation, recession incidence.
- Time period:
  - Post-WWII, 16 presidential terms (1949–2013) as reported in the highlight.
- Party/presidency coding:
  - Based on Blinder & Watson term definitions (with discussion that attribution conventions matter but don’t overturn the result).
- Data sources:
  - Secondary summary; underlying data come from Blinder & Watson (BEA/BLS/FRED/NBER and associated shock series).

## Methodology / Identification
- Summary:
  - Not an original analysis; explains Blinder & Watson’s approach in plain language.
  - Highlights the permutation test: randomly assign party labels to terms (keeping 9 R, 7 D) and compare the distribution of GDP gaps.
- Lags / attribution window:
  - Notes that B&W consider lags; not detailed in the highlight.
- Controls / covariates:
  - Notes B&W find fiscal/monetary policies don’t explain the gap; emphasizes external shocks and wartime mobilization timing.
- Robustness:
  - Mentions the permutation distribution result (gap as large as observed occurs about ~1% of randomized assignments).

## Results (Quantitative)
- GDP growth (B&W as summarized):
  - ~4.33%/year under Democrats vs ~2.54%/year under Republicans (gap ~1.8 pp).
  - Under random reassignment of term-party labels, a gap this large shows up only ~1% of the time.
- Recession incidence:
  - Economy “in recession” about ~7% of the time under Democrats vs ~28% under Republicans (as stated in the highlight).
- Mechanism correlates:
  - Oil prices and wars/defense spending timing materially affect the gap; removing Truman + first Eisenhower term reduces the GDP gap by ~20% (as stated).
  - Productivity, consumer confidence, and European growth also contribute; ~45% of the gap remains unexplained (as stated).

## Strengths
- Clear explanation of the permutation/random-label logic, which is directly implementable in our pipeline as a robustness check.
- Highlights key caveats: association does not automatically imply policy causation; fiscal/monetary policy may not be the driver.

## Weaknesses / Risks
- Secondary source; does not provide full methodological detail or replication code (must refer back to B&W).
- Some statements compress nuance (e.g., wars/oil as “external” even though geopolitical choices can be policy-linked).

## Replication Notes
- Code/data availability:
  - None in the highlight; use B&W replication package for exact reproduction.
- Gotchas:
  - Must implement the party-term permutation test carefully (fixed number of D/R terms; define term boundaries and attribution rules).

## Takeaways For Our Pipeline
- Add a permutation-test module that:
  - Splits history into fixed-length blocks (e.g., 16-quarter terms),
  - Randomly assigns party labels preserving counts,
  - Produces an empirical p-value for observed gaps.
- Provide a “drivers” section with explicit disclaimers:
  - Distinguish plausible correlates (oil, foreign growth, defense) from identified causal effects.

## Open Questions
- How stable are the permutation-test results after adding terms beyond 2013 (including Trump/Biden and the pandemic shock)?
- Can we design a decomposition that is interpretable and avoids post-treatment bias when attributing “drivers”?
