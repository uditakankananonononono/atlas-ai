# M01 free-source match contract

Module: `backend/app/modules/m01_opportunity_discovery/free_source_match.py`
Tests: `tests/modules/test_m01_free_source_match.py`

## What this is

A read-only layer on top of the existing M01 student sources
(`student_platforms.py`, `student_intelligence.py`). It reuses them by import; nothing is copied. Form prefill is not part of this module (m02 owns it).

## Per-source truth

| Source | Public parsing | Why |
| --- | --- | --- |
| Fastweb | Yes: listing rows and detail pages | Public, logged-out pages; `robots.txt` disallows only `/member/`, `/new/`, `/ads_test_page` (checked 2026-10-11). |
| RippleMatch | No | Matching and auto-apply need an authorized account flow. |
| Simplify | No | Chrome extension the student installs; Atlas does not run it. The Copilot paid tier is not used. |
| RaiseMe | No | Balances and school matching need the student account. |
| Bold.org | No | The public listing returned a rate-limit challenge; Atlas does not evade it. |

For the four "No" sources the module returns `items: []` and the stated reason.
It never invents rows for them.

## Functions

- `source_capabilities()` - the five sources and what each can do.
- `read_fastweb_listing(client=None)` - rows from m01 `discover('fastweb')`; title, url and provider (title suffix) only, `evidence_status: listing_title_only`.
- `fetch_fastweb_detail(url, client=None)` / `parse_fastweb_detail(html, url)` - one public page into a row: title, provider, amount (USD), awards available, deadline (ISO date or the raw text such as `Varies`), description, minimum GPA when the text states one, whether applying needs an account. `evidence_status: parsed_from_public_page`.
- `match(profile, rows, as_of='YYYY-MM-DD')` - ranks rows. Criteria: `gpa` (hard), `level`, `award`, `deadline` (hard when passed), `interests`. Each has `status` met / unmet / unknown and an explanation quoting its evidence. Unknown stays unknown. `score` = met / (met + unmet). Order: eligible first, score, award, title. GPA is on the 4.0 scale (0-5 accepted).
- `search_and_match(profile, as_of, detail_limit=5, client=None)` - listing, detail pages for the first rows, matching. Detail failures are listed in `detail_errors`, not hidden.

## Refusals

`FREE_SOURCE_URL`, `FREE_SOURCE_PARSE:<field>`, `FREE_SOURCE_PROFILE:<field>`, `FREE_SOURCE_AS_OF`, `FREE_SOURCE_ROWS`, `FREE_SOURCE_LIMIT`. Network problems raise `PlatformUnavailable`.

## Limits

- No submit, no login, no account creation, no payment, no outreach. `submits` is always `false`.
- Listing rows carry no amount or deadline; only detail pages do. A page that shows `Varies` stays `deadline.value = null`.
- Level and region come from text mentions, not eligibility rules. Fastweb eligibility beyond the description text sits behind login and is not read.
- Fixtures in the tests are trimmed excerpts of real public Fastweb pages fetched 2026-10-11; negative cases are labelled synthetic. A live smoke test runs only with `ATLAS_LIVE_SMOKE=1`.
- No claim is made that a listed scholarship is open, legitimate or won.
