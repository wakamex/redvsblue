# Notes: Does the Economy Really Do Better Under Democratic Presidents? | The Belfer Center for Science and International Affairs

**URL:** https://www.belfercenter.org/publication/does-economy-really-do-better-under-democratic-presidents  
**Authors/Org:** Jeffrey Frankel (Belfer Center)  
**Published:** June 27, 2016  
**Retrieved:** 2026-02-09  
**Local files:** `literature/belfer-2016-economy-better-democrats/source.*`, `literature/belfer-2016-economy-better-democrats/source.txt`

## What It Claims
- Hillary Clinton’s claim that “the economy does better when we have a Democrat in the White House” is true as a descriptive statement (historical averages), but does not imply Democrats *caused* the performance gap.
- Fact-checkers conflate “gap exists” with “causal channels identified”; the latter is much harder and remains partly unexplained.
- Blinder & Watson (AER) find fiscal and monetary policy shocks do not explain the gap; several external factors (oil, productivity, defense spending, foreign growth, consumer confidence) explain a portion.

## Data & Definitions
- Metrics highlighted (via Blinder & Watson summary):
  - Real GDP growth, recession incidence, unemployment changes, stock market returns, structural budget deficit.
- Time period:
  - Postwar, 16 complete presidential terms from Truman through Obama (as summarized).
- Party/presidency coding:
  - Notes that results are similar regardless of whether one assigns the first quarter(s) of a term to the new president or predecessor.
- Data sources:
  - Secondary commentary; relies on Blinder & Watson for the underlying computations.

## Methodology / Identification
- Summary:
  - Commentary/interpretation piece rather than original econometrics.
  - Uses simple probability arguments (recession-start “coin flips,” transition patterns) to illustrate statistical unlikelihood under pure chance.
- Lags / attribution window:
  - Emphasizes that attribution-window choice does not overturn the headline gap.
- Controls / covariates / robustness:
  - Does not add new controls; summarizes Blinder & Watson’s causal exploration and stresses limits.

## Results (Quantitative)
- Numbers quoted (from Blinder & Watson):
  - GDP growth averages ~4.3% (Democrats) vs ~2.5% (Republicans), gap ~1.8 percentage points.
  - Average recession quarters per term: ~1.1 (Democratic) vs ~4.6 (Republican).
  - Change in unemployment over terms: -0.8 pp (Democratic) vs +1.1 pp (Republican), gap ~1.9 pp.
  - S&P 500 returns: ~8.4% (Democratic) vs ~2.7% (Republican), gap ~5.7 pp (not as statistically strong).
  - Structural deficit: ~1.5% (Democratic) vs ~2.2% (Republican), not statistically strong.
- “Mechanism share” claim:
  - Mentions several factors together explaining roughly ~56% of the gap (oil, productivity, defense spending, foreign growth, consumer confidence).

## Strengths
- Clear distinction between “association exists” and “causation/policy attribution is known.”
- Good framing for how our pipeline should communicate results to avoid overclaiming.

## Weaknesses / Risks
- Not a primary analysis; relies on others’ work.
- Uses informal probability/coin-flip analogies that can be misread as rigorous inference without the needed assumptions (independence, equal exposure).

## Replication Notes
- Code/data availability:
  - None in this post; replication should be done from primary data or from Blinder & Watson replication packages.
- Gotchas:
  - The claim “100% true” in the post is rhetorical; operationally we should report “on average” with uncertainty and exceptions (e.g., individual administrations can deviate).

## Takeaways For Our Pipeline
- Separate dashboards:
  - “What happened” (party-conditional averages).
  - “Why it happened” (explicitly marked as hypotheses with partial explanatory power).
- Provide language discipline:
  - Replace “always” with “on average” and quantify uncertainty and sensitivity.

## Open Questions
- How should a modern update treat atypical shocks (e.g., 2020 pandemic) without letting them dominate the inference?
- How do we present findings in a way that is neither partisan spin nor false balance?
