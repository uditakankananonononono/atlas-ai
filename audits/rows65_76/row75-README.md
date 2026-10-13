# Row 75 evidence sheet

Code under test: `c31/integrate.py`.
Covered behavior: Tool selection: paid refusal, tie refusal, tier scores, adapter stub.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_c31_integrate_s16.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row75.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
Receipt: `receipts/row75.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: c31 emits NotImplementedError adapter stubs only; m22 installer is on sheet 70; m13 pc_daemon not mutated; no arbitrary tool rebuild or install. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
