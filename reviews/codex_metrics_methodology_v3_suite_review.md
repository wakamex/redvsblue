# Codex Review: Metrics + Methodology (v3 suite)

Date: 2026-02-11

Inputs reviewed:
- `reviews/claude_metrics_methodology_v3_suite_review.txt`
- `reviews/gemini_metrics_methodology_v3_suite_review.txt`
- `reviews/codex_metrics_methodology_v2_review.md`
- current implementation in `rb/` (claims/inference/scoreboard/narrative/publication-bundle)

## Question Under Review

Did we drift by elevating stability outputs, and should we add more methods now (small-cluster exact/randomization inference), or pare back?

## Findings

### 1) Did stability become a primary screen?

- **Implementation answer:** No.
- Current primary screening still comes from permutation + BH FDR (`q_bh_fdr`) tiers.
- Stability is currently used as:
  - publication-facing display columns (`Stab@0.05`, `Stab@0.10`),
  - optional/derived publication gating (downgrade when unstable),
  - narrative annotations.

### 2) Alignment with v2 direction

- **Mostly aligned, with a presentational drift risk.**
- Aligned:
  - q-centered multiplicity control remains primary.
  - dual-inference stack exists for robustness checks.
  - downgrading fragile claims is directionally consistent with v2 goals.
- Drift risk:
  - stability diagnostics now have prominent user-facing footprint, which can be misread as co-primary with q.

### 3) External v3 provider convergence

Both providers converge on:
- Stability should be a **secondary guardrail**, not a primary decision axis.
- Current method stack is already deep; avoid adding another major inference layer immediately.

Provider differences:
- Claude: keep current suite but **demote stability display prominence**, keep as artifact/gate.
- Gemini: similar direction, stronger recommendation to simplify visible outputs and avoid adding exact small-cluster method now.

### 4) Should we add exact small-cluster/randomization method now?

- **Recommendation: Not now.**
- Reason:
  - marginal informational value is low relative to added complexity and interpretation burden,
  - current stack already contains multiple robustness checks,
  - with small presidential cluster counts, power constraints remain a core bottleneck regardless of another inferential wrapper.

## Decision

1. Keep `q_bh_fdr` as primary screening/statistical ranking object.
2. Keep wild-cluster and stability diagnostics, but treat them as robustness metadata.
3. Do not add a new exact small-cluster/randomization layer yet.
4. Focus next on communication/hierarchy clarity rather than method proliferation.

## Concrete Next Steps

1. Consider demoting stability from default presentation surface:
- optional display in scoreboard/narrative (or appendix-style section), while retaining generated CSV artifacts.

2. Keep publication stability gate available, but ensure docs clearly state gate order:
- q-tier first, then robustness downgrades.

3. Reassess the need for exact small-cluster method only if:
- more metrics become near-threshold and unstable under current robustness stack,
- or external review/publication requirements explicitly demand that exact method.

## Bottom Line

We did **not** replace q with stability; however, we made stability visually prominent enough to risk that interpretation. The right move is to keep stability as a secondary guardrail and avoid adding another major inference method for now.
