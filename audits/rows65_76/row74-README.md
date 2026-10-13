# Row 74 evidence sheet

Code under test: `m20_general_cognitive_worker/c30_b1/chat_bind.py`.
Covered behavior: Offline owner-message snapshot: read-only action, source filter, future/duplicate/count checks.

Selector (repository root): `PYTHONPATH=backend ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python -m pytest --noconftest -p no:cacheprovider tests/b1_chat_bind/test_chat_bind.py -q -rf`
Mutations: `python scripts/release/scoped_mutations.py audits/rows65_76/row74.json OUT` (5 exact-site mutations).
Final: 5 CAUGHT of 5. 
Receipt: `receipts/row74.json`. CAUGHT means rc=1 with FAILED test IDs and no ERROR, collection or skip marker. Source SHA restored after each mutation.
Evidence tier: local offline fixtures. Run on Python 3.10; the released standard selector is Python 3.12 and was not re-run there.

UNTESTED: spec_ledger_s82.py is mapped but its selector has 2 skips so it was not used; historic request completeness and fulfillment. Whole-repository regression, live platforms, accounts and network are untested. Literal row remains PARTIAL.
