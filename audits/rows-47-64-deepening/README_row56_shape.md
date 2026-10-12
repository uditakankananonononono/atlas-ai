# Row 56 shape deepening (admitted_cases.json index and its loader)

Scope literal: test hardening only. Row 56 stays PARTIAL: the index is 20 publisher links, explicitly not a copied essay
dataset, not a licensed corpus and not admission evidence. No fetching, no production change. Uses the harness
`run_mutations.py` from batch A.

## Reproduce
- Tests: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m23_admitted_cases.py tests/modules/test_m23_admitted_cases_shape_deepening.py -q`
- Battery: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 audits/rows-47-64-deepening/run_mutations.py b56_shape`
  (writes `receipts_b56_shape.txt`; mutants in `batteries/b56_shape.py`, exact old/new text, on `admitted_cases.py` and on
  the JSON data file). CAUGHT only on pytest rc 1 with FAILED lines; INVALID otherwise unless rc 0 (SURVIVED); SHA-256
  restore check on every mutated file.

## Results
- Final run: 14 mutants (Z1-Z3, Z5-Z15), CAUGHT=14, SURVIVED=0, INVALID=0, SHA restore True. They cover the loader's
  duplicate-id, duplicate-host and https assertions, search casefolding, the evidence_type filter and searched fields,
  the unknown-id error, the reading route's `source_only` status and no-rehost reason, and data edits to one entry (http
  url, duplicate id, duplicate host, evidence type, title).
- Run 1 (existing tests only, 15 mutants including Z4): CAUGHT=6, SURVIVED=9. Preserved as
  `receipts_b56_shape_run1_existing_tests_only.txt`.
- Run 2 (with the new tests): CAUGHT=14, SURVIVED=1 (Z4, preserved as
  `receipts_b56_shape_run2_with_1_equivalent_survivor.txt`). Z4 removes the `min(limit, 20)` search cap; with exactly 20
  catalog entries the cap cannot be observed, so Z4 is an EQUIVALENT mutant and was removed from the final battery, not
  counted. It would become observable if the catalog grows past 20.
- New tests: `tests/modules/test_m23_admitted_cases_shape_deepening.py` (6 tests): exact ids and 20 hosts, exact field
  set and scope-note start, one pinned entry, loader refusals on a temp catalog, search behavior, unknown id.

## Limits: what stays uncovered
- Only entry `olin` has its title, URL and evidence type pinned; the other 19 entries are pinned by host only, so a title,
  school or evidence-type edit in them is not caught.
- The live fetch path is not touched here. Its row 56 runner and receipts (`run_row56_liveness.py`,
  `row56_receipts.json`, `verify_row56_receipts.py`) are not part of this patch; their compliance and results are not
  re-verified here, and the crawl-delay and host-pacing batteries cover the helper, not the runner.
- Nothing here shows the pages exist, say what the index claims, or are licensed for any use. `checked_on` is only checked
  as the fixed date 2026-09-25 by the existing test.
- Equivalent-mutant analysis was done only for Z4.
- A green run shows the tests notice these 14 edits, not that the index is correct.
- Receipts are recorded local harness runs, not independently re-run.
