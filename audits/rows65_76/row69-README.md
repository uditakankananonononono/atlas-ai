# Row 69 evidence sheet

Code under test: `c32/ideate.py`.
Covered behavior: Combinatorial recombination with novelty vs supplied prior art; training is spend-gated.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_c32_ideate_s26.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row69.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
Receipt: `receipts/row69.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: c37/news_create.py (mapped, not mutated here), trained creativity, measured inventions. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
