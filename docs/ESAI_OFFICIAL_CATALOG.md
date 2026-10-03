# Official school/program catalog (ESAI lane D)

Status: bounded importer + runtime retrieval, built and run on real public files. Not a global database. Not a parity claim.

## Sources (public bulk files, no login, no API key, no sign-up)
| key | URL | sha256 (as imported 2026-10-03) |
|---|---|---|
| hd | https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip | d98425c123d7c0e872aec6e83960dfb501884818bf17385c340790f3d1f28345 |
| completions | https://nces.ed.gov/ipeds/datacenter/data/C2024_A.zip | 03234cc27fe4e7eb835a66d4f37aaec11bdac8dfa278f971584e1b20d03e1159 |
| cip | https://nces.ed.gov/ipeds/cipcode/Files/CIPCode2020.csv | 6cf0882c1f5beb94981d0a1a72285ab5cf633759f45433fb909afbfb6d6b2657 |

Freshness: IPEDS HD collection year 2024, 2023-24 award completions, CIP 2020 titles. The files on nces.ed.gov carry Last-Modified 2025-09-21. A 2025 HD file (HD2025.zip) returned 404 on 2026-10-03, so this is the newest I could confirm, not a claim that nothing newer exists.

## Terms (UNCONFIRMED for these files)
https://nces.ed.gov/help/disclaimer.asp returned HTTP 301 to https://nces.ed.gov/about/public-access-research (200); fetched 2026-10-03, saved in `docs/nces_disclaimer_fetch_20261003.txt`. Verbatim: "Unless stated otherwise, all information on the U.S. Department of Education's IES website at http://ies.ed.gov is in the public domain and may be reproduced, published, linked to, or otherwise used without IES' permission. This statement does not pertain to information at websites other than http://ies.ed.gov, whether funded by or linked to from IES." Cite: U.S. Department of Education. Institute of Education Sciences.
That statement names ies.ed.gov and expressly excludes other websites; it does not name nces.ed.gov, where the files are hosted. No file-specific grant was found. So public-domain status of the dataset is NOT settled and commercial redistribution is NOT licensed by anything I found. What this supports: a private, local catalog built from public downloads, with attribution. Do not redistribute the data files or the built database, and do not claim a licence, until NCES clarifies the terms. IPEDS collection forms also show "restricted data" warnings; these files are the public Data Center downloads.

## Downloader integrity
`--download` pins each URL to a sha256 and a size cap, streams with the cap enforced, ignores proxy environment variables (explicit empty ProxyHandler), refuses redirects off https://nces.ed.gov, and discards the file on hash mismatch (NCES changing the file means: review, then re-pin deliberately). A live run on 2026-10-03 downloaded all three files and the hashes matched the pins.

## Sources checked and NOT used
- College Scorecard bulk files: data.ed.gov lists them as Creative Commons Attribution, but every download URL I could find or derive (ed-public-download.scorecard.network, collegescorecard.ed.gov/files, ed-public-download.app.cloud.gov) returned 403/404 from this environment. Not imported. Consequence: no cost, net price, earnings or admission data.
- Scholarships: no official bulk source with verified terms was found. Not covered. The existing `scholarship_guide` stays caller-supplied.
- Non-US schools: not covered.

## Coverage (real import, `scripts/verification/catalog_real_import_coverage.json`)
6072 institutions (5994 active, 4090 active degree-granting by DEGGRANT flag), 6001 with an institution-reported website, 5827 with at least one program row, 200,947 program rows (institution x CIP x award level), 2325 CIP titles, 0 program rows without a title. 20,679 completions rows were dropped as totals/aggregates, 0 unknown-unitid rows.
Programs are DERIVED from 2023-24 completions: a program that awarded nobody that year is absent, so this is not an offered-majors list. Website URLs are what institutions reported to IPEDS; they are not re-checked live.

## Use
- Import: `python -m app.modules.m23_study_abroad.official_catalog_cli import --dir DIR --db PATH [--download]`. `--download` only fetches the pinned https://nces.ed.gov URLs and refuses redirects off that host. The built sqlite is read-only at runtime and is not committed.
- Runtime (`ATLAS_CATALOG_DB`, default `backend/data/official_catalog.sqlite`; 503 with an explicit message if not imported):
  - GET /study-abroad/catalog/coverage, /catalog/schools?q&state&control&program&award&limit, /catalog/schools/{unitid}, /catalog/programs?q
  - POST /study-abroad/school-match-from-catalog {profile, unitids[<=200]} runs the existing school_match on catalog rows. annual_cost_usd is null, so budget fit is null. Unresolved unitids are listed, never invented.
- Every response carries file URLs, sha256 and retrieval time; the licence statement is in /catalog/coverage.

## Limits
- Tests use small authored fixtures (counts, filters, wildcard escaping, schema-drift refusal, host pinning) plus one smoke test against the real build that skips unless `ATLAS_REAL_CATALOG` is set. Fixture tests do not prove real-data behaviour; the real-run output is in `scripts/verification/catalog_real_queries.out`.
- Catalog routes use the existing tenant dependency; dev-mode header auth, not a production-auth claim.
- Matching quality is unchanged: school_match is token overlap on CIP titles and says nothing about fit or admission.
