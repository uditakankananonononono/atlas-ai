# ATLAS-5 - M25 metadata first-new-append restart canary (PREP, authored-not-run)

Prep-only test canary. The builder authored it under PREP-NORUN constraints:
no pytest, no execution, no imports of product code, no network, no
credentials, no pushes, no main writes, no product edits. The integrator
executes and audits. Base pin: `94fba3f76ae55d02163577921b4fd85f82a548c5`.

## What it pins (beyond `tests/modules/test_m25_version_metadata.py`)

The existing file verifies one append in a single process. This canary
verifies the legacy-unknown / new-exact pair across an ACTUAL second Python
process:

1. First process builds a legacy number/hash-only manifest under the test
   root (a real ingest whose manifest row is then stripped to
   `{'number','hash'}`, matching the established pattern in
   `test_legacy_fallback_not_promoted_to_historical_metadata`).
2. Verified restore via `restore_verified(same_adapters_attested=True)` at a
   frozen clock (`RESTORE_STAMP`).
3. Exactly ONE new version appended at a distinct timezone-aware clock
   (`APPEND_STAMP`) and a distinct MIME (`text/html`; the legacy row
   re-derives as `text/plain`). The pipeline clock is fixed at construction,
   so the one-process restore-then-append uses a mutable clock cell.
4. A real subprocess (second Python process) restores from the same test
   root at `SECOND_STAMP` and reports state as JSON; the parent asserts:
   - legacy row still number/hash-only, `metadata_known` false (restamped per
     restore, by design), MIME re-derived `text/plain`;
   - new row `created_at`/`mime_type`/`metadata_known` EXACT (recorded
     metadata survives; restamping it on restore is a named failure);
   - chunks: exactly one per version, legacy chunk stamped at the second
     restore, new-version chunk carrying the exact append time; unique chunk
     ids (no duplicate append);
   - tree hash unchanged by the second-process restore (read-only);
   - a second `restore_verified` in the same process refuses
     (`pipeline-state`), pinning no duplicate append.
5. Negative (parametrized, 2 cases): malformed new-row metadata
   (`metadata_version: 2`; timezone-naive `created_at`) is refused
   (`manifest-schema`) in the second process WITHOUT publishing records or
   chunks, and without writing.

## Mutation expectations (acceptance is the integrator's)

- Promoting the legacy row to metadata-known at append -> named FAIL
  ("legacy promotion").
- Restamping the new row's `created_at` on restore -> named FAIL
  ("metadata pair").
- Duplicate append / chunk duplication / restamped chunk time -> named FAIL
  ("chunk identity").
- Existing tests are preserved untouched; nothing here weakens them.

## Scope exclusions (per unit)

No authenticity or signature claims for MIME-equivalent tamper (the
`text/plain`/`text/markdown` extraction equivalence is unchanged and out of
scope). No trusted-wall-clock claims. No historical reconstruction claims
(legacy rows restamp per restore; only metadata-known rows preserve time).
No deployment claims.

## Planned commands (integrator executes; builder ran NONE)

    python -m pytest tests/modules/test_m25_metadata_process_restart_prep.py -v
    python -m pytest tests/modules/test_m25_version_metadata.py tests/modules/test_m25_verified_rehydration.py -v   # preservation check

## Builder checks actually run (static only, reported separately)

- `python3 -m py_compile tests/modules/test_m25_metadata_process_restart_prep.py` -> OK.
- AST parse of the test file and of the embedded `CHILD_SOURCE` literal -> OK.
- No product code was imported, no test or subprocess was executed.

## Function vs case counts

2 test functions, 3 cases:
- `test_legacy_unknown_new_exact_pair_survives_second_process_restore` (1 case)
- `test_second_process_refuses_malformed_new_metadata` (2 parametrized cases:
  `metadata_version_not_1`, `created_at_timezone_naive`)
Helpers (not tests): `run_child`, `build_legacy_new_pair`, `CHILD_SOURCE`.

## Reading the unit required (all present at base 94fba3f7)

`tests/modules/test_m25_version_metadata.py`, `tests/modules/test_m25_verified_rehydration.py`
(helpers reused: `pipe`, `ingest`, `src`, `NOW`, `tree_hashes`,
`load_manifest`, `save_manifest`), `pipeline.py`, `recovery.py`,
`schemas.py`, `service_factory.py` (the factory doc: single-process,
explicit-root, owner-pinned; constructs `LocalKnowledgePipeline` with
`DeterministicEmbedder` + `UnavailableTranscriber` and calls
`restore_verified(same_adapters_attested=True)`). The M21 ORM/Session lesson
does not apply to M25 (no ORM); the factory's adapter pinning is mirrored by
constructing pipelines with the same default adapters and attested restore.
