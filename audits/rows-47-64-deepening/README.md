# Rows 47-64 mutation deepening - batch A (rows 57, 58; mapping for 56, 59, 63, 64)

Scope literal: test hardening only. No row is promoted beyond PARTIAL, no production code changed, nothing live was called.
Rows 41-46 are parked and untouched. Account-dependent rows (47-50, 52, live 57-59 tests) stay PARTIAL pending owner
authorization.

## Reproduce
- Tests: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 -m pytest tests/modules/test_c31_clicky_a3.py tests/modules/test_c31_okara_a3.py tests/modules/test_c31_adapter_plan_deepening.py -q`
- Battery: `ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python3 audits/rows-47-64-deepening/run_mutations.py b57_58`
  (writes `receipts_b57_58.txt`). Mutants are in `batteries/b57_58.py`, each one exact old/new text.
- Accounting: CAUGHT only when pytest exits 1 with FAILED lines (ids recorded). rc 2/4/5, a timeout or no FAILED line is
  INVALID. rc 0 is SURVIVED. A mutant whose old text does not occur exactly once is NOT-APPLICABLE. Every mutated file is
  SHA-256 checked as restored. Commit before running: a killed run can leave a mutant on disk.

## Results
- Row 57 (`c31/clicky.py`, plan, identify, parse and stats-planner layer): K1-K16, 16 mutants. Row 58 (`c31/okara.py`):
  O1-O11, 11 mutants.
- First run: CAUGHT=23, SURVIVED=4 (K6/O6 planned params not sorted; K10/O10 api_base trailing slash not stripped). That
  receipt is preserved as `receipts_b57_58_run1_with_4_survivors.txt`.
- Repair: new `tests/modules/test_c31_adapter_plan_deepening.py` pins parameter order, the encoded string and the base-URL
  join, for both adapters. Final run: 27 mutants, CAUGHT=27, SURVIVED=0, INVALID=0, NOT-APPLICABLE=0, SHA restore True.

## Mapping to existing receipts (not re-run here)
- Row 57 transport (`execute_stats_request`): C1-C10 in `audits/rows-47-64-delta/mutation_receipts.txt` (loopback tests).
- Row 63 (`training_data_units.py`): R1-R20 in the same file. Row 64 (`pipeline.py`, scale workflow): S1-S5 in the same file.
- Row 56: the fetch helper it relies on has the crawl-delay and host-pacing batteries in `audits/m23-crawl-delay/` and
  `audits/m23-host-pacing/`. NOT covered: the shape of `admitted_cases.json` (20 links) itself; no mutant targets it yet.
- Those receipts were produced by earlier batteries and are not part of this run's count.

## Row 59 (PaperBleach): skipped by decision, no mutation battery
The owner refused this product (a detector-evading humanizer) as policy, so row 59 was skipped by decision: no mutation
battery was run and `c35/paperbleach.py` is not hardened here. The file does contain identification and refusal logic
(refusals for missing source, oversize, bad candidate type, duplicate, bad free_tier, bad or missing evidence, and an
unidentified product that is never guessed). That logic is covered only by the existing
`tests/modules/test_c35_paperbleach_a2.py` (15 tests), which were not mutation-tested. No work to improve this row is planned.

## Limits: what stays untested
- Row 58: no public API was found. The okara module is a copy of the shared descriptor/plan/parse layer; the mutants test
  that layer, not any real Okara behavior. No endpoint was invented.
- Row 57: live behavior against the real service is unverified; `api.clicky.com` was never called.
- Only the layer with direct assertions is covered. Descriptor text fields (docs_url, pricing_evidence, key_ref) have no
  dedicated mutants. Equivalent-mutant analysis was not done beyond what the harness shows.
- A green mutation run shows the tests notice these 27 edits, not that the adapters are correct or complete.
- Receipts are recorded local harness runs, not independently re-run.
