# Rows 47-54 mutation deepening (student_platforms registry and listing parsers)

Scope literal: test hardening only. Rows 47-50 and 52 remain launch_only PARTIAL pending the owner's account
authorization; 51, 53 and 54 remain PARTIAL. No row is promoted. No network: all requests go to httpx.MockTransport, and the
launch_only rows are asserted to make no request at all. One comment-only edit outside the tests is described below.
Uses the harness `run_mutations.py` from batch A.

## Reproduce
- Tests: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m01_student_platforms.py tests/modules/test_m01_student_platforms_row54.py tests/modules/test_m01_student_platforms_deepening.py -q`
- Battery: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 audits/rows-47-64-deepening/run_mutations.py b47_54`
  (writes `receipts_b47_54.txt`; mutants in `batteries/b47_54.py`, exact old/new text). CAUGHT only on pytest rc 1 with
  FAILED lines; rc 2/4/5, timeout or no FAILED line is INVALID; rc 0 is SURVIVED; SHA-256 restore check on every mutated
  file. Commit before running.

## Results
Final run: 55 mutants, CAUGHT=55, SURVIVED=0, INVALID=0, NOT-APPLICABLE=0, SHA restore True. Per row (mutants CAUGHT):
47: 5, 48: 5, 49: 5, 50: 6, 51: 6, 52: 5, 53: 6, 54: 17. Launch_only rows are mutated on mode, URL, display name, kind and
reason (row 50 also on the "do not evade" wording); 51 and 53 on the h3 and card filters, path patterns, host, scheme,
userinfo, query/fragment stripping and title filters; 54 on the shared RSS reader (https check, dedupe, ranking, limit,
status, content type, size cap, redirects, atom, bounds, unknown id) and on the registry entries of the ten sources.
- Run 1 (existing tests only): CAUGHT=15, SURVIVED=33, INVALID=1 (the INVALID was a malformed mutant of mine, H51-f; the
  mutant was corrected). Preserved as `receipts_b47_54_run1_with_33_survivors_1_invalid.txt`.
- Run 2 (after the new tests and 7 added mutants): CAUGHT=53, SURVIVED=2, INVALID=1 (D54-p nsffunding kind survived; D54-r
  survived; D54-q was a malformed mutant). Preserved as `receipts_b47_54_run2_with_2_survivors_1_invalid.txt`.
- D54-r (dropping the module-level `assert len(BY_ID) == len(PLATFORMS) == 27`) is an EQUIVALENT mutant relative to the
  existing test of the same 27-count, so it was removed from the battery rather than counted. D54-q was rewritten as a
  kind change; D54-p was killed by new exact pins for the ten row 54 sources.
- New tests: `tests/modules/test_m01_student_platforms_deepening.py` (30 tests).

## Comment-only edit in c31/clicky.py
The `execute_stats_request` docstring residue paragraph is corrected: connect and header phases have only a
per-operation socket timeout and no total deadline in the worker, so the worker may outlive the call (a server sending
header bytes just inside each per-operation timeout may keep it running longer than `timeout`), and pool workers are joined
at interpreter exit, so a worker still running then can delay process exit. Comment-only; the clicky tests were re-run
(66 passed) and the batch A mutants are not affected.

## Limits: what stays untested
- No live fetch: layouts of fastweb and challengerocket (and every feed) are fixtures or synthetic HTML; a site layout
  change would not be caught. The challengerocket pattern list is pinned only by the cases in the new tests.
- MLH, Internshala and the other registry rows outside 47-54 are not mutated here.
- `scanned_at`, score values and the cosine ranking are not asserted beyond what existing tests check.
- Launch_only rows are asserted by registry pin and "no request"; nothing here shows any account workflow works.
- A green run shows the tests notice these 55 edits, not that the platform integrations are correct or complete.
- Receipts are recorded local harness runs, not independently re-run.
