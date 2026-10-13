# Row 67 evidence sheet

Code under test: `c35/prefill.py`.
Covered behavior: Offline prefill guards: submit/password/login tokens, essay fields, caps.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_c35_prefill_s45.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row67.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
Receipt: `receipts/row67.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: account/site coverage, successful reviewed submissions; the m02 integrated flow is on sheet 72. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
