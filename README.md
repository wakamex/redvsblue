# rb

Reproducible pipeline comparing U.S. economic metrics under Democratic vs. Republican presidents.
10 primary metrics, permutation-based inference with FDR correction.

**Bottom line:** GDP growth is significantly higher under Democratic presidents (q=0.021,
surviving FDR correction across all 10 metrics). The other 9 primary metrics are exploratory
(q > 0.10) — the sample of 23-51 four-year presidential terms has limited power for most
effect sizes.

## Quick Start

Prereqs:
- Python 3.13+ and `uv`
- `FRED_API_KEY` in `.env` (for FRED series)

```sh
uv sync
```

## Pipeline

```sh
rb ingest --refresh              # fetch and cache raw data
rb presidents --refresh          # presidential terms + party labels
rb compute                       # term-level metrics + party summaries
rb validate                      # sanity checks on derived data
rb randomization                 # permutation tests with FDR correction
rb inference-table               # side-by-side inference table (permutation + HAC)
rb claims-table                  # baseline-vs-strict claims table
rb scoreboard                    # markdown scoreboard from computed CSVs
```

## Key Outputs

- `reports/term_metrics_v1.csv` — metric values per presidential term
- `reports/claims_table_v1.csv` — machine-readable claim tiers
- `reports/scoreboard.md` — human-readable summary

## Where Things Live

- Pipeline code: `rb/`
- Metric and attribution specs: `spec/`
- Literature corpus: `literature/`
