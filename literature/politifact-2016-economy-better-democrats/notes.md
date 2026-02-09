# Notes: PolitiFact |  Does the economy always do better under Democratic presidents?

**URL:** https://www.politifact.com/factchecks/2016/apr/06/hillary-clinton/does-economy-always-do-better-under-democratic-pre/  
**Authors/Org:** Anthony Cave (PolitiFact)  
**Published:** April 6, 2016  
**Retrieved:** 2026-02-09  
**Local files:** `literature/politifact-2016-economy-better-democrats/source.*`, `literature/politifact-2016-economy-better-democrats/source.txt`

## What It Claims
- Confirms that (per Blinder & Watson) average GDP growth has been higher under Democratic presidents in postwar data, but argues Clinton’s wording “always” requires caveats.
- Emphasizes that other factors (oil prices, international conditions, inherited conditions) can drive the observed averages; president has limited control.
- Concludes the claim is “Half True” because:
  - It’s not literally always true for every president/period, and
  - Comparisons are sensitive to time periods and confounding factors.

## Data & Definitions
- Metrics:
  - Gross Domestic Product (GDP) growth (focus).
  - Mentions unemployment rate and other macro indicators in passing.
- Time period:
  - Cites quarterly GDP data dating back to 1947 (as per B&W); also references growth through last quarter of 2015 via an expert’s calculations.
- Party/presidency coding:
  - Not specified; relies on B&W’s conventions and an external expert’s computations.
- Data sources:
  - B&W study (Princeton economists) as the main quantitative source.
  - Quotes/interviews with academics/experts; cites a Heritage Foundation report for one “inherited expansion” claim.

## Methodology / Identification
- Summary:
  - PolitiFact-style evaluation: summarizes B&W findings and interviews experts who highlight caveats and alternative interpretations.
- Identification:
  - Treats party-performance differences as potentially confounded; does not attempt new causal analysis.

## Results (Quantitative)
- Reports (via B&W and an expert’s calculation):
  - Democrats have higher average GDP growth than Republicans in postwar quarterly data (exact B&W numbers not fully enumerated in the extracted snippet, but referenced as higher).
  - Christian Weller calculation (through 2015): ~3.8% real growth under Democrats vs ~2.4% under Republicans (as quoted).
  - Notes Reagan’s growth rate as higher than Obama’s at the time, used to argue “not always.”

## Strengths
- Useful for cataloging common objections and caveats (wording “always,” inherited conditions, confounding shocks).
- Provides pointers to alternative narratives and sources that we can explicitly test in the pipeline (e.g., “expansion already underway” at a handoff).

## Weaknesses / Risks
- Not a primary statistical analysis; much depends on qualitative judgments about what caveats “should” downgrade the rating.
- Incorporates politically motivated sources (e.g., Heritage) alongside academic work; must separate evidence quality.

## Replication Notes
- Code/data availability:
  - None; should be replicated from primary data (BEA/BLS/NBER) and B&W replication materials.
- Gotchas:
  - “Always” is a linguistic claim; quantitative pipeline should instead show distributions across administrations and the probability of exceptions.

## Takeaways For Our Pipeline
- Publish both:
  - The average gap by party, and
  - A per-administration/term breakdown that makes exceptions obvious (so “always” can be evaluated precisely).
- Include an “inherited conditions” view:
  - Show economic state at handoff and first-year/first-quarter attribution sensitivity.

## Open Questions
- What is the cleanest quantitative way to represent “inherited conditions” at transitions (e.g., conditional on lagged growth / recession state)?
- How should we formalize the evaluation of absolute claims (“always”) vs probabilistic/average claims?
