# Row 71 evidence sheet

Code under test: `m06_social_media_manager/social_reading/reader.py (Pinterest read path)`.
Covered behavior: Paired-session requirement, limit bounds, 429/4xx, host and login-wall blocks.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/modules/test_m06_social_reading.py tests/modules/test_rows65_76_sensitivity.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row71.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
First run (receipts in run1_receipts/row71.json, preserved): 5 SURVIVED. Added `tests/modules/test_rows65_76_sensitivity.py` to the selector (new tests only, no product code changed) and re-ran.

Receipt: `receipts/row71.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: Instagram/LinkedIn reads, social_signal_review.py, m10 email assistant, any liked/comment/starred-email scan-to-action loop. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
