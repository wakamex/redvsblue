Work Plan: D vs R Economic Performance Pipeline

Principles

1. Reproducible “from scratch” via code that pulls from online sources (no hand-edited data).
2. Every measurement choice is explicit, parameterized, and logged (so disputes are about settings, not hidden assumptions).
3. Default outputs include uncertainty and sensitivity, not just point estimates.
4. “Shock years” are handled as diagnostics and robustness, not as subjective exclusions (but we still explicitly address
   them).

Current Execution Plan (v3, post external review refresh)

1. Keep inferential hierarchy explicit:
    - Primary screening remains permutation + BH FDR `q_bh_fdr`.
    - HAC / cluster / wild-cluster / stability remain robustness diagnostics.
2. Reduce publication-surface overemphasis of diagnostics:
    - Do not show stability tags by default in public-facing scoreboard/narrative.
    - Keep stability artifacts generated and available for audit.
3. Keep method stack stable for now:
    - Do not add another exact small-cluster/randomization layer yet.
    - Prioritize communication clarity and decision-rule consistency.
4. Keep publication robustness gating available but explicit:
    - Publication stability downgrade should be opt-in unless explicitly requested.
5. Continue reproducibility discipline:
    - All changes remain fully code-driven with deterministic artifact generation and manifests.

Current Execution Plan (v4, impact focus: revision/vintage transparency)

1. Ship publication-facing vintage transparency as a first-class artifact:
    - Generate per-primary-metric FRED vintage metadata (`realtime_start/end`, `observation_end`, `last_updated`, snapshot timestamp/hash).
    - Emit both CSV + markdown in `reports/`.
2. Integrate vintage artifact into publication flow:
    - `rb publication-bundle` must regenerate vintage report every run.
    - Manifest must include vintage artifact metadata.
3. Keep inferential stack stable while improving publication reliability:
    - No additional inference methods until vintage/reporting reproducibility is hardened.
4. Next impactful milestone after vintage:
    - Add Congress-control inferential checks (binary unified vs not) with explicit small-cell caveats and scope-locked outputs.

Implementation Order (v1)

1. Lock the v1 “spec stack” for the initial scoreboard set:
    - Metric registry (`spec/metrics_v1.yaml`)
    - Aggregation semantics (`spec/aggregation_kinds_v1.yaml`)
    - Attribution / boundary semantics (`spec/attribution_v1.yaml`)
2. Implement ingestion + caching for the minimum required sources (likely: FRED + NBER + Wikidata + Congress control).
3. Implement the transform library (log diff, pct change, annualization, per-capita, %GDP, etc.) with unit tests.
4. Implement metric evaluation + validation checks (schema checks, transform invariants, and cross-series consistency checks).
5. Implement the time joiners (series -> president term; series -> {House,Senate} control) with explicit attribution manifests.
6. Generate the first end-to-end scoreboard report (president-only + optional {P,H,S} regimes) and export CSVs.
7. Add inference/sensitivity runs (permutation tests, term clustering, attribution-window sweeps) once the descriptive layer is stable.

Phase 0: Repo Scaffolding

1. Create a Python package + CLI (using uv).
2. Add a config system (YAML/JSON) for:
    - Series catalog (source + id + transform + frequency).
    - Presidency attribution rule (see Phase 2).
    - Output selection (scoreboard vs explanations).
3. Create a standard data layout:
    - data/raw/ (immutable downloads + metadata + hashes)
    - data/derived/ (cleaned tables)
    - reports/ (tables, figures, rendered markdown)

Phase 1: Data Ingestion (Online, Reproducible)

1. Implement source connectors with consistent interfaces and caching:
    - FRED:
        - Preferred: official FRED API (requires `FRED_API_KEY`; provides metadata + supports ALFRED vintages).
        - Fallback: `fredgraph.csv` downloads (no key; less stable; minimal metadata).
    - NBER business cycle dates JSON (already in literature/).
    - Ken French data library (market factors / portfolio returns) if accessible.
    - Stooq CSV for stock index levels (S&P 500, DJIA).
    - Treasury/OMB/CBO/Fiscal Data if needed for deficit/debt (prefer stable CSV/JSON endpoints).
    - Wikidata SPARQL for president/party/term dates.
2. For every fetch, persist:
    - Raw bytes as-downloaded.
    - Request URL + params + retrieval timestamp.
    - sha256 hash and parsed schema info (columns, frequency, units if available).
    - Politeness controls: rate limiting, retries with backoff, and a stable user-agent; do not hammer sources.
    - Licensing/TOS note per source (especially for datasets like Ken French) so automation stays within allowed use.
3. Provide two modes:
    - --refresh re-downloads.
    - Default uses cached raw artifacts to make reports rerunnable and stable.
4. Revision/vintage strategy (important for “online sources” reproducibility):
    - Default: pull “latest available” data, but cache raw downloads and record retrieval timestamps/hashes so any result can be re-rendered from the cached raw artifacts.
    - Optional later: add an “as-of” / vintage mode for sources that support it (e.g., ALFRED/FRED vintages), so historical reproductions can be pinned to a revision date.

Phase 2: Presidency and Party Coding (Reproducible, Parameterized)

1. Generate data/derived/presidents.csv from a stored Wikidata query (the query text lives in-repo and is executed by code).
2. Implement a reusable “time-to-president” join with explicit rules:
    - assignment_rule: midpoint (who holds office on the midpoint date) or majority_of_days.
    - frequency: monthly/quarterly alignment rules.
    - lag: lag_months / lag_quarters to shift attribution (the “inherited economy” question).
    - daily boundary rule for market index endpoints (close-before-inauguration vs close-on-inauguration).
    - fiscal-year handling for FY-based annual series (e.g., deficit) with explicit alternatives.
3. Emit a machine-readable “attribution manifest” per run documenting the exact rule (so results are auditably
   reproducible).
4. Add a reproducible Congress control dataset:
    - Produce data/derived/congress_control.csv with House-majority party + Senate-majority party by date.
    - Join it onto observations so every row can be tagged with a full regime triple: {P, H, S}.
    - Derive regime labels used by reports (examples):
        - unified_government = (P == H == S)
        - trifecta = “D trifecta” / “R trifecta”
        - divided = anything else (optionally further split by which chamber differs)
    - Note: this will materially shrink sample sizes per cell; treat many of these cuts as descriptive unless inference is carefully designed.

Phase 3: Metric Definitions (Explicit, Multi-Definition Where Contested)

1. Build a metric registry with clear transforms (each metric is “base series + transforms + aggregation”):
    - Required fields per metric:
        - id: stable name used in code and reports.
        - source: fred | bea | bls | ken_french | nber | fiscaldata | wikidata | etc.
        - series_id: upstream identifier(s).
        - units and type: level | flow | rate | index.
        - seasonal_adjustment: SA | NSA (and what upstream provides).
        - real/nominal: if real, document deflator choice and formula.
        - per_capita/per_worker: if applicable, document denominator series.
        - transform: pct_change | log_diff | diff | level | ratio_to_gdp | etc.
        - annualization: none | annualized (and exact formula).
        - frequency + alignment: monthly/quarterly; how conversions are done.
        - term_aggregation: mean | median | start_end_change | CAGR | sum | count (and whether weighted by days).
        - missing/revision policy: how missing data is handled; whether we always pull latest vintage (default) vs point-in-time (optional later).
    - Provide “primary” and “alternate” definitions for contested metrics so disputes are settings, not rewrites.

2. Enumerate common transform disagreements (explicitly support multiple):
    - “Job creation”:
        - payroll (CES) vs household (CPS).
        - total change over term vs average annual change vs compounded growth rate.
    - “GDP growth”:
        - real GDP vs real GDP per capita.
        - average of quarterly annualized growth vs start/end level growth vs CAGR.
    - “Inflation”:
        - CPI vs PCE; YoY vs annualized period-to-period.
    - “Deficit/debt”:
        - flow vs stock; nominal vs real; gross vs held-by-public; as %GDP vs dollars.
    - “Recessions”:
        - NBER dates vs “two negative quarters” (diagnostic only); and “recession started under X” attribution rules.

3. Seed the registry with a small, explicit “v1 scoreboard” set (with primary + at least one alternate per metric):
    - GDP.
    - Payroll employment.
    - Unemployment rate.
    - Inflation.
    - Stock returns (excess).
    - Recession incidence (using NBER).
    - Deficit/debt (as %GDP, plus a nominal/real alternate).

Phase 3B: Metric Validation (Tests Before Reports)

Goal: catch transform/spec mistakes early and make it hard to silently change definitions.

1. Schema tests for every base series:
    - monotone time index; no duplicates; expected frequency; unit sanity (where known).
2. Transform unit tests:
    - log-diff/percent-change/annualization formulas on tiny synthetic series.
    - alignment/conversion tests (monthly->quarterly aggregation rules).
3. Cross-series consistency tests (where possible):
    - Example: compute real GDP annualized growth from the level series and compare to a published growth-rate series (tolerance-based).
    - Example: compute inflation YoY from CPI and compare to an alternate published inflation-rate series (if available).
4. Golden/snapshot tests:
    - With cached raw inputs, the derived metric outputs and scoreboard tables should match a checked-in snapshot within tolerances.
5. Spec/version hygiene:
    - Hash the metric spec + transform code version used for each output and write it into per-run metadata.
    - If a definition changes, treat it as a new metric version (avoid silently changing historical results).

Phase 4: Scoreboard (Descriptive, No Mechanism Claims)

1. Produce per-president/per-term summaries (tables + CSV):
    - Mean/median metric values, start-to-end changes, distributions.
2. Produce party aggregates:
    - Party-conditional averages with uncertainty (next phase).
    - Optional regime cuts: by trifecta/divided status (P+H+S) in addition to president-only.
3. Render reports/scoreboard.md with charts and a data appendix.

Phase 4B: Congressional Control As A Potential Confounder (Check, Don’t Assume)

Goal: test whether “president party” gaps are better described as (or materially altered by) House/Senate control and unified vs divided government. Be open to Congress mattering, but expect small cells and interpret accordingly.

1. Descriptive regime splits (always report sample sizes per cell):
    - Break out outcomes by {P,H,S} regimes:
        - D trifecta, R trifecta
        - D president + split Congress
        - R president + split Congress
        - (optional) finer splits: which chamber differs
    - Show both:
        - within-term summaries (4-year buckets)
        - within-quarter/month summaries tagged by contemporaneous Congress (captures midterm flips)

2. Within-president comparisons (controls for “who the president is”):
    - For presidents whose party stayed constant while Congress flipped, compare outcomes pre/post flip under that same president.
    - Treat this as descriptive (midterms are not random), but it helps separate “president-party only” from “legislative environment” stories.

3. Model-based checks (not causal proof, but a structured sanity test):
    - Regressions with robust SEs / few-cluster inference:
        - outcome_t ~ PresidentParty_t + HouseParty_t + SenateParty_t
        - outcome_t ~ PresidentParty_t + unified_government_t + interactions
    - Report:
        - coefficient stability for PresidentParty when adding Congress controls
        - whether interactions (trifecta vs divided) change the magnitude/sign of the president gap
    - Use permutation/randomization tests at an appropriate block level (terms / Congress sessions) as a nonparametric check.

4. Interpretation guardrails:
    - Congress can be both a confounder and a mediator (coattails / joint election outcomes), so “controlling for Congress” is not automatically “more causal.”
    - The primary deliverable is still a transparent scoreboard; these checks are robustness/context, not a definitive causal decomposition.

Phase 5: Inference and Uncertainty (Small-Sample Appropriate)

1. Term-level (few cluster) uncertainty:
    - Cluster by presidency/term (not by month), plus conservative options.
2. Randomization/permutation tests:
    - Shuffle party labels at the term level as a default “how surprising is this gap” check.
3. Sensitivity grid:
    - Re-run the scoreboard across plausible attribution lags and assignment rules, then show the range of outcomes.

Phase 6: “Shock” Handling (Address It Without Subjective Shock Labeling)
You’re right that defining “shocks” is subjective. The plan is to treat this as robustness/diagnostics, using mostly
objective partitions.

1. Objective split views:
    - Expansion vs recession months using NBER dates as well as “two negative quarters”.
2. Robust estimators:
    - Medians, trimmed means, winsorized means (so single extreme episodes can’t dominate silently).
3. Influence diagnostics:
    - Leave-one-term-out and “top contributing months/quarters” reporting so users can see what drives gaps without
      declaring what counts as a “shock.”
4. Optional “event windows”:
    - Only if we include them, they must be user-specified and clearly labeled as subjective scenarios, not defaults.

Phase 7: Explanation Module (Clearly Separated, Optional)

1. Add hypothesis blocks with strict labeling:
    - “Business-cycle proxies,” “oil shocks,” “risk aversion/state selects party” (Pastor/Veronesi style), etc.
2. Guardrails:
    - Avoid post-treatment controls where possible.
    - Always report how much variance is explained and what remains.

Phase 8: Claims Audit (Bridges Popular Claims to Reproducible Checks)

1. Create claims.yaml where each claim maps to:
    - Metric definition + time window + attribution rule.
2. Auto-generate a “pass/fail/requires-qualification” table with exact reproducible code paths.

Phase 9: Automation

1. Single-command rebuild:
    - uv run command --refresh (or without --refresh for cached reproducibility).
2. Continuous checks:
    - Smoke tests for data fetch/parsing.
    - Determinism tests when using cached raw downloads.

Key Choices to Confirm

1. Time scope: post-1947 only for macro, but allow 1927+ for stock returns if the source supports it? Or go back as far as possible?
2. Primary metrics for the first scoreboard: GDP, payrolls, unemployment, inflation, recession incidence, stock levels, stock excess returns, deficit/debt?
3. Default attribution rule: midpoint/majority-of-days, and default lag (0, 1 quarter, 2 quarters)?
