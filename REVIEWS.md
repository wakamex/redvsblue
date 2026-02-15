# External Reviews

Raw review outputs are in `reviews/` (named `{reviewer}_v{round}_review.txt`).
Reconciliation docs are `codex_v{round}_reconciliation.md`. This file summarizes
actionable findings across all review rounds.

## Round 4: Post-simplification (commit `0dde770`)

Reviewers: Gemini 3, ChatGPT 5.2.

### Actionable

1. **Unit tests for core math** (Gemini). No tests exist for permutation p-value
   calculation, BH-FDR ranking, or bootstrap CI. `rb validate` checks data sanity,
   not code correctness. High-value, small scope.

2. **Leave-one-term-out sensitivity** (ChatGPT). Check whether the confirmatory
   unemployment result depends on a single outlier term. Cheap robustness check.

3. **Note metric correlation structure** (ChatGPT). The 83 metrics are highly
   correlated; the 3 significant results (unemployment change, unemployment change/yr,
   payroll jobs) reflect 1-2 independent signals, not 3. BH-FDR overstates the
   effective test count. Already in CLAUDE.md but not surfaced to readers.

### Considered, not pursued

- **Visualization / `rb plot`** (Gemini). A plot would help but is not a correctness issue.
- **Exogenous shock covariates** (Gemini, ChatGPT). Requires regression, not permutation. Small N makes it impractical.
- **Pandemic term isolation** (ChatGPT). Better handled by leave-one-term-out than ad hoc exclusion flags.
- **Reframe wording** (ChatGPT). README already says "association" not "causation." Results are mostly null.
- **Balance literature corpus** (ChatGPT). Literature is reference material; the pipeline does not read it.
- **Secular trend regressions** (ChatGPT). Scope creep. Unrestricted permutation handles trends more conservatively than parametric regression at N=15.

---

## Round 3: Stability and complexity budget (commit `e3a82f3`)

Reviewers: Claude (Sonnet), Gemini. Reconciled in `codex_metrics_methodology_v3_suite_review.md`.

Context: The pipeline had accumulated stability diagnostics, wild-cluster bootstrap,
and HAC inference layers. The review asked whether stability had been elevated too far
and whether to add small-cluster exact inference or pare back.

### Actionable (acted on)

1. **Stability should be secondary guardrail, not primary screen.** Both reviewers
   converged: q_bh_fdr must remain the primary ranking. Stability gates risk silently
   rewriting tiers. Demote stability from default presentation.

2. **Do not add small-cluster exact inference.** Cluster-count problem is structural
   (N=15 terms). Adding another method increases complexity without resolving power limits.

3. **Keep hierarchy: q -> permutation p -> HAC -> stability.** Wild-cluster and stability
   are robustness metadata, not decision axes.

### Considered, not pursued

- **Drop draws=499 from stability grid** (Claude). Minor tuning, deferred.
- **Expand seeds to 5** (Claude). Diminishing returns at current sample size.

### Outcome

Stability diagnostics, wild-cluster bootstrap, and narrative generators were later
removed entirely in the simplification pass (commit `a7a2d6d`). The round 3 feedback
correctly identified the complexity drift that motivated that cleanup.

---

## Round 2: Methodology and inference (commit `07040de`)

Reviewers: Claude (Sonnet), Gemini. Reconciled in `codex_metrics_methodology_v2_review.md`.

Context: First review of the full inference pipeline — permutation tests, bootstrap CIs,
tier classification, and metric coverage. The prompt included the spec, rationale,
coverage matrix, and analysis findings.

### Actionable (acted on)

1. **Default block_years=0 may be anticonservative** (Claude). Recommended block_years=20.
   Gemini recommended 4 or 8, citing Blinder-Watson. We adopted 20, later reverted to 0
   after finding it inflated significance (see CLAUDE.md permutation blocking note).

2. **Add macro coverage: FEDFUNDS, DGS10, T10Y2Y, CIVPART, core CPI/PCE** (both).
   All added to spec.

3. **Add HAC/Newey-West as parallel inference track** (Claude). Implemented as
   `rb inference-table`, later removed in simplification.

4. **Report minimum detectable effect / power proxies** (both). MDE machinery added,
   confirmed the fundamental power problem.

5. **Demote `ff_mkt_excess_return_ann_arith`** (both). Arithmetic vs geometric return
   confusion. Removed from headline.

6. **Pin primary metric per family** (Claude). Added `primary: true/false` to spec.
   Later removed when we switched to single FDR universe.

### Considered, not pursued

- **Data-vintage sensitivity panel** (Claude). ALFRED integration deferred; caching raw downloads provides reproducibility.
- **Percentile bootstrap CIs unreliable at small N** (Claude). Valid concern but bootstrap CIs are reported as context, not used for tier gating.
- **Add Real Disposable Personal Income per Capita** (Gemini). Deferred to potential v2 spec.

---

## Round 1: Spec review (commit `d98b72c`)

Reviewers: Claude (Sonnet), Gemini.

Context: First external review of `spec/metrics_v1.yaml` and `spec/metrics_rationale.md`
before any inference code existed. Focused on spec completeness and data-source risks.

### Actionable (acted on)

1. **No attribution/boundary spec** (Claude H1). Created `spec/attribution_v1.yaml`
   with explicit window rules, daily boundary selection, and fiscal year handling.

2. **No schema for aggregation kinds** (Claude H4). Created `spec/aggregation_kinds_v1.yaml`
   with formulas, missing-data policies, and parameter definitions.

3. **Missing real wages** (Gemini). Added `LES1252881600Q` real median weekly earnings.

4. **Daily series lack term-level sampling rule** (Gemini). Addressed in attribution spec
   with `last_trading_day_strictly_before` boundary rule.

5. **Fiscal year attribution** (both). Added `series_overrides` in attribution spec for
   fiscal-year series with explicit `fiscal_year_start_month`.

6. **Add cumulative price-level change metrics** (Gemini). Added term pct_change and
   CAGR for CPI and PCE price indices.

7. **NSA vs SA CPI sensitivity** (Claude H3). Added both NSA and SA CPI variants;
   documented the tradeoff in rationale.

### Considered, not pursued

- **Data revision/vintage pinning via ALFRED** (Claude M2). Deferred; raw caching sufficient for now.
- **Ken French file format fragility** (Claude M4). Accepted as known risk; parser handles it.
- **`inputs` schema inconsistency** (Claude H5). `series` vs `table`/`column` kept as-is; both patterns needed.
