# Row 65 evidence sheet

Code under test: `m19_idea_incubator/trend_pipeline_u03.py`.
Covered behavior: Term-frequency trends and templated ideas over supplied posts only.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_m19_trend_pipeline_u03.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row65.json OUT` (6 exact-site mutations).
Final: 6 CAUGHT of 6. 
Receipt: `receipts/row65.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: no independent continuous discovery, no live trend feed, no learned novelty, no algorithm generation beyond templated ideas. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
