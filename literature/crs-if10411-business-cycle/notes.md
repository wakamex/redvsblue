# Notes: Introduction to U.S. Economy: The Business Cycle and Growth

**URL:** https://crsreports.congress.gov/product/pdf/IF/IF10411  
**Authors/Org:** Congressional Research Service (CRS); Lida R. Weinstock (Analyst in Macroeconomic Policy)  
**Published:** Updated October 3, 2024 (IF10411, Version 13; originally authored by Jeffrey Stupak)  
**Retrieved:** 2026-02-09  
**Local files:** `literature/crs-if10411-business-cycle/source.*`, `literature/crs-if10411-business-cycle/source.txt`

## What It Claims
- “Recession” is **not** defined by NBER as “two consecutive quarters of negative real GDP.” NBER uses a broader definition: a significant, persistent decline in activity spread across the economy, using multiple indicators (GDP, employment, sales, industrial production, etc.).
- Business cycles are dated using **peaks and troughs** of economic activity; expansions and contractions vary in duration and are not smooth or predictable.
- Post-WWII, expansions have tended to be longer and recessions shorter (on average) than pre-WWII.

## Data & Definitions
- Metrics:
  - Real GDP (inflation-adjusted output) as the broadest measure of activity; plus indicators like employment, real sales, industrial production.
- Time period:
  - Discusses NBER dating generally since the 1850s; provides summary stats and figures for 1947:Q1-2024:Q2.
- Party/presidency coding:
  - None (this is measurement/macro background, not a partisan comparison).
- Data sources:
  - NBER Business Cycle Dating Committee; U.S. Bureau of Economic Analysis (GDP).

## Methodology / Identification
- Summary:
  - Expository “In Focus” memo: definitions, historical context, and mechanisms (demand vs supply shocks; fiscal/monetary policy as countercyclical tools).
- Lags / attribution window:
  - Not applicable.
- Controls / covariates:
  - Not applicable.
- Robustness:
  - Not applicable.

## Results (Quantitative)
- Notes examples of recession durations: COVID recession ~2 months; Great Recession 18 months (Dec 2007-Jun 2009).
- Reports average annual real GDP growth of ~3.1% over 1947:Q1-2024:Q2 (as presented in the CRS figure).
- Post-WWII (1945-2019), average expansion ~65 months and average recession ~11 months; pre-WWII expansions shorter and recessions longer (as described in the memo).

## Strengths
- Clear, nonpartisan definitions from a government research arm; explicitly corrects a common recession misconception used in media/political claims.
- Useful operational guidance for building a “recession under presidents” metric using NBER dates rather than ad hoc rules.

## Weaknesses / Risks
- Not a research paper; does not provide a partisan attribution framework or causal analysis.
- “In Focus” documents are concise and may omit nuances needed for econometric work.

## Replication Notes
- Code/data availability:
  - CRS documents are U.S. government works (generally reproducible); underlying data is from NBER/BEA.
- Any gotchas:
  - For pipeline implementation: treat NBER recession “dates” (monthly peaks/troughs) carefully when mapping to quarterly series (GDP) and presidential terms.

## Takeaways For Our Pipeline
- Use **NBER recession dates** (not “two negative quarters”) for any recession/expansion labeling.
- When mapping recessions to presidents, document the join rule (monthly NBER dates vs inauguration dates vs quarterly aggregation).

## Open Questions
- For a partisan comparison, should we treat “recession months” as the target metric, or use recession start/peak attribution (who inherited it) with explicit lag rules?
