# CLAUDE.md

## Project

Reproducible pipeline comparing U.S. economic metrics under D vs R presidents.
83 metrics across 10 families, permutation-based inference with single-universe BH-FDR correction.

## Results (Feb 2026)

One confirmatory result (q < 0.05, BH-FDR across all 83 metrics, unrestricted permutation):
**Unemployment rate change** (D -1.16pp vs R +1.16pp, gap -2.32pp, q=0.025, CI [-3.24, -1.36]).

Two supportive (q < 0.10): unemployment rate change per year (q=0.075), payroll employment
percent change (q=0.089).

GDP growth is exploratory (q=0.149) under unrestricted permutation but becomes confirmatory
(q=0.025) with 20-year block shuffling. We default to unrestricted (more conservative).
See `--term-block-years` flag for sensitivity analysis.

Most metrics are exploratory — the sample (23-51 four-year terms depending on data coverage)
has limited power for smaller effect sizes.

## Codebase (~3,000 lines)

- `rb/sources/` — ingest from 7 sources with atomic caching
- `rb/metrics.py` — joins series onto terms, applies transforms
- `rb/presidents.py` — presidential terms + party labels
- `rb/validate.py` — sanity checks on derived data
- `rb/randomization.py` — permutation tests + BH-FDR (single universe, all metrics)
- `rb/scoreboard.py` — markdown scoreboard renderer (sorted by q)
- `rb/cli.py` — 6 subcommands
- `spec/` — declarative metric and attribution definitions

## Commands

```sh
uv sync                          # install
rb ingest --refresh              # fetch raw data
rb compute                       # term metrics + party summaries
rb randomization                 # permutation tests
rb scoreboard                    # human-readable summary
```

## Permutation blocking note

Earlier versions defaulted to `--term-block-years 20`, shuffling D/R labels only within
20-year windows. This was recommended by LLM reviewers to control for secular trends, but
the specific value of 20 was ad hoc (Blinder-Watson 2014 used 4-year blocks; another reviewer
suggested 4 or 8). Block shuffling with small blocks inflates significance by constraining the
null distribution. We switched to unrestricted permutation (block_years=0) as the conservative
default. Use `--term-block-years N` for sensitivity analysis.
