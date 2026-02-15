# Codex Review: Metrics + Methodology (v2)

Date: 2026-02-11

Inputs reviewed:
- `reviews/claude_metrics_methodology_v2_review.txt`
- `reviews/gemini_metrics_methodology_v2_review.txt`
- `spec/metrics_v1.yaml`
- `spec/metrics_rationale.md`
- `spec/metrics_coverage_v1.md`
- `notes/analysis_rationale_and_findings.md`

## Decisions On External Feedback

1. `term_block_years=0` default is too permissive for confirmatory claims.
- Decision: **Accept**.
- Action: switch default randomization profile to blocked for publication-facing outputs.

2. `permutations=2000` is too noisy near q/p thresholds.
- Decision: **Accept**.
- Action: raise default to `10000`.

3. CI exclusion as a hard gate for evidence tiers can mislead at small n.
- Decision: **Accept with modification**.
- Action: keep CI reporting, remove CI-as-required-gate from tier assignment; use `q_bh_fdr + min_n` for tier labels.

4. Within-president unified-minus-divided estimand is computed in multiple places.
- Decision: **Accept**.
- Action: factor to shared utility used by scoreboard and randomization.

5. No multi-seed stability check.
- Decision: **Accept**.
- Action: add a primary-metric stability report across multiple seeds.

6. Counting significant rows across many correlated transforms can overstate breadth.
- Decision: **Accept**.
- Action: add family-level / primary-only headline significance summary alongside all-metrics BH.

7. Need dual-inference track (permutation plus HAC/clustered style check).
- Decision: **Accept**.
- Action: add a parallel regression-based table for primary metrics.

8. Annual fiscal attribution (`FYFSGDA188S`) may need lag handling/sensitivity.
- Decision: **Accept with caution**.
- Action: keep fiscal deficit series non-primary and add explicit attribution sensitivity/lag variant before headline use.

9. CPI NSA vs SA primary choice.
- Decision: **Accept with modification**.
- Action: keep NSA primary for now, always show SA companion and a divergence diagnostic.

10. `ff_mkt_excess_return_ann_arith` is easy to misuse in headline reporting.
- Decision: **Accept**.
- Action: keep as diagnostic metric; exclude from headline claims tables/scoreboard defaults.

11. Add labor-force participation (`CIVPART`).
- Decision: **Accept**.
- Action: add to next metric expansion.

12. Add policy-rate / yield metrics (`FEDFUNDS`, `DGS10` or `T10Y2Y`).
- Decision: **Accept**.
- Action: add in next macro channel pass.

13. Add core inflation measure (`CPILFESL` or core PCE).
- Decision: **Accept**.
- Action: add as inflation-family robustness metric.

14. Add welfare/labor alternates (`A229RX0`, `AHETPI`, possibly `PFI`).
- Decision: **Defer**.
- Reason: useful but second wave after inference hardening and core omitted macro channels.

15. Pre-1957 backfilled SPX should not drive headline inferential batteries.
- Decision: **Accept with modification**.
- Action: keep historical diagnostics, exclude from headline significance summaries.

16. Rename tier labels to avoid causal overreach.
- Decision: **Accept**.
- Action: move to wording such as `robust_association`, `suggestive_association`, `exploratory`.

## Priority Order

1. Inference hardening defaults: blocked permutation + higher permutations + updated tier logic.
2. Shared estimand implementation: unify within-president delta computation path.
3. Reporting hardening: family-level/primary-only headline significance and tier-language rename.
4. Macro coverage expansion: `CIVPART`, `FEDFUNDS`, `DGS10/T10Y2Y`, core inflation.
5. Secondary expansion: welfare/investment add-ons (`A229RX0`, `AHETPI`, `PFI`).

## Bottom Line

External feedback was directionally strong. The highest-risk issues are inference defaults and presentation semantics, not lack of metrics volume. We should harden inferential defaults first, then continue metric expansion with explicit symmetry and attribution caveats.
