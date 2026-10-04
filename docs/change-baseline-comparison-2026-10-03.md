# Change baseline comparison

Including the first period's change requires a baseline from the preceding period. Applying this rule affects 50 of the 96 metrics: unadjusted p-values rise for 37 and fall for 13. The other 46 metrics retain identical term results and p-values. The comparison holds source observations and inference settings fixed and checks the original results against the updated calculation.

## Calculation and coverage

Monthly, quarterly, and annual endpoint-change metrics use the last nonmissing observation before the first attributed period and the last nonmissing observation within the term. If the preceding baseline is unavailable, the first available in-term observation supplies a partial-coverage baseline. Two distinct observation dates are required. Annualization uses elapsed days divided by 365.25. Means, last values, growth-rate averages, compounded returns, and daily boundary rules retain their existing calculations.

For household income, Biden's term compares 2020 with 2024 and Trump's current term compares 2024 with 2025. Johnson's partial history remains 1967 to 1968 and is labeled accordingly.

## Results across all 96 metrics

The table compares the original within-term baseline with the preceding-period baseline and partial-coverage fallback. Higher p-values indicate weaker evidence against equal party means. Adjusted q-values use the [Benjamini-Hochberg false discovery rate correction](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x) across all 96 metrics, so they can change even when a metric's own results remain identical.

| Measure | Higher after update | Lower after update | Unchanged |
| --- | ---: | ---: | ---: |
| Unadjusted p-value | 37 | 13 | 46 |
| Adjusted q-value | 84 | 9 | 3 |

Two metrics cross the site's evidence thresholds. Lower q-values indicate stronger evidence under this correction.

| Metric | Original q-value | Updated q-value | Original label | Updated label |
| --- | ---: | ---: | --- | --- |
| Total unemployment-rate change | 0.028800 | 0.067200 | Confirmatory | Supportive |
| Real gross domestic product per capita annualized growth | 0.097056 | 0.107723 | Supportive | Exploratory |

The updated set contains zero confirmatory, eight supportive, and 88 exploratory metrics. All eight income, inequality, and poverty metrics remain exploratory; seven have higher p-values and one has a lower p-value.

Of the previously valid metric-term entries, 1,054 change value or selected endpoints. Six formerly unavailable entries become available. Two former zero-change entries become unavailable because each had only one observation: core consumer price index total percent change and monthly S&P 500 total percent change in Eisenhower's 1953 to 1957 term. Partial-coverage fallback preserves 46 entries, with their original values, that a strict preceding-baseline requirement would exclude. These counts refer to metric-term entries, not independent presidential terms.

## Reproducibility

The [complete before/after table](change-baseline-comparison-2026-10-03.csv) includes all 96 metric identifiers, labels, units, party means, term counts, differences, p-values, q-values, and evidence labels. Differences are Democratic minus Republican means; their interpretation depends on the metric's units and whether increases are desirable.

Source input hashes were unchanged. Both calculations use 10,000 unrestricted permutations, 2,000 bootstrap samples, seed 42, and a 12-term minimum for evidence labels. Replaying the old attribution configuration reproduces every original term-result field and the original party summary. The boundary and fallback tests cover monthly, quarterly, calendar-year, fiscal-year, missing-observation, and daily series.
