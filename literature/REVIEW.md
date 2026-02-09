# Literature Review (Draft)

This project’s core question (measuring economic performance under Democratic vs. Republican presidents) sits at the intersection of three things:
1. A robust **descriptive pattern** in postwar US macro/asset data.
2. Serious **identification limits** (few administrations, large shocks, lags, endogeneity).
3. A public discourse dominated by **secondary summaries** and **partisan rhetoric** that often hides the measurement choices.

## What The Better Sources Agree On (Association)

Across multiple sources in `literature/` (notably Blinder & Watson; Pastor & Veronesi; EPI’s synthesis), the common descriptive claim is:
- Average postwar performance on many common indicators (GDP growth, employment growth, recession incidence, stock returns) has tended to look better in Democratic administrations than Republican administrations.

Importantly, the stronger sources also agree on the caveat:
- The president has limited direct control over the economy; a lot of the observed variation is driven by shocks and inherited conditions, so **association is not policy causation**.

## Major Methodological Fault Lines

These are the main places the body of work diverges, or where popular writeups get sloppy:

1. **Attribution window (lags)**
   - Blinder & Watson often attribute the first quarter of a presidency to the prior president; EPI uses “Q3 after election”; many popular posts use inauguration-to-inauguration with no lag.
   - These choices can change point estimates materially, especially around recessions or major turning points.

2. **What metric is being measured**
   - “Job creation” can mean: level at start/end, average annual change, compounded growth rate, or total payrolls vs household employment.
   - “Deficit/debt” can mean: deficit flow vs debt stock, nominal vs real, gross vs held-by-public, or debt-to-GDP.

3. **Institutional control (unified vs divided government)**
   - Some academic work checks whether party control of the House/Senate adds explanatory power beyond the president (and interactions like “trifecta” vs divided government).
   - Often, the headline gaps line up more with the party in the White House than with Congressional control, but sample sizes get even smaller once you split into {P,H,S} regimes.

4. **Small sample inference**
   - With ~16–20 postwar terms (depending on endpoint), classical asymptotics are fragile.
   - Better work uses term clustering, HAC, and permutation/random-label tests; popular sources often replace this with coin-flip analogies.

5. **Confounding shocks and endogeneity**
   - Oil shocks, wars, global growth, productivity shocks, and consumer expectations correlate with party eras.
   - But some of these “shocks” are not purely exogenous (e.g., foreign policy choices can affect oil/war).
   - Pastor & Veronesi’s mechanism explicitly flips causality in finance: macro risk states help determine who wins elections.

6. **Sample endpoints and regime changes**
   - Adding a few years (e.g., 1999–2015 in stock returns, or pandemic era in macro data) can swing results because shocks are large relative to the number of administrations.

## What We Can Improve (Concrete)

If we want to materially improve on the existing ecosystem of posts/charts, the pipeline should:

1. **Make every measurement choice explicit and parameterized**
   - Presidency window definition and lag rule.
   - “Recession start” definition (month after NBER peak vs peak month vs quarter rule).
   - Metric transforms (levels vs growth rates; log vs simple returns; real vs nominal; %GDP scaling).

2. **Produce uncertainty, not just point estimates**
   - Term-clustered inference, few-cluster conservative tests, and permutation tests as default.
   - Sensitivity grids that show how conclusions change across reasonable windowing rules.

3. **Separate “Scoreboard” from “Explanation”**
   - Scoreboard module: party-conditional averages and distributions (what happened).
   - Explanation module: explicitly labeled hypotheses with partial explanatory power (oil, TFP, global growth, risk aversion proxies), avoiding post-treatment bias where possible.

4. **Support regime splits beyond president-only (carefully)**
   - Provide breakdowns by {President party, House majority, Senate majority} and collapsed views like “trifecta vs divided.”
   - Treat very small cells as descriptive; report cell sizes and avoid over-interpreting noisy deltas.

5. **Update through “now” with careful shock handling**
   - Extend beyond 2013/2015 to include Obama-2, Trump, Biden, and (if applicable) later terms.
   - Provide views that isolate extraordinary shocks (e.g., pandemic) rather than letting them dominate every metric.

6. **Cross-check popular claims against primary data**
   - Maintain a “claims audit” table that marks claims as reproducible/not, and documents why.
   - Prefer primary sources (BEA/BLS/FRED/Treasury/NBER) and peer-reviewed papers over tertiary summaries.

## Pipeline Implications (Design)

Minimum viable outputs that would be an improvement over most existing work:
- A fully reproducible dataset build (series ids + transformations + versioning).
- A report that prints:
  - Party averages with confidence intervals.
  - Per-term/per-administration distributions (so “always” claims can be evaluated).
  - Recession-start counts with sensitivity to attribution rules.
  - A permutation-test p-value for key gaps (GDP growth, unemployment change).

Then, optional “mechanism” extensions:
- Shock decomposition (oil, TFP/utilization-adjusted productivity, global growth).
- Event-study around elections using market expectations (to distinguish “policy causes” vs “state of the world selects party” narratives).
