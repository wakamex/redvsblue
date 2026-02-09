# Notes: Clinton: Economy Better Under Democrats - FactCheck.org

**URL:** https://www.factcheck.org/2015/10/clinton-economy-better-under-democrats/  
**Authors/Org:** Robert Farley (FactCheck.org)  
**Published:** October 20, 2015  
**Retrieved:** 2026-02-09  
**Local files:** `literature/factcheck-2015-economy-better-democrats/source.*`, `literature/factcheck-2015-economy-better-democrats/source.txt`

## What It Claims
- Clinton’s claim that “the economy does better when you have a Democrat in the White House” is supported by Blinder & Watson’s empirical findings (as a descriptive average).
- However, the Princeton authors do not attribute the growth gap to Democratic fiscal or monetary policy; they find fiscal/monetary shocks do not explain the partisan gap.
- Multiple external factors (oil, productivity, defense spending/war, foreign growth, consumer expectations) explain a large share of the gap, but a portion remains unexplained.
- Fact-checking should distinguish “gap exists” from “Democratic policies caused the gap.”

## Data & Definitions
- Metrics discussed (via Blinder & Watson summary):
  - Real GDP growth; unemployment level vs change; stock market returns (S&P 500); recession quarters (NBER dating); inflation.
- Time period:
  - Blinder & Watson’s postwar sample beginning with Truman through Obama (as summarized).
- Party/presidency coding:
  - Not specified in the FactCheck article; it references B&W’s conventions.
- Data sources:
  - Secondary analysis summarizing B&W; includes mention of NBER recession classification.

## Methodology / Identification
- Summary:
  - FactCheck-style synthesis of B&W’s documented numbers and caveats, plus reporting on author interviews.
- Identification:
  - Emphasizes the difference between correlation and causal attribution; notes B&W’s limited success in pinning down causal channels.

## Results (Quantitative)
- Selected figures quoted from B&W (as reported):
  - GDP growth: ~4.33% (Dem) vs ~2.54% (Rep), gap ~1.79 pp.
  - Unemployment level: ~5.64% (Dem) vs ~6.01% (Rep), described as “small and not statistically significant.”
  - Change in unemployment: -0.8 pp (Dem terms) vs +1.1 pp (Rep terms), gap ~-1.9 pp.
  - S&P 500 returns: ~8.35% (Dem) vs ~2.7% (Rep), gap ~5.65 pp; significance limited by volatility.
  - Recession quarters (NBER): 41 of 49 recession quarters under Republicans in their sample.
  - Inflation: “about equally well under presidents of either party.”
- Mechanism share:
  - Oil, productivity, defense spending, foreign growth, and consumer expectations can explain “as much as 70%” of the gap (as reported).

## Strengths
- Good “translation layer” between academic work and political claims; highlights the key caveat (gap ≠ proof of policy causation).
- Includes direct reporting on the paper authors’ interpretations and revisions.

## Weaknesses / Risks
- Relies heavily on a single core academic source (B&W) rather than independent replication.
- Still framed around a political talking point; could inherit framing biases (though caveats are explicit).

## Replication Notes
- Code/data availability:
  - None; replication should use B&W replication materials and/or our pipeline’s primary-data reconstruction.
- Gotchas:
  - The statement “100% accurate” refers to historical averages, not a deterministic “always” claim and not causal identification.

## Takeaways For Our Pipeline
- Our outputs should explicitly separate:
  - “Historical averages by party” (what FactCheck treats as supported),
  - “Policy causation” (largely unresolved).
- Include a “claim language” layer: flag words like “always” and translate to “on average,” with uncertainty bands.

## Open Questions
- How should we communicate the “unexplained remainder” without inviting speculative narratives?
- What is the cleanest way to quantify uncertainty with so few presidential terms (term-cluster inference vs permutation tests)?
