# Row 62 (part a) mutation deepening: c32 dossier and c31 replicate_plan

Scope literal: test hardening only; row 62 stays PARTIAL. PART A ONLY: `c37/patents.py` (the third module named for row 62)
is NOT covered by this patch. No production change, no network. Uses the harness `run_mutations.py` from batch A.

## Reproduce
- Tests: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_c32_dossier_s27.py tests/modules/test_c31_replicate_plan_s12.py tests/modules/test_c62_dossier_plan_deepening.py -q`
- Battery: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 audits/rows-47-64-deepening/run_mutations.py b62a`
  (writes `receipts_b62a.txt`; mutants in `batteries/b62a.py`, exact old/new text). CAUGHT only on pytest rc 1 with FAILED
  lines; rc 0 SURVIVED; otherwise INVALID; SHA-256 restore check on every mutated file.

## Results
- Final run: 24 mutants (dossier G1-G12, replicate_plan R1-R12), CAUGHT=24, SURVIVED=0, INVALID=0, SHA restore True.
  They cover the private-facts refusal, name filter, per-dimension cap, completeness denominator, sentence splitting,
  case handling, citation counting, keyword sets, source validation and caps; and license routing (bsd/gpl/unknown),
  closed-source copy refusal, route and count semantics, capability de-duplication, ordering, validation and caps.
- First run (existing tests only): CAUGHT=19, SURVIVED=5 (G3 per-dimension cap, G10 'award' keyword, R1 bsd, R5 duplicate
  capabilities, R9 gpl treated as open). Preserved as `receipts_b62a_run1_with_5_survivors.txt`.
- Repair: new `tests/modules/test_c62_dossier_plan_deepening.py` (4 tests).

## Limits: what stays untested
- `c37/patents.py` and the venture_v2 tests are not mutated here.
- Both modules work only over SUPPLIED records; nothing here shows autonomous research, real people or ventures, or
  "better version" builds. The keyword lists drive dimension coverage; only the recognition list is checked keyword by
  keyword. The other four lists are not pinned individually.
- A green run shows the tests notice these 24 edits, not that the dossier or plan is correct or complete.
- Receipts are recorded local harness runs, not independently re-run.
