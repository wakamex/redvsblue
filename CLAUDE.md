# CLAUDE.md

## Project

Reproducible pipeline comparing U.S. economic metrics under D vs R presidents.
10 primary metrics, permutation-based inference with FDR correction.

## Results (Feb 2026)

**Null across the board.** All 10 primary metrics are exploratory (q > 0.10).
Direction split is 5-5 (D > R vs R > D). With ~15 presidential terms,
there is not enough statistical power to detect plausible effect sizes.

## Codebase (~2,500 lines)

- `rb/sources/` — ingest from 7 sources with atomic caching
- `rb/metrics.py` — joins series onto terms, applies transforms
- `rb/presidents.py` — presidential terms + party labels
- `rb/validate.py` — sanity checks on derived data
- `rb/randomization.py` — permutation tests + FDR correction
- `rb/inference.py` — HAC/Newey-West inference table
- `rb/scoreboard.py` — markdown scoreboard renderer
- `rb/cli.py` — 8 subcommands
- `spec/` — declarative metric and attribution definitions

## Commands

```sh
uv sync                          # install
uv run pytest                    # tests
rb ingest --refresh              # fetch raw data
rb compute                       # term metrics + party summaries
rb randomization                 # permutation tests
rb scoreboard                    # human-readable summary
```
