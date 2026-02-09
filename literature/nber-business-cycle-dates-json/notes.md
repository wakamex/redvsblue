# Notes: NBER Business Cycle Dates (JSON)

**URL:** https://data.nber.org/data/cycles/business_cycle_dates.json  
**Authors/Org:** National Bureau of Economic Research (Business Cycle Dating Committee; data.nber.org)  
**Published:** Data file (directory listing indicates last-modified July 2021; treat as periodically maintained)  
**Retrieved:** 2026-02-09  
**Local files:** `literature/nber-business-cycle-dates-json/source.*`, `literature/nber-business-cycle-dates-json/source.txt`

## What It Claims
- Provides the canonical NBER chronology of US business cycle peaks and troughs (monthly dates).
- Intended for identifying recession/contraction windows (peak-to-trough) used widely in economics and in “recession started under X” claims.

## Data & Definitions
- Data fields:
  - Array of objects with `peak` and `trough` fields formatted as `YYYY-MM-01` (first day of the month).
  - The first entry has an empty `peak` (series begins with a trough in 1854).
- Time period:
  - Starts in the mid-19th century (1854) and runs through the most recent NBER-dated cycle in the file.
- Party/presidency coding:
  - Not included; we must join these dates to a presidency calendar to attribute “recession starts” or “recession months/quarters” by party.
- Data sources:
  - NBER Business Cycle Dating Committee chronology (published on NBER’s site; this is a machine-readable version).

## Methodology / Identification
- Summary:
  - Not an analysis; a reference dataset.

## Results (Quantitative)
- N/A (dataset).

## Strengths
- Authoritative, widely used recession dating benchmark.
- Machine-readable format is convenient for automated pipelines.

## Weaknesses / Risks
- Monthly granularity + presidency transitions within months can create ambiguity in attribution.
- Must be careful about interpretation:
  - NBER “peak month” is typically the last month of expansion; contraction begins the following month.
  - NBER “trough month” is typically the last month of contraction; expansion begins the following month.

## Replication Notes
- Code/data availability:
  - The JSON file is directly downloadable; no additional code required.
- Gotchas:
  - When computing “recession started under President X,” use a clearly defined rule:
    - Start month = month after `peak` (recommended), or
    - Start month = `peak` month (if you interpret differently), but be consistent and disclose.
  - Converting to quarters: decide whether a quarter is “in recession” if any month is in contraction vs majority-of-months, etc.

## Takeaways For Our Pipeline
- Use this file (or an equivalent canonical NBER source) as the single source of truth for recession windows.
- Publish an explicit recession-attribution function (month-level) with test cases around inaugurations.

## Open Questions
- Do we want to define “recession begins under” by:
  - the start month (month after peak),
  - the peak month,
  - or the quarter containing the start month?
  Each leads to different headline counts; we should report sensitivity.
