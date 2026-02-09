# Notes: The Historical Puzzle of US Economic Performance under Democrats vs. Republicans | The Belfer Center for Science and International Affairs

**URL:** https://www.belfercenter.org/publication/historical-puzzle-us-economic-performance-under-democrats-vs-republicans  
**Authors/Org:** Jeffrey Frankel (Belfer Center)  
**Published:** March 28, 2024  
**Retrieved:** 2026-02-09  
**Local files:** `literature/belfer-frankel-2024-historical-puzzle/source.*`, `literature/belfer-frankel-2024-historical-puzzle/source.txt`

## What It Claims
- Since World War II, US macro performance has been consistently better under Democratic presidents than Republican presidents (a “historical puzzle” analogous to the Biden perception gap).
- These differences are large enough that “standard statistical methodology” rejects the idea they are purely random chance.
- The causal explanation remains unclear; “it remains a puzzle.”

## Data & Definitions
- Metrics:
  - Average job creation growth rates by party.
  - Average GDP growth rates by party.
  - Recession incidence and recession “starts under” a party.
  - Term-to-term growth changes at party transitions.
- Time period:
  - Post-WWII data covering “19 presidential terms — from Truman through Biden” (as stated in the article).
  - Mentions that extending back to Hoover/FDR increases the gap.
- Party/presidency coding:
  - Not fully specified; references that results are similar “regardless whether one assigns responsibility for the first quarter… to him or to his predecessor.”
- Data sources:
  - Secondary summary; points readers to check recession chronology at NBER; cites Blinder & Watson and references compiled statistics “updated.”

## Methodology / Identification
- Summary:
  - Narrative + descriptive statistics, with informal “coin-flip” probability calculations for recession-start patterns and for party-transition patterns.
- Lags / attribution window:
  - Discusses that first-quarter assignment convention does not change the qualitative result.
- Controls / covariates / robustness:
  - No econometric controls; statistical reasoning is informal and assumes independence in some back-of-envelope probability calculations.

## Results (Quantitative)
- Claims reported (post-WWII):
  - Job creation: ~1.7%/year (Democrats) vs ~1.0%/year (Republicans).
  - GDP growth: ~4.23%/year (Democrats) vs ~2.36%/year (Republicans), difference ~1.87 percentage points.
  - Recession time per term: ~1 of 16 quarters (Democratic term average) vs ~5 of 16 (Republican term average).
- Probability-style claims:
  - “Last five recessions started under a Republican” -> “1/32” if equal-probability coin flips.
  - “9 of last 10 recessions started under a Republican” -> “~1/100” (rough claim).
  - Party transitions since WWII updated through Trump/Biden: growth always goes down when D->R and up when R->D (10/10), claimed odds 1/1024 under coin flips.

## Strengths
- Clear, accessible summary of the “puzzle” and a useful set of concrete claims to verify (GDP/job growth by party, recession incidence, party-transition pattern).
- Explicitly distinguishes “pattern is real” from “causal channel is unclear.”

## Weaknesses / Risks
- Informal probability calculations can be misleading:
  - Recessions are not independent Bernoulli draws; party tenures have unequal durations; and “start under X” depends on attribution rules.
  - Some calculations in the article appear simplified (e.g., using `1/2^n` approximations rather than exact binomial tails).
- Not a primary empirical analysis; relies on secondary compiled statistics.

## Replication Notes
- Code/data availability:
  - None; should be re-derived from primary data (BEA/BLS + NBER dates + presidency calendar).
- Gotchas:
  - Must define “recession started under president/party” consistently (month/quarter boundaries; inauguration timing).

## Takeaways For Our Pipeline
- Include a “popular-claims audit” module that reproduces these headline numbers and shows sensitivity to window definitions.
- When reporting “odds/chance” arguments, compute exact binomial (or permutation) probabilities *and* disclose assumptions (independence, equal probability, equal exposure time).
- Provide a “party transition” view: growth changes at D->R vs R->D transitions with confidence intervals.

## Open Questions
- Which exact job series and GDP definitions underpin the quoted growth rates (employment level vs growth; real GDP vs per-capita vs NDP)?
- How should a modern update handle the pandemic recession and post-pandemic rebound (which can dominate short windows)?
