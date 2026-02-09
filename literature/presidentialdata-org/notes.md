# Notes: Presidential Data 2024

**URL:** https://presidentialdata.org/  
**Authors/Org:** Jere Glover (site operator; compilation effort dating back to ~1980 per site)  
**Published:** Living webpage (states “Data updated for 2024”)  
**Retrieved:** 2026-02-09  
**Local files:** `literature/presidentialdata-org/source.*`, `literature/presidentialdata-org/source.txt`

## What It Claims
- Post-WWII, a range of macro indicators “perform better” under Democratic presidents than Republican presidents (GDP growth, job growth, unemployment, recessions, etc.).
- “Ten of the last eleven recessions have begun under Republican Presidents.”
- Job creation per year is “more than twice as high” under Democrats than Republicans (headline numbers provided).

## Data & Definitions
- Metrics (as presented):
  - Recessions started by party (links to NBER recession chronology).
  - Job creation totals and average annual job growth by party.
  - Average GDP growth by party.
  - Business investment growth by party.
  - Budget deficits (% of GDP) by party.
  - Average unemployment by party.
  - Federal spending growth ($ per year) by party.
  - Trade deficits (total) by party.
  - “Average increase in weekly earnings” by party (claim; definition not shown).
- Time period:
  - Mix of “since World War 2” and “since 1961” statements; exact start/end dates not fully specified in the extracted text.
- Party/presidency coding:
  - Not clearly documented on the landing page; unclear whether windows are calendar years, fiscal years, or term windows with lags.
- Data sources:
  - Claims compilation from “official government sources such as Statistical Abstracts of the United States, the Economic Reports of the President, and the US Census Bureau.”
  - Recession chronology referenced explicitly to NBER.

## Methodology / Identification
- Summary:
  - Descriptive: party-conditional averages and totals. No causal identification attempted.
- Lags / attribution window:
  - Not stated; likely important for replication (e.g., whether the first year/quarter is attributed to predecessor).
- Controls / covariates:
  - None on the landing page; no adjustments for inherited conditions, Congress, Fed, global shocks, etc.
- Robustness:
  - Not discussed.

## Results (Quantitative)
- The site reports, among others:
  - Average yearly job growth: ~2.25M jobs/year (Democrats) vs ~0.80M (Republicans).
  - Average GDP growth: ~3.46%/yr (Democrats) vs ~2.4%/yr (Republicans).
  - Average unemployment: ~5.71% (Democrats) vs ~6.07% (Republicans).
  - Trade deficit totals (millions): ~$7.80T (Democrats) vs ~$8.07T (Republicans).

## Strengths
- Easy-to-consume summary that enumerates the key metrics the public debates.
- Points to official sources (at least at a high level) and links recession claims to NBER.
- “Updated for 2024” makes it a useful sanity-check target for our pipeline once we implement it.

## Weaknesses / Risks
- Insufficient methodological transparency for replication (coding rules, windows, inflation adjustments, start/end dates, treatment of partial terms).
- Potential for transcription/typo errors (e.g., one job-total line appears to be missing a digit in the extracted text).
- Purely descriptive and highly aggregative; does not address confounding shocks or causal attribution.

## Replication Notes
- Code/data availability:
  - No code or raw dataset links are present in the extracted landing-page text; may exist elsewhere on the site (needs checking if we rely on it).
- Gotchas:
  - Must decide whether to replicate their numbers exactly (requires knowing their window definitions) vs treat as approximate/public-facing claims.

## Takeaways For Our Pipeline
- Treat `presidentialdata.org` as a **claim list** to replicate from first principles using BEA/BLS/FRED/NBER series plus explicit coding rules.
- Our pipeline should publish:
  - A complete “data dictionary” for each metric.
  - A standard presidency window spec (and sensitivity toggles) so comparisons are reproducible.
  - Cross-check tables showing where our computed values match/differ from this site’s headline numbers.

## Open Questions
- Where (if anywhere) does the site publish its underlying time series and coding methodology?
- Which of the headline metrics are based on levels at start/end vs within-term averages vs year-over-year growth rates?
