# Notes: Trump and Biden: The National Debt-Mon, 06/24/2024 - 12:00 | Committee for a Responsible Federal Budget

**URL:** https://www.crfb.org/papers/trump-and-biden-national-debt  
**Authors/Org:** Committee for a Responsible Federal Budget (CRFB) / US Budget Watch 2024 project  
**Published:** June 24, 2024  
**Retrieved:** 2026-02-09  
**Local files:** `literature/crfb-trump-biden-national-debt/source.*`, `literature/crfb-trump-biden-national-debt/source.txt`

## What It Claims
- Compares Presidents Trump and Biden’s fiscal records using **estimated ten-year debt impact of policies approved** (legislation + executive actions) near enactment time.
- Argues this “approved-policy scoring” is different from measuring debt accumulated during a term, and is useful for comparing fiscal policy choices net of some inherited/baseline effects.
- Emphasizes that both Trump and Biden approved substantial borrowing, with COVID-era policy complicating comparisons.

## Data & Definitions
- Metrics:
  - “Ten-year debt impact” of policies approved by each president, including interest.
  - Gross deficit increases vs deficit-reducing actions.
  - Breakdown by partisan vs bipartisan legislation; executive actions vs legislation.
  - Also reports changes in “debt held by the public” over overlapping time windows.
- Time period:
  - Trump: full term (Jan 20, 2017–Jan 20, 2021).
  - Biden: first ~3 years and 5 months (Jan 20, 2021–Jun 21, 2024).
- Party/presidency coding:
  - Not a D/R comparison paper; focuses on two presidents.
- Data sources:
  - Uses official budget scores/projections from CBO/JCT and OMB where available; agency/regulatory estimates; CRFB estimates where needed.

## Methodology / Identification
- Summary:
  - Collect major legislation and executive actions with >$10B ten-year impact.
  - Use the **ten-year budget window at the time of enactment** (so policies cover different calendar windows; numbers are not strictly additive/comparable).
  - Incorporate interest costs using CBO debt service tools; mostly conventional scoring, with TCJA scored dynamically per CBO.
- Key methodological caveat:
  - This is *not* realized debt accumulation; it is “scored” policy impact at time of approval, and actual outcomes can differ.

## Results (Quantitative)
- Headline findings (as stated in the CRFB text):
  - Trump approved **$8.4T** of new ten-year borrowing over his full term; **$4.8T** excluding CARES Act + other COVID relief.
  - Biden (through Jun 21, 2024) approved **$4.3T** of new ten-year borrowing; **$2.2T** excluding the American Rescue Plan.
  - Trump: **$8.8T** gross new borrowing and **$443B** deficit reduction actions.
  - Biden: **$6.2T** gross new borrowing and **$1.9T** deficit reduction actions.
  - Debt held by the public rose by **$7.2T** during Trump’s term; debt held by the public has grown by **$6.0T** during Biden’s term so far.
  - Executive actions: Trump < **$20B** net; Biden **$1.2T** net ten-year debt increase (as stated).

## Strengths
- Clear definition of what is being measured (“approved policy scores”) vs what is *not* (realized debt over the term).
- Uses official scoring sources and documents numerous caveats and likely score-vs-reality divergences.
- Nonpartisan framing; useful for pipeline modules that need a “policy-scored fiscal impact” view.

## Weaknesses / Risks
- Comparability issues:
  - Ten-year windows differ across enactments; scores are not directly additive or time-aligned.
  - Scoring uncertainty is material (TCJA, IRA credits, pandemic programs, executive actions).
- Excludes smaller actions (<$10B) and unfinalized actions; may miss important cumulative effects.

## Replication Notes
- Code/data availability:
  - Not a full replication package in the extracted text; reconstruction would require assembling the same list of actions and the referenced scores.
- Gotchas:
  - Must distinguish “ten-year scored impact” from “observed debt change” (they explicitly say they will publish debt-during-term as a supplemental analysis).

## Takeaways For Our Pipeline
- Add two distinct fiscal lenses:
  - **Realized debt change** (Treasury series; nominal/real/%GDP).
  - **Scored approved-policy impact** (CBO/JCT/OMB/CRFB style), clearly labeled and non-additive across different windows.
- For any president-to-president comparison, publish both lenses to avoid category errors.

## Open Questions
- For our “performance under presidents” pipeline, which fiscal metric should be the default: realized deficit/debt outcomes, or scored policy actions?
- How should we handle score revisions (ex post) vs “as-enacted” scores in a reproducible way?
