# Row 68 evidence sheet

Code under test: `c32/ingest.py`.
Covered behavior: Resumable supplied-record ingestion, duplicate/url/id refusals, checkpoint range.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_c32_ingest_s20.py tests/modules/test_c32_ingest_stream_s20.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row68.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
Receipt: `receipts/row68.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: internet-wide crawl, automatic inner-model training, throughput; training_data_units.py is mapped but not mutated on this sheet. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
