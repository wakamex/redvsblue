# Publication Runbook (v1)

This runbook is the minimal, repeatable path from raw pulls to publication-facing artifacts.

## 1) Environment

1. Ensure `.env` contains `FRED_API_KEY`.
2. Install dependencies:

```sh
uv sync
```

## 2) Rebuild Data + Core Tables

```sh
.venv/bin/rb ingest --refresh
.venv/bin/rb presidents --source congress_legislators --granularity tenure --refresh
.venv/bin/rb compute
.venv/bin/rb congress --refresh
.venv/bin/rb regimes --refresh
.venv/bin/rb randomization
```

## 3) Build Publication Artifacts

```sh
.venv/bin/rb publication-bundle --profile strict_vs_baseline
```

Primary outputs:
- `reports/final_product_summary_v1.md`
- `reports/scoreboard.md`
- `reports/claims_table_v1.csv`
- `reports/inference_table_primary_v1.csv`
- `reports/publication_narrative_template_v1.md`
- `reports/fred_vintage_primary_metrics_v1.csv`
- `reports/publication_bundle_manifest_v1.json`

## 4) Validation Gate

```sh
.venv/bin/rb validate
```

Expected:
- 0 errors.
- Coverage warnings can be expected for series that start after earliest president windows.

## 5) Reporting Rules

1. Claim status should use publication-tier columns from claims table (`tier_strict_publication`).
2. `q` values are primary for multiplicity-aware screening; raw `p` is supporting context.
3. Congress unified-vs-divided checks are confounding diagnostics, not causal decomposition.
4. If results are mostly exploratory, report direction/magnitude as descriptive and avoid claim-grade language.
