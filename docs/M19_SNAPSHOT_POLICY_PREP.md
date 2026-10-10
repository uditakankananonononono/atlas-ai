# M19 snapshot frontier: honest policy and future snapshot contract (PREP)

Base: 94fba3f76ae55d02163577921b4fd85f82a548c5. Docs and tests only. No product edits.
Status: the builder authored this work and did NOT run it (only a py_compile syntax check on the test file). The peer's independent auditor
reported running it: the 11 new tests PASS (5 of them killed by a mutation, along with the existing binding test). That execution is the PEER
auditor's, reported to the builder, and is not a builder or this-side run.
Open LOW items (not fixed): the stage test compares two identical repositories, so it shows determinism rather than "no memory of the prior stage";
the stage test's negative field-name assertion is brittle; the doc-text test is a weak substring check.
Read at base: m19_idea_incubator/{historical_ranking.py,ranking.py,schemas.py,repository.py,ranking_router.py}, docs/M19_ASOF_RANKING.md,
tests/modules/test_m19_historical_ranking.py. `sql_repository.py` does NOT exist at this base; `SqlIdeaRepository` and
`MemoryIdeaRepository` both live in repository.py. This document therefore treats repository.py as the storage surface.

## 1. What `rank_portfolio_as_of` is today
A filter over CURRENT repository state. It compares each row's own timestamps to `as_of`, then reuses `rank_portfolio` unchanged.
It returns diagnostics for excluded rows (kind, id, reason, timestamp) and a sha256 digest over: as_of, half-life, include_terminal,
stale policy, limit, the INCLUDED scoring rows (full `model_dump`), included ids, excluded (kind,id,reason), ranked order.
It states `reconstruction_claimed=False`. This document does not change that.

## 2. Exactly what state is unrecoverable
Derived from schemas.py and repository.py at base (each row type stores only its latest values):
1. Idea stage at as_of. `Idea.stage`, `version`, `updated_at` are overwritten by `save_idea`. `Decision` rows (from_stage, to_stage, decided_at) exist,
   so stage MAY be inferable by replaying decisions, but no code does this and decisions are not guaranteed to be the only writer. Today: unrecoverable.
2. Idea title/problem/proposed_solution/tags/metadata at as_of (overwritten on save; only `version` counter survives).
3. Experiment status, observed_value, learnings, deadline at as_of. `save_experiment` overwrites; only `updated_at` shows that a change happened later.
   Hence the `exclude` policy for experiments with updated_at > as_of.
4. Evidence and feasibility-test field VALUES if edited in place after as_of. Repository exposes only add_*; no edit API was seen for them at base, but nothing in the
   schema prevents a direct SQL update, and `created_at` is a single value, not a revision list. A value change is invisible to timestamps.
5. EXCLUDED rows' values. The digest binds excluded rows only by (kind, id, reason). Changing an excluded row's strength/claim/etc. at the same id, reason and
   timestamp leaves the digest unchanged (documented residue in docs/M19_ASOF_RANKING.md: "Editing an excluded future row's strength need not change it").
6. Rows deleted after as_of: absent from the repository now, so neither included nor diagnosed.
7. Diagnostics scope: only rows visited for eligible current-stage ideas (per M19_ASOF_RANKING.md), not a census.
8. Read consistency: each list_* call is a separate read; no point-in-time transaction.

What IS recoverable from row timestamps alone: whether a row's creation/observation/test timestamp is <= as_of. That is all the current filter uses.

## 3. Proposed future immutable snapshot contract (NOT IMPLEMENTED; proposal only)
Goal: a record captured AT ranking time that later readers can compare against, instead of inferring the past from current rows.
Snapshot object (`M19RankingSnapshot`), append-only, never updated:
- `snapshot_id`, `tenant_id`, `revision` (monotonic int per tenant), `captured_at` (server time at capture, UTC), `as_of`, `half_life_days`, `include_terminal`,
  `limit`, `stale_experiment_policy`, `code_version` (git sha of scoring code).
- `included`: FULL rows (ideas, evidence, tests, experiments) as `model_dump(mode="json")` that fed scoring.
- `excluded`: FULL rows (not just id/reason) with reason and timestamp, for every row visited, plus an explicit `census_scope` field (`visited_rows_only` or `all_rows`).
- `result`: the ranked output.
- `content_hash`: sha256 over canonical JSON (sorted keys, compact separators) of every field above except `content_hash`.
- `source_state_caveat`: fixed string saying rows were read from CURRENT state at captured_at; a snapshot captures what the system saw then, and says nothing about earlier history.
Rules:
- Snapshots are inserted, never updated or deleted by application code.
- Reading a snapshot later is the only way to know "what the ranking saw"; recomputing from current rows is a different thing and must be labelled so.
- A snapshot taken after an in-place edit records the edited value; it cannot repair earlier time.
Explicit non-claims: no signature, no anti-rollback, no tamper-evidence beyond the content hash being a checksum. Anyone with write access can insert a consistent
fake snapshot or delete rows. The hash proves only internal consistency of one record.
Consistency: capture inside one read transaction (or REPEATABLE READ) when the backend supports it; otherwise record `consistent_read=false`.

## 4. Migration / backfill / unknown policies
- Existing deployments have no snapshots. No backfill creates historical snapshots: reconstructing them would be exactly the pretense this policy rejects.
  Option: a one-time "genesis" snapshot at migration time, labelled `kind=genesis`, captured_at = migration time.
- Queries for an `as_of` earlier than the tenant's first snapshot: respond with the current as-of filter result AND `snapshot_available=false`; never present it as archival.
- Queries when a snapshot exists for the exact parameters: return it with its captured_at and hash; also allowed to return the live filter result side by side with a
  `diverged` flag computed by comparing hashes of included rows.
- Unknown/missing fields in old rows (e.g. null updated_at): record as `unknown` in the snapshot, do not default to as_of.
- Stale experiment policy stays `exclude` by default; `current` must continue to flag.
- Schema/versioning: `snapshot_schema_version` in each record; readers reject unknown versions rather than guess.

## 5. Claims that must be rejected
- "as-of ranking reconstructs historical state."
- "the digest binds excluded values" (it binds excluded kind/id/reason only).
- "snapshots are signed / tamper-proof / rollback-protected."
- "diagnostics are a complete repository census."

## 6. Boundary tests (builder-authored; independently run by the peer auditor, 11 PASS): tests/modules/test_m19_asof_digest_boundary_prep.py
Uses only existing APIs (`rank_portfolio_as_of`, schemas) with an in-test fake repository (no engines/sessions, avoiding the ORM Connection pitfall).
- excluded_value_change_same_id_reason_time_leaves_digest_unchanged: pins today's honest residue; does NOT demand binding.
- included_strength_change_changes_digest (and a second case per included kind): sensitivity test; fails if included scoring inputs are dropped from the digest.
- current_stage_mutation_changes_current_filter_not_archival_state.
- stale_experiment_exclude_and_current_are_distinct.
Canonical command from repo root (pyproject pythonpath=backend): `python -m pytest tests/modules/test_m19_asof_digest_boundary_prep.py -q`, then the whole M19 module set.
Unresolved: snapshot storage location (table vs object store), retention, whether decisions replay should be offered for stage-at-as_of.

## 7. Current claim contract

This table pins today's claim boundaries, not the proposed snapshot implementation.

| Capability | Status | Meaning |
| --- | --- | --- |
| As-of ranking | CURRENT_FILTER | Current stage and field values; row timestamps only. |
| Historical reconstruction | NOT_IMPLEMENTED | No archival state can be recovered from current rows. |
| Immutable snapshots | PROPOSAL_ONLY | No snapshot storage or capture endpoint exists. |
| Excluded values | NOT_BOUND | Digest binds excluded kind/id/reason, not full excluded values. |
| Diagnostic census | VISITED_ONLY | Not a complete repository census. |
| Signature and anti-rollback | NOT_CLAIMED | Hash is a checksum, not authentication or rollback protection. |

## 8. Local audit refresh

The landed peer prep is already present on main7792260305b4208d3657099c973e914f3302dbcf. This additive docs/test follow-up does not re-land the same original package, change product behavior or implement snapshot storage. Baseline fresh wholeM19:291PASS8SKIP20.36s. The three LOWs above are historical and now addressed: one same repository is ranked, changed to PARKED, ranked again, restored and ranked again, with complete result equality and intermediate exclusion asserted; affirmative reconstruction_claimed/note/caveat assertions replace brittle absent-field-name guessing; exact parsed claim/status/meaning table replaces loose doc substring checks. Independent audit confirmation is pending.

After LOW repairs: wholeM19291PASS8SKIP16.74s under default environment. All eight skips require an isolated SQL database, not missing behavior; fresh isolated SQLite wholeM19299PASS22.68s with no skips. Three new direct mutation probes fail at the intended acceptance assertions: retained prior ranking across same-repository stage edits, reconstruction_claimed=True, and changing the structured historical-reconstruction status to IMPLEMENTED. All sources restored after each probe. This execution is local, not inherited peer verification. The future snapshot implementation remains a separate unit requiring its own audit.
