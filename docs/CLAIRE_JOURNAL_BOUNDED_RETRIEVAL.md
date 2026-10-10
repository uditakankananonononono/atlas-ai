# Claire journal bounded retrieval integration candidate

Status: local integration candidate. Additive session-owned method and authenticated
/decisions/bounded route; legacy retrieval unchanged. No migration or main landing.

Problem: `PersistentJournal.retrieve` (`backend/app/modules/m21_claire/persistent_journal.py`)
loads every row for the tenant/actor/kind into memory and scores in Python, so
read cost grows with journal size.

Helper: `backend/app/modules/m21_claire/bounded_journal_retrieval.py`
- `validate_retrieval_bounds(...) -> JournalRetrievalBounds`: validates the
  nonempty query (max 4000 chars), limit 1-20, kind in {decision, correction},
  timezone-aware since/until with since <= until, positive after_id/before_id
  with after_id < before_id, and scan_cap 1-2000 with limit <= scan_cap. Runs
  before any read; invalid input raises ValueError without touching the DB.
- `bounded_retrieve(session, *, tenant_id, actor_id, ...)`: read-only SELECTs
  against a caller-owned Session. Filters (tenant, actor, kind, time and ID
  window) are pushed into SQL; the scan is `ORDER BY id DESC LIMIT scan_cap`
  (newest first, deterministic; page older rows with before_id). A single SQL window
  COUNT in the bounded select yields matched_total so omission accounting
  is exact without reading the uncapped set. Scoring reuses `lexical_vector`
  from `persistent_journal` (imported, not duplicated) and hit ordering
  matches `retrieve`: score desc, id asc on ties, zero scores dropped.
- Result: hits plus matched_total, rows_read, scored, below_threshold,
  omitted_by_limit, omitted_by_scan_cap, truncated, and the echoed window.
  Every hit and the summary carry `"retrieval": "lexical_not_semantic"`;
  scores are hashed bag-of-words, not semantic embeddings, and
  `"external_action_permission": false` - no stored decision grants action.

Tests (integrator executed; raw receipt supplied separately): `tests/modules/test_m21_bounded_journal_retrieval.py`
- `test_validation_happens_before_any_read`
- `test_bounded_scan_reports_honest_truncation`
- `test_time_and_id_window_predicates`
- `test_tenant_actor_kind_isolation_and_threshold_accounting`
- `test_scoring_parity_with_persistent_journal_retrieve`

Open dependency decisions for the integrator:
- Helper imports `JournalEntry`/`lexical_vector` from `persistent_journal`;
  that module is unmodified, so scoring parity is by construction.
- Session ownership, route wiring, any index/migration for created_at, and
  running the tests belong to the integrating side. The ID primary key is the
  deterministic ordering; created_at is filter-only.

Paging uses oldest_scanned_id, even when no positive hits exist. Newest ID window
is not global top-k. Row count and results share a single-statement view, but COUNT
can still scan all matches in the database; bounded Python rows is not bounded DB
CPU. SQLite tested; PostgreSQL behavior/load remains unverified. No table/index
changes are included. Caller/session ownership is explicit in retrieve_bounded.

## Independent integration verdict

Clean4ac7212c source equivalent to reviewed71ad0198 except executed test marker.
Independent SQLite whole266PASS32.7s; new8tests repeated six runs. Paging union,
zero-hit/empty windows, tenant isolation, pre-query refusals reproduced. Shared
require_tenant route code-read, not TestClient permission proof.
Earlier builder timeout-interrupted3FAIL lines remain UNRECONCILED; reviewer did
not reproduce them. Timeout-kill hypothesis is plausible, NOT a finding.
count(*) OVER() still counts all matching rows: Python row materialization bound,
NOT DB CPU cost bound. SQLite only; PostgreSQL/load unmeasured, no index/migration.
Concurrent inserts/deletes can shift matched_total between pages. ID paging key,
created_at filter-only. Newest scan window selected BEFORE scoring, not global
top-k. limit<=scan_cap. Legacy route unchanged.

## Additive no-total cursor window candidate
After journal initialization, each cursor retrieval issues one SELECT LIMIT scan_cap+1 with no COUNT. HTTP store dependency may also inspect/create schema; unchanged exact-count endpoint still uses COUNT. Probe row determines has_more but is not scored
or consumed by next_before_id, including zero-hit pages. matched_total and
omitted_by_scan_cap are null/unknown_not_counted, never invented0. At most2001
Python rows, up to2000scored; no DB CPU bound because filters may examine more
rows. Existing exactcount route unchanged. No migration/index claim; time/cursor
Retrieval helper validates time/cursor bounds before its SELECT. HTTP store dependency initializes/checks journal schema before route-level bounds rejection. Tenant+actor predicates. Concurrent inserts/deletes can
change page contents/has_more. Cursor points to consumed oldestID, not lexical
hits. scan_cap selects newest window before scoring; hit limit applies after lexical scoring. No global top-k. SQLite and isolated localPG canaries
separately reported; no deployedload/backup/transaction-snapshot paging claim.

Cursor candidate builder evidence: new14PASS including real localPostgreSQL16.2
LIMIT/noCOUNT probe and productionOIDC TestClient 401/tenantisolation/422canary.
All tests selected by tests/modules/test_m21*.py: candidate 277 PASS 3 FAIL; exact 02a75fbd base 263 PASS 3 FAIL; no skips; identical 3 failing nodes. Not repository-wide suite. SameM21claire nodes
missingm00_approval_events. Base-present fixture issue, cause isolation beyond
missingtable not yet performed; no regression or wholegreen claim. Legacy prior
266PASS depended on environment state and doesn't erase these failure receipts.

matched_total and omitted_by_scan_cap unknown; omitted_by_limit counts positive matches omitted within scored window.
