# Row 76 evidence sheet

Code under test: `m14_project_builder/service.py`.
Covered behavior: Planning/approval gates, workspace path escape, milestone lookup, plan-quality precondition.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/test_m14_m15.py tests/modules/test_m14_milestones.py tests/modules/test_rows65_76_sensitivity.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row76.json OUT` (5 exact-site mutations).
Final: 4 CAUGHT of 5. Not caught: artifact_validation. artifact_validation survives: no test registers an artifact that fails validation; left open.
First run (receipts in run1_receipts/row76.json, preserved): 5 SURVIVED. Added `tests/modules/test_rows65_76_sensitivity.py` to the selector (new tests only, no product code changed) and re-ran.

Receipt: `receipts/row76.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: m21 universal_creator_row_1.py is mapped but its test file does not collect on Python 3.10; no universal build or owner-task completion. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
