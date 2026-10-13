# Row 73 evidence sheet

Code under test: `c31/deploy.py`.
Covered behavior: Fleet planning: spend refusal, 1000 cap, duplicate jobs, concurrency clamp.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_c31_deploy_s17.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row73.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
Receipt: `receipts/row73.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: actual 1,000-builder deployment: 1,000 is logical planning only, local dispatch is limited to 2 workers/4 tasks, operational deployment is OPEN. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
