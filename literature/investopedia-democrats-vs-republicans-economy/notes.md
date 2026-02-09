# Notes: Democrats vs. Republicans: Who Had More National Debt?

**URL:** https://www.investopedia.com/democrats-vs-republicans-who-had-more-national-debt-8738104  
**Authors/Org:** Hiranmayi Srinivasan (Investopedia)  
**Published:** December 16, 2024 (page metadata); Updated February 4, 2026 (page text)  
**Retrieved:** 2026-02-09  
**Local files:** `literature/investopedia-democrats-vs-republicans-economy/source.*`, `literature/investopedia-democrats-vs-republicans-economy/source.txt`

## What It Claims
- The US national debt exceeded ~$38T in February 2026 and continues to grow.
- Republican presidents have added slightly more to the national debt **per four-year term** than Democratic presidents (inflation-adjusted), though Democrats added more in total due to more years in office since 1913.
- Debt outcomes are heavily shaped by major events (wars, recessions, public health crises) and by fiscal policy choices.

## Data & Definitions
- Metrics:
  - National debt levels and increases, including inflation-adjusted debt added per term and total.
  - Mentions debt impact estimates of policy plans (CRFB) for 2024 election candidates.
- Time period:
  - Debt comparisons “since 1913” through end of fiscal 2024 (for per-term comparisons), plus narrative updates through February 2026 for current debt level.
- Party/presidency coding:
  - Not fully specified; implied per-term comparisons across administrations.
- Data sources (as cited in the article text):
  - US Treasury (Fiscal Data / “Debt to the Penny”), BLS (inflation adjustment), Federal Reserve of St. Louis (debt holders), Peter G. Peterson Foundation, CRFB, National Archives, Brown University “Costs of War” project, etc.

## Methodology / Identification
- Summary:
  - Descriptive comparisons; does not attempt causal identification.
  - Adjusts debt changes for inflation (implied by “inflation-adjusted data”).

## Results (Quantitative)
- Headline figures reported:
  - National debt ~$38.56T in February 2026.
  - Inflation-adjusted debt added per 4-year term since 1913: ~+$1.4T (Republicans) vs ~+$1.2T (Democrats).
  - Total inflation-adjusted debt added since 1913: ~+$18.0T (Democrats) vs ~+$17.3T (Republicans).
  - Trump “added the most national debt per term”: ~+$7.1T (as stated).
  - CRFB estimate (campaign plans): Harris +$3.95T through 2035 vs Trump +$7.75T (as quoted).

## Strengths
- Useful popular synthesis focused on a single metric (debt), with explicit citations to primary sources and nonpartisan analyses (CRFB/Peterson Foundation).
- Updated recently (Feb 2026) which is relevant for a “current” pipeline.

## Weaknesses / Risks
- Per-term dollar comparisons can be misleading without scaling by GDP and without separating baseline/inherited deficits from policy changes.
- “Debt added under a president” depends heavily on window definitions (fiscal year vs calendar year, inauguration timing), inflation adjustment method, and treatment of extraordinary shocks (wars, pandemics).
- Not a peer-reviewed analysis; should be treated as a secondary explainer.

## Replication Notes
- Code/data availability:
  - No code; underlying primary data are available from Treasury Fiscal Data and BLS price indices.
- Gotchas:
  - Define “debt added” precisely:
    - Debt held by the public vs gross debt,
    - Nominal vs real vs %GDP,
    - Start/end dates aligned to fiscal years or presidential terms.

## Takeaways For Our Pipeline
- Include fiscal metrics as:
  - Nominal debt change, real debt change, and debt-to-GDP change.
  - Separate “policy-scored” impacts (e.g., CRFB/CBO scoring) from realized debt accumulation.
- When comparing parties, always show sensitivity to start/end rules (inauguration-day vs FY boundaries).

## Open Questions
- Can we reconcile “debt per term” narrative metrics with CRFB’s “policy approved ten-year debt impact” framework (which is conceptually different)?
- What is the best default fiscal metric for a cross-party “performance” scoreboard: debt-to-GDP, primary deficit, or something else?
