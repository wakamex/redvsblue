# Notes: The U.S. Economy Performs Better Under Democratic Presidents - The U.S. Economy Performs Better Under Democratic Presidents - United States Joint Economic Committee

**URL:** https://www.jec.senate.gov/public/index.cfm/democrats/2024/10/the-u-s-economy-performs-better-under-democratic-presidents  
**Authors/Org:** United States Joint Economic Committee (Democrats)  
**Published:** October 7, 2024  
**Retrieved:** 2026-02-09  
**Local files:** `literature/jec-democrats-2024-economy-better-democrats/source.*`, `literature/jec-democrats-2024-economy-better-democrats/source.txt`

## What It Claims
- In the “modern era,” the US economy performs better under Democratic presidents than Republican presidents across a wide set of indicators (jobs, unemployment, growth, manufacturing, small business formation, debt).
- Republican tax cuts for the wealthy/corporations do not boost growth or pay for themselves; Democrats’ middle-class investment approach yields stronger outcomes.
- Recessions disproportionately begin under Republican presidents.

## Data & Definitions
- Metrics mentioned:
  - Total job growth and net job creation/losses.
  - Unemployment rates at start vs end of presidency.
  - Real GDP growth over administrations.
  - Manufacturing job levels and manufacturing construction/investment.
  - New business applications and small-business job creation contribution.
  - National debt changes attributed to presidents/party.
  - Recession “began under” party.
- Time period:
  - Mix of “modern era,” “since early 1980s,” and administration-specific windows (Biden-Harris through Sep 2024).
- Party/presidency coding:
  - Not specified (no explicit term boundary / lag rules).
- Data sources:
  - Page includes external links to supporting writeups (e.g., Washington Post for Trump jobs claim; Brookings/Equitable Growth/CAP for tax-growth claims; other linked sources).
  - Underlying datasets are not directly provided on the page.

## Methodology / Identification
- Summary:
  - Partisan policy explainer + descriptive statistics; not an econometric paper.
- Lags / attribution window / controls / robustness:
  - Not discussed; claims appear to be based on start/end comparisons and totals over administrations, but definitions are not formalized.

## Results (Quantitative)
- Examples of claims on the page:
  - Since early 1980s (last seven presidents): “over 50 million” jobs under Democratic presidents vs “only 17 million” under Republican presidents.
  - Biden-Harris admin: “nearly 16.2 million” jobs added (as of the page date).
  - Trump admin: “2.7 million fewer” employed at end vs start (net job losses).
  - Unemployment: Biden from 6.4% to 4.1% (Sep 2024); Trump from 4.7% to 6.4%.
  - GDP: “10%” growth under Biden-Harris vs “9%” under Trump (claim; window definitions not specified).
  - Manufacturing jobs: -178k under Trump vs +729k under Biden-Harris.
  - Business applications: “nearly 19 million” new applications under Biden-Harris.
  - Recessions: “10 of 11” modern-era recessions began under Republican presidents.

## Strengths
- Provides a compact list of the most commonly cited headline metrics and links to some external supporting material.
- Useful as a target list for our pipeline’s “claim replication” outputs.

## Weaknesses / Risks
- Partisan framing; claims and causal interpretations are not clearly separated.
- No clear methodology for definitions (e.g., what constitutes “job growth total,” which job series, seasonally adjusted vs not, window boundaries, lags).
- Embeds some charting in-page; not a clean primary dataset source.

## Replication Notes
- Code/data availability:
  - No code/data downloads identified in the extracted text; replication requires reconstructing from primary series (BLS/BEA/NBER/Treasury).
- Gotchas:
  - Several claims depend on endpoints (e.g., “start of admin” unemployment rate) and on whether you measure levels, averages, or changes.

## Takeaways For Our Pipeline
- Convert each claim into a structured spec (metric, series id, transform, window) and publish a “replicated vs not replicated” table.
- For administration-specific claims (Biden vs Trump), include explicit cutoff dates (e.g., through 2024-09 for unemployment) and update logic.

## Open Questions
- What exact series and transformations yield the “GDP 10% under Biden vs 9% under Trump” claim?
- How should we treat pandemic-era distortions when comparing start/end job levels and unemployment?
