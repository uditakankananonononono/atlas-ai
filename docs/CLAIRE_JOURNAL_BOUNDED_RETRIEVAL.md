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
