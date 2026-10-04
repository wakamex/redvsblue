# Literature

This directory publishes source links and review notes used to inform the economic comparison methodology. Downloaded source files and extracted text are local reference material excluded from Git by `.gitignore`.

## Source index

Each source links to its publisher or host. Review notes summarize claims, methods, and implications for the pipeline.

- [Political Cycles and Stock Returns](https://www.nber.org/system/files/working_papers/w23184/w23184.pdf) ([review notes](nber-w23184/notes.md))
- [Political Cycles and the Stock Market](https://www.escholarship.org/uc/item/00n6f3ph.pdf) ([review notes](santa-clara-valkanov-presidential-puzzle/notes.md))
- [Presidential Data 2024](https://presidentialdata.org/) ([review notes](presidentialdata-org/notes.md))
- [Shattering the GOP Economic Myth - Senator Jerry McNerney](https://sd05.senate.ca.gov/news/shattering-gop-economic-myth) ([review notes](ca-senate-shattering-gop-economic-myth/notes.md))
- [Presidents and the U.S. Economy: An Econometric Exploration](https://www.nber.org/system/files/working_papers/w20324/w20324.pdf) ([review notes](blinder-watson-2014-presidents-us-economy/notes.md))
- [The Historical Puzzle of US Economic Performance under Democrats vs. Republicans - The Belfer Center for Science and International Affairs](https://www.belfercenter.org/publication/historical-puzzle-us-economic-performance-under-democrats-vs-republicans) ([review notes](belfer-frankel-2024-historical-puzzle/notes.md))
- [Does the Economy Really Do Better Under Democratic Presidents? - The Belfer Center for Science and International Affairs](https://www.belfercenter.org/publication/does-economy-really-do-better-under-democratic-presidents) ([review notes](belfer-2016-economy-better-democrats/notes.md))
- [Why does the economy do better when Democrats are in the White House?](https://www.aeaweb.org/research/why-does-the-economy-do-better-democrats-white-house) ([review notes](aea-why-economy-better-under-democrats/notes.md))
- [Economic Performance Is Stronger When Democrats Hold the White House](https://epiaction.org/wp-content/uploads/2024/08/Full-Report_Economic-performance-is-stronger-when-Democrats-hold-the-White-House.pdf) ([review notes](epi-bivens-2024-economic-performance/notes.md))
- [The U.S. Economy Performs Better Under Democratic Presidents - The U.S. Economy Performs Better Under Democratic Presidents - United States Joint Economic Committee](https://www.jec.senate.gov/public/index.cfm/democrats/2024/10/the-u-s-economy-performs-better-under-democratic-presidents) ([review notes](jec-democrats-2024-economy-better-democrats/notes.md))
- [Clinton: Economy Better Under Democrats - FactCheck.org](https://www.factcheck.org/2015/10/clinton-economy-better-under-democrats/) ([review notes](factcheck-2015-economy-better-democrats/notes.md))
- [PolitiFact -  Does the economy always do better under Democratic presidents?](https://www.politifact.com/factchecks/2016/apr/06/hillary-clinton/does-economy-always-do-better-under-democratic-pre/) ([review notes](politifact-2016-economy-better-democrats/notes.md))
- [NBER Business Cycle Dates (JSON)](https://data.nber.org/data/cycles/business_cycle_dates.json) ([review notes](nber-business-cycle-dates-json/notes.md))
- [Introduction to U.S. Economy: The Business Cycle and Growth](https://crsreports.congress.gov/product/pdf/IF/IF10411) ([review notes](crs-if10411-business-cycle/notes.md))
- [Democrats vs. Republicans: Who Had More National Debt?](https://www.investopedia.com/democrats-vs-republicans-who-had-more-national-debt-8738104) ([review notes](investopedia-democrats-vs-republicans-economy/notes.md))
- [Trump and Biden: The National Debt-Mon, 06/24/2024 - 12:00 - Committee for a Responsible Federal Budget](https://www.crfb.org/papers/trump-and-biden-national-debt) ([review notes](crfb-trump-biden-national-debt/notes.md))

## Local reference files

- `literature/<slug>/source.*`: optional downloaded originals and extracted text, retained locally and ignored by Git.
- `literature/<slug>/notes.md`: tracked review notes.
- `literature/manifest.json`: source URLs and expected local paths; a listed source or text path does not imply the file is included in a checkout.
- `literature/_scripts/`: download and text-extraction utilities.
- `literature/_templates/`: review-note templates.

Keep extracted text in the ignored source files and analysis in the tracked notes. A fresh checkout contains the links and notes; downloaded reference files must be obtained separately from the linked sources.
