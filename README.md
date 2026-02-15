# rb

Reproducible pipeline comparing U.S. economic metrics under Democratic vs. Republican presidents.
83 metrics across 10 families, permutation-based inference with BH-FDR correction.

**Bottom line:** One metric survives FDR correction (q < 0.05) across all 83 tests:
unemployment rate change (D -1.16pp vs R +1.16pp, q=0.025). Two more are supportive
(q < 0.10): unemployment change per year and payroll employment percent change.
GDP growth is exploratory (q=0.149) under unrestricted permutation. Most metrics lack
power — the sample of 23-51 four-year presidential terms is small for the effect sizes involved.

**Caveat on permutation blocking:** Results are highly sensitive to the `--term-block-years`
setting. Unrestricted permutation (default, block_years=0) yields 1 confirmatory result.
Switching to 20-year blocks yields 6 — including GDP growth (q=0.025). The choice of block
size is a researcher degree of freedom with no consensus value in the literature
(Blinder-Watson 2014 used 4; LLM reviewers suggested 4, 8, or 20). We default to
unrestricted as the most conservative option. See CLAUDE.md for full discussion.

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
rb scoreboard                    # markdown scoreboard from computed CSVs
```

## Key Outputs

- `reports/term_metrics_v1.csv` — metric values per presidential term
- `reports/party_summary_v1.csv` — D vs R party-level means and medians
- `reports/permutation_party_term_v1.csv` — permutation test results with FDR q-values
- `reports/scoreboard.md` — human-readable summary (sorted by q)

## Where Things Live

- Pipeline code: `rb/`
- Metric and attribution specs: `spec/`
- Literature corpus: `literature/`
