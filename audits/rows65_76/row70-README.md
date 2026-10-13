# Row 70 evidence sheet

Code under test: `m22_tools_hub/installer.py`.
Covered behavior: Installer gates: scan, review, review binding, rollback preconditions.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_m22_secure_installer.py tests/modules/test_rows65_76_sensitivity.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row70.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
First run (receipts in run1_receipts/row70.json, preserved): 4 SURVIVED. Added `tests/modules/test_rows65_76_sensitivity.py` to the selector (new tests only, no product code changed) and re-ran.

Receipt: `receipts/row70.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: arbitrary tool trial, m21 orchestrator.py (no test file maps to it; not mutated), owner device/communication runtime. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
