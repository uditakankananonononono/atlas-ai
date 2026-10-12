# m12 education_support helper hardening (standalone tests + mutation battery)

NO ROW-COMPLETION CLAIM. This hardens the existing helper `backend/app/modules/m12_ai_research_lab/education_support.py`
(feature rows 1460-1509 of its own numbering). It is not the requested Class 11 CBSE app (crosswalk row 46) and does not
promote any crosswalk row. No production code was changed; the patch adds a test file and audit files only.

## Why a new test file
The two older test files (`test_m12_education_1460_1509.py`, `test_m12_education_b5_remaining.py`) import `app.main`, which
needs Python 3.11 (`enum.StrEnum`); on this Python 3.10 sandbox they cannot be collected, so they were not run and are not
part of this battery. `tests/modules/test_m12_education_support_hardening.py` imports only the helper module, so it runs on
3.10 (31 tests). It asserts exact values, boundaries, orderings and refusals; it does not replace the older route tests.

Run (repo root): `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_m12_education_support_hardening.py -q`

## Mutation receipts
`python3 audits/m12-education-support/run_mutations.py` -> `mutation_receipts.txt` (38 mutants E1-E38, all in
education_support.py). CAUGHT only when pytest exits 1 with FAILED lines (ids recorded); rc 2/4/5, a timeout or no FAILED line
is INVALID. Mutated files are SHA-256 checked as restored.
- First run: CAUGHT=36, SURVIVED=2 (E9 recommendation tie-break by id removed; E36 need() treating empty as present). The
  first-run file is preserved as `mutation_receipts_run1_with_2_survivors.txt`.
- Repair: the 1463 test now feeds tied candidates in the reverse of id order, and a new test checks that None, an empty list
  and an empty dict are all refused as missing input. Final run: CAUGHT=38, SURVIVED=0, INVALID=0, SHA restore True.
- Commit the source and tests before running the harness: killing it mid-run can leave a mutant on disk.

## Limits: what stays untested
- The older route and endpoint tests (app.main, FastAPI routes, tenant and actor context) are NOT run here; the route layer
  is untested by this file.
- Rows with exact-value or list assertions here: 1460-1471, 1473, 1476, 1477, 1479-1484, 1486, 1489, 1490, plus the
  boundary and provenance envelope. Rows 1472, 1474, 1475, 1478, 1485, 1487, 1488 and 1491-1509 are covered only by the
  older tests (not run here) or not at all. No mutant targets 1491-1509 (tutor dialogue, human, inclusion, language
  spaced repetition).
- Equivalent or redundant checks were not mutated: in 1460 the value and weight range checks are enforced twice (inside
  `number()` and again after it), so removing one copy is not observable.
- Some tests pin current behavior rather than a spec: for example 1486 `review` includes the current step, and the
  language and spaced-repetition arithmetic is unpinned.
- Output text (prompts, boundary statement) is mostly not asserted. These are decision-support drafts; nothing here shows
  educational validity, fairness, or fitness for any learner.
- No live or network calls; there are none in the helper.
- Mutation receipts are recorded local harness runs, not independently re-run.
