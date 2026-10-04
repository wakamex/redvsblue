# Red vs. Blue

Reproducible pipeline comparing U.S. economic metrics under Democratic vs. Republican presidents.
The metric registry is evaluated with permutation-based inference and BH-FDR correction.

**Live results:** [redvsblue.fyi](https://redvsblue.fyi)

## Methodology

### Why permutation tests?

Standard t-tests assume normally distributed data and large samples. Presidential terms give us
neither — depending on data coverage, we have only 23 to 51 four-year terms. Permutation tests
make no distributional assumptions. They work by shuffling the D/R party labels across terms
thousands of times and asking: how often does the shuffled data produce a gap as large as the
real one? If the answer is "rarely" the observed gap is unlikely to be chance.

### Controlling for multiple comparisons (BH-FDR)

Testing many metrics at once means some will look significant by luck. The [Benjamini-Hochberg
procedure](https://en.wikipedia.org/wiki/False_discovery_rate#Benjamini%E2%80%93Hochberg_procedure) controls the *false discovery rate* — the expected fraction of "discoveries" that are
false positives. Each metric gets a q-value: the smallest FDR threshold at which it would still
be called significant. A q-value of 0.05 means that among all metrics at or below that
threshold, no more than 5% are expected to be false discoveries.

The registered metrics are intentionally broad but highly correlated (e.g., GDP level and GDP growth
move together), so the number of truly independent signals is smaller than the nominal metric count. BH-FDR corrects
for the nominal count, not the effective one — this makes it conservative in practice.

### Confidence intervals

Bootstrap confidence intervals (2,000 resamples) give a range for the D-minus-R gap on each
metric. These are computed independently of the permutation p-values and provide a complementary
measure of uncertainty.

### Permutation blocking

By default, the pipeline uses unrestricted permutation: any D/R label arrangement is equally
likely under the null. An alternative is *block shuffling*, which only permutes labels within
time windows (e.g., 20-year blocks) to control for secular trends. Block shuffling with small
blocks constrains the null distribution and can inflate significance — the choice of block size
is a researcher degree of freedom with no consensus value in the literature (Blinder-Watson 2014
used 4-year blocks; other reviewers have suggested 4, 8, or 20). We default to unrestricted
permutation as the most conservative option. Use `--term-block-years N` for sensitivity
analysis.

### Change baselines

Monthly, quarterly, and annual endpoint-change metrics use the last nonmissing observation before the first attributed period as their baseline. When that observation is unavailable, they use the first available observation within the term and label the result as partial coverage; two distinct observation dates are required. The endpoint is the last available observation within the term. Annualized changes use the elapsed time between observations. Term averages and daily-market boundary rules are unchanged.

The [baseline comparison report](docs/change-baseline-comparison-2026-10-03.md) records the effect on all 96 metrics using unchanged source data and inference settings.

## Data freshness

A GitHub Actions workflow re-runs the full pipeline every Sunday at 06:00 UTC and commits
`site/data.json` if anything changed. The live site at [redvsblue.fyi](https://redvsblue.fyi)
picks up the update automatically. The workflow can also be triggered manually via
`workflow_dispatch`.

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
rb export-json                   # JSON export for the static site
```

## Key Outputs

- `reports/term_metrics_v1.csv` — metric values per presidential term
- `reports/party_summary_v1.csv` — D vs R party-level means and medians
- `reports/permutation_party_term_v1.csv` — permutation test results with FDR q-values
- `reports/scoreboard.md` — human-readable summary (sorted by q)
- `site/data.json` — JSON bundle consumed by the static site
- `site/index.html` — static scoreboard page

## BH-FDR validity under correlated metrics

The Benjamini-Hochberg procedure was originally proven under independence (Benjamini &
Hochberg, 1995). Benjamini & Yekutieli (2001) later showed it also controls the FDR under
[*positive regression dependency from a subset* (PRDS)](https://en.wikipedia.org/wiki/False_discovery_rate#Dependency_among_the_test_statistics)
— roughly, when learning that one test statistic is large makes the others more likely to be
large too. Our metrics are drawn from
a handful of underlying economic series (GDP, employment, inflation, etc.), so they are
positively correlated almost by construction. This satisfies PRDS, meaning BH is formally valid
here, not merely a heuristic. Because BH corrects for all nominal tests rather than the
smaller number of independent signals, the procedure is conservative: the true FDR is likely
well below the reported q-values.

## Where Things Live

- Pipeline code: `rb/`
- Metric and attribution specs: `spec/`
- Static site: `site/`
- Literature corpus: `literature/`
- AI reviews: `reviews/`
- Website: `site/`

## Chart screenshots

Capture a metric's title and presidential-term chart with [Playwright](https://playwright.dev/python/). Run these commands from the repository root after installing the development dependencies with `uv sync --locked`:

```sh
uv run --locked playwright install chromium
uv run --locked python -m rb.screenshot --metric "Real median household income annualized growth"
```

Images are saved under `reports/screenshots/` in [Portable Network Graphics (PNG)](https://www.w3.org/TR/png/) format. Each image uses the site's existing chart renderer, party colors, values, and mean lines. The script serves the local `site/` directory temporarily on loopback, waits for rendering, and crops to the title and chart. Online data fallback is disabled so captures use the selected local data release. Existing images with the same filename are replaced. Browser installation is a one-time step per Playwright version; Linux hosts may also need its browser system dependencies installed.

```sh
uv run --locked python -m rb.screenshot --list
uv run --locked python -m rb.screenshot --all
uv run --locked python -m rb.screenshot --metric "Official poverty rate change" --agg end_minus_start
```

Metric matching prefers an exact name, then an unambiguous substring. Use `--agg` when names overlap, or `--index N` for the exact row number shown by `--list`. Filenames include that row number to prevent collisions between identically named metrics. Use `--output-dir PATH` to select another destination or `--site PATH` to capture another local site snapshot. The browser runs headlessly and needs no desktop session.
