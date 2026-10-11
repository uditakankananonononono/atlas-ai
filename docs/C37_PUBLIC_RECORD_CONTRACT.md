# c37 public-record watcher contract (S6.3)

HER-WORDS (15:01:13, verbatim): "keep an eye out for top secret projects, governement stuff too, super elite stuff"

## What it does
Watches the fixed source registry in `backend/app/modules/c37/public_record.py` over supplied fixtures. It diffs new/changed items, classifies topic, ranks by novelty and reports each item with source URL and fetch date.

Routes (handlers `post_run` / `get_report`, path table `ROUTES`):
- POST /api/v1/c37/public-record/run  body `{"fetch_date": "YYYY-MM-DD", "sources": {source_id: [items]}}`
- GET /api/v1/c37/public-record/report

## Refusals
- INTEL_REFUSED_CLASSIFIED: classification markers on an item (item is dropped; only a positional handle `<source>#<index>` and the code are reported); credentials, auth or probing keys anywhere in a request (run raises).
- INTEL_REFUSED_NOSOURCE: no https URL on the registry source's hosts, or source not in the registry.
- INTEL_REFUSED_PRIVATE: private-individual fields or SSN/email/phone patterns.
Check order: CLASSIFIED, NOSOURCE, PRIVATE. Marker matching is fail-closed and can drop a harmless public item that mentions "top secret".

## Never-echo rule
Refused items, unknown source keys and rejected requests are reported by code and positional handle only (`item_ref`, `unknown-source#N`). Item id, title, summary, published and url are all scanned for classified markers and private-individual patterns before anything is reported or stored, so a refused value never appears in the report or the diff state.
Other checks: `fetch_date` must be a real calendar date (YYYY-MM-DD); a malformed URL or a port other than 443 is INTEL_REFUSED_NOSOURCE.

## LIMITS
- Public records only. It cannot see, obtain or confirm "top secret" or classified content, and every report says so.
- Only registry-listed sources are watched (10 today, count reported in `coverage`). Never "all government".
- Fixtures only: no network, no crawling, no accounts. A live fetcher is a separate unit and must respect each source's terms.
- Registry hosts are listed from general knowledge and not verified live in this unit.
- Novelty and topic are keyword and diff heuristics, not a judgement of significance.
