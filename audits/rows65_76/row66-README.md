# Row 66 evidence sheet

Code under test: `c36/ev.py (EV helper); m18_side_hustle_scraper not mutated`.
Covered behavior: Expected-value arithmetic and claim guards over supplied estimates.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_c36_ev_s71.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row66.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
Receipt: `receipts/row66.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: collectors/ranking in m18 (only a 2-test lane selector exists and was not mutated), any trend-to-real-operation outcome, technical/medical/entrepreneurship coverage. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
