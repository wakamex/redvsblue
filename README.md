# rb

Reproducible pipeline for comparing U.S. economic metrics under Democratic vs. Republican presidents, with Congress-control diagnostics and publication-oriented reporting.

## Quick Start

Prereqs:
- Python + `uv`
- `FRED_API_KEY` in `.env` (for FRED series)

Install:

```sh
uv sync
```

Run end-to-end:

```sh
.venv/bin/rb ingest --refresh
.venv/bin/rb presidents --source congress_legislators --granularity tenure --refresh
.venv/bin/rb compute
.venv/bin/rb congress --refresh
.venv/bin/rb regimes --refresh
.venv/bin/rb randomization
.venv/bin/rb publication-bundle --profile strict_vs_baseline
```

## Main Outputs

Use these in order:

1. `reports/final_product_summary_v1.md`
2. `reports/scoreboard.md`
3. `reports/claims_table_v1.csv`
4. `reports/inference_table_primary_v1.csv`
5. `reports/fred_vintage_primary_metrics_v1.csv`

## Interpretation Rule

- Treat `tier_strict_publication` as the default claim status.
- Treat congress unified-vs-divided outputs as confounding diagnostics, not causal attribution.
- Prefer family-level interpretation over single-metric cherry-picking.

## Where Things Live

- Pipeline code: `rb/`
- Metric/attribution specs: `spec/`
- Durable rationale + project notes: `notes/`
- Literature review corpus: `literature/`
- External model reviews: `reviews/`
- Working plan: `workplan.md`
